import {useEffect,useRef} from 'react';
import {useRouter} from 'next/router';

// Guest history stays on this browser. Keep at most 32 shared-file bookmarks.
export default function usePublicBookmark(key,videoRef,element=null) {
  const router=useRouter(),initial=useRef(null);
  useEffect(()=>{
    const video=element || videoRef.current;
    if(!key || !video)return;
    let bookmarks={};try{bookmarks=JSON.parse(localStorage.getItem('autolycus:public-watch:v1') || '{}');}catch{}
    const requested=Number(new URL(location.href).searchParams.get('t'));
    initial.current=new URL(location.href).searchParams.has('t') && Number.isFinite(requested) ? Math.max(0,requested) : bookmarks[key]?.position || 0;
    let saved=0,timer;
    function save(force=false,updateUrl=true){
      if(!video || video.readyState===0 || !(video.duration>0) || !Number.isFinite(video.duration) || initial.current!==null || (!force&&Date.now()-saved<10000))return;
      saved=Date.now();
      bookmarks[key]={position:video.ended?0:video.currentTime,at:saved};
      const recent=Object.fromEntries(Object.entries(bookmarks).sort((a,b)=>b[1].at-a[1].at).slice(0,32));
      try{localStorage.setItem('autolycus:public-watch:v1',JSON.stringify(recent));}catch{}
      if(updateUrl)router.replace({pathname:'/watch',query:{key,t:Math.floor(video.currentTime)}},undefined,{shallow:true,scroll:false}).catch(()=>{});
    }
    const tick=()=>save(),pause=()=>save(true),seek=()=>{clearTimeout(timer);timer=setTimeout(()=>save(true),350);};
    video?.addEventListener('timeupdate',tick);video?.addEventListener('pause',pause);video?.addEventListener('seeked',seek);window.addEventListener('pagehide',pause);
    return()=>{clearTimeout(timer);save(true,false);video?.removeEventListener('timeupdate',tick);video?.removeEventListener('pause',pause);video?.removeEventListener('seeked',seek);window.removeEventListener('pagehide',pause);};
  },[key,videoRef,element]);
  return()=>{const video=videoRef.current;if(key&&video&&initial.current!==null&&Number.isFinite(video.duration)&&video.duration>0){video.currentTime=Math.min(initial.current,Math.max(0,video.duration-.1));initial.current=null;}};
}
