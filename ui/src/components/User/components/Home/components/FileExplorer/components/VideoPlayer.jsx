import {mediaConnection} from "@/shared/mediaConnection";
import axios from "axios";
import {useDispatch,useSelector} from "react-redux";
import {authActions,authSelector} from "@/redux/features/authSlice";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Modal } from "@mantine/core";
import { Video, VideoPlayer as Player } from "@videojs/react/video";
import { createMediaTransport, attachNativeBridge } from "@/shared/mediaTransport";
import { inspectMedia, startClientPlayback, subtitleVtt, needsAudioCompatibility } from "@/shared/mediaPlayback";
import usePlaybackBookmark from "@/shared/usePlaybackBookmark";
import usePlaybackQuality from "@/shared/usePlaybackQuality";
import { profileHeaders } from "@/shared/mediaProfile";
import useSubtitlePreferences from "@/shared/useSubtitlePreferences";
import useAlternateAudio from "@/shared/useAlternateAudio";
import usePublicBookmark from "@/shared/usePublicBookmark";
import useEpisodeQueue from "@/shared/useEpisodeQueue";
import MoviePlayerSkin from "./MoviePlayerSkin";

export default function VideoPlayer({ open, url, name, onClose, queueRoot, onEpisodeSelect, publicKey="", displayTitle, playlist, allowDownload=true, sourceControls, initialPlayback, onPlaybackProgress, bookmarkUrl }) {
  const online = /^\/api\/(?:files\/online\/media\/[a-f0-9]{64}|torrent\/preview\/[a-f0-9]{48}\/file\/\d+)$/.test(new URL(url,window.location.origin).pathname);
  const discoveredQueue = useEpisodeQueue(queueRoot,!publicKey && !online && !playlist?.length);
  const queue = playlist?.length ? {entries:playlist,loading:false,limited:false} : discoveredQueue;
  const account=useSelector(authSelector),dispatch=useDispatch();
  const audioLanguage=useRef("en");audioLanguage.current=account?.preferences?.video_audio_language || "en";
  const normalizeLanguage=value=>{try{return new Intl.Locale(value).language;}catch{return value;}};
  async function chooseAudio(value) {
    capturePlayback();if(alternateAudio.choice)await alternateAudio.clear();setAudio(value);setCompatibility(true);
    const language=tracks.find(track=>String(track.id)===value)?.language;
    if(!publicKey && language && language!=="und")try{const {data}=await axios.patch("/api/auth/preferences",{video_audio_language:normalizeLanguage(language)});dispatch(authActions.updateAccountInfo({preferences:data.preferences}));}catch{setError("Unable to save audio language preference.");}
  }
  const [autoNext, setAutoNext] = useState(true);
  const videoRef = useRef(null);
  const [videoElement,setVideoElement]=useState(null);
  const attachVideo=useCallback(element=>{videoRef.current=element;setVideoElement(element);},[]);
  const transportRef = useRef(null);
  const mediaRef = useRef(null);
  const restoreBookmark = usePlaybackBookmark(bookmarkUrl || url, videoRef,!publicKey && (!online || !!bookmarkUrl),videoElement,sourceControls ? (sourceControls.active==="library"?null:sourceControls.active) : undefined);
  const restorePublicBookmark=usePublicBookmark(publicKey,videoRef,videoElement);
  const quality = usePlaybackQuality(url, videoRef, transportRef,publicKey);
  const currentPath = quality.versions[0]?.path || new URL(url, window.location.origin).searchParams.get("path");
  const episodeIndex = queue.entries.findIndex(entry => entry.path === currentPath);
  const displayName = displayTitle || queue.entries[episodeIndex]?.displayName || name;
  const nextEpisode = queue.entries[episodeIndex + 1];
  const playUrl = quality.playUrl, playName = quality.playName || name;
  const playbackRef = useRef(null);
  const playbackResume = useRef(initialPlayback || null);
  const initialResume=useRef(initialPlayback),lastPlaybackState=useRef(initialPlayback || null);
  const restoreSourcePosition=()=>{const video=videoRef.current,state=initialResume.current;if(!video||!state||!Number.isFinite(video.duration)||video.duration<=0)return;initialResume.current=null;video.currentTime=Math.min(Math.max(0,state.time||0),Math.max(0,video.duration-.1));video.playbackRate=state.rate||1;if(state.paused)video.pause();else video.play().catch(()=>{});};
  const capturePlayback = () => { const video=videoRef.current;if(!video)return;if(video.readyState===0 && lastPlaybackState.current){playbackResume.current={...lastPlaybackState.current};return;}const state={time:video.currentTime,paused:video.readyState===0 ? !video.autoplay : video.paused,rate:video.playbackRate};lastPlaybackState.current=state;playbackResume.current=state; };
  useEffect(() => {
    const video=videoRef.current;
    if(!video)return;
    const root=document.documentElement;
    if(root.requestFullscreen || root.webkitRequestFullscreen){
      video.setAttribute("playsinline","");video.setAttribute("webkit-playsinline","");
      return;
    }
    // iPhone Safari provides device fullscreen through the video element.
    if(!video.webkitEnterFullscreen)return;
    video.removeAttribute("playsinline");video.removeAttribute("webkit-playsinline");
    let entered=false;
    const enter=()=>{if(entered || video.paused)return;try{video.webkitEnterFullscreen();entered=true;}catch{}};
    video.addEventListener("playing",enter);
    enter();
    return()=>video.removeEventListener("playing",enter);
  },[videoElement]);
  const [loadedSource,setLoadedSource] = useState("");
  const loading = !playUrl || loadedSource !== playUrl;
  const [src, setSrc] = useState("");
  const [route, setRoute] = useState("public");
  const [connection,setConnection]=useState({kind:"connecting",label:"Connecting"});
  useEffect(()=>{
    let cancelled=false;
    const update=async()=>{const t=transportRef.current;try{const stats=await t?.routeStats?.()||[];if(!cancelled)setConnection(mediaConnection(stats,route==="direct",location.hostname,t?.mediaBytes?.()));}catch{}};
    update();const timer=setInterval(update,5000);return()=>{cancelled=true;clearInterval(timer);};
  },[route]);
  const [tracks, setTracks] = useState([]);
  const [audio, setAudio] = useState("");
  const [subtitles, setSubtitles] = useState([]);
  const [subtitle, setSubtitle] = useState("");
  const [error, setError] = useState("");
  const [compatibility, setCompatibility] = useState(false);
  const [mediaReady, setMediaReady] = useState(0);
  const alternateAudio = useAlternateAudio(currentPath,mediaRef,capturePlayback,()=>setCompatibility(true),!publicKey && !online);
  const subtitlePreferences = useSubtitlePreferences(currentPath, subtitles, mediaReady, setSubtitle,!publicKey && !online);
  const [softwareVideo, setSoftwareVideo] = useState(false);
  const [softwareAvailable, setSoftwareAvailable] = useState(false);
  useEffect(() => {
    if (!open || !playUrl) return;
    const video = videoRef.current;
    let cancelled = false, bridge, transport, media;
    setError(""); setTracks([]); setSubtitles([]); setAudio(""); setSubtitle(""); setCompatibility(false); setMediaReady(0); setSrc(""); setSoftwareVideo(false); setSoftwareAvailable(false);
    (async () => {
      try {
        transport = await createMediaTransport(playUrl, value => { if (!cancelled) setRoute(value); });
        if (cancelled) { transport.close(); return; }
        transportRef.current = transport;
        setSubtitles(transport.info.subtitles);
        await Promise.race([transport.ready, new Promise(resolve => setTimeout(resolve, 2500))]);
        bridge = await attachNativeBridge(transport).catch(() => ({ url: playUrl, close() {} }));
        if (cancelled) return;
        if (!/\.(mkv|avi|ts|m2ts)$/i.test(playName)) setSrc(bridge.url);
        media = await inspectMedia(transport);
        if (cancelled) { media.input.dispose(); return; }
        const preferredAudio=media.tracks.find(track=>normalizeLanguage(track.language)===normalizeLanguage(audioLanguage.current)) || media.tracks[0];
        mediaRef.current = media; setTracks(media.tracks); setAudio(String(preferredAudio?.id ?? "")); setMediaReady(1);
        if (media.embeddedSubtitles) setSubtitles([...transport.info.subtitles, ...media.embeddedSubtitles.tracks.map(track => {
          let language = track.language;
          try { if (language && typeof Intl.DisplayNames === "function") language = new Intl.DisplayNames(["en"], { type: "language" }).of(language); } catch {}
          return { path: `mkv:${track.number}`, language: track.language, name: [language, track.name].filter(Boolean).join(" · ") || `Subtitles ${track.number}` };
        })]);
        setSoftwareAvailable(await media.video?.getCodec() === "hevc");
        if (/\.(mkv|avi|ts|m2ts)$/i.test(playName) || preferredAudio?.id !== media.tracks[0]?.id || await needsAudioCompatibility(media, video)) setCompatibility(true);
      } catch (failure) { if (!cancelled) { console.warn("Media inspection unavailable; using native playback",failure?.message); setSrc(playUrl); setError(""); } }
    })();
    return () => {
      cancelled = true; playbackRef.current?.close(); playbackRef.current = null;
      bridge?.close(); transport?.close(); media?.input.dispose();
      mediaRef.current = null; transportRef.current = null;
      if (video) { video.pause(); video.removeAttribute("src"); video.load(); video.disableRemotePlayback=false; }
    };
  }, [open, playUrl, playName]);
  useEffect(() => {
    if (!compatibility || !mediaReady || !mediaRef.current || !videoRef.current) return;
    let cancelled = false, playback;
    const controller = new AbortController();
    setError("");
    (async () => {
      try {
        playbackRef.current?.close();
        playback = await startClientPlayback(videoRef.current, mediaRef.current, Number(audio), message => { if (!cancelled) setError(message); }, controller.signal, softwareVideo, {resumeState:playbackResume.current || quality.resumeState,alternateAudio:alternateAudio.playback});
        playbackResume.current=null;
        if (cancelled) playback.close(); else playbackRef.current = playback;
      } catch (failure) { if (!cancelled) setError(failure.message); }
    })();
    return () => { cancelled = true; controller.abort(); playback?.close(); };
  }, [compatibility, audio, mediaReady, softwareVideo, alternateAudio.media, alternateAudio.choice]);
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !open) return;
    let cancelled = false, objectUrl, trackElement, embedded;
    (async () => {
      if (!subtitle) return;
      try {
        if (subtitle.startsWith("mkv:") && mediaRef.current?.embeddedSubtitles) {
          const { attachEmbeddedSubtitles } = await import("@/shared/matroskaSubtitles");
          if (cancelled) return;
          embedded = attachEmbeddedSubtitles(video, mediaRef.current.embeddedSubtitles, Number(subtitle.slice(4)), message => { if (!cancelled) setError(message); });
          return;
        }
        const endpoint = publicKey && subtitle.startsWith("public-subtitle:") ? `/api/files/public-playback/${encodeURIComponent(publicKey)}/subtitle?name=${encodeURIComponent(subtitle.slice(16))}` : subtitle.startsWith("os:") ? `/api/files/playback/opensubtitles/file?path=${encodeURIComponent(currentPath)}&file_id=${encodeURIComponent(subtitle.slice(3))}` : `/api/files/playback/subtitle?path=${encodeURIComponent(subtitle)}`;
        const response = await fetch(endpoint, {headers:profileHeaders()});
        if (!response.ok) throw new Error();
        const text = subtitleVtt(await response.text()); if (cancelled) return;
        objectUrl = URL.createObjectURL(new Blob([text], { type: "text/vtt" }));
        trackElement = document.createElement("track"); trackElement.kind = "subtitles"; trackElement.label = "Selected subtitles"; trackElement.src = objectUrl; trackElement.default = true;
        video.appendChild(trackElement); trackElement.track.mode = "showing";
      } catch { if (!cancelled) setError("Unable to load these subtitles"); }
    })();
    return () => { cancelled = true; embedded?.close(); trackElement?.remove(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [subtitle, open, audio, softwareVideo]);
  return (
    <Modal opened={open} onClose={onClose} withCloseButton={false} padding={0} fullScreen radius={0} xOffset={0} yOffset={0}
      aria-label={displayName} transitionProps={{ duration: 0 }}
      classNames={{ content: "movie-player-dialog", body: "movie-player-body" }}
      styles={{ content: { background: "#000", boxShadow: "none", border: 0, borderRadius: 0, height: "100dvh", overflow: "hidden" }, body: { padding: 0, height: "100dvh", background: "#000" }, inner: { padding: 0 } }}>
      {open && <Player aria-label={displayName} style={{ width: "100%", height: "100dvh", background: "#000" }}>
        <MoviePlayerSkin remote={online} sourceControls={sourceControls && {...sourceControls,choose:entry=>{capturePlayback();sourceControls.choose(entry,playbackResume.current);}}} publicKey={publicKey} downloadUrl={allowDownload ? `${playUrl || url}${(playUrl || url).includes("?")?"&":"?"}download=1` : ""} loading={loading && !error} quality={quality} videoElement={videoElement} videoRef={videoRef} queue={queue} currentPath={currentPath} episodeIndex={episodeIndex}
          onEpisodeSelect={onEpisodeSelect} autoNext={autoNext} onAutoNextChange={() => setAutoNext(value => !value)} name={displayName} originalName={name} onClose={onClose} tracks={tracks} audio={audio}
          alternateAudio={alternateAudio} onAudioChange={chooseAudio}
          subtitles={[...subtitles,...subtitlePreferences.online]} subtitle={subtitle} onSubtitleChange={subtitlePreferences.choose} subtitleSearch={subtitlePreferences}
          route={route} connection={connection} compatibility={compatibility} onCompatibility={() => {capturePlayback();setCompatibility(true);}}
          softwareAvailable={softwareAvailable} softwareVideo={softwareVideo}
          onSoftwareVideo={() => { capturePlayback(); setSoftwareVideo(true); setCompatibility(true); }} error={error}>
          <Video ref={attachVideo} src={src || undefined} playsInline controls={false} autoPlay preload="metadata"
            onTimeUpdate={()=>{const v=videoRef.current;if(v?.readyState>0){lastPlaybackState.current={time:v.currentTime,paused:v.paused,rate:v.playbackRate};onPlaybackProgress?.(lastPlaybackState.current,false);}}}
            onSeeked={()=>{const v=videoRef.current;if(v?.readyState>0)onPlaybackProgress?.({time:v.currentTime,paused:v.paused,rate:v.playbackRate},true);}}
            onLoadedData={() => setLoadedSource(playUrl)}
            onLoadedMetadata={() => { quality.restorePosition(); restoreBookmark();restorePublicBookmark();restoreSourcePosition(); }} onDurationChange={() => { quality.restorePosition(); restoreBookmark();restorePublicBookmark();restoreSourcePosition(); }}
            className="movie-player-video" onContextMenu={event => event.preventDefault()}
            onEnded={() => { if (autoNext && episodeIndex >= 0 && nextEpisode) onEpisodeSelect(nextEpisode); }}
            onError={() => { if (mediaRef.current && !compatibility) setCompatibility(true); else setError("Playback failed. Try client compatibility playback or another audio track."); }} />
        </MoviePlayerSkin>
      </Player>}
    </Modal>
  );
}
