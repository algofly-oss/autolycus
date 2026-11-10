import { profileHeaders, activeMediaProfile } from "./mediaProfile";
import { useEffect, useRef } from "react";
import { useRouter } from "next/router";

export default function usePlaybackBookmark(url, videoRef, enabled=true,element=null,routeSource=undefined) {
  const router = useRouter(), routerRef = useRef(router); routerRef.current = router;
  const initial = useRef(null), ready = useRef(false);
  useEffect(() => {
    if(!enabled){initial.current=null;ready.current=false;return;}
    const node=element || videoRef.current;if(!node)return;
    const headers=profileHeaders(), profile=activeMediaProfile();
    const path = new URL(url,location.href).searchParams.get('path');
    const controller = new AbortController();
    const locationUrl = new URL(location.href), requested = Number(locationUrl.searchParams.get('t'));
    const explicitTime = locationUrl.searchParams.has("t");
    ready.current = explicitTime;
    initial.current = locationUrl.searchParams.has('t') && Number.isFinite(requested) ? requested : null;
    fetch(`/api/files/playback/progress?path=${encodeURIComponent(path)}`,{signal:controller.signal,headers}).then(response=>response.ok?response.json():null).then(data=>{
      if(controller.signal.aborted) return;
      if(!explicitTime && initial.current === null && data?.progress && !data.progress.completed)initial.current=data.progress.position;
      ready.current=true;
      const element=videoRef.current;
      if(element && element.readyState>0 && initial.current !== null && Number.isFinite(element.duration) && element.duration>0){element.currentTime=Math.min(initial.current,Math.max(0,element.duration-.1));initial.current=null;}
    }).catch(()=>{ready.current=true;});
    const video = node;
    let lastSaved=0, seekTimer, allowUrl=true;
    const expectedSource=routeSource===undefined?locationUrl.searchParams.get('source'):routeSource;
    const onRouteChange = next => { const params=new URL(next,location.origin).searchParams;if(params.get('video')!==path || params.get('source')!==expectedSource)allowUrl=false; };
    routerRef.current.events.on('routeChangeStart',onRouteChange);
    function save(force=false,updateUrl=true) {
      if(!ready.current || initial.current !== null || !video || !(video.duration>0) || !Number.isFinite(video.duration) || video.readyState===0 || (!force && Date.now()-lastSaved<10000)) return;
      lastSaved=Date.now();
      const progress={path,profile_id:profile,position:video.currentTime,duration:video.duration,completed:video.ended};
      fetch('/api/files/playback/progress',{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify(progress),keepalive:force}).then(response=>{if(response.ok)window.dispatchEvent(new CustomEvent('autolycus-watch-progress',{detail:progress}));}).catch(()=>{});
      const current=new URL(location.href);
      if(updateUrl && allowUrl && current.searchParams.get('video')===path){
        const route=routerRef.current;
        route.replace({pathname:route.pathname,query:{...route.query,video:path,t:Math.floor(progress.position)}},undefined,{shallow:true,scroll:false}).catch(()=>{});
      }
    }
    const tick=()=>save(), pause=()=>save(true), seeked=()=>{clearTimeout(seekTimer);seekTimer=setTimeout(()=>save(true),350);};
    video?.addEventListener('timeupdate',tick);video?.addEventListener('pause',pause);video?.addEventListener('seeked',seeked);video?.addEventListener('ended',pause);
    window.addEventListener('pagehide',pause);
    return ()=>{clearTimeout(seekTimer);save(true,false);routerRef.current.events.off("routeChangeStart",onRouteChange);controller.abort();video?.removeEventListener('timeupdate',tick);video?.removeEventListener('pause',pause);video?.removeEventListener('seeked',seeked);video?.removeEventListener('ended',pause);window.removeEventListener('pagehide',pause);};
  },[url,videoRef,enabled,element,routeSource]);
  return () => {
    const video=videoRef.current;
    if(ready.current && video && initial.current !== null && Number.isFinite(video.duration) && video.duration>0){
      video.currentTime=Math.min(initial.current,Math.max(0,video.duration-.1));initial.current=null;
    }
  };
}
