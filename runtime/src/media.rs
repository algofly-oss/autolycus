//! Authenticated upstream control is loopback-only. Each peer owns one open file,
//! one UDP socket and at most one 256 KiB read; no media decoding or disk cache.
use anyhow::{Context, Result};
use axum::{
    extract::{DefaultBodyLimit, State},
    http::StatusCode,
    routing::post,
    Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Value};
use std::{
    collections::HashMap,
    fs::File,
    net::{IpAddr, Ipv4Addr, SocketAddr, UdpSocket},
    os::unix::fs::FileExt,
    path::PathBuf,
    sync::{
        atomic::{AtomicU64, Ordering},
        Arc, Mutex,
    },
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use str0m::{
    change::SdpOffer,
    net::{Protocol, Receive},
    Candidate, Event, Input, Output, Rtc, RtcConfig,
};

const MAX_PEERS: usize = 8;
const MAX_READ: usize = 256 * 1024;
const SEND_WINDOW: usize = 256 * 1024;
type Peers = Arc<Mutex<HashMap<String, Arc<AtomicU64>>>>;
fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Offer {
    id: String,
    path: PathBuf,
    offer: SdpOffer,
}
#[derive(Deserialize)]
struct Lease {
    id: String,
    #[serde(default)]
    close: bool,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Read {
    id: u32,
    start: u64,
    length: usize,
}

pub async fn run() -> Result<()> {
    if std::env::var("WEBRTC_ENABLED").as_deref() == Ok("0") {
        std::future::pending::<()>().await;
    }
    str0m::crypto::from_feature_flags().install_process_default();
    let peers: Peers = Arc::default();
    let app = Router::new()
        .route("/offer", post(offer))
        .route("/lease", post(lease))
        .layer(DefaultBodyLimit::max(48 * 1024))
        .with_state(peers);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:9088").await?;
    axum::serve(listener, app).await?;
    Ok(())
}
async fn lease(State(peers): State<Peers>, Json(lease): Json<Lease>) -> StatusCode {
    match peers.lock().unwrap().get(&lease.id) {
        Some(expiry) => {
            expiry.store(if lease.close { 0 } else { now() + 60 }, Ordering::Relaxed);
            StatusCode::NO_CONTENT
        }
        None => StatusCode::NOT_FOUND,
    }
}
async fn offer(
    State(peers): State<Peers>,
    Json(request): Json<Offer>,
) -> Result<Json<Value>, StatusCode> {
    let root = std::fs::canonicalize(std::env::var("DOWNLOAD_PATH").unwrap_or("/downloads".into()))
        .map_err(|_| StatusCode::SERVICE_UNAVAILABLE)?;
    let path = request
        .path
        .canonicalize()
        .map_err(|_| StatusCode::NOT_FOUND)?;
    if !path.starts_with(&root) || !path.is_file() || request.id.len() != 64 {
        return Err(StatusCode::FORBIDDEN);
    }
    let file = File::open(path).map_err(|_| StatusCode::NOT_FOUND)?;
    let size = file.metadata().map_err(|_| StatusCode::NOT_FOUND)?.len();
    let expiry = Arc::new(AtomicU64::new(now() + 60));
    {
        let mut active = peers.lock().unwrap();
        if active.len() >= MAX_PEERS || active.contains_key(&request.id) {
            return Err(StatusCode::TOO_MANY_REQUESTS);
        }
        active.insert(request.id.clone(), expiry.clone());
    }
    let configured = std::env::var("WEBRTC_UDP_PORT_START")
        .ok()
        .and_then(|p| p.parse::<u16>().ok())
        .unwrap_or(8555);
    let probe =
        UdpSocket::bind((Ipv4Addr::UNSPECIFIED, 0)).map_err(|_| StatusCode::SERVICE_UNAVAILABLE)?;
    probe
        .connect("192.0.2.1:9")
        .map_err(|_| StatusCode::SERVICE_UNAVAILABLE)?;
    let local_ip = probe
        .local_addr()
        .map_err(|_| StatusCode::SERVICE_UNAVAILABLE)?
        .ip();
    let socket = (configured..configured + MAX_PEERS as u16)
        .find_map(|port| UdpSocket::bind((local_ip, port)).ok());
    let result = (|| -> Result<_> {
        let socket = socket.context("no UDP slots available")?;
        let port = socket.local_addr()?.port();
        let mut rtc = RtcConfig::new()
            .set_sctp_max_buffered_amount(SEND_WINDOW)
            .build(Instant::now());
        let mut hosts: Vec<IpAddr> = std::env::var("WEBRTC_CANDIDATE_HOSTS")
            .unwrap_or_default()
            .split(',')
            .filter_map(|s| s.trim().parse().ok())
            .collect();
        // The container address is useful for host-network and isolated testing.
        let probe = UdpSocket::bind("0.0.0.0:0")?;
        probe.connect("192.0.2.1:9")?;
        hosts.push(probe.local_addr()?.ip());
        hosts.sort();
        hosts.dedup();
        for host in hosts {
            rtc.add_local_candidate(Candidate::host(SocketAddr::new(host, port), "udp")?)
                .context("candidate rejected")?;
        }
        let answer = rtc.sdp_api().accept_offer(request.offer)?;
        Ok((rtc, socket, answer))
    })();
    match result {
        Ok((rtc, socket, answer)) => {
            let id = request.id;
            tokio::task::spawn_blocking(move || {
                if let Err(error) = serve_peer(rtc, socket, file, size, expiry) {
                    tracing::warn!(%error, "direct media peer ended");
                }
                peers.lock().unwrap().remove(&id);
            });
            Ok(Json(json!({"answer":answer,"size":size})))
        }
        Err(_) => {
            peers.lock().unwrap().remove(&request.id);
            Err(StatusCode::BAD_REQUEST)
        }
    }
}
fn serve_peer(
    mut rtc: Rtc,
    socket: UdpSocket,
    file: File,
    size: u64,
    expiry: Arc<AtomicU64>,
) -> Result<()> {
    let mut incoming = [0u8; 2048];
    let mut pending: Option<(str0m::channel::ChannelId, Vec<u8>, usize, u32)> = None;
    let mut channel_id = None;
    while expiry.load(Ordering::Relaxed) > now() {
        // Queue only bounded chunks. SCTP enforces a total bytes-in-flight cap.
        if let Some((id, data, offset, request_id)) = pending.as_mut() {
            if let Some(mut channel) = rtc.channel(*id) {
                while *offset < data.len() {
                    let end = (*offset + 16 * 1024).min(data.len());
                    let mut frame = Vec::with_capacity(4 + end - *offset);
                    frame.extend_from_slice(&request_id.to_be_bytes());
                    frame.extend_from_slice(&data[*offset..end]);
                    if !channel.write(true, &frame)? {
                        break;
                    }
                    *offset = end;
                }
                if *offset == data.len() {
                    pending = None;
                }
            } else {
                return Ok(());
            }
        }
        let timeout = loop {
            match rtc.poll_output()? {
                Output::Timeout(at) => break at.min(Instant::now() + Duration::from_secs(1)),
                Output::Transmit(packet) => {
                    socket.send_to(&packet.contents, packet.destination)?;
                }
                Output::Event(Event::ChannelOpen(id, label)) => {
                    anyhow::ensure!(
                        channel_id.is_none() && label == "autolycus-bytes-v1",
                        "unexpected channel"
                    );
                    channel_id = Some(id);
                }
                Output::Event(Event::ChannelClose(_)) => return Ok(()),
                Output::Event(Event::ChannelData(message)) => {
                    anyhow::ensure!(
                        !message.binary
                            && message.data.len() <= 256
                            && Some(message.id) == channel_id
                            && pending.is_none(),
                        "invalid read"
                    );
                    let read: Read = serde_json::from_slice(&message.data)?;
                    anyhow::ensure!(
                        read.length > 0
                            && read.length <= MAX_READ
                            && read.start < size
                            && read
                                .start
                                .checked_add(read.length as u64)
                                .is_some_and(|end| end <= size),
                        "invalid range"
                    );
                    let mut data = vec![0; read.length];
                    file.read_exact_at(&mut data, read.start)?;
                    pending = Some((message.id, data, 0, read.id));
                }
                _ => {}
            }
        };
        // A new request must be flushed before waiting for more input.
        if let Some((id, _, offset, _)) = &pending {
            if *offset == 0
                && rtc
                    .channel(*id)
                    .is_some_and(|mut channel| channel.buffered_amount() < SEND_WINDOW - 17 * 1024)
            {
                continue;
            }
        }
        let wait = timeout.saturating_duration_since(Instant::now());
        if wait.is_zero() {
            rtc.handle_input(Input::Timeout(Instant::now()))?;
            continue;
        }
        socket.set_read_timeout(Some(wait))?;
        let input = match socket.recv_from(&mut incoming) {
            Ok((n, source)) => match incoming[..n].try_into() {
                Ok(contents) => Input::Receive(
                    Instant::now(),
                    Receive {
                        proto: Protocol::Udp,
                        source,
                        destination: socket.local_addr()?,
                        contents,
                    },
                ),
                Err(_) => continue,
            },
            Err(error)
                if matches!(
                    error.kind(),
                    std::io::ErrorKind::WouldBlock | std::io::ErrorKind::TimedOut
                ) =>
            {
                Input::Timeout(Instant::now())
            }
            Err(error) => return Err(error.into()),
        };
        rtc.handle_input(input)?;
    }
    Ok(())
}
