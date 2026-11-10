import {useEffect,useRef,useState} from 'react';
import {useVirtualizer} from '@tanstack/react-virtual';
import {FiLoader} from 'react-icons/fi';
import useBrowserLayoutEffect from './hooks/useBrowserLayoutEffect';

export default function InfiniteMediaList({items,scrollRef,viewMode='list',mobileColumns=2,renderItem,itemKey,hasMore,loading,error,loadMore,onRange,initialOffset=0,onScrollOffset,scrollToKey}) {
  const [width,setWidth]=useState(0),[viewport,setViewport]=useState(0),[margin,setMargin]=useState(0);
  const root=useRef(null),callbacks=useRef({onRange,onScrollOffset});callbacks.current={onRange,onScrollOffset};
  useBrowserLayoutEffect(()=>{
    const resize=()=>{setWidth(root.current?.clientWidth||0);setViewport(innerWidth);if(root.current&&scrollRef.current)setMargin(root.current.getBoundingClientRect().top-scrollRef.current.getBoundingClientRect().top+scrollRef.current.scrollTop);};
    const observer=new ResizeObserver(resize);if(root.current)observer.observe(root.current);
    window.addEventListener('resize',resize);resize();
    return()=>{observer.disconnect();window.removeEventListener('resize',resize);};
  },[]);
  const columns=viewMode==='grid'?(viewport>=1536?8:viewport>=1024?6:viewport>=640?5:mobileColumns):1;
  const rows=Math.ceil(items.length/columns),footer=hasMore||loading||error;
  const posterWidth=Math.max(0,(width-8-(columns-1)*10)/columns);
  const virtual=useVirtualizer({count:rows+(footer?1:0),getScrollElement:()=>scrollRef.current,estimateSize:index=>index>=rows?56+(viewMode==='grid'?16:6):viewMode==='grid'?(posterWidth*1.5+16):100,overscan:3,initialOffset,scrollMargin:margin,getItemKey:index=>index<rows?itemKey(items[index*columns]):'load-more'});
  const targetIndex=scrollToKey?items.findIndex(item=>itemKey(item)===scrollToKey):-1;
  useEffect(()=>{if(targetIndex>=0)virtual.scrollToIndex(Math.floor(targetIndex/columns),{align:"center"});},[targetIndex,scrollToKey,columns,virtual]);
  const visible=virtual.getVirtualItems(),first=visible[0]?.index??0,last=visible.at(-1)?.index??-1;
  useBrowserLayoutEffect(()=>{
    virtual.measure();
    // Resetting the cache also drops measurements collected by the ref callbacks.
    // Re-read mounted rows even when their size hasn't changed (and no resize fires).
    root.current?.querySelectorAll('[data-index]').forEach(element=>virtual.measureElement(element));
  },[columns,viewMode,width,virtual]);
  useEffect(()=>{callbacks.current.onRange?.(first*columns,Math.min(items.length,(last+1)*columns));},[first,last,columns,items.length]);
  useEffect(()=>{if(last>=rows-2&&hasMore&&!loading&&!error&&scrollRef.current?.clientHeight>0)loadMore();},[last,rows,hasMore,loading,error,loadMore,scrollRef]);
  useEffect(()=>{
    const element=scrollRef.current;let timer;
    const save=()=>{clearTimeout(timer);timer=setTimeout(()=>callbacks.current.onScrollOffset?.(element.scrollTop),100);};
    element?.addEventListener('scroll',save,{passive:true});return()=>{clearTimeout(timer);element?.removeEventListener('scroll',save);};
  },[scrollRef]);
  return <div ref={root} data-infinite-media-list data-loaded-count={items.length} style={{height:virtual.getTotalSize(),position:'relative',width:'100%',minHeight:!items.length&&!loading?56:undefined}}>
    {!items.length&&!loading&&!error&&<p className="p-4 text-center text-sm text-neutral-500">No files found</p>}
    {visible.map(row=><div key={row.key} data-index={row.index} ref={virtual.measureElement} data-media-row={row.index<rows?'':undefined} style={{position:'absolute',top:0,left:0,width:'100%',transform:`translateY(${row.start-margin}px)`,paddingBottom:viewMode==='grid'?16:6}}>
      {row.index<rows?<div style={{display:'grid',gridTemplateColumns:`repeat(${columns},minmax(0,1fr))`,gap:viewMode==='grid'?10:0,paddingInline:4}}>{items.slice(row.index*columns,(row.index+1)*columns).map(item=><div key={itemKey(item)} data-media-item>{renderItem(item)}</div>)}</div>:<div className="flex min-h-[56px] items-center justify-center gap-2 text-sm text-neutral-500" role="status">{error?<><span>{error}</span><button type="button" onClick={loadMore} className="rounded px-3 py-2 text-blue-500">Retry</button></>:loading?<FiLoader aria-label="Loading more files" className="animate-spin" size={18}/>:null}</div>}
    </div>)}
  </div>;
}
