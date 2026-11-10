// Read only Matroska headers, its bounded cue index, and selected text blocks.
// transport.read shares the viewer's bounded byte cache with video playback.
const ID = { segment:0x18538067, seek:0x114d9b74, tracks:0x1654ae6b, info:0x1549a966, cues:0x1c53bb6b, cluster:0x1f43b675 };
function vint(bytes, offset = 0, keepMarker = false) {
  let marker = 128, length = 1;
  while (length <= 8 && !(bytes[offset] & marker)) { marker >>= 1; length++; }
  if (length > 8 || offset+length > bytes.length) throw new Error("Invalid Matroska header");
  let value = keepMarker ? bytes[offset] : bytes[offset] & (marker-1);
  let unknown = !keepMarker && value === marker-1;
  for (let i=1; i<length; i++) { value = value*256+bytes[offset+i]; unknown = unknown && bytes[offset+i] === 255; }
  if (!unknown && !Number.isSafeInteger(value)) throw new Error("Unsupported Matroska size");
  return { value, length, unknown };
}
export async function inspectMatroskaSubtitles(transport) {
  const size = transport.info.size;
  let sparse = false;
  const bytes = (start, length) => sparse && transport.readMetadata ? transport.readMetadata(start, length) : transport.read(start, length);
  async function header(start, limit = size) {
    if (start >= limit) return null;
    const data = await bytes(start, Math.min(12, limit-start));
    const id = vint(data, 0, true), length = vint(data, id.length);
    const offset = start+id.length+length.length, end = length.unknown ? limit : offset+length.value;
    if (end > limit || end < offset || offset <= start) throw new Error("Invalid Matroska element");
    return { id:id.value, start, offset, end, length:end-offset };
  }
  async function* children(parent, max = 20000) {
    let position = parent.offset, count = 0;
    while (position < parent.end) {
      if (++count > max) throw new Error("Matroska index is too large");
      const item = await header(position, parent.end); if (!item) break;
      yield item; if (item.end <= position) throw new Error("Invalid Matroska index"); position = item.end;
    }
  }
  async function uint(item) {
    if (!item.length || item.length > 8) throw new Error("Invalid Matroska integer");
    let value = 0; for (const byte of await bytes(item.offset, item.length)) value = value*256+byte;
    if (!Number.isSafeInteger(value)) throw new Error("Unsupported Matroska integer"); return value;
  }
  const text = async item => new TextDecoder().decode(await bytes(item.offset, Math.min(item.length, 1024)));
  const ebml = await header(0); if (ebml?.id !== 0x1a45dfa3) return null;
  const segment = await header(ebml.end); if (segment?.id !== ID.segment) return null;
  let scale = 0.001, cuesPosition = null;
  const tracks = [];
  for await (const item of children(segment, 64)) {
    if (item.id === ID.cluster) break;
    if (item.id === ID.info) for await (const part of children(item, 256)) if (part.id === 0x2ad7b1) scale = await uint(part)/1e9;
    if (item.id === ID.seek) for await (const seek of children(item, 256)) {
      if (seek.id !== 0x4dbb) continue;
      let target, position;
      for await (const part of children(seek, 16)) { if (part.id === 0x53ab) target = await uint(part); if (part.id === 0x53ac) position = await uint(part); }
      if (target === ID.cues) cuesPosition = segment.offset+position;
    }
    if (item.id === ID.tracks) for await (const entry of children(item, 128)) {
      if (entry.id !== 0xae) continue;
      const track = { language: "eng" }; // Matroska's default when Language is omitted.
      for await (const part of children(entry, 256)) {
        if (part.id === 0xd7) track.number = await uint(part);
        if (part.id === 0x83) track.type = await uint(part);
        if (part.id === 0x86) track.codec = await text(part);
        if (part.id === 0x536e) track.name = await text(part);
        if (part.id === 0x22b59c) track.language = await text(part);
      }
      if (track.type === 17 && ["S_TEXT/UTF8", "S_TEXT/ASS", "S_TEXT/SSA"].includes(track.codec)) tracks.push(track);
    }
  }
  // No full-file scan: only offer indexed, seekable text subtitles.
  if (!tracks.length || cuesPosition === null) return null;
  const cueRoot = await header(cuesPosition);
  if (!cueRoot || cueRoot.id !== ID.cues || cueRoot.length > 2*1024*1024) return null;
  const index = [], subtitleIndex = new Map();
  for await (const point of children(cueRoot, 30000)) {
    if (point.id !== 0xbb) continue;
    let time;
    const locations=[];
    for await (const part of children(point, 128)) {
      if (part.id === 0xb3) time = await uint(part)*scale;
      if (part.id === 0xb7) {
        const location={};
        for await (const value of children(part,32)) {
          if(value.id===0xf7)location.track=await uint(value);
          if(value.id===0xf1)location.position=segment.offset+await uint(value);
          if(value.id===0xf0)location.relative=await uint(value);
          if(value.id===0xb2)location.duration=await uint(value);
        }
        locations.push(location);
      }
    }
    for(const location of locations) if(Number.isFinite(time)&&Number.isSafeInteger(location.position)&&location.position<size) {
      index.push({time,position:location.position});
      if(Number.isSafeInteger(location.relative)&&tracks.some(track=>track.number===location.track)){
        if(!subtitleIndex.has(location.track))subtitleIndex.set(location.track,[]);
        subtitleIndex.get(location.track).push({...location,time});
      }
    }
  }
  index.sort((a,b) => a.time-b.time);
  for(const points of subtitleIndex.values())points.sort((a,b)=>a.time-b.time);
  if (!index.length) return null;
  sparse = true;
  async function readBlock(block, track, clusterTime, duration) {
    if (block.length < 4) return null;
    const prefix = await bytes(block.offset, Math.min(block.length, 12)), number = vint(prefix);
    if (number.value !== track.number || block.length > 64*1024 || number.length+3 > prefix.length || (prefix[number.length+2]&6)) return null;
    const relative = new DataView(prefix.buffer, prefix.byteOffset).getInt16(number.length);
    const payload = await bytes(block.offset+number.length+3, block.length-number.length-3);
    let content = new TextDecoder().decode(payload);
    if (track.codec !== "S_TEXT/UTF8") content = content.split(",").slice(8).join(",").replace(/\{[^}]*\}/g, "").replace(/\\[Nn]/g, "\n").replace(/\\h/g, " ");
    const start = (clusterTime+relative)*scale;
    return { start, end:start+(duration ? duration*scale : 5), text:content };
  }
  return { tracks,
    async readWindow(number, start, end, cancelled = () => false) {
      const track = tracks.find(track => track.number === number); if (!track) return [];
      const indexed=subtitleIndex.get(number);
      if(indexed?.length) {
        const result=[];
        const points=indexed.filter((point,i)=>point.time<=end && (point.duration!==undefined ? point.time+point.duration*scale : indexed[i+1]?.time ?? point.time+5)>=start).slice(0,200);
        for(const point of points) {
          if(cancelled())return [];
          const cluster=await header(point.position);
          if(!cluster || cluster.id!==ID.cluster)continue;
          const element=await header(cluster.offset+point.relative,cluster.end);
          if(!element)continue;
          let block=element,duration=point.duration;
          if(element.id===0xa0)for await(const child of children(element,64)){if(child.id===0xa1)block=child;if(child.id===0x9b&&duration===undefined)duration=await uint(child);}
          if(![0xa1,0xa3].includes(block.id))continue;
          const cue=await readBlock(block,track,0,duration);
          if(cue?.text)result.push({...cue,start:point.time,end:point.time+(duration!==undefined?duration*scale:5)});
        }
        return result;
      }
      let left = 0, right = index.length-1;
      while (left < right) { const mid = Math.ceil((left+right)/2); if (index[mid].time <= Math.max(0,start-30)) left = mid; else right = mid-1; }
      let position = index[left].position, clusters = 0;
      const result = [];
      while (position < size && !cancelled() && clusters++ < 64) {
        const cluster = await header(position); if (!cluster) break; position = cluster.end;
        if (cluster.id !== ID.cluster) continue;
        let clusterTime = 0;
        for await (const part of children(cluster, 10000)) {
          if (cancelled()) return [];
          if (part.id === 0xe7) { clusterTime = await uint(part); if (clusterTime*scale > end+1) return result; }
          let cue;
          if (part.id === 0xa3) cue = await readBlock(part, track, clusterTime);
          if (part.id === 0xa0) {
            let block, duration;
            for await (const child of children(part, 64)) { if (child.id === 0xa1) block = child; if (child.id === 0x9b) duration = await uint(child); }
            if (block) cue = await readBlock(block, track, clusterTime, duration);
          }
          if (cue && cue.text && cue.end >= start && cue.start <= end && result.length < 200) result.push(cue);
        }
      }
      return result;
    }
  };
}

