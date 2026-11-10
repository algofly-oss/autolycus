import {useEffect} from 'react';

// Refresh an idle app after its new worker takes control, never during playback.
export default function usePwaUpdates() {
  useEffect(()=>{
    if(!('serviceWorker' in navigator))return;
    let pending=false,reloaded=false;
    const refresh=()=>{
      if(!pending || reloaded || document.visibilityState!=='visible' || document.querySelector('.movie-player'))return;
      reloaded=true;window.location.reload();
    };
    const changed=()=>{pending=true;refresh();};
    const check=()=>{
      if(document.visibilityState!=='visible')return;
      navigator.serviceWorker.getRegistration().then(registration=>registration?.update()).catch(()=>{});
      refresh();
    };
    navigator.serviceWorker.addEventListener('controllerchange',changed);
    document.addEventListener('visibilitychange',check);
    const observer=new MutationObserver(refresh);
    observer.observe(document.body,{childList:true,subtree:true});
    check();
    return()=>{observer.disconnect();navigator.serviceWorker.removeEventListener('controllerchange',changed);document.removeEventListener('visibilitychange',check);};
  },[]);
}
