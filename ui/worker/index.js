// This route is deliberately separate from API/offline caching. Every response
// streams bounded ranges, through the owning page's RTC channel or HTTP fallback.
const ask = (client, data) => new Promise((resolve, reject) => {
  const channel = new MessageChannel();
  const timer = setTimeout(() => { channel.port1.close(); reject(new Error("Page unavailable")); }, data.action === "read" ? 45000 : 6000);
  channel.port1.onmessage = event => { clearTimeout(timer); channel.port1.close(); event.data.error ? reject(new Error("Read failed")) : resolve(event.data); };
  client.postMessage({ type: "autolycus-media", ...data }, [channel.port2]);
});
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || url.pathname !== "/__autolycus_media") return;
  event.stopImmediatePropagation();
  event.respondWith((async () => {
    const source = url.searchParams.get("source");
    if (!source || !(source.startsWith("/api/files/stream?") || /^\/api\/files\/public\/[^/?#]+$/.test(source) || /^\/api\/(?:files\/online\/media\/[a-f0-9]{64}|torrent\/preview\/[a-f0-9]{48}\/file\/\d+)$/.test(source))) return new Response("Invalid source", { status: 400 });
    const fallback = () => fetch(source, { headers: event.request.headers, credentials: "same-origin", cache: "no-store", signal: event.request.signal });
    const client = await self.clients.get(event.clientId);
    if (!client) return fallback();
    let info;
    try { info = await ask(client, { action: "info", source }); } catch { return fallback(); }
    const range = event.request.headers.get("Range");
    let start = 0, end = info.size - 1;
    if (range) {
      const match = /^bytes=(\d*)-(\d*)$/.exec(range);
      if (!match || (!match[1] && !match[2])) return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${info.size}` } });
      if (!match[1]) start = Math.max(0, info.size - Number(match[2]));
      else { start = Number(match[1]); if (match[2]) end = Math.min(end, Number(match[2])); }
    }
    if (start > end || start >= info.size) return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${info.size}` } });
    const headers = { "Content-Type": info.type, "Accept-Ranges": "bytes", "Content-Length": String(end-start+1), "Cache-Control": "no-store" };
    if (range) headers["Content-Range"] = `bytes ${start}-${end}/${info.size}`;
    if (event.request.method === "HEAD") return new Response(null, { status: range ? 206 : 200, headers });
    let cursor = start, cancelled = false;
    const stream = new ReadableStream({
      async pull(controller) {
        if (cancelled) return;
        try {
          const length = Math.min(256*1024, end-cursor+1);
          let bytes;
          try { ({ bytes } = await ask(client, { action: "read", source, start: cursor, length })); }
          catch {
            if (cancelled) return;
            const response = await fetch(source, { headers: { Range: `bytes=${cursor}-${cursor+length-1}` }, credentials: "same-origin", cache: "no-store" });
            if (response.status !== 206) throw new Error("Read failed");
            bytes = new Uint8Array(await response.arrayBuffer());
          }
          if (cancelled) return;
          if (bytes.byteLength !== length) throw new Error("Incomplete range");
          controller.enqueue(bytes); cursor += length;
          if (cursor > end) controller.close();
        } catch (error) { if (!cancelled) controller.error(error); }
      },
      cancel() { cancelled = true; }
    }, { highWaterMark: 0 });
    return new Response(stream, { status: range ? 206 : 200, headers });
  })());
});
