import {donorTime,videoTime} from "./audioTimeline";
// Demux/remux happens on the viewer's device. Video packets are copied by default;
// explicitly enabled software video compatibility also runs entirely on the client.
export async function inspectMedia(transport) {
  const bunny = await import("mediabunny");
  const source = new bunny.CustomSource({ getSize: () => transport.info.size, maxCacheSize: 4*1024*1024, prefetchProfile: "network",
    read: (start, end) => {
      let cancelled = false;
      return new ReadableStream({ async pull(controller) {
        try { const length = Math.min(256*1024, end-start); const data = await transport.read(start, length); if (cancelled) return; controller.enqueue(data); start += length; if (start === end) controller.close(); }
        catch (error) { if (!cancelled) controller.error(error); }
      }, cancel() { cancelled = true; } }, { highWaterMark: 0 });
    } });
  const input = new bunny.Input({ formats: bunny.ALL_FORMATS, source });
  try {
    const video = await input.getPrimaryVideoTrack();
    const audio = await input.getAudioTracks();
    const tracks = await Promise.all(audio.map(async track => {
      const language = await track.getLanguageCode(), name = await track.getName();
      let label = language && language !== "und" ? language : "";
      try { if (label && typeof Intl.DisplayNames === "function") label = new Intl.DisplayNames(["en"], { type: "language" }).of(label); } catch {}
      return { id: track.id, language: language || "und", codec: await track.getCodec(), label: [label, name].filter(Boolean).join(" · ") || `Audio ${track.number}` };
    }));
    let embeddedSubtitles = null;
    if (/\.(mkv|webm)$/i.test(transport.info.name || new URL(transport.source, location.href).searchParams.get("path") || "")) {
      embeddedSubtitles = await (await import("./matroskaSubtitles")).inspectMatroskaSubtitles(transport).catch(() => null);
    }
    return { bunny, input, video, audio, tracks, embeddedSubtitles, duration: await input.getDurationFromMetadata() };
  } catch (error) { input.dispose(); throw error; }
}

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
function append(buffer, data, alive) {
  return new Promise((resolve, reject) => {
    if (!alive()) return reject(new DOMException("Playback ended", "AbortError"));
    const done = () => { buffer.removeEventListener("updateend", end); buffer.removeEventListener("error", error); };
    const end = () => { done(); resolve(); };
    const error = () => { done(); reject(new Error("This device cannot decode the selected track")); };
    buffer.addEventListener("updateend", end); buffer.addEventListener("error", error);
    try { buffer.appendBuffer(data); } catch (failure) { done(); reject(failure); }
  });
}
function remove(buffer, end) {
  return new Promise(resolve => {
    if (buffer.updating || end <= 0 || !buffer.buffered.length || buffer.buffered.start(0) >= end-0.5) return resolve();
    buffer.addEventListener("updateend", resolve, { once: true });
    try { buffer.remove(0, end); } catch { resolve(); }
  });
}

