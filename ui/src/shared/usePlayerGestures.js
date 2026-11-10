import { useEffect, useRef, useState } from "react";

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const clock = seconds => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

export default function usePlayerGestures(containerRef, videoRef, toggleControls, lockControls, fullscreen,element=null) {
  const [hud, setHud] = useState("");
  const actions = useRef({ toggleControls, lockControls, fullscreen });
  actions.current = { toggleControls, lockControls, fullscreen };
  useEffect(() => {
    const root = containerRef.current, video = videoRef.current;
    if (!root || !video) return;
    let active, holdTimer, tapTimer, hudTimer, lastTap, brightness = 0.5, volume = video.volume;
    let audioContext, gain, releaseLock, jumpTotal = 0, lastJump = 0;
    const show = text => { clearTimeout(hudTimer); setHud(text); };
    const fade = () => { clearTimeout(hudTimer); hudTimer = setTimeout(() => setHud(""), 800); };
    const restore = () => {
      clearTimeout(holdTimer);
      if (active?.rate !== undefined) video.playbackRate = active.rate;
      root.removeAttribute("data-gesture-scrubbing");
      root.style.removeProperty("--movie-preview-percent");
      releaseLock?.(); releaseLock = undefined;
    };
    function seek(step) {
      if (!Number.isFinite(video.duration)) return;
      const before = video.currentTime;
      const target = clamp(before + step, 0, Math.max(0, video.duration - 0.1));
      const delta = target - before;
      if (Math.abs(delta) < .01) return;
      video.currentTime = target;
      const now = performance.now();
      jumpTotal = now - lastJump < 900 && Math.sign(jumpTotal) === Math.sign(step) ? jumpTotal + delta : delta;
      lastJump = now;
      show(`${jumpTotal > 0 ? "+" : "−"}${Math.round(Math.abs(jumpTotal))}s`); fade();
    }
    function keydown(event) {
      if (event.defaultPrevented || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return;
      if (event.target.closest('input,textarea,select,[contenteditable="true"],[role="slider"],[role^="menu"],.media-popup')) return;
      const key = event.key.toLowerCase();
      if (key === "f") { event.preventDefault(); actions.current.fullscreen?.(); return; }
      if (!["arrowleft", "arrowright", "j", "l"].includes(key)) return;
      event.preventDefault();
      seek(key === "arrowleft" || key === "j" ? -10 : 10);
    }
    function point(event) {
      const rect=root.getBoundingClientRect();
      return root.hasAttribute('data-landscape') ? {x:event.clientY-rect.top,y:rect.right-event.clientX,rect:{left:0,top:0,width:root.clientWidth,height:root.clientHeight}} : {x:event.clientX,y:event.clientY,rect};
    }
    function down(event) {
      if(event.defaultPrevented)return;
      const mouse=event.pointerType==="mouse";
      if (!mouse && event.pointerType !== "touch" && event.pointerType !== "pen") return;
      if(mouse && event.button!==0)return;
      if (active) { finish(null, true); return; }
      if (event.target.closest('button,a,input,select,[role="slider"],[role^="menu"],.media-popup,.media-slider,.movie-landscape-timeline')) {
        // Track and buffer layers are siblings of the slider's ARIA thumb.
        // They must never schedule a video tap or inherit a pending one.
        clearTimeout(tapTimer);lastTap=undefined;
        return;
      }
      const {x,y,rect} = point(event);
      volume = gain ? gain.gain.value : video.volume;
      active = { mouse,id: event.pointerId, x, y, rect, mode: "tap", time: video.currentTime, paused: video.paused, volume, brightness };
      root.setPointerCapture(event.pointerId);
      // Resume an existing iOS gain graph inside the user gesture, never on a render.
      audioContext?.resume().catch(() => {});
      if(!mouse)holdTimer = setTimeout(() => {
        if (!active || active.mode !== "tap") return;
        active.mode = "hold"; active.rate = video.playbackRate;
        video.playbackRate = 2; show("2×");
      }, 400);
    }
    function move(event) {
      if (!active || active.id !== event.pointerId) return;
      const {x,y}=point(event);
      const dx = x - active.x, dy = y - active.y;
      if(active.mouse && Math.hypot(dx,dy)>12){active.mode="ignore";return;}
      if (active.mode === "tap" && Math.hypot(dx, dy) > 12) {
        clearTimeout(holdTimer);
        active.mode = Math.abs(dy) > Math.abs(dx) ? (active.x - active.rect.left < active.rect.width / 2 ? "brightness" : "volume") : "ignore";
      }
      if (active.mode === "hold" && Math.abs(dx) > 12) {
        active.mode = "scrub"; video.playbackRate = active.rate;
        video.pause(); actions.current.toggleControls?.(true);
        releaseLock = actions.current.lockControls?.();
      }
      if (active.mode === "brightness") {
        brightness = clamp(active.brightness - dy / (active.rect.height * 0.7), 0, 1);
        video.style.filter = Math.abs(brightness - 0.5) < 0.005 ? "" : `brightness(${0.25 + brightness * 1.5})`;
        show(`Brightness ${Math.round(brightness * 100)}%`);
      } else if (active.mode === "volume") {
        volume = clamp(active.volume - dy / (active.rect.height * 0.7), 0, 1);
        video.muted = false;
        if (!gain) {
          video.volume = volume;
          // iOS ignores HTMLMediaElement.volume; use a client gain node only there.
          if (Math.abs(video.volume - volume) > 0.01) {
            const Audio = window.AudioContext || window.webkitAudioContext;
            if (Audio) {
              try {
                audioContext = new Audio(); gain = audioContext.createGain();
                audioContext.createMediaElementSource(video).connect(gain); gain.connect(audioContext.destination);
                video.volume = 1; audioContext.resume().catch(() => {});
              } catch { gain = undefined; }
            }
          }
        }
        if (gain) gain.gain.value = volume;
        show(`Volume ${Math.round(volume * 100)}%`);
      } else if (active.mode === "scrub" && Number.isFinite(video.duration)) {
        active.target = clamp(active.time + dx / active.rect.width * Math.min(video.duration, 180), 0, Math.max(0, video.duration - 0.1));
        root.setAttribute("data-gesture-scrubbing", "");
        root.style.setProperty("--movie-preview-percent", `${active.target / video.duration * 100}%`);
        show(clock(active.target));
      }
      if (active.mode !== "tap" && active.mode !== "ignore") event.preventDefault();
    }
    function finish(event, cancelled = false) {
      if (!active || (event && active.id !== event.pointerId)) return;
      const gesture = active;
      restore(); active = undefined;
      if (root.hasPointerCapture(gesture.id)) root.releasePointerCapture(gesture.id);
      if (gesture.mode === "scrub") {
        if (!cancelled && gesture.target !== undefined) video.currentTime = gesture.target;
        if (!gesture.paused) video.play().catch(() => {});
      } else if (!cancelled && gesture.mode === "tap") {
        const now = performance.now();
        const region = (gesture.x - gesture.rect.left) / gesture.rect.width;
        if (lastTap && lastTap.mouse===gesture.mouse && now - lastTap.time < (lastTap.chain ? 900 : 300) && Math.hypot(gesture.x - lastTap.x, gesture.y - lastTap.y) < 60) {
          clearTimeout(tapTimer);
          if (region < 0.35 || region > 0.65) {
            seek(region < 0.35 ? -10 : 10);
            lastTap = { mouse:gesture.mouse,time: now, x: gesture.x, y: gesture.y, chain: true };
          } else {
            lastTap = undefined;
            if(gesture.mouse)actions.current.fullscreen?.();
            else actions.current.toggleControls?.();
          }
        } else {
          lastTap = { mouse:gesture.mouse,time: now, x: gesture.x, y: gesture.y };
          clearTimeout(tapTimer);
          tapTimer = setTimeout(() => { lastTap = undefined;if(gesture.mouse && region>=.35 && region<=.65){if(video.paused)video.play().catch(()=>{});else video.pause();}else actions.current.toggleControls?.(); }, 300);
        }
      }
      if (event) { event.preventDefault(); event.stopPropagation(); }
      fade();
    }
    const up = event => finish(event);
    const cancel = event => finish(event, true);
    const blur = () => finish(null, true);
    root.addEventListener("keydown", keydown);
    root.addEventListener("pointerdown", down);
    root.addEventListener("pointermove", move, { passive: false });
    root.addEventListener("pointerup", up, true);
    root.addEventListener("pointercancel", cancel);
    root.addEventListener("lostpointercapture", cancel);
    window.addEventListener("blur", blur);
    document.addEventListener("visibilitychange", blur);
    return () => {
      finish(null, true); clearTimeout(tapTimer); clearTimeout(hudTimer);
      root.removeEventListener("keydown", keydown);
      root.removeEventListener("pointerdown", down); root.removeEventListener("pointermove", move);
      root.removeEventListener("pointerup", up, true); root.removeEventListener("pointercancel", cancel);
      root.removeEventListener("lostpointercapture", cancel);
      window.removeEventListener("blur", blur); document.removeEventListener("visibilitychange", blur);
      audioContext?.close().catch(() => {});
    };
  }, [containerRef, videoRef,element]);
  return hud;
}
