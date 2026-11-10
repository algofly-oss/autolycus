import {useEffect, useRef} from 'react';

// Parking a mouse at either side clears the viewing area without an idle delay.
export default function usePlayerEdgeControls(rootRef, toggleControls, dismissOverlays) {
  const actions=useRef({toggleControls,dismissOverlays});
  actions.current={toggleControls,dismissOverlays};
  useEffect(()=>{
    const root=rootRef.current;
    if(!root)return;
    let hidden=false;
    const show=()=>{
      if(!hidden)return;
      hidden=false;root.removeAttribute('data-pointer-edge');
      actions.current.toggleControls?.(true);
    };
    const move=event=>{
      if(event.pointerType!=='mouse' || event.buttons)return;
      const rect=root.getBoundingClientRect();
      const distance=Math.min(event.clientX-rect.left,rect.right-event.clientX);
      if(distance<=12){
        if(hidden)return;
        hidden=true;root.setAttribute('data-pointer-edge','');
        actions.current.dismissOverlays?.();
        actions.current.toggleControls?.(false);
      }else if(distance>24)show();
    };
    root.addEventListener('pointermove',move,true);
    root.addEventListener('pointerleave',move);
    root.addEventListener('keydown',show,true);
    return()=>{root.removeAttribute('data-pointer-edge');root.removeEventListener('pointermove',move,true);root.removeEventListener('pointerleave',move);root.removeEventListener('keydown',show,true);};
  },[rootRef]);
}
