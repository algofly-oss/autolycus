import {useEffect,useRef,useState} from 'react';
import {useDispatch,useSelector} from 'react-redux';
import axios from 'axios';
import {authActions,authSelector} from '@/redux/features/authSlice';
import {profileHeaders} from './mediaProfile';

export default function useSubtitlePreferences(path, tracks, ready, setSubtitle, enabled=true) {
  const user=useSelector(authSelector),dispatch=useDispatch();
  const preferences=user?.preferences?.video_subtitles || {enabled:false,language:'en',auto_match:true};
  const [results,setResults]=useState([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [stored,setStored]=useState(null),[loaded,setLoaded]=useState(false);
  const initialized=useRef(false),generation=useRef(0);
  useEffect(()=>{
    const controller=new AbortController();generation.current++;initialized.current=false;setStored(null);setLoaded(false);setResults([]);setError('');
    if(enabled&&path)axios.get('/api/files/playback/subtitle-selection',{params:{path},headers:profileHeaders(),signal:controller.signal}).then(({data})=>{setStored(data.selection);setLoaded(true);}).catch(()=>{if(!controller.signal.aborted)setLoaded(true);});
    return()=>controller.abort();
  },[path,enabled]);
  async function search(query='',automatic=false) {
    const current=generation.current;setBusy(true);setError('');
    try {
      const {data}=await axios.post('/api/files/playback/opensubtitles/search',{path,query,language:preferences.language},{headers:profileHeaders()});
      if(current!==generation.current)return;
      setResults(data.results || []);
      if(automatic){const match=data.results?.find(row=>row.hash_match);if(match)await choose(`os:${match.id}`,match);}
    }catch(failure){if(current===generation.current&&!automatic)setError(failure.response?.data?.detail || 'Subtitle search unavailable. Check your OpenSubtitles connection.');}
    finally{if(current===generation.current)setBusy(false);}
  }
  async function choose(value,row) {
    if(!enabled){setSubtitle(value);return;}
    row=row || results.find(item=>`os:${item.id}`===value);
    setSubtitle(value);setError('');
    const language=row?.language || tracks.find(track=>track.path===value)?.language || preferences.language;
    const next={...preferences,enabled:!!value,language};
    try{
      const [response]=await Promise.all([
        axios.patch('/api/auth/preferences',{video_subtitles:next}),
        axios.put('/api/files/playback/subtitle-selection',{path,subtitle:value,language,name:row?.name || tracks.find(track=>track.path===value)?.name || ''},{headers:profileHeaders()})
      ]);
      dispatch(authActions.updateAccountInfo({preferences:response.data.preferences}));
      setStored({subtitle:value,name:row?.name || 'Online subtitles',language});
    }catch{setError('Unable to save subtitle preference.');}
  }
  useEffect(()=>{
    if(!ready){initialized.current=false;return;}
    if(!enabled || !loaded || initialized.current)return;
    initialized.current=true;
    if(!preferences.enabled)return;
    if(stored?.subtitle && (stored.subtitle.startsWith('os:') || tracks.some(track=>track.path===stored.subtitle))){setSubtitle(stored.subtitle);return;}
    const language=preferences.language;
    const normalize=value=>{try{return new Intl.Locale(value).language;}catch{return value;}};
    const match=tracks.find(track=>normalize(track.language)===normalize(language));
    if(match)setSubtitle(match.path);
    else if(preferences.auto_match)search('',true);
  },[ready,loaded,tracks,stored]);
  const online=results.map(row=>({path:`os:${row.id}`,name:row.name,language:row.language}));
  if(stored?.subtitle?.startsWith('os:')&&!online.some(row=>row.path===stored.subtitle))online.push({path:stored.subtitle,name:stored.name || 'Online subtitles',language:stored.language});
  async function setLanguage(language) {
    try{const {data}=await axios.patch('/api/auth/preferences',{video_subtitles:{...preferences,language}});dispatch(authActions.updateAccountInfo({preferences:data.preferences}));setResults([]);}catch{setError('Unable to save subtitle language.');}
  }
  return {choose,search,results,busy,error,online,language:preferences.language,setLanguage};
}
