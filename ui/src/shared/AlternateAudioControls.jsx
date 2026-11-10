import {useEffect,useState} from 'react';

export default function AlternateAudioControls({audio,name}) {
  const suggested=(name || '').split('·')[0].replace(/\(\d{4}\)/g,'').trim();
  const [query,setQuery]=useState(suggested),[delay,setDelay]=useState(0),[rate,setRate]=useState(1);
  useEffect(()=>{setDelay(audio.choice?.delay || 0);setRate(audio.choice?.rate || 1);},[audio.choice]);
  useEffect(()=>{if(suggested)audio.search(suggested);},[suggested]);
  const input='w-full rounded border border-white/20 bg-transparent p-2';
  return <div className="movie-playback-info space-y-3" onKeyDown={event=>event.stopPropagation()}>
    <form onSubmit={event=>{event.preventDefault();audio.search(query);}}>
      <input aria-label="Find alternate audio file" placeholder="Search your media files" value={query} onChange={event=>setQuery(event.target.value)} className={input}/>
      <button disabled={audio.busy} type="submit" className="mt-2 text-blue-400">{audio.busy?'Loading…':'Find soundtrack'}</button>
    </form>
    <div className="max-h-40 overflow-y-auto">{audio.results.map(row=><button type="button" key={row.relative_path} className="block w-full py-2 text-left" disabled={audio.busy} onClick={()=>audio.select(row)}>{row.name || row.relative_path.split('/').pop()}</button>)}</div>
    {audio.choice&&<>
      <p className="break-words">{audio.choice.donor.split('/').pop()}</p>
      <label className="block">Track<select aria-label="Alternate audio track" value={audio.choice.track_id} onChange={event=>audio.apply({track_id:Number(event.target.value)})} className={input}>{audio.media?.tracks.map(track=><option key={track.id} value={track.id}>{track.label}</option>)}</select></label>
      <form className="space-y-3" onSubmit={event=>{event.preventDefault();audio.apply({delay:Number(delay),rate:Number(rate)});}}>
        <label className="block">Audio delay (seconds)<input aria-label="Audio delay seconds" type="number" min="-3600" max="3600" step="0.1" required value={delay} onChange={event=>setDelay(event.target.value)} className={input}/></label>
        <label className="block">Audio speed<input aria-label="Audio speed ratio" type="number" min="0.5" max="2" step="0.00001" required value={rate} onChange={event=>setRate(event.target.value)} className={input}/></label>
        <p>Positive delay plays audio later. Speed changes can alter pitch.</p>
        <button type="submit" className="text-blue-400">Apply sync</button>
      </form>
      <div className="flex flex-wrap gap-3"><button type="button" className="text-blue-400" onClick={audio.aligning?audio.cancelAlign:audio.align}>{audio.aligning?'Stop alignment':'Auto align'}</button><button type="button" onClick={()=>audio.apply({delay:0,rate:1})}>Reset sync</button><button type="button" onClick={audio.clear}>Use original audio</button></div>
    </>}
    {audio.message&&<p role="status">{audio.message}</p>}
  </div>;
}
