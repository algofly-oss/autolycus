import { useEffect, useState } from "react";
export default function SeekPreview({path,time,active,publicKey}) {
  const [sprite,setSprite]=useState(null);
  useEffect(()=>{setSprite(null);if(!path)return;let cancelled=false,timer;async function load(){try{const response=await fetch(publicKey ? `/api/files/public-playback/${encodeURIComponent(publicKey)}/preview` : `/api/files/playback/preview?path=${encodeURIComponent(path)}`);if(!response.ok)return;const data=await response.json();if(cancelled)return;if(data.status==='ready')setSprite(data);else if(data.status==='queued'&&active)timer=setTimeout(load,5000);}catch{}}load();return()=>{cancelled=true;clearTimeout(timer);};},[path,active,publicKey]);
  if(!active || !sprite)return null;
  const index=Math.max(0,Math.min(sprite.count-1,Math.floor(time/sprite.duration*sprite.count))),width=144,height=width*sprite.height/sprite.width;
  return <div className="movie-seek-thumbnail" aria-hidden="true" style={{width,height,backgroundImage:`url("${sprite.image}")`,backgroundSize:`${sprite.columns*width}px ${sprite.rows*height}px`,backgroundPosition:`-${index%sprite.columns*width}px -${Math.floor(index/sprite.columns)*height}px`}}/>;
}
