import React,{useState,useEffect,useContext,useCallback} from 'react';
import axios from 'axios';
import apiRoutes from '@/shared/routes/apiRoutes';
import useInfinitePages from '@/shared/useInfinitePages';
import InfiniteMediaList from '@/shared/InfiniteMediaList';
import useWatchProgress,{relativeMediaPath} from '@/shared/useWatchProgress';
import {SocketContext} from '@/shared/contexts/socket';
import socketRoutes from '@/shared/routes/socketRoutes';
import TorrentCard from './TorrentCard';
const PAGE_SIZE=50;
const getTorrentKey=item=>item.info_hash||item.url_hash||item.id;
export default function TorrentList({state,onPathChange,viewMode='list',scrollRef}) {
 const socket=useContext(SocketContext),[range,setRange]=useState([0,20]);
 const fetchPage=useCallback(async(offset,signal)=>{const {data}=await axios.get(apiRoutes.listTorrents,{params:{page:Math.floor(offset/PAGE_SIZE)+1,page_size:PAGE_SIZE},signal});return {items:data.data||[],total:data.meta?.total||0};},[]);
 const pages=useInfinitePages(fetchPage,getTorrentKey,{initial:state?.get('torrentInfiniteCache'),onReset:()=>{if(scrollRef.current)scrollRef.current.scrollTop=0;}});
 useEffect(()=>{state?.set('torrentInfiniteCache',pages.snapshot);},[state,pages.snapshot]);
 useEffect(()=>{const refresh=()=>pages.reload();socket.on(socketRoutes.stcTorrentAddedOrRemoved,refresh);return()=>socket.off(socketRoutes.stcTorrentAddedOrRemoved,refresh);},[socket,pages.reload]);
 const visible=pages.items.slice(range[0],range[1]),visibleKeys=visible.map(getTorrentKey).join(',');
 useEffect(()=>{
  const listeners=visible.map(item=>{const event=socketRoutes.stcTorrentPropsUpdate+'/'+getTorrentKey(item);const handler=data=>pages.update(items=>items.map(old=>getTorrentKey(old)===getTorrentKey(data)?{...old,...data}:old));socket.on(event,handler);return [event,handler];});
  return()=>listeners.forEach(([event,handler])=>socket.off(event,handler));
 },[socket,visibleKeys,pages.update]);
 const watched=useWatchProgress(visible.filter(item=>item.save_dir).map(item=>({path:relativeMediaPath(item.save_dir),directory:true})));
 const hovered=state.get('hoveredTorrentInfoHash');
 useEffect(()=>{if(hovered)state.set('hoveredTorrent',pages.items.find(item=>getTorrentKey(item)===hovered)||null);},[hovered,pages.items,state]);
 const onRange=useCallback((start,end)=>setRange(old=>old[0]===start&&old[1]===end?old:[start,end]),[]);
 return <InfiniteMediaList {...pages} scrollRef={scrollRef} viewMode={viewMode} itemKey={getTorrentKey} onRange={onRange} initialOffset={state.get('torrentListScrollOffset')||0} onScrollOffset={offset=>state.set('torrentListScrollOffset',offset)} renderItem={torrent=><div className="cursor-pointer min-w-0" onClick={()=>{state.set({hoveredTorrentInfoHash:getTorrentKey(torrent),activeTorrent:torrent});onPathChange(torrent.save_dir);}} onMouseEnter={()=>state.set({hoveredTorrentInfoHash:getTorrentKey(torrent),hoveredTorrent:torrent})}>
  <TorrentCard watchProgress={watched[relativeMediaPath(torrent.save_dir)]} torrentData={torrent} compact={viewMode==='grid'}/>
 </div>}/>;
}
