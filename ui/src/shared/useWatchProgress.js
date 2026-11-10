import { profileHeaders, activeMediaProfile } from "./mediaProfile";
import { useEffect, useState } from "react";
export const relativeMediaPath = value => String(value || "").replace(/^\/downloads\/*/, "").replace(/\/+$/, "");
export default function useWatchProgress(entries) {
  const key = JSON.stringify(entries);
  const [records, setRecords] = useState({});
  useEffect(() => {
    const headers=profileHeaders(), profile=activeMediaProfile();
    const controller = new AbortController(), paths = JSON.parse(key);
    setRecords({});
    (async () => {
      for(let i=0;i<paths.length;i+=200) {
        const response=await fetch('/api/files/playback/progress/batch',{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({entries:paths.slice(i,i+200)}),signal:controller.signal});
        if(response.ok) { const data=await response.json(); if(!controller.signal.aborted)setRecords(old=>({...old,...data.progress})); }
      }
    })().catch(()=>{});
    let refreshTimer;
    const update = event => {
      if(event.detail.profile_id && event.detail.profile_id!==profile)return;
      setRecords(old=>({...old,...Object.fromEntries(paths.filter(entry=>!entry.directory && entry.path===event.detail.path).map(entry=>[entry.path,event.detail]))}));
      const directories=paths.filter(entry=>entry.directory && event.detail.path.startsWith(entry.path+'/'));
      if(directories.length){clearTimeout(refreshTimer);refreshTimer=setTimeout(()=>fetch('/api/files/playback/progress/batch',{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({entries:directories}),signal:controller.signal}).then(response=>response.ok?response.json():null).then(data=>{if(data&&!controller.signal.aborted)setRecords(old=>({...old,...data.progress}));}).catch(()=>{}),150);}
    };
    window.addEventListener('autolycus-watch-progress',update);
    return ()=>{clearTimeout(refreshTimer);controller.abort();window.removeEventListener('autolycus-watch-progress',update);};
  },[key]);
  return records;
}
