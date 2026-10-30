//! Embedded Arti, following PortHub's bounded stream-based Tor client pattern.
//! Local SOCKS5 compatibility for redsocks and other bundled services.
use anyhow::{bail, ensure, Context, Result};
use arti_client::{config::CfgPath, TorClient, TorClientConfig};
use std::{
    net::{Ipv4Addr, Ipv6Addr},
    path::PathBuf,
    sync::Arc,
    time::Duration,
};
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::{TcpListener, TcpStream},
    sync::Semaphore,
};
use tokio_util::compat::FuturesAsyncReadCompatExt;

pub async fn run() -> Result<()> {
    let _ = rustls::crypto::ring::default_provider().install_default();
    let directory = PathBuf::from("/data/tor");
    let mut builder = TorClientConfig::builder();
    builder
        .storage()
        .state_dir(CfgPath::new_literal(directory.join("state")))
        .cache_dir(CfgPath::new_literal(directory.join("cache")));
    let client = tokio::time::timeout(
        Duration::from_secs(180),
        TorClient::create_bootstrapped(builder.build()?),
    )
    .await
    .context("Tor bootstrap timed out")??;
    let listener = TcpListener::bind("127.0.0.1:9050").await?;
    tracing::info!("embedded Tor ready on localhost:9050");
    // Reuse a bounded set of isolated circuit groups, as PortHub does. Creating
    // a new isolation token for every asset connection causes extra circuits,
    // CPU work and latency on pages with many resources.
    let clients: Vec<_> = (0..4).map(|_| client.isolated_client()).collect();
    let mut cursor = 0;
    let permits = Arc::new(Semaphore::new(128));
    loop {
        let (mut socket, _) = listener.accept().await?;
        let permit = match permits.clone().try_acquire_owned() {
            Ok(permit) => permit,
            Err(_) => {
                let _ = socket.shutdown().await;
                continue;
            }
        };
        let client = clients[cursor].clone();
        cursor = (cursor + 1) % clients.len();
        tokio::spawn(async move {
            let _permit = permit;
            let result: Result<()> = async {
                let (host, port) =
                    tokio::time::timeout(Duration::from_secs(10), negotiate(&mut socket)).await??;
                let upstream = tokio::time::timeout(
                    Duration::from_secs(60),
                    client.connect((host.as_str(), port)),
                )
                .await;
                let mut upstream = match upstream {
                    Ok(Ok(stream)) => stream.compat(),
                    _ => {
                        socket.write_all(&[5, 4, 0, 1, 0, 0, 0, 0, 0, 0]).await?;
                        bail!("Tor destination unavailable");
                    }
                };
                socket.write_all(&[5, 0, 0, 1, 0, 0, 0, 0, 0, 0]).await?;
                // Streaming with fixed-size buffers; no unbounded response buffering.
                tokio::io::copy_bidirectional(&mut socket, &mut upstream).await?;
                Ok(())
            }
            .await;
            if let Err(error) = result {
                tracing::debug!(%error, "Tor stream closed");
            }
        });
    }
}

async fn negotiate(socket: &mut TcpStream) -> Result<(String, u16)> {
    ensure!(socket.read_u8().await? == 5, "SOCKS5 required");
    let count = socket.read_u8().await? as usize;
    let mut methods = vec![0; count];
    socket.read_exact(&mut methods).await?;
    if !methods.contains(&0) {
        socket.write_all(&[5, 255]).await?;
        bail!("no supported authentication method");
    }
    socket.write_all(&[5, 0]).await?;
    let mut header = [0; 4];
    socket.read_exact(&mut header).await?;
    if header[0..3] != [5, 1, 0] {
        socket.write_all(&[5, 7, 0, 1, 0, 0, 0, 0, 0, 0]).await?;
        bail!("only SOCKS CONNECT is supported");
    }
    let host = match header[3] {
        1 => {
            let mut ip = [0; 4];
            socket.read_exact(&mut ip).await?;
            Ipv4Addr::from(ip).to_string()
        }
        3 => {
            let count = socket.read_u8().await? as usize;
            ensure!(count > 0, "empty hostname");
            let mut bytes = vec![0; count];
            socket.read_exact(&mut bytes).await?;
            String::from_utf8(bytes)?
        }
        4 => {
            let mut ip = [0; 16];
            socket.read_exact(&mut ip).await?;
            Ipv6Addr::from(ip).to_string()
        }
        _ => {
            socket.write_all(&[5, 8, 0, 1, 0, 0, 0, 0, 0, 0]).await?;
            bail!("unsupported address type");
        }
    };
    let port = socket.read_u16().await?;
    ensure!(port != 0, "invalid port");
    Ok((host, port))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[tokio::test]
    async fn socks_preserves_hostname_for_remote_dns_and_rejects_bind() -> Result<()> {
        let listener = Arc::new(TcpListener::bind("127.0.0.1:0").await?);
        let address = listener.local_addr()?;
        let first_listener = listener.clone();
        let server = tokio::spawn(async move {
            let (mut socket, _) = first_listener.accept().await?;
            negotiate(&mut socket).await
        });
        let mut socket = TcpStream::connect(address).await?;
        socket.write_all(&[5, 1, 0]).await?;
        let mut reply = [0; 2];
        socket.read_exact(&mut reply).await?;
        assert_eq!(reply, [5, 0]);
        socket
            .write_all(b"\x05\x01\x00\x03\x0bexample.com\x01\xbb")
            .await?;
        assert_eq!(server.await??, ("example.com".into(), 443));
        let server = tokio::spawn(async move {
            let (mut socket, _) = listener.accept().await?;
            negotiate(&mut socket).await
        });
        let mut socket = TcpStream::connect(address).await?;
        socket.write_all(&[5, 1, 0]).await?;
        socket.read_exact(&mut reply).await?;
        socket.write_all(&[5, 2, 0, 1]).await?;
        let mut failure = [0; 10];
        socket.read_exact(&mut failure).await?;
        assert_eq!(failure[1], 7);
        assert!(server.await?.is_err());
        Ok(())
    }
}
