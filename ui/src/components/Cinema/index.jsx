import {requestPlayerFullscreen} from "@/shared/usePlayerFullscreen";
import {useEffect,useMemo,useRef,useState} from 'react';
import {useRouter} from 'next/router';
import Link from 'next/link';
import Head from 'next/head';
import dynamic from 'next/dynamic';
import axios from 'axios';
import {FiChevronLeft,FiChevronRight,FiFilm,FiInfo,FiLoader,FiPlay,FiSearch} from 'react-icons/fi';
import useAuth from '@/shared/hooks/useAuth';
import {ProfileSwitcher,useMediaProfiles} from '@/shared/MediaProfiles';
import useCinemaCatalog from './useCinemaCatalog';
import {Artwork,Rating,Shelf} from './Cards';
import TitleDetails,{TrailerDialog} from './TitleDetails';
import SearchView from './SearchView';
const VideoPlayer=dynamic(()=>import('@/components/User/components/Home/components/FileExplorer/components/VideoPlayer'),{ssr:false});

function FeatureTitle({item}){
 const [failed,setFailed]=useState(false);useEffect(()=>setFailed(false),[item.logo]);
 return <div className="cinema-hero-title-slot">{item.logo&&!failed?<><img className="cinema-title-logo" src={item.logo} alt="" onError={()=>setFailed(true)}/><h1 className="sr-only">{item.title}</h1></>:<h1>{item.title}</h1>}</div>;
}
function HeroSkeleton(){return <section className="cinema-hero cinema-hero-skeleton" role="status" aria-label="Opening your library"><div className="cinema-hero-art"/><div className="cinema-hero-content"><div className="cinema-skeleton-heading"/><div className="cinema-skeleton-line"/><div className="cinema-skeleton-line short"/><div className="cinema-skeleton-action"/></div></section>;}

