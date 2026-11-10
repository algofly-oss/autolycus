import {useEffect,useRef,useState} from 'react';
import {FiCheckCircle,FiChevronLeft,FiChevronRight,FiFilm,FiInfo,FiPlay,FiStar} from 'react-icons/fi';
export const percent=p=>p?.duration>0?Math.min(100,p.position/p.duration*100):0;
export function Rating({value}){return Number(value)>0?<span className="cinema-rating"><FiStar fill="currentColor"/>{Number(value).toFixed(1)}</span>:null;}
export function Artwork({item,background=false}){
 const [failedSrc,setFailedSrc]=useState(null),[loadedSrc,setLoadedSrc]=useState(null);const src=background?item.background:item.poster;
 return src&&failedSrc!==src?<img key={src} src={src} alt="" width={background?1920:400} height={background?1080:600} className={`cinema-art-image ${loadedSrc===src?'is-loaded':''}`} loading={background?'eager':'lazy'} decoding="async" onLoad={()=>setLoadedSrc(src)} onError={()=>setFailedSrc(src)}/>:<div className="cinema-artwork-fallback"><FiFilm/><span>{item.title}</span></div>;
}

export function Card({item,onOpen,onPlay,onVisible,continuing=false}){
 const ref=useRef(null),watched=item.watch_progress||item.progress;
 useEffect(()=>{if(!onVisible||!item.owned)return;const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){onVisible(item);observer.disconnect();}},{rootMargin:'160px'});if(ref.current)observer.observe(ref.current);return()=>observer.disconnect();},[item.id,item.owned,onVisible]);
 return <article ref={ref} className="cinema-card-wrap"><button type="button" className="cinema-card" onClick={()=>item.owned?onPlay(item):onOpen(item)} aria-label={`${item.owned?'Play':'View'} ${item.title}`}>
  <div className="cinema-card-art"><Artwork item={item}/><span className="cinema-card-play">{item.owned?<FiPlay fill="currentColor"/>:<FiInfo/>}</span><span className="cinema-card-rating"><Rating value={item.rating}/></span>{watched?.position>0&&<span className="cinema-watch-track"><span style={{width:`${percent(watched)}%`}}/></span>}</div>
  <span className="cinema-card-title-line"><span className="cinema-card-name">{item.title}</span>{item.owned&&<span className="cinema-library-mark" role="img" aria-label="In your library" title="In your library"><FiCheckCircle size={12}/></span>}</span><span className="cinema-card-meta">{continuing?(item.next_episode?'Next episode':`${Math.round(percent(item.progress))}% watched`):[item.year,item.kind==='series'?'Series':item.runtime||'Movie'].filter(Boolean).join(' · ')}</span>
 </button>{item.owned&&<button type="button" className="cinema-card-info" aria-label={`Info about ${item.title}`} title="More info" onClick={()=>onOpen(item)}><FiInfo/></button>}</article>;
}
export function Shelf({title,items,onOpen,onPlay,onVisible,continuing=false}){const rail=useRef(null);if(!items?.length)return null;return <section className="cinema-shelf"><div className="cinema-shelf-heading"><h2>{title}</h2><div className="cinema-shelf-arrows"><button type="button" aria-label={`Previous ${title}`} onClick={()=>rail.current?.scrollBy({left:-rail.current.clientWidth*.8,behavior:'smooth'})}><FiChevronLeft/></button><button type="button" aria-label={`More ${title}`} onClick={()=>rail.current?.scrollBy({left:rail.current.clientWidth*.8,behavior:'smooth'})}><FiChevronRight/></button></div></div><div ref={rail} className="cinema-rail">{items.map(item=><Card key={item.id} item={item} onOpen={onOpen} onPlay={onPlay} onVisible={onVisible} continuing={continuing}/>)}</div></section>;}
