import {useEffect,useState} from 'react';
import {useRouter} from 'next/router';
import dynamic from 'next/dynamic';
import Head from 'next/head';
import {FiLoader,FiPlay} from 'react-icons/fi';
const VideoPlayer=dynamic(()=>import('@/components/User/components/Home/components/FileExplorer/components/VideoPlayer'),{ssr:false,loading:()=> <div className="fixed inset-0 grid place-content-center bg-black text-white" role="status" aria-label="Loading video"><FiLoader className="animate-spin" size={28}/></div>});

export default function PublicWatch() {
  const router=useRouter(),key=typeof router.query.key==='string'?router.query.key:'';
  const download=['1','true'].includes(String(router.query.download).toLowerCase());
  const [info,setInfo]=useState(null),[error,setError]=useState(''),[closed,setClosed]=useState(false);
  useEffect(()=>{
    if(!router.isReady || !key)return;
    if(download){window.location.replace(`/api/files/public/${encodeURIComponent(key)}?download=true`);return;}
    const controller=new AbortController();setInfo(null);setError('');setClosed(false);
    fetch(`/api/files/public-playback/${encodeURIComponent(key)}/info`,{signal:controller.signal,cache:'no-store'}).then(async response=>{if(response.status===415){window.location.replace(`/api/files/public/${encodeURIComponent(key)}`);return null;}if(!response.ok)throw new Error(response.status===404?'This share link is unavailable or has been revoked.':'This file cannot be played here.');return response.json();}).then(value=>{if(!controller.signal.aborted)setInfo(value);}).catch(failure=>{if(!controller.signal.aborted)setError(failure.message);});
    return()=>controller.abort();
  },[router.isReady,key,download]);
  const source=`/api/files/public/${encodeURIComponent(key)}`;
  return <><Head><title>Autolycus</title><meta name="robots" content="noindex,nofollow"/><meta name="referrer" content="same-origin"/></Head>
    <main className="fixed inset-0 grid place-content-center bg-black p-6 text-center text-white">
      {error?<p role="alert">{error}</p>:!info?<FiLoader className="mx-auto animate-spin" size={28} aria-label="Loading video"/>:closed?<div><h1 className="text-lg">{info.display_name}</h1><div className="mt-6 flex justify-center gap-5"><button type="button" className="inline-flex items-center gap-2 text-sm" onClick={()=>setClosed(false)}><FiPlay/>Play</button></div></div>:null}
    </main>
    {info&&!download&&!closed&&!error&&<VideoPlayer key={key} publicKey={key} open url={source} name={info.name} displayTitle={info.display_name} onClose={()=>setClosed(true)}/>}
  </>;
}