export default function Cinema(){
 const auth=useAuth(),router=useRouter(),profiles=useMediaProfiles();
 const [ready,setReady]=useState(false),[authError,setAuthError]=useState('');
 const [category,setCategory]=useState('all'),[heroIndex,setHeroIndex]=useState(0),[query,setQuery]=useState(''),[searchOpen,setSearchOpen]=useState(false);
 const [selected,setSelected]=useState(null),[trailer,setTrailer]=useState(null),[sources,setSources]=useState(null),[onlineSession,setOnlineSession]=useState(null);
 const localResume=useRef(null),lastOnlineSave=useRef(0);
 const selectedRef=useRef(null);selectedRef.current=selected;
 const catalog=useCinemaCatalog(ready,profiles?.active?.id),{library,discovery,enrich,matchOwned}=catalog;
 useEffect(()=>{let live=true;auth.getAccountInfo().then(user=>{if(!live)return;if(!['admin','user'].includes(user?.role))router.replace('/account/signin');else setReady(true);}).catch(()=>{if(live)setAuthError('Unable to connect. Please try again.');});return()=>{live=false;};},[]);
 const wanted=item=>category==='all'||category==='library'||item.kind===category;
 const local=library.filter(wanted),shelves=discovery.map(row=>({...row,items:row.items.filter(wanted)})).filter(row=>row.items.length);
 const continuing=local.filter(item=>item.progress&&(!item.progress.completed||item.next_episode)).sort((a,b)=>b.progress.updated-a.progress.updated);
 const featured=useMemo(()=>{
  const pool=[...continuing.slice(0,1),...(category==='library'?local:shelves.find(s=>s.id==='trending-movies')?.items||shelves[0]?.items||[]),...local];
  return [...new Map(pool.map(item=>[item.imdb_id||item.id,item])).values()].slice(0,6);
 },[library,discovery,category]);
 const hero=featured[heroIndex%Math.max(1,featured.length)];
 useEffect(()=>{setHeroIndex(0);},[category]);
 useEffect(()=>{if(hero?.owned)enrich(hero);},[hero?.id,hero?.owned,enrich]);
 useEffect(()=>{if(selected?.owned)enrich(selected);},[selected?.id,selected?.owned,enrich]);
 useEffect(()=>{
  const id=typeof router.query.title==='string'?router.query.title:'';
  if(!id){setSelected(null);return;}
  const known=library.find(i=>i.id===id||i.imdb_id===id)||discovery.flatMap(row=>row.items).find(i=>i.id===id||i.imdb_id===id);
  if(known){setSelected(known);return;}
  if(!/^tt\d{5,12}$/.test(id))return;
  const c=new AbortController();axios.get(`/api/files/cinema/title/${id}`,{params:{kind:router.query.kind==='series'?'series':'movie'},signal:c.signal}).then(({data})=>{if(data.item)setSelected(matchOwned(data.item));}).catch(()=>{});return()=>c.abort();
 },[router.query.title,router.query.kind,library,discovery,matchOwned]);
 useEffect(()=>{const key=e=>{if(e.key==='Escape'&&!selected&&!trailer&&searchOpen)setSearchOpen(false);};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);},[selected,trailer,searchOpen]);
 const videoPath=typeof router.query.video==='string'?router.query.video:'';
 const playingItem=library.find(item=>item.files.some(f=>f.path===videoPath));
 useEffect(()=>{if(playingItem?.owned)enrich(playingItem);},[playingItem?.id,enrich]);
 const playingFile=playingItem?.files.find(f=>f.path===videoPath);
 const playlist=useMemo(()=>(playingItem?.kind==='series'?playingItem.files:playingFile?[playingFile]:[]).map(f=>({path:f.path,name:f.name,displayName:f.display_name,episodeInfo:f.episode_info,label:f.display_name})),[playingItem,playingFile]);
 const updateRoute=(changes,remove=[])=>{const next={...router.query,...changes};for(const key of remove)delete next[key];return router.push({pathname:router.pathname,query:next},undefined,{shallow:true,scroll:false});};
 const openDetails=item=>{setSelected(item);updateRoute({title:item.owned?item.id:item.imdb_id,kind:item.kind},['video','t']);};
 const closeDetails=()=>{selectedRef.current=null;setSelected(null);updateRoute({},['title','kind']);};
 const play=(item,path=item.resume_path||item.path,time)=>{setOnlineSession(null);localResume.current=null;if(!item.owned){openDetails(item);return;}requestPlayerFullscreen();setSelected(null);setSearchOpen(false);setTrailer(null);updateRoute({video:path,...(Number.isFinite(time)?{t:Math.floor(time)}:{})},['title','kind','online','source','season','episode',...(Number.isFinite(time)?[]:['t'])]);};
 const closePlayer=()=>{setOnlineSession(null);updateRoute({},['video','t','source','online','season','episode']);catalog.load().catch(()=>{});};
 const findInSearch=item=>{const title=item.kind==='series'?item.title:[item.title,item.year].filter(Boolean).join(' ');router.push({pathname:'/home',query:{tab:'search',q:title}});};
 const startOnline=(item,source,resume)=>{
  item={...item,imdb_id:source.imdb_id||item.imdb_id};
  setSelected(null);setTrailer(null);setSearchOpen(false);
  const state=resume||{time:0,paused:false,rate:1};
  setOnlineSession({item,source,resume:state});
  updateRoute({online:item.imdb_id,kind:item.kind,source:source.id,season:source.season||0,episode:source.episode||0,t:Math.floor(state.time||0)},['title']);
 };
 const loadSources=async(item,source,autoStart=false)=>{
  if(source){startOnline(item,source);return;}
  const itemId=item.id;
  setSources({itemId,loading:true,entries:[]});
  try{
   let identity=item;
   if(!identity.imdb_id){
    const {data}=await axios.get('/api/files/cinema/search',{params:{q:item.title}});
    const key=value=>String(value||'').toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu,'');
    const match=data.items?.find(candidate=>candidate.kind===item.kind&&key(candidate.title)===key(item.title)&&(!item.year||candidate.year===item.year));
    if(!match)throw new Error('No exact title match');
    identity={...item,imdb_id:match.imdb_id};
   }
   const currentFile=item.files?.find(file=>file.path===videoPath)||item.files?.[0];
   const {data}=await axios.get('/api/files/online/sources',{params:{imdb_id:identity.imdb_id,kind:item.kind,season:item.kind==='series'?currentFile?.season||1:0,episode:item.kind==='series'?currentFile?.episode||1:0}});
   const entries=(data.sources||[]).map(entry=>({...entry,imdb_id:data.imdb_id,season:data.season,episode:data.episode}));
   setSources({itemId,imdb_id:identity.imdb_id,entries,loading:false,error:entries.length?'':'No compatible source was found. You can still find this title in search.'});
   if(autoStart&&entries.length&&selectedRef.current?.id===item.id)startOnline(identity,[...entries].sort((a,b)=>b.height-a.height)[0]);
  }catch{setSources({itemId,entries:[],loading:false,error:'No compatible source is available right now. Please try again or find this title in search.'});}
 };
 useEffect(()=>{
  if(!ready)return;
  if(typeof router.query.online!=='string'){setOnlineSession(null);return;}
  if(onlineSession?.item.imdb_id===router.query.online && onlineSession.source.id===router.query.source)return;
  const controller=new AbortController(),id=router.query.online,kind=router.query.kind==='series'?'series':'movie';
  Promise.all([axios.get(`/api/files/cinema/title/${id}`,{params:{kind},signal:controller.signal}),axios.get('/api/files/online/sources',{params:{imdb_id:id,kind,season:Number(router.query.season)||0,episode:Number(router.query.episode)||0},signal:controller.signal})]).then(([metadata,result])=>{
   const item=matchOwned(metadata.data.item),entries=result.data.sources||[],source=entries.find(entry=>entry.id===router.query.source)||entries[0];
   setSources({itemId:id,entries,loading:false});
   if(source)setOnlineSession({item,source,resume:{time:Number(router.query.t)||0,paused:false,rate:1}});
   else setSources({itemId:id,entries:[],error:'This source is unavailable. Please choose another.'});
  }).catch(()=>{if(!controller.signal.aborted)setSources({itemId:id,entries:[],error:'Unable to open this source. Please try again.'});});
  return()=>controller.abort();
 },[ready,router.query.online,router.query.source]);
 const saveOnlinePosition=(state,force=false)=>{
  if(!router.query.online || (!force && Date.now()-lastOnlineSave.current<10000))return;
  lastOnlineSave.current=Date.now();
  router.replace({pathname:router.pathname,query:{...router.query,t:Math.floor(state.time)}},undefined,{shallow:true,scroll:false}).catch(()=>{});
 };
 const watchedTitles=[...local].filter(item=>item.progress?.position>0).sort((a,b)=>(b.progress.updated||0)-(a.progress.updated||0));
 useEffect(()=>{watchedTitles.slice(0,2).forEach(enrich);},[watchedTitles[0]?.id,watchedTitles[1]?.id,enrich]);
 const recommendationSeed=watchedTitles.find(item=>item.genres?.length);
 const recommendations=recommendationSeed?[...new Map(shelves.flatMap(s=>s.items).filter(item=>!item.owned&&item.genres?.some(g=>recommendationSeed.genres.includes(g))).map(i=>[i.id,i])).values()].slice(0,16):[];
 const shelfProps={onOpen:openDetails,onPlay:play,onVisible:enrich};
 const sourceItem=playingItem||onlineSession?.item;
 const sourceEntries=sourceItem && sources && (sources?.itemId===sourceItem.id||(sourceItem.imdb_id&&sources?.imdb_id===sourceItem.imdb_id)||sources?.itemId===sourceItem.imdb_id)?sources.entries||[]:[];
 const sourceControls=sourceItem?{
  label:onlineSession?onlineSession.source.provider:'Autolycus',active:onlineSession?.source.id||'library',
  loading:sources?.loading,entries:[...(playingItem?[{id:'library',label:'Autolycus · your library'}]:[]),...sourceEntries.map(entry=>({...entry,label:`${entry.provider} · ${entry.label}`}))],
  error:sources?.error,load:()=>loadSources(sourceItem),choose:(entry,resume)=>{
   if(entry.id==='library'){localResume.current=resume;setOnlineSession(null);updateRoute({t:Math.floor(resume?.time||0)},['online','source']);}
   else startOnline(sourceItem,entry,resume);
  }
 }:null;
 return <><Head><title>Autolycus</title><meta name="robots" content="noindex,nofollow"/><meta name="theme-color" content="#101113"/></Head>
  <main className="cinema-app cinema-experience"><header className="cinema-header"><Link href="/" className="cinema-brand">Autolycus</Link><nav className="cinema-categories" aria-label="Library categories">{[['all','For you'],['movie','Movies'],['series','Series'],['library','My library']].map(([id,label])=><button type="button" key={id} aria-pressed={category===id} onClick={()=>{setCategory(id);setSearchOpen(false);}}>{label}</button>)}</nav><div className="cinema-header-actions"><button type="button" className="cinema-header-search" aria-label="Search movies and series" onClick={()=>setSearchOpen(true)}><FiSearch/></button><Link href="/home" className="cinema-manage" aria-label="Manage library" title="Manage library"><FiFilm/><span>Manage library</span></Link><ProfileSwitcher collapsed appearance="dark"/></div></header>
  {authError?<div className="cinema-state" role="alert"><p>{authError}</p><button type="button" onClick={()=>router.reload()}>Try again</button></div>:!ready||catalog.loading?<HeroSkeleton/>:<>
   {hero&&<section className="cinema-hero" aria-label="Featured title"><div className="cinema-hero-art"><Artwork key={hero.id} item={hero} background/></div><div className="cinema-hero-shade"/><div className="cinema-hero-content"><span className="cinema-eyebrow">{hero.owned?(hero.progress?'CONTINUE YOUR STORY':'FROM YOUR LIBRARY'):'DISCOVER YOUR NEXT WATCH'}</span><FeatureTitle item={hero}/><div className="cinema-feature-meta"><Rating value={hero.rating}/><span>{hero.year}</span><span>{hero.kind==='series'?'Series':'Movie'}</span>{hero.runtime&&<span>{hero.runtime}</span>}{hero.owned&&<span className="cinema-library-status">In your library</span>}</div>{hero.overview&&<p>{hero.overview}</p>}<div className="cinema-hero-actions"><button type="button" className="cinema-play" onClick={()=>hero.owned?play(hero):openDetails(hero)}><FiPlay fill="currentColor"/>{hero.owned?(hero.next_episode?'Next episode':hero.progress&&!hero.progress.completed?'Continue watching':'Play'):'Watch options'}</button>{hero.trailers?.length>0&&<button type="button" className="cinema-more" onClick={()=>setTrailer(hero)}><FiFilm/>Trailer</button>}<button type="button" className="cinema-feature-info" aria-label={`Info about ${hero.title}`} onClick={()=>openDetails(hero)}><FiInfo/></button></div></div>{featured.length>1&&<div className="cinema-hero-pagination"><button type="button" aria-label="Previous featured title" onClick={()=>setHeroIndex(i=>(i-1+featured.length)%featured.length)}><FiChevronLeft/></button><div>{featured.map((item,i)=><button key={item.id} type="button" aria-label={`Feature ${item.title}`} aria-current={heroIndex%featured.length===i} onClick={()=>setHeroIndex(i)}/>)}</div><button type="button" aria-label="Next featured title" onClick={()=>setHeroIndex(i=>(i+1)%featured.length)}><FiChevronRight/></button></div>}</section>}
   <div className="cinema-shelves">{catalog.error&&<p role="status" className="cinema-catalog-note">{catalog.error}</p>}{local.length>0&&<div className="cinema-section-heading"><span>YOUR LIBRARY</span><p>Ready to play · {local.length} titles</p></div>}<Shelf title="Continue watching" items={continuing} continuing {...shelfProps}/><Shelf title="Recently added" items={local.slice(0,18)} {...shelfProps}/>{category!=='series'&&<Shelf title="Your movies" items={local.filter(i=>i.kind==='movie')} {...shelfProps}/>} {category!=='movie'&&<Shelf title="Your series" items={local.filter(i=>i.kind==='series')} {...shelfProps}/>} {!local.length&&category==='library'&&<div className="cinema-library-empty"><FiFilm/><h1>Your library starts here</h1><p>Saved movies and episodes appear here automatically.</p><Link href="/home">Manage library</Link></div>}
    {category!=='library'&&<><div className="cinema-section-heading cinema-discover-heading"><span>DISCOVER</span><p>Explore beyond your library</p></div>{catalog.discoverLoading?<div className="cinema-discovery-skeleton" aria-label="Loading discovery">{[0,1,2,3,4,5].map(i=><span key={i}/>)}</div>:<>{recommendationSeed&&<Shelf title={`Because you watched ${recommendationSeed.title}`} items={recommendations} {...shelfProps}/>} {shelves.map(s=><Shelf key={s.id} title={s.title} items={s.items} {...shelfProps}/>)}</>}{!catalog.discoverLoading&&!shelves.length&&<p className="cinema-catalog-note">Discovery is temporarily unavailable. Your library is ready to play.</p>}</>}{catalog.limited&&<p className="cinema-catalog-note">Showing the first part of your library.</p>}</div>
  </>}<footer className="cinema-footer"><span>Autolycus</span><Link href="/home">Manage library</Link></footer></main>
  {searchOpen&&<SearchView query={query} setQuery={setQuery} library={library} matchOwned={matchOwned} onClose={()=>setSearchOpen(false)} onOpen={openDetails} onPlay={play} enrich={enrich}/>}
  {selected&&<TitleDetails onlineEnabled item={selected} onClose={closeDetails} onPlay={play} onTrailer={setTrailer} onSearch={findInSearch} onOnline={(item,source)=>loadSources(item,source,true)} sources={sources}/>}
  {trailer&&<TrailerDialog item={trailer} onClose={()=>setTrailer(null)}/>}
  {router.query.online&&!onlineSession&&<div className="cinema-online-opening" role="status"><button type="button" aria-label="Close player" onClick={closePlayer}>Close</button>{sources?.error?<><p>{sources.error}</p><button type="button" onClick={()=>router.reload()}>Try again</button></>:<><FiLoader className="animate-spin"/><p>Opening video…</p></>}</div>}
  {onlineSession?<VideoPlayer key={onlineSession.source.url} open url={onlineSession.source.url} name={onlineSession.item.title+".mp4"} displayTitle={onlineSession.item.title} playlist={[]} allowDownload={false} sourceControls={sourceControls} initialPlayback={onlineSession.resume} bookmarkUrl={playingItem?`/api/files/stream?path=${encodeURIComponent(videoPath)}`:undefined} onPlaybackProgress={playingItem?undefined:saveOnlinePosition} onClose={closePlayer}/>:videoPath&&playingItem&&<VideoPlayer key={videoPath} open url={`/api/files/stream?path=${encodeURIComponent(videoPath)}`} name={playingFile.name} displayTitle={playingFile.display_name} playlist={playlist} allowDownload={false} onClose={closePlayer} onEpisodeSelect={entry=>play(playingItem,entry.path)} sourceControls={sourceControls} initialPlayback={localResume.current}/>}
 </>;
}
