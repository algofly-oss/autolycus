import {useEffect,useRef,useState} from 'react';
import axios from 'axios';
import {createMediaTransport} from './mediaTransport';
import {inspectMedia} from './mediaPlayback';
import {profileHeaders} from './mediaProfile';
import {autoAlignAudio} from './alignAudio';

export default function useAlternateAudio(path,mainRef,capturePlayback,onActivate,enabled=true) {
  const [choice,setChoice]=useState(null),[media,setMedia]=useState(null),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[results,setResults]=useState([]),[aligning,setAligning]=useState(false);
  const searchRequest=useRef(null);
  const generation=useRef(0),alignment=useRef(null),resource=useRef(null);
  const capture=useRef(capturePlayback);capture.current=capturePlayback;
  const activate=useRef(onActivate);activate.current=onActivate;
  const choiceRef=useRef(null);choiceRef.current=choice;
  async function persist(value){await axios.put('/api/files/playback/alternate-audio',{path,...value},{headers:profileHeaders()});}
  async function load(value,automatic=false) {
    const gen=++generation.current;
    alignment.current?.abort();capture.current();setBusy(true);setMessage('');
    resource.current?.media.input.dispose();resource.current?.transport.close();resource.current=null;setMedia(null);setChoice(null);
    if(!value.donor){setBusy(false);return;}
    let transport,inspected;
    try{
      transport=await createMediaTransport(`/api/files/stream?path=${encodeURIComponent(value.donor)}`);
      inspected=await inspectMedia(transport);
      if(gen!==generation.current){inspected.input.dispose();transport.close();return;}
      if(!inspected.audio.length)throw new Error('This file has no audio track.');
      const next={...value,track_id:inspected.audio.some(track=>track.id===value.track_id)?value.track_id:inspected.audio[0].id};
      resource.current={transport,media:inspected};setChoice(next);setMedia(inspected);activate.current();
      if(!automatic){await persist(next);if(gen===generation.current)align(inspected,next);}
    }catch(error){inspected?.input.dispose();transport?.close();if(gen===generation.current)setMessage(error.response?.data?.detail || error.message || 'Unable to open this soundtrack.');}
    finally{if(gen===generation.current)setBusy(false);}
  }
  useEffect(()=>{
    const controller=new AbortController();
    if(enabled&&path)axios.get('/api/files/playback/alternate-audio',{params:{path},headers:profileHeaders(),signal:controller.signal}).then(({data})=>{if(data.selection?.donor&&!controller.signal.aborted)load(data.selection,true);}).catch(()=>{});
    return()=>{controller.abort();generation.current++;alignment.current?.abort();searchRequest.current?.abort();resource.current?.media.input.dispose();resource.current?.transport.close();resource.current=null;setMedia(null);setChoice(null);};
  },[path,enabled]);
  async function search(query){searchRequest.current?.abort();const controller=new AbortController();searchRequest.current=controller;setBusy(true);setMessage('');try{const {data}=await axios.get('/api/files/search',{params:{q:query,item_type:'file',limit:30},signal:controller.signal});if(!controller.signal.aborted)setResults((data.data || []).filter(row=>row.relative_path!==path&&/\.(mkv|mp4|webm|mov|avi|m4v|ts|m2ts|mp3|aac|m4a|wav|flac|ogg)$/i.test(row.relative_path)));}catch{if(!controller.signal.aborted)setMessage('Unable to search your files.');}finally{if(!controller.signal.aborted)setBusy(false);}}
  async function apply(values){const next={...choice,...values};capture.current();setChoice(next);try{await persist(next);setMessage('Sync saved.');}catch{setMessage('Unable to save sync.');}}
  async function clear(){alignment.current?.abort();capture.current();await load({donor:''});activate.current();try{await persist({donor:'',track_id:0,delay:0,rate:1});}catch{setMessage('Unable to save soundtrack preference.');}}
  async function align(donor=media,value=choice){
    if(!mainRef.current||!donor)return;
    alignment.current?.abort();const controller=new AbortController();alignment.current=controller;setAligning(true);setMessage('Matching audio on this device…');
    const timer=setTimeout(()=>controller.abort(),55000);
    try{
      const match=await Promise.race([
        autoAlignAudio(mainRef.current,donor,value.track_id,controller.signal),
        new Promise((_,reject)=>controller.signal.addEventListener('abort',()=>reject(new DOMException('Cancelled','AbortError')),{once:true}))
      ]);
      if(controller.signal.aborted)return;
      capture.current();const next={...value,...match};setChoice(next);await persist(next);setMessage('Audio aligned. Adjust manually if needed.');
    }catch(error){if(alignment.current===controller)setMessage(controller.signal.aborted?'Automatic alignment stopped. Manual sync is available.':error.message);}
    finally{clearTimeout(timer);if(alignment.current===controller)setAligning(false);}
  }
  return {choice,media,results,busy,message,aligning,search,select:row=>load({donor:row.relative_path,track_id:0,delay:0,rate:1}),apply,clear,align:()=>align(),cancelAlign:()=>alignment.current?.abort(),playback:media&&choice?{media,trackId:choice.track_id,delay:choice.delay,rate:choice.rate}:null};
}
