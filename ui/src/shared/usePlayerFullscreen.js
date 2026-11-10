import {useEffect, useRef, useState} from 'react';

const mobile = () => typeof window !== 'undefined' && navigator.maxTouchPoints > 0 && matchMedia('(max-width: 1024px)').matches;
const current = () => document.fullscreenElement || document.webkitFullscreenElement;
const unlock = () => { try { screen.orientation?.unlock?.(); } catch {} };

// Called synchronously from Play so browsers that require user activation can
// enter fullscreen before the player bundle or media metadata has loaded.
export function requestPlayerFullscreen() {
  if (current()) return;
  const root = document.documentElement;
  const enter = root.requestFullscreen || root.webkitRequestFullscreen;
  try { Promise.resolve(enter?.call(root, {navigationUI: 'hide'})).catch(() => {}); } catch {}
}

export default function usePlayerFullscreen(containerRef, videoElement) {
  const [expanded, setExpanded] = useState(mobile);
  const [portrait, setPortrait] = useState(() => innerHeight > innerWidth);
  const [native, setNative] = useState(() => !!current());
  const hadNative=useRef(!!current());
  useEffect(() => {
    const resize = () => setPortrait(innerHeight > innerWidth);
    const sync = () => { const full=!!current(); if(hadNative.current&&!full)setExpanded(false);hadNative.current=full;setNative(full);resize(); };
    window.addEventListener('resize', resize);
    window.visualViewport?.addEventListener('resize', resize);
    document.addEventListener('fullscreenchange', sync);
    document.addEventListener('webkitfullscreenchange', sync);
    return () => {
      window.removeEventListener('resize', resize);
      window.visualViewport?.removeEventListener('resize', resize);
      document.removeEventListener('fullscreenchange', sync);
      document.removeEventListener('webkitfullscreenchange', sync);
      unlock();
      const full = current();
      if (full && (full === document.documentElement || full === containerRef.current)) {
        const exit = document.exitFullscreen || document.webkitExitFullscreen;
        try { Promise.resolve(exit?.call(document)).catch(() => {}); } catch {}
      }
    };
  }, [containerRef]);
  useEffect(() => {
    if (!expanded || !native || !mobile()) return;
    try { Promise.resolve(screen.orientation?.lock?.('landscape')).catch(() => {}); } catch {}
  }, [expanded, native]);
  useEffect(() => {
    if (!videoElement) return;
    const sync = () => {const full=!!videoElement.webkitDisplayingFullscreen || videoElement.webkitPresentationMode==='fullscreen';setNative(full);setExpanded(full);};
    videoElement.addEventListener('webkitbeginfullscreen',sync);
    videoElement.addEventListener('webkitendfullscreen',sync);
    return () => {videoElement.removeEventListener('webkitbeginfullscreen',sync);videoElement.removeEventListener('webkitendfullscreen',sync);};
  }, [videoElement]);
  function toggle() {
    const root=containerRef.current;
    if (!root?.requestFullscreen && !root?.webkitRequestFullscreen && videoElement?.webkitEnterFullscreen) {
      try {if(videoElement.webkitDisplayingFullscreen || videoElement.webkitPresentationMode==='fullscreen')videoElement.webkitExitFullscreen();else videoElement.webkitEnterFullscreen();} catch {}
      return;
    }

    if (expanded || native) {
      setExpanded(false); unlock();
      const exit = document.exitFullscreen || document.webkitExitFullscreen;
      if (current()) try { Promise.resolve(exit?.call(document)).catch(() => {}); } catch {}
    } else {
      setExpanded(true);
      const root = containerRef.current, enter = root?.requestFullscreen || root?.webkitRequestFullscreen;
      try { Promise.resolve(enter?.call(root, {navigationUI: 'hide'})).catch(() => {}); } catch {}
    }
  }
  const videoOnlyFullscreen=!document.documentElement.requestFullscreen && !document.documentElement.webkitRequestFullscreen && !!videoElement?.webkitEnterFullscreen;
  return {fullscreen: videoOnlyFullscreen ? native : expanded || native, rotated: expanded && mobile() && portrait, toggle};
}
