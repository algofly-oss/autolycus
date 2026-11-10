import {useCallback,useEffect,useRef,useState} from 'react';

// Touch controls use explicit tap visibility, including while paused. Desktop
// retains Video.js activity/focus handling. No polling or playback processing.
export default function useTouchPlayerControls(rootRef,video,menuOpen,desktopToggle) {
  const touch=typeof navigator!=='undefined'&&navigator.maxTouchPoints>0;
  const [visible,setVisible]=useState(true),shown=useRef(true),timer=useRef(),menu=useRef(menuOpen),interacting=useRef(false);
  menu.current=menuOpen;
  const show=useCallback(value=>{shown.current=value;setVisible(value);},[]);
  const schedule=useCallback(()=>{
    clearTimeout(timer.current);
    if(touch&&video&&!video.paused&&!menu.current&&!interacting.current)timer.current=setTimeout(()=>show(false),2500);
  },[touch,video,show]);
  const toggle=useCallback(force=>{
    if(!touch){desktopToggle?.(force);return;}
    const next=typeof force==='boolean'?force:!shown.current;
    clearTimeout(timer.current);show(next);if(next)schedule();
  },[touch,desktopToggle,show,schedule]);
  useEffect(()=>{
    if(!touch||!video)return;
    const root=rootRef.current;
    const play=()=>{show(true);schedule();},pause=()=>{clearTimeout(timer.current);show(true);};
    const interact=event=>{if(event.type==='keydown'||event.target.closest('button,a,input,select,[role="slider"],.media-popup')){interacting.current=event.type==='pointerdown';show(true);schedule();}};
    const release=()=>{if(interacting.current){interacting.current=false;schedule();}};
    window.addEventListener('pointerup',release,true);window.addEventListener('pointercancel',release,true);
    video.addEventListener('playing',play);video.addEventListener('pause',pause);
    root?.addEventListener('pointerdown',interact,true);root?.addEventListener('keydown',interact,true);
    schedule();
    return()=>{interacting.current=false;window.removeEventListener('pointerup',release,true);window.removeEventListener('pointercancel',release,true);clearTimeout(timer.current);video.removeEventListener('playing',play);video.removeEventListener('pause',pause);root?.removeEventListener('pointerdown',interact,true);root?.removeEventListener('keydown',interact,true);};
  },[touch,video,rootRef,show,schedule]);
  useEffect(()=>{if(menuOpen){clearTimeout(timer.current);show(true);}else schedule();},[menuOpen,show,schedule]);
  return {touch,visible,toggle};
}
