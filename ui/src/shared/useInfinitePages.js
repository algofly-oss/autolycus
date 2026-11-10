import {useCallback,useEffect,useRef,useState} from 'react';

const empty=()=>({items:[],offset:0,total:0,hasMore:true});

// Sequential, cancellable pages. Keep the lightweight loaded records, while the
// view virtualizes cards. A failed page never advances the offset or spins.
export default function useInfinitePages(fetchPage,keyOf,{initial,onReset}={}) {
  const [data,setData]=useState(()=>initial||empty());
  const [loading,setLoading]=useState(!initial?.items?.length),[error,setError]=useState(''),[ready,setReady]=useState(false);
  const dataRef=useRef(data),action=useRef(null),initialRef=useRef(initial),resetRef=useRef(onReset);
  resetRef.current=onReset;
  useEffect(()=>{
    const controller=new AbortController();let busy=false,active=true;
    const request=async(reset=false)=>{
      if(busy||!active||(!reset&&!dataRef.current.hasMore))return;
      busy=true;setLoading(true);setError('');
      const previous=reset?empty():dataRef.current;
      try {
        const page=await fetchPage(previous.offset,controller.signal);
        if(!active)return;
        const seen=new Map(previous.items.map(item=>[keyOf(item),item]));
        for(const item of page.items)seen.set(keyOf(item),item);
        const offset=previous.offset+page.items.length;
        const next={items:[...seen.values()],offset,total:page.total,hasMore:page.items.length>0&&offset<page.total};
        dataRef.current=next;setData(next);
      } catch(failure){if(active&&!controller.signal.aborted)setError('Could not load more files.');}
      finally {busy=false;if(active)setLoading(false);}
    };
    action.current=request;setReady(true);
    if(!initialRef.current?.items?.length){dataRef.current=empty();setData(dataRef.current);resetRef.current?.();request();}
    initialRef.current=null;
    return()=>{active=false;controller.abort();action.current=null;};
  },[fetchPage,keyOf]);
  const loadMore=useCallback(()=>action.current?.(),[]);
  const reload=useCallback(()=>{resetRef.current?.();return action.current?.(true);},[]);
  const update=useCallback(updater=>{const next={...dataRef.current,items:updater(dataRef.current.items)};dataRef.current=next;setData(next);},[]);
  return {...data,loading:loading||!ready,error,loadMore,reload,update,snapshot:data};
}
