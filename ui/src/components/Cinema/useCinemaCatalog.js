import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import axios from 'axios';
import {profileHeaders} from '@/shared/mediaProfile';
const normalize=value=>String(value||'').toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu,'');
export default function useCinemaCatalog(ready,profileId){
 const [raw,setRaw]=useState([]),[shelves,setShelves]=useState([]),[rich,setRich]=useState({}),[loading,setLoading]=useState(true),[discoverLoading,setDiscoverLoading]=useState(true),[error,setError]=useState(''),[limited,setLimited]=useState(false);
 const pending=useRef(new Set()),alive=useRef(true),queue=useRef([]),running=useRef(0);
 const load=useCallback(async(signal)=>{const {data}=await axios.get('/api/files/cinema',{signal,headers:profileHeaders()});setRaw(data.items);setLimited(data.limited);setError('');},[]);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;queue.current=[];};},[]);
 useEffect(()=>{if(!ready||!profileId)return;const c=new AbortController();setLoading(true);load(c.signal).catch(()=>{if(!c.signal.aborted)setError('Your library could not be loaded. Please try again.');}).finally(()=>{if(!c.signal.aborted)setLoading(false);});const refresh=()=>{if(!document.hidden)load(c.signal).catch(()=>{});};const timer=setInterval(refresh,90000);window.addEventListener('focus',refresh);return()=>{c.abort();clearInterval(timer);window.removeEventListener('focus',refresh);};},[ready,profileId,load]);
 useEffect(()=>{if(!ready)return;const c=new AbortController();setDiscoverLoading(true);axios.get('/api/files/cinema/discover',{signal:c.signal}).then(({data})=>setShelves(data.shelves||[])).catch(()=>{}).finally(()=>{if(!c.signal.aborted)setDiscoverLoading(false);});return()=>c.abort();},[ready]);
 const enrich=useCallback(item=>{
  if(!item?.owned||pending.current.has(item.id))return;
  pending.current.add(item.id);
  const run=()=>{while(running.current<2&&queue.current.length){const task=queue.current.shift();running.current++;task().finally(()=>{running.current--;if(alive.current)run();});}};
  queue.current.push(async()=>{try{let info;
   if(item.imdb_id){const {data}=await axios.get(`/api/files/cinema/title/${item.imdb_id}`,{params:{kind:item.kind}});info=data.item;}
   else {
    const {data}=await axios.get('/api/files/cinema/search',{params:{q:item.title}});
    info=data.items?.find(m=>m.kind===item.kind&&normalize(m.title)===normalize(item.title)&&(!item.year||!m.year||Math.abs(item.year-m.year)<=1));
    if(info?.imdb_id)try{const detail=await axios.get(`/api/files/cinema/title/${info.imdb_id}`,{params:{kind:item.kind}});if(detail.data.item)info={...info,...detail.data.item};}catch{}
   }
   if(info&&alive.current)setRich(old=>({...old,[item.id]:info}));
  }catch{}});run();
 },[]);
 const library=useMemo(()=>raw.map(item=>{const meta=rich[item.id]||{};return {...meta,...item,owned:true,imdb_id:item.imdb_id||meta.imdb_id,tmdb_id:item.tmdb_id||meta.tmdb_id,overview:item.overview||meta.overview,poster:item.poster||meta.poster,background:meta.background,logo:meta.logo,rating:meta.rating||item.rating,genres:meta.genres||[],cast:meta.cast||[],directors:meta.directors||[],runtime:meta.runtime||'',trailers:meta.trailers||[],awards:meta.awards||''};}),[raw,rich]);
 const matchOwned=useCallback(item=>{const owned=library.find(local=>local.kind===item.kind&&((item.imdb_id&&local.imdb_id===item.imdb_id)||(normalize(local.title)===normalize(item.title)&&(!local.year||!item.year||local.year===item.year))));return owned?{...item,...owned,background:owned.background||item.background,logo:owned.logo||item.logo,overview:owned.overview||item.overview,genres:owned.genres?.length?owned.genres:item.genres,trailers:owned.trailers?.length?owned.trailers:item.trailers,cast:owned.cast?.length?owned.cast:item.cast,rating:owned.rating||item.rating}:item;},[library]);
 const discovery=useMemo(()=>shelves.map(s=>({...s,items:s.items.map(matchOwned)})),[shelves,matchOwned]);
 return {library,discovery,loading,discoverLoading,error,limited,load,enrich,matchOwned};
}
