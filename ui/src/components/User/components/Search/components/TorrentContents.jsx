import {useEffect,useMemo,useRef,useState} from 'react';
import dynamic from 'next/dynamic';
import axios from 'axios';
import {Modal} from '@mantine/core';
import {useVirtualizer} from '@tanstack/react-virtual';
import {FiCheck,FiClipboard,FiDownload,FiFile,FiLoader,FiPlay,FiSearch,FiX} from 'react-icons/fi';
import useTheme from '@/shared/hooks/useTheme';
import useToast from '@/shared/hooks/useToast';
import {sortEpisodes} from '@/shared/episodeOrder';
import {formatBytes} from '../utils';
const VideoPlayer=dynamic(()=>import('../../Home/components/FileExplorer/components/VideoPlayer'),{ssr:false});

export default function TorrentContents({item,alternatives=[],onChooseSource,resolveMagnet,onCopy,onDownload,onClose}){
 const theme=useTheme(),toast=useToast(),token=useRef(null),scroller=useRef(null);
 const [stage,setStage]=useState('Resolving torrent link…'),[actionBusy,setActionBusy]=useState('');
 async function runAction(action,handler){setActionBusy(action);try{const added=await handler(item);if(action==='download'&&added)onClose();}finally{setActionBusy('');}}
 const [data,setData]=useState(null),[error,setError]=useState(''),[retry,setRetry]=useState(0),[query,setQuery]=useState(''),[selected,setSelected]=useState(()=>new Set()),[saving,setSaving]=useState(false),[preview,setPreview]=useState(null);
 useEffect(()=>{
  let cancelled=false,timer;setData(null);setError('');setSelected(new Set());token.current=null;setStage('Resolving torrent link…');
  const release=id=>fetch(`/api/torrent/preview/${id}`,{method:'DELETE',keepalive:true}).catch(()=>{});
  async function poll(id){
   try{const result=await axios.get(`/api/torrent/preview/${id}`);if(cancelled)return;setData(result.data);if(result.data.status!=='ready')timer=setTimeout(()=>poll(id),1000);}
   catch(failure){if(!cancelled)setError(failure.response?.data?.detail||'Unable to retrieve torrent contents.');}
  }
  (async()=>{
   try{const magnet=await resolveMagnet(item);if(cancelled)return;if(!magnet)throw new Error('No magnet is available for this result.');
    setStage('Retrieving file list from peers…');const result=await axios.post('/api/torrent/preview',{magnet});if(cancelled){release(result.data.id);return;}token.current=result.data.id;setData(result.data);poll(result.data.id);
   }catch(failure){if(!cancelled)setError(failure.response?.data?.detail||failure.message||'Unable to inspect this torrent.');}
  })();
  const leave=()=>{if(token.current)release(token.current);};window.addEventListener('pagehide',leave);
  return()=>{cancelled=true;clearTimeout(timer);leave();window.removeEventListener('pagehide',leave);};
 },[item,resolveMagnet,retry]);
 const orderedFiles=useMemo(()=>sortEpisodes((data?.files||[]).map(file=>({...file,label:file.path}))),[data?.files]);
 const files=useMemo(()=>{const needle=query.toLocaleLowerCase();return orderedFiles.filter(file=>file.path.toLocaleLowerCase().includes(needle));},[orderedFiles,query]);
 const selectedSize=useMemo(()=>(data?.files||[]).reduce((sum,file)=>sum+(selected.has(file.index)?file.size:0),0),[data?.files,selected]);
 const virtual=useVirtualizer({count:files.length,getScrollElement:()=>scroller.current,estimateSize:()=>72,overscan:4});
 const toggle=index=>setSelected(old=>{const next=new Set(old);if(next.has(index))next.delete(index);else next.add(index);return next;});
 async function retryLookup(){const id=token.current;token.current=null;if(id)try{await axios.delete(`/api/torrent/preview/${id}`);}catch{}setRetry(n=>n+1);}
 async function download(){setSaving(true);setError('');try{await axios.post(`/api/torrent/preview/${token.current}/download`,{indices:[...selected]});toast.success('Selected files added to downloads');onClose();}catch(failure){setError(failure.response?.data?.detail||'Could not add these files.');}finally{setSaving(false);}}
 function stopPreview(){setPreview(null);if(token.current)axios.post(`/api/torrent/preview/${token.current}/suspend`).catch(()=>{});}
 return <><Modal opened onClose={onClose} withCloseButton={false} centered size="lg" padding={0} radius="md" styles={{content:{background:theme.isDarkTheme?'#151619':'#fff',color:theme.isDarkTheme?'#e5e7eb':'#202124'},body:{padding:0}}}>
  <section className="p-4 sm:p-5" aria-label="Torrent contents"><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><h2 className="text-base font-semibold">Torrent files</h2><p className="mt-1 line-clamp-2 break-words text-xs text-neutral-500" title={item.Title}>{item.Title}</p><p className="mt-1 text-xs text-neutral-500">{item.Tracker||item.TrackerId||"Source"} · {formatBytes(item.Size)} · {item.Seeders??"—"} seeders</p></div><button type="button" aria-label="Close torrent files" onClick={onClose} className="rounded-md p-2 hover:bg-neutral-500/10"><FiX size={20}/></button></div>
   <div className="mt-4 flex flex-wrap gap-2">
    <button type="button" disabled={Boolean(actionBusy)||saving} onClick={()=>runAction('download',onDownload)} className="flex items-center gap-2 rounded-lg bg-neutral-800 px-3 py-2.5 text-sm text-white hover:bg-neutral-700 disabled:opacity-40 dark:bg-neutral-200 dark:text-neutral-900 dark:hover:bg-neutral-300">{actionBusy==='download'?<FiLoader className="animate-spin"/>:<FiDownload/>}{actionBusy==='download'?'Adding…':'Download torrent'}</button>
    <button type="button" disabled={Boolean(actionBusy)||saving} onClick={()=>runAction('copy',onCopy)} className="flex items-center gap-2 rounded-lg border border-neutral-500/20 px-3 py-2.5 text-sm hover:bg-neutral-500/10 disabled:opacity-40">{actionBusy==='copy'?<FiLoader className="animate-spin"/>:<FiClipboard/>}{actionBusy==='copy'?'Retrieving…':'Copy magnet'}</button>
   </div>
   {error&&<div className="mt-4 text-sm" role="alert"><p>{error}</p>{!data?.files?.length&&<>
    <button type="button" className="mt-2 rounded-md px-3 py-2 text-neutral-600 hover:bg-neutral-500/10 dark:text-neutral-300" onClick={retryLookup}>Try again</button>
    {alternatives.length>0&&<div className="mt-3 space-y-2"><p className="text-xs text-neutral-500">Other sources with the same release title. Compare sizes before choosing.</p>{alternatives.map(candidate=><button key={candidate.TrackerId||candidate.Tracker} type="button" onClick={()=>{setQuery('');onChooseSource(candidate);}} className="flex w-full items-center justify-between gap-3 rounded-lg border border-neutral-500/20 px-3 py-3 text-left hover:bg-neutral-500/10"><span>Try {candidate.Tracker||candidate.TrackerId}</span><span className="text-xs text-neutral-500">{formatBytes(candidate.Size)} · {candidate.Seeders??'—'} seeders</span></button>)}</div>}
   </>}</div>}
   {data?.status!=='ready'&&!error&&<div className="flex min-h-[220px] flex-col items-center justify-center gap-3 text-sm text-neutral-500" role="status"><FiLoader className="animate-spin" size={24}/><p>{stage}</p>{data&&<span className="text-xs">{data.peers||0} connected peers</span>}</div>}
   {data?.status==='ready'&&<><label className="mt-4 flex items-center gap-2 rounded-md border border-neutral-500/20 px-3"><FiSearch className="text-neutral-500"/><input aria-label="Filter torrent files" placeholder="Filter files" value={query} onChange={e=>{setQuery(e.target.value);scroller.current?.scrollTo(0,0);}} className="h-10 min-w-0 flex-1 bg-transparent text-sm outline-none"/></label><div className="my-3 flex items-center justify-between gap-2 text-xs text-neutral-500"><span>{data.files.length} files · Preview videos before downloading</span><button type="button" className="shrink-0 text-blue-500" onClick={()=>setSelected(new Set())} disabled={!selected.size}>Clear selection</button></div>
    <div ref={scroller} data-torrent-files className="relative overflow-auto" style={{height:`min(${Math.max(72,Math.min(files.length*72,360))}px,45dvh)`}}><div style={{height:virtual.getTotalSize(),position:'relative'}}>{virtual.getVirtualItems().map(row=>{const file=files[row.index];return <div key={file.index} className="absolute left-0 top-0 flex h-[72px] w-full items-center gap-3 border-b border-neutral-500/10" style={{transform:`translateY(${row.start}px)`}}><label className="relative flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center">
      <input id={`preview-file-${token.current}-${file.index}`} type="checkbox" aria-label={`Select ${file.path}`} checked={selected.has(file.index)} onChange={()=>toggle(file.index)} className="peer sr-only"/>
      <span aria-hidden="true" className="flex h-5 w-5 items-center justify-center rounded-md border border-neutral-400 bg-neutral-100 text-transparent transition-colors peer-checked:border-neutral-700 peer-checked:bg-neutral-700 peer-checked:text-white peer-focus-visible:ring-2 peer-focus-visible:ring-neutral-400 peer-focus-visible:ring-offset-2 dark:border-neutral-600 dark:bg-neutral-800 dark:peer-checked:border-neutral-300 dark:peer-checked:bg-neutral-300 dark:peer-checked:text-neutral-900 dark:peer-focus-visible:ring-offset-neutral-900"><FiCheck size={14} strokeWidth={2.5}/></span>
     </label><FiFile className="hidden shrink-0 text-neutral-500 sm:block"/><label htmlFor={`preview-file-${token.current}-${file.index}`} className="min-w-0 flex-1 cursor-pointer"><span className="block truncate text-sm" title={file.name}>{file.name}</span><span className="mt-1 block truncate text-xs text-neutral-500" title={file.path}>{formatBytes(file.size)} · {file.path}</span></label>{file.video&&<button type="button" aria-label={`Preview ${file.name}`} disabled={file.previewable===false} title={file.previewable===false?"Download this file to play it; its torrent pieces exceed the preview limit":"Preview video"} onClick={()=>setPreview(file)} className="mr-1 rounded-md p-3 text-blue-500 hover:bg-blue-500/10 disabled:opacity-30"><FiPlay size={18}/></button>}</div>;})}</div>{!files.length&&<p className="py-10 text-center text-sm text-neutral-500">No matching files</p>}</div>
    <div className="mt-4 flex items-center justify-between gap-3"><span className="text-xs text-neutral-500">{selected.size} selected · {selectedSize?formatBytes(selectedSize):"0 B"}</span><button type="button" disabled={!selected.size||saving||Boolean(actionBusy)} onClick={download} className="flex shrink-0 items-center gap-2 rounded-md bg-blue-600 px-3 py-2.5 text-sm text-white hover:bg-blue-500 disabled:opacity-40"><FiDownload/>{saving?'Adding…':'Download selected'}</button></div><p className="mt-3 text-[11px] text-neutral-500">Temporary previews stop at 2 GB. Closing this window clears their data.</p>
   </>}
  </section></Modal>
  {preview&&token.current&&<VideoPlayer key={preview.index} open url={`/api/torrent/preview/${token.current}/file/${preview.index}`} name={preview.name} displayTitle={preview.name} playlist={[]} allowDownload={false} onClose={stopPreview}/>}
 </>;
}