export async function startClientPlayback(videoElement, media, audioId, onError, signal, softwareVideo = false, options = {}) {
  const resumeState = options.resumeState || { time: videoElement.currentTime || 0, paused: !videoElement.autoplay, rate: videoElement.playbackRate };
  const { bunny, input, video, audio, duration } = media;
  const MediaSourceClass = window.MediaSource || window.ManagedMediaSource;
  if (!MediaSourceClass || !video) throw new Error("Client playback is unavailable on this device");
  const alternate = options.alternateAudio;
  const audioTracks = alternate?.media.audio || audio;
  const selectedAudio = audioTracks.find(track => track.id === (alternate ? alternate.trackId : audioId)) || audioTracks[0];
  let videoCodec = await video.getCodecParameterString(), outputVideoCodec = null;
  if(await video.getCodec()==="hevc" && videoCodec)videoCodec=videoCodec.replace(/^hev1/,"hvc1");
  const convertVideo = !videoCodec || !MediaSourceClass.isTypeSupported(`video/mp4; codecs="${videoCodec}"`);
  if (convertVideo) {
    if (!softwareVideo || await video.getCodec() !== "hevc") throw new Error("This device cannot play this video directly. Try client video compatibility.");
    const { registerHevcDecoder } = await import("@hevcjs/mediabunny-plugin");
    await registerHevcDecoder({ workerUrl: "/media-codecs/hevc-1.6.0/decode-worker.js" });
    const width = await video.getCodedWidth(), height = await video.getCodedHeight();
    for (const [codec, fullCodecString] of [["avc", "avc1.420033"], ["vp9", "vp09.00.51.08"]]) {
      if (MediaSourceClass.isTypeSupported(`video/mp4; codecs="${fullCodecString}"`) && await bunny.canEncodeVideo(codec, { width, height, fullCodecString })) {
        outputVideoCodec = codec; videoCodec = fullCodecString; break;
      }
    }
    if (!outputVideoCodec || !await video.canDecode()) throw new Error("Client video compatibility is unavailable on this device.");
  }
  const audioCodec = selectedAudio && await selectedAudio.getCodecParameterString();
  const convertAudio = selectedAudio && (!!alternate || !audioCodec || !MediaSourceClass.isTypeSupported(`audio/mp4; codecs="${audioCodec}"`));
  if (convertAudio) {
    const codec = await selectedAudio.getCodec();
    if (codec === "ac3" || codec === "eac3") (await import("@mediabunny/ac3")).registerAc3Decoder();
    if (codec === "dts") (await import("@mediabunny/dts")).registerDtsDecoder();
    if (!await selectedAudio.canDecode()) throw new Error("This device cannot decode the selected audio track. Try another audio track.");
    if (!await bunny.canEncodeAudio("aac", { numberOfChannels: 2, sampleRate: 48000 })) (await import("@mediabunny/aac-encoder")).registerAacEncoder();
  }
  let closed = false, generation = 0, outputs = [], sourceBuffers = [], targetTime = resumeState.time || 0;
  if (signal?.aborted) throw new DOMException("Playback ended", "AbortError");
  const wasPlaying = !resumeState.paused;
  const mse = new MediaSourceClass();
  const objectUrl = URL.createObjectURL(mse);
  videoElement.disableRemotePlayback = MediaSourceClass === window.ManagedMediaSource; // Required only by ManagedMediaSource on iPhone.
  const close = () => { closed = true; generation++; videoElement.removeEventListener("seeking", seeking); outputs.forEach(output => output.cancel().catch(() => {})); URL.revokeObjectURL(objectUrl); };
  const opened = new Promise((resolve, reject) => {
    mse.addEventListener("sourceopen", resolve, { once: true });
    signal?.addEventListener("abort", () => { close(); reject(new DOMException("Playback ended", "AbortError")); }, { once: true });
  });
  videoElement.src = objectUrl; videoElement.load();
  await opened;
  if (Number.isFinite(duration) && duration > 0) mse.duration = duration;
  const tracks = [{ track: video, mime: `video/mp4; codecs="${videoCodec}"`, convert: convertVideo },
    ...(selectedAudio ? [{ track: selectedAudio, mime: `audio/mp4; codecs="${convertAudio ? "mp4a.40.2" : audioCodec}"`, convert: convertAudio, alternate }] : [])];
  for (const spec of tracks) sourceBuffers.push(mse.addSourceBuffer(spec.mime));
  async function pumpTrack(spec, buffer, start, gen) {
    const alive = () => !closed && gen === generation && mse.readyState !== "closed";
    const sink = new bunny.EncodedPacketSink(spec.track);
    const trackStart = spec.alternate ? donorTime(start,spec.alternate.delay,spec.alternate.rate) : start;
    const first = spec.track === video ? (await sink.getKeyPacket(start) || await sink.getFirstKeyPacket())
      : (await sink.getPacket(trackStart) || await sink.getFirstPacket());
    if (!first || !alive()) return;
    let pendingFragmentBytes=0;
    const target = new bunny.StreamTarget(new WritableStream({ async write({ data }) {
      if (!alive()) throw new DOMException("Playback ended", "AbortError");
      await append(buffer, data, alive);
      pendingFragmentBytes=0;
    } }));
    const output = new bunny.Output({ format: new bunny.Mp4OutputFormat({ fastStart: "fragmented", minimumFragmentDuration: 1 }), target });
    outputs.push(output);
    const softwareCanvas = spec.convert && spec.track === video ? new OffscreenCanvas(await video.getDisplayWidth(), await video.getDisplayHeight()) : null;
    const softwareContext = softwareCanvas?.getContext("2d", { alpha: false });
    const codec = await spec.track.getCodec();
    const packetSource = spec.convert && spec.track === video ? new bunny.VideoSampleSource({ codec: outputVideoCodec, fullCodecString: videoCodec, bitrate: 6000000, keyFrameInterval: 2, latencyMode: "realtime" })
      : spec.convert ? new bunny.AudioSampleSource({ codec: "aac", bitrate: 160000, transform: { numberOfChannels: 2, sampleRate: 48000 } })
      : spec.track === video ? new bunny.EncodedVideoPacketSource(codec) : new bunny.EncodedAudioPacketSource(codec);
    if (spec.track === video) output.addVideoTrack(packetSource, { rotation: spec.convert ? 0 : await video.getRotation() });
    else output.addAudioTrack(packetSource);
    await output.start();
    const decoderConfig = await spec.track.getDecoderConfig();
    const iterator = spec.convert && spec.track === video ? new bunny.VideoSampleSink(spec.track).samples(first.timestamp)
      : spec.convert ? new bunny.AudioSampleSink(spec.track).samples(first.timestamp) : sink.packets(first);
    let firstPacket = true, audioEnd=start;
    async function silence(until) {
      while(alive() && audioEnd<until-.001) {
        while(alive() && audioEnd>Math.max(videoElement.currentTime,start)+15)await delay(100);
        if(!alive())return;
        const frames=Math.min(48000,Math.ceil((until-audioEnd)*48000));
        const sample=new bunny.AudioSample({data:new Float32Array(frames*2),format:'f32-planar',numberOfChannels:2,sampleRate:48000,timestamp:audioEnd});
        try{await packetSource.add(sample);}finally{sample.close();}
        audioEnd+=frames/48000;
      }
    }
    if(spec.alternate)await silence(Math.min(duration,Math.max(start,videoTime(first.timestamp,spec.alternate.delay,spec.alternate.rate))));
    for await (const packet of iterator) {
      try {
        if (!alive()) break;
        const mappedTime = spec.alternate ? videoTime(packet.timestamp,spec.alternate.delay,spec.alternate.rate) : packet.timestamp;
        if(spec.alternate && mappedTime>=duration)break;
        if(spec.alternate && mappedTime+packet.duration/spec.alternate.rate<=start)continue;
        const videoBufferLow=!buffer.buffered.length || buffer.buffered.end(buffer.buffered.length-1)-Math.max(videoElement.currentTime,start)<3;
        if(spec.track===video && videoBufferLow && mappedTime>Math.max(videoElement.currentTime,start)+60)throw new Error("This video has an unusually long keyframe interval. Try original playback or another version.");
        const lookahead=spec.track===video && videoBufferLow ? 60 : 15;
        while (alive() && mappedTime > Math.max(videoElement.currentTime,start) + lookahead) await delay(100);
        pendingFragmentBytes+=packet.byteLength || 0;
        if(pendingFragmentBytes>32*1024*1024)throw new Error("This video needs a larger client playback buffer. Try original playback or another version.");
        if (!alive()) break;
        await remove(buffer, videoElement.currentTime - 20);
        if (softwareCanvas) {
          // Some client encoders reject I420P10 frames. Normalize on the client
          // through a single reusable canvas before feeding the browser encoder.
          packet.draw(softwareContext, 0, 0, softwareCanvas.width, softwareCanvas.height);
          const normalized = new bunny.VideoSample(softwareCanvas, { timestamp: packet.timestamp, duration: packet.duration });
          try { await packetSource.add(normalized); } finally { normalized.close(); }
        } else if(spec.alternate) {
          const rate=spec.alternate.rate, sampleRate=Math.round(packet.sampleRate*rate);
          const skip=Math.max(0,Math.ceil((start-mappedTime)*sampleRate));
          const frames=packet.numberOfFrames-skip;
          if(frames<=0)continue;
          const data=new Float32Array(frames*packet.numberOfChannels);
          for(let channel=0;channel<packet.numberOfChannels;channel++)packet.copyTo(data.subarray(channel*frames,(channel+1)*frames),{planeIndex:channel,format:'f32-planar',frameOffset:skip,frameCount:frames});
          const mapped=new bunny.AudioSample({data,format:'f32-planar',numberOfChannels:packet.numberOfChannels,sampleRate,timestamp:mappedTime+skip/sampleRate});
          try{await packetSource.add(mapped);audioEnd=mapped.timestamp+mapped.duration;}finally{mapped.close();}
        } else await packetSource.add(packet, firstPacket && !spec.convert ? { decoderConfig } : undefined);
        firstPacket = false;
      } finally { if (spec.convert) packet.close(); }
    }
    if(spec.alternate && alive())await silence(duration);
    if (alive()) { packetSource.close(); await output.finalize(); }
  }
  let restarting = Promise.resolve();
  function restart(start) {
    const gen = ++generation;
    restarting = restarting.catch(() => {}).then(async () => {
      await Promise.allSettled(outputs.map(output => output.cancel())); outputs = [];
      if (closed || gen !== generation) return;
      for (const buffer of sourceBuffers) {
        if (buffer.updating) await new Promise(resolve => buffer.addEventListener("updateend", resolve, { once: true }));
        if (buffer.buffered.length) await new Promise(resolve => { buffer.addEventListener("updateend", resolve, { once: true }); buffer.remove(0, Infinity); });
      }
      const running = tracks.map((spec, index) => pumpTrack(spec, sourceBuffers[index], start, gen));
      Promise.all(running).then(() => { if (!closed && gen === generation && mse.readyState === "open" && !sourceBuffers.some(buffer => buffer.updating)) mse.endOfStream(); })
        .catch(error => { if (!closed && gen === generation && error.name !== "AbortError") onError(error.message); });
    });
  }
  let restoringUntil=0,restoreTarget=0;
  const seeking = () => {
    const time = videoElement.currentTime;
    if(performance.now()<restoringUntil && Math.abs(time-restoreTarget)<.5)return;
    targetTime = time;
    if (!sourceBuffers.every(buffer => { for (let i=0; i<buffer.buffered.length; i++) if (time >= buffer.buffered.start(i) && time < buffer.buffered.end(i)-0.1) return true; return false; })) restart(time);
  };
  videoElement.addEventListener("seeking", seeking);
  videoElement.addEventListener("loadedmetadata", () => { if(closed)return;restoringUntil=performance.now()+500;restoreTarget=targetTime;if (targetTime > 0) { videoElement.currentTime = targetTime; targetTime = 0; } videoElement.playbackRate=resumeState.rate || 1;if (wasPlaying) videoElement.play().catch(() => {}); else videoElement.pause(); }, { once: true });
  restart(targetTime);
  return { close };
}

export function subtitleVtt(text) {
  const clean = text.replace(/^\uFEFF/, "");
  return clean.startsWith("WEBVTT") ? clean : "WEBVTT\n\n" + clean.replace(/(\d{2}:\d{2}:\d{2}),(\d{3})/g, "$1.$2");
}

export async function needsAudioCompatibility(media, element) {
  const track=media.audio[0];
  if(!track)return false;
  const codec=await track.getCodecParameterString();
  const Mse=window.MediaSource || window.ManagedMediaSource;
  if(!Mse)return false;
  if(!codec)return true;
  return !element.canPlayType(`audio/mp4; codecs="${codec}"`) || !Mse.isTypeSupported(`audio/mp4; codecs="${codec}"`);
}