export function attachEmbeddedSubtitles(video, parser, number, onError) {
  const trackInfo = parser.tracks.find(track => track.number === number);
  const track = video.addTextTrack("subtitles", trackInfo.name || trackInfo.language || "Subtitles", trackInfo.language || "und");
  track.mode = "showing";
  let closed = false, generation = 0, coveredUntil = -Infinity, busy = false;
  const cues = new Map();
  function clear() { for (const cue of cues.values()) track.removeCue(cue); cues.clear(); }
  const seeking = () => { generation++; coveredUntil = -Infinity; clear(); };
  async function refresh() {
    if (closed || busy || coveredUntil >= video.currentTime+5) return;
    const gen = generation, time = video.currentTime; busy = true;
    try {
      const rows = await parser.readWindow(number, Math.max(0,time-2), time+12, () => closed || gen !== generation);
      if (closed || gen !== generation) return;
      for (const [key,cue] of cues) if (cue.endTime < time-30) { track.removeCue(cue); cues.delete(key); }
      for (const row of rows) {
        const key = `${row.start}:${row.end}:${row.text}`;
        if (!cues.has(key) && cues.size < 200 && row.end > row.start && row.start >= 0) {
          const cue = new VTTCue(row.start, row.end, row.text); track.addCue(cue); cues.set(key,cue);
        }
      }
      coveredUntil = time+12;
    } catch { if (!closed) { coveredUntil = time+12; onError("Unable to read embedded subtitles for this section"); } }
    finally { busy = false; }
  }
  video.addEventListener("seeking", seeking);
  const timer = setInterval(refresh, 1000); refresh();
  return { close() { closed = true; clearInterval(timer); video.removeEventListener("seeking", seeking); clear(); track.mode = "disabled"; } };
}
