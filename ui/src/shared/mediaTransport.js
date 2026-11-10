// Pool transfer bytes and durations so a brief fast burst cannot mask a later
// slow connection for minutes. Four scalar samples, no extra media cache.
export function recordThroughput(samples,bytes,seconds) {
  samples.push({bytes,seconds:Math.max(.001,seconds)});
  if(samples.length>4)samples.shift();
  return samples.reduce((total,sample)=>total+sample.bytes,0)/samples.reduce((total,sample)=>total+sample.seconds,0);
}

// Original-byte transport. No codecs, whole-file downloads or persistent caches.
const MAX_READ = 256 * 1024;
const deadline = (promise, ms) => Promise.race([promise, new Promise((_, reject) => setTimeout(() => reject(new Error("Connection timed out")), ms))]);

export async function createMediaTransport(url, onRoute = () => {}) {
  const source = new URL(url, location.href);
  const path = source.searchParams.get("path");
  const onlineMatch=source.pathname.match(/^\/api\/(?:files\/online\/media\/[a-f0-9]{64}|torrent\/preview\/[a-f0-9]{48}\/file\/\d+)$/);
  const torrentPreview=source.pathname.startsWith('/api/torrent/preview/');
  const publicMatch=source.pathname.match(/^\/api\/files\/public\/([^/]+)$/);
  const controlBase=publicMatch ? `/api/files/public-playback/${publicMatch[1]}` : '/api/files/playback';
  const controller = new AbortController();
  const infoResponse = await fetch(onlineMatch ? `${source.pathname}/info` : publicMatch ? `${controlBase}/info` : `${controlBase}/info?path=${encodeURIComponent(path)}`, { signal: controller.signal });
  if (!infoResponse.ok) throw new Error("Unable to open this file");
  const info = await infoResponse.json();
  let pc, channel, lease, leaseTimer, closed = false, serial = Promise.resolve(), sequence = 0;
  let measuredThroughput = 0, directBytes=0, httpBytes=0;
  const throughputSamples=[];
  const pending = new Map();
  // Share original byte pages between playback, demuxing and subtitle readers.
  // Client-only LRU: at most 16 MiB, never the complete movie or a disk cache.
  const pages = new Map(), loadingPages = new Map(), metadataPages = new Map();
  function dropDirect() {
    clearInterval(leaseTimer);
    const oldChannel = channel, oldPeer = pc;
    channel = null; pc = null;
    if (oldChannel) { oldChannel.onclose = null; oldChannel.close(); }
    if (oldPeer) { oldPeer.onconnectionstatechange = null; oldPeer.close(); }
    for (const read of pending.values()) { clearTimeout(read.timer); read.reject(new Error("Direct connection ended")); }
    pending.clear();
    onRoute("public");
  }
  async function connect() {
    if (!info.direct || !window.RTCPeerConnection) return;
    pc = new RTCPeerConnection({ iceServers: [{ urls: "stun:stun.l.google.com:19302" }], bundlePolicy: "max-bundle" });
    channel = pc.createDataChannel("autolycus-bytes-v1", { ordered: true });
    channel.binaryType = "arraybuffer";
    channel.onmessage = ({ data }) => {
      if (!(data instanceof ArrayBuffer) || data.byteLength < 5) { dropDirect(); return; }
      const id = new DataView(data).getUint32(0);
      const read = pending.get(id);
      if (!read || read.offset + data.byteLength - 4 > read.buffer.length) { dropDirect(); return; }
      read.buffer.set(new Uint8Array(data, 4), read.offset); read.offset += data.byteLength - 4;
      if (read.offset === read.buffer.length) { clearTimeout(read.timer); pending.delete(id); read.resolve(read.buffer); }
    };
    const opened = new Promise((resolve, reject) => { channel.onopen = resolve; channel.onerror = reject; });
    await pc.setLocalDescription(await pc.createOffer());
    if (pc.iceGatheringState !== "complete") await deadline(new Promise(resolve => {
      pc.addEventListener("icegatheringstatechange", () => { if (pc?.iceGatheringState === "complete") resolve(); });
    }), 1000).catch(() => {});
    if (closed || !pc) return;
    const response = await fetch(`${controlBase}/offer`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, sdp: pc.localDescription.sdp }), signal: controller.signal });
    if (!response.ok) throw new Error("Direct connection unavailable");
    const answer = await response.json(); lease = answer.id;
    if (closed || !pc) return;
    await pc.setRemoteDescription(answer.answer);
    await deadline(opened, 4000);
    if (closed) return;
    onRoute("direct");
    channel.onclose = dropDirect;
    pc.onconnectionstatechange = () => { if (pc && ["failed", "closed", "disconnected"].includes(pc.connectionState)) dropDirect(); };
    leaseTimer = setInterval(async () => {
      try {
        const response = await fetch(`${controlBase}/lease`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: lease }) });
        if (!response.ok) dropDirect();
      } catch { dropDirect(); }
    }, 20000);
  }
  const ready = connect().catch(() => { dropDirect(); });
  // Playback can start on HTTP while ICE is gathering; subsequent reads use direct.
  async function rawRead(start, length) {
    if (closed) throw new DOMException("Playback closed", "AbortError");
    if (channel?.readyState === "open") {
      try {
        const received=await new Promise((resolve, reject) => {
          const id = ++sequence;
          const timer = setTimeout(() => { pending.delete(id); reject(new Error("Direct read timed out")); }, 4000);
          pending.set(id, { resolve, reject, buffer: new Uint8Array(length), offset: 0, timer });
          channel.send(JSON.stringify({ id, start, length }));
        });
        directBytes+=received.length;return received;
      } catch { dropDirect(); }
    }
    let response;
    for(let attempt=0;attempt<(torrentPreview?3:1);attempt++) {
      response = await fetch(source.href, { headers: { Range: `bytes=${start}-${start+length-1}` }, signal: controller.signal, cache: "no-store" });
      if(response.status===206)break;
      let detail;
      try { const body=await response.json();if(typeof body.detail==='string')detail=body.detail; } catch {}
      if(torrentPreview&&response.status===503&&attempt<2&&(!detail||/peers|busy/i.test(detail)))continue;
      if(torrentPreview&&response.status===404)throw new Error('Torrent preview expired. Close the player and reopen Browse files.');
      throw new Error(detail||'This file cannot be streamed');
    }
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes.length !== length) throw new Error("Incomplete media range");
    httpBytes+=bytes.length;
    return bytes;
  }
  async function oneRead(start, length) {
    const started = performance.now();
    const bytes = await rawRead(start, length);
    if (length >= 65536) {
      measuredThroughput = recordThroughput(throughputSamples,length,(performance.now()-started)/1000);
    }
    return bytes;
  }
  async function read(start, length) {
    if (!Number.isSafeInteger(start) || !Number.isSafeInteger(length) || start < 0 || length < 1 || length > MAX_READ || start+length > info.size) return Promise.reject(new Error("Invalid media range"));
    const result = new Uint8Array(length);
    let offset = 0;
    while (offset < length) {
      const position = start + offset, pageStart = Math.floor(position/MAX_READ)*MAX_READ;
      let page = pages.get(pageStart);
      if (page) { pages.delete(pageStart); pages.set(pageStart, page); }
      else {
        let load = loadingPages.get(pageStart);
        if (!load) {
          if (loadingPages.size >= 16) throw new Error("Too many media reads");
          load = serial.then(() => oneRead(pageStart, Math.min(MAX_READ, info.size-pageStart)));
          serial = load.catch(() => {}); loadingPages.set(pageStart, load);
          load.then(bytes => { if (!closed) { pages.set(pageStart, bytes); while (pages.size > 64) pages.delete(pages.keys().next().value); } }, () => {}).finally(() => loadingPages.delete(pageStart));
        }
        page = await load;
      }
      const within = position-pageStart, count = Math.min(length-offset, page.length-within);
      result.set(page.subarray(within, within+count), offset); offset += count;
    }
    return result;
  }
  async function readMetadata(start,length) {
    if(!Number.isSafeInteger(start)||!Number.isSafeInteger(length)||start<0||length<1||length>65536||start+length>info.size)throw new Error("Invalid metadata range");
    const result=new Uint8Array(length);
    for(let offset=0;offset<length;) {
      const position=start+offset,big=Math.floor(position/MAX_READ)*MAX_READ;
      if(pages.has(big)){const page=pages.get(big),within=position-big,count=Math.min(length-offset,page.length-within);result.set(page.subarray(within,within+count),offset);offset+=count;continue;}
      const base=Math.floor(position/65536)*65536;
      let page=metadataPages.get(base);
      if(!page){const load=serial.then(()=>oneRead(base,Math.min(65536,info.size-base)));serial=load.catch(()=>{});page=await load;if(!closed){metadataPages.set(base,page);while(metadataPages.size>64)metadataPages.delete(metadataPages.keys().next().value);}}
      const within=position-base,count=Math.min(length-offset,page.length-within);result.set(page.subarray(within,within+count),offset);offset+=count;
    }
    return result;
  }
  return { info, read, readMetadata, ready, throughput: () => measuredThroughput, source: source.pathname+source.search,
    mediaBytes:()=>({direct:directBytes,http:httpBytes}),
    async routeStats() { return pc ? [...(await pc.getStats()).values()].filter(item => ["transport", "candidate-pair", "local-candidate", "remote-candidate"].includes(item.type)) : []; },
    close() {
      closed = true; controller.abort(); dropDirect(); pages.clear(); metadataPages.clear();
      if (lease) fetch(`${controlBase}/lease`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: lease, close: true }), keepalive: true }).catch(() => {});
    }
  };
}

export async function attachNativeBridge(transport) {
  if (!navigator.serviceWorker || !window.isSecureContext) return { url: transport.source, close() {} };
  await deadline(navigator.serviceWorker.ready, 2000);
  if (!navigator.serviceWorker.controller) return { url: transport.source, close() {} };
  const listener = async event => {
    if (event.data?.type !== "autolycus-media" || event.data.source !== transport.source || !event.ports[0]) return;
    const port = event.ports[0];
    try {
      if (event.data.action === "info") port.postMessage({ size: transport.info.size, type: transport.info.type });
      else { const bytes = await transport.read(event.data.start, event.data.length); port.postMessage({ bytes }, [bytes.buffer]); }
    } catch { port.postMessage({ error: true }); }
    finally { port.close(); }
  };
  navigator.serviceWorker.addEventListener("message", listener);
  return { url: `/__autolycus_media?source=${encodeURIComponent(transport.source)}`, close() { navigator.serviceWorker.removeEventListener("message", listener); } };
}
