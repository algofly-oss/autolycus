import { useEffect, useRef, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import axios from "axios";
import { authActions, authSelector } from "@/redux/features/authSlice";
import apiRoutes from "@/shared/routes/apiRoutes";
import { adaptiveQuality, qualityLabel } from "./playbackQuality";

export default function usePlaybackQuality(url, videoRef, transportRef, publicKey="") {
  const user = useSelector(authSelector), dispatch = useDispatch();
  const saved = publicKey ? "auto" : user?.preferences?.video_quality || "auto";
  const [preference, setPreference] = useState(saved);
  const [manifest, setManifest] = useState(null), [active, setActive] = useState("original");
  const [saving, setSaving] = useState(false), [error, setError] = useState("");
  const mounted = useRef(true);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  const originalHeight = useRef(0);
  const resume = useRef(null), lastSwitch = useRef(performance.now());
  const current = manifest?.url === url ? manifest : null;
  useEffect(() => { if (!saving) setPreference(saved); }, [saved, saving]);
  useEffect(() => {
    const controller = new AbortController();
    const path = new URL(url, location.href).searchParams.get("path");
    setManifest(null); resume.current = null; originalHeight.current = 0;
    const source = new URL(url,location.href);
    const online = /^\/api\/(?:files\/online\/media\/[a-f0-9]{64}|torrent\/preview\/[a-f0-9]{48}\/file\/\d+)$/.test(source.pathname);
    fetch(online ? `${source.pathname}/info` : publicKey ? `/api/files/public-playback/${encodeURIComponent(publicKey)}/info` : `/api/files/playback/info?path=${encodeURIComponent(path)}`, { signal: controller.signal }).then(response => {
      if (!response.ok) throw new Error();
      return response.json();
    }).then(info => {
      if (controller.signal.aborted) return;
      const versions = info.versions?.length ? info.versions : [{quality:"original",path,size:info.size}];
      setManifest({url,versions});
    }).catch(() => { if (!controller.signal.aborted) setManifest({url,versions:[{quality:"original",path}]}); });
    return () => controller.abort();
  }, [url,publicKey]);
  const switchTo = quality => {
    const video = videoRef.current;
    if (video && video.readyState > 0) resume.current = {time:video.currentTime,paused:video.paused,rate:video.playbackRate};
    lastSwitch.current = performance.now(); setActive(quality);
  };
  useEffect(() => {
    if (!current) return;
    const chosen = preference === "auto" ? "original" : current.versions.some(version => version.quality === preference) ? preference : "original";
    switchTo(chosen);
  }, [current, preference]);
  const version = current?.versions.find(item => item.quality === active) || current?.versions[0];
  const playUrl = version ? version.url || `${new URL(url,location.href).pathname}?path=${encodeURIComponent(version.path)}` : "";
  useEffect(() => {
    if (preference !== "auto" || !current || current.versions.length < 2) return;
    let stalledAt = 0, lowBufferAt=0, previousTime=NaN, stableAt = performance.now();
    const timer = setInterval(() => {
      const video = videoRef.current, now = performance.now();
      if (!video || video.paused || video.ended || video.seeking || video.readyState === 0 || document.hidden) { stalledAt = 0; lowBufferAt=0; previousTime=video?.currentTime ?? NaN; stableAt = now; return; }
      let buffer = 0;
      for(let i=0;i<video.buffered.length;i++) if(video.currentTime>=video.buffered.start(i)&&video.currentTime<=video.buffered.end(i)) buffer=video.buffered.end(i)-video.currentTime;
      const advanced=Number.isFinite(previousTime)?video.currentTime-previousTime:Infinity;previousTime=video.currentTime;
      if(buffer<4){if(!lowBufferAt)lowBufferAt=now;}else lowBufferAt=0;
      if (buffer < 1 && (video.readyState < 3 || advanced<.5)) { if (!stalledAt) stalledAt = now; stableAt = now; } else stalledAt = 0;
      if(active === "original" && video.videoHeight)originalHeight.current=video.videoHeight;
      const versions=current.versions.filter(item=>item.quality==="original" || !originalHeight.current || item.height<=originalHeight.current);
      const quality = adaptiveQuality({versions,active,buffer,stalledFor:stalledAt?(now-stalledAt)/1000:0,stableFor:(now-stableAt)/1000,sinceSwitch:(now-lastSwitch.current)/1000,throughput:transportRef.current?.throughput?.() || 0,duration:video.duration,lowBufferFor:lowBufferAt?(now-lowBufferAt)/1000:0});
      if (quality) switchTo(quality);
    },2000);
    return () => clearInterval(timer);
  },[preference,current,active,videoRef,transportRef]);
  async function choose(value) {
    if (saving || value === preference) return;
    if(publicKey){setPreference(value);return;}
    const previous = preference; setPreference(value); setSaving(true); setError("");
    try {
      const response=await axios.patch(apiRoutes.updatePreferences,{video_quality:value});
      if(!mounted.current)return;
      dispatch(authActions.updateAccountInfo({preferences:response.data.preferences}));
    } catch { setPreference(previous); setError("Could not save quality preference"); }
    finally { setSaving(false); }
  }
  function restorePosition() {
    const video = videoRef.current, state = resume.current;
    if (!video || !state || !Number.isFinite(video.duration) || video.duration <= 0) return;
    resume.current = null;
    video.currentTime = Math.min(state.time,Math.max(0,video.duration-.1)); video.playbackRate = state.rate;
    if(state.paused) video.pause(); else video.play().catch(()=>{});
  }
  return {playUrl,playName:version?.name || version?.path?.split("/").pop(),versions:current?.versions||[],preference,active,choose,saving,error,restorePosition,
    resumeState:resume.current,
    hint:preference === "auto" ? `Auto · ${qualityLabel(active)}` : active !== preference ? `${qualityLabel(preference)} · playing ${qualityLabel(active)}` : qualityLabel(active)};
}
