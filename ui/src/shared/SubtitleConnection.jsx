import {useEffect,useState} from 'react';
import axios from 'axios';

export default function SubtitleConnection() {
  const [connection,setConnection]=useState(null),[key,setKey]=useState(''),[username,setUsername]=useState(''),[password,setPassword]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
  useEffect(()=>{const controller=new AbortController();axios.get('/api/auth/opensubtitles',{signal:controller.signal}).then(({data})=>{setConnection(data);setUsername(data.username || '');}).catch(()=>{if(!controller.signal.aborted)setMessage('Unable to load connection.');});return()=>controller.abort();},[]);
  async function save(event){event.preventDefault();setBusy(true);setMessage('');try{const {data}=await axios.put('/api/auth/opensubtitles',{api_key:key,username,password});setConnection({...data,has_password:!!password || connection?.has_password});setKey('');setPassword('');setMessage('Connection saved.');}catch{setMessage('Unable to save connection.');}finally{setBusy(false);}}
  const field='settings-input';
  return <section><div className="settings-intro"><h2>Subtitles</h2><p>Search and match subtitles from the player. Your connection is stored encrypted on the server.</p></div><div className="settings-row"><div><h3>OpenSubtitles</h3><p>Connect your account to find subtitles directly in the player.</p></div><form onSubmit={save} className="space-y-5">
    <label className="block text-sm">API key<input type="password" autoComplete="off" value={key} onChange={event=>setKey(event.target.value)} placeholder={connection?.configured?'Saved · leave blank to keep':'OpenSubtitles API key'} className={field}/></label>
    <label className="block text-sm">OpenSubtitles username<input autoComplete="username" value={username} onChange={event=>setUsername(event.target.value)} className={field}/></label>
    <label className="block text-sm">Password<input type="password" autoComplete="current-password" value={password} onChange={event=>setPassword(event.target.value)} placeholder={connection?.has_password?'Saved · leave blank to keep':''} className={field}/></label>
    <button type="submit" disabled={busy || !connection} className="settings-button settings-button-primary">{busy?'Saving…':'Save connection'}</button>
    {message&&<p role="status" className="text-sm text-neutral-500">{message}</p>}
  </form></div></section>;
}
