import usePlayerEdgeControls from "@/shared/usePlayerEdgeControls";
import useTouchPlayerControls from "@/shared/useTouchPlayerControls";
import usePlayerFullscreen from "@/shared/usePlayerFullscreen";
import AlternateAudioControls from "@/shared/AlternateAudioControls";
// Composed from Video.js 10's public primitives and Neutral skin conventions.
// Keep settings in the control bar instead of wrapping the movie in a form.
import React, { useEffect, useRef, useState } from "react";
import { usePlayer } from "@videojs/react/video";
import { QUALITY_OPTIONS, qualityLabel } from "@/shared/playbackQuality";
import SeekPreview from "@/shared/SeekPreview";
import usePlayerGestures from "@/shared/usePlayerGestures";
import {
  Container, Controls, PlayButton, MuteButton, VolumePopover, VolumeSlider,
  TimeSlider, Time, Menu, PlaybackRateRadioGroup, PiPButton, AirPlayButton,
  CastButton, BufferingIndicator, Hotkey,
} from "@videojs/react";
import {
  PlayIcon, PauseIcon, RestartIcon, GearIcon, CheckIcon, ChevronIcon,
  VolumeOffIcon, VolumeLowIcon, VolumeHighIcon, PipEnterIcon, PipExitIcon,
  FullscreenEnterIcon, FullscreenExitIcon, AirPlayEnterIcon, AirPlayExitIcon,
  CastEnterIcon, CastExitIcon, SpinnerIcon, CaptionsOnIcon, CaptionsOffIcon,
  SpeechIcon, SpeedIcon, SwitchesIcon,
} from "@videojs/react/icons/neutral";
import { FiX, FiList, FiSkipBack, FiSkipForward, FiDownload } from "react-icons/fi";

function RadioItem({ children, ...props }) {
  return <Menu.RadioItem className="media-menu-radio-item" {...props}>
    <span className="movie-menu-label">{children}</span>
    <Menu.ItemIndicator forceMount className="media-menu-item-indicator"><CheckIcon className="media-menu-radio-item-icon" /></Menu.ItemIndicator>
  </Menu.RadioItem>;
}
function Submenu({ label, hint, Icon, children }) {
  return <Menu.Root>
    <Menu.Trigger className="media-menu-trigger-item" aria-label={label}>
      <Icon className="media-menu-trigger-item-icon" />{label}
      <span className="media-menu-hint"><span className="media-menu-hint-label">{hint}</span><ChevronIcon className="movie-menu-chevron" /></span>
    </Menu.Trigger>
    <Menu.Content className="media-menu-content" aria-label={label}>
      <Menu.Item className="media-menu-back-item"><ChevronIcon className="movie-menu-chevron movie-menu-back" />{label}</Menu.Item>
      <Menu.Separator className="media-menu-separator" />{children}
    </Menu.Content>
  </Menu.Root>;
}

// Show the actual buffered ranges, preserving gaps after a seek.
function BufferedRanges({video}) {
  const [ranges,setRanges]=useState([]);
  useEffect(()=>{
    if(!video){setRanges([]);return;}
    const update=()=>{
      const duration=video.duration,next=[];
      if(Number.isFinite(duration)&&duration>0){
        for(let i=0;i<video.buffered.length;i++){
          const start=Math.max(0,Math.min(100,video.buffered.start(i)/duration*100));
          const end=Math.max(start,Math.min(100,video.buffered.end(i)/duration*100));
          if(end>start)next.push({start,width:end-start});
        }
      }
      setRanges(previous=>JSON.stringify(previous)===JSON.stringify(next)?previous:next);
    };
    const events=['progress','timeupdate','durationchange','loadedmetadata','emptied','seeking','seeked'];
    update();events.forEach(event=>video.addEventListener(event,update));
    return()=>events.forEach(event=>video.removeEventListener(event,update));
  },[video]);
  return <span className="movie-buffered-ranges" aria-hidden="true">{ranges.map(({start,width},index)=><span key={index} className="movie-buffered-range" style={{left:`${start}%`,width:`${width}%`}}/>)}</span>;
}

// CSS landscape fallback rotates the whole control surface. Map the timeline's
// physical vertical axis back to video time; commit one seek when scrubbing ends.
function LandscapeTimeline({video,publicKey,path}) {
  const [time,setTime]=useState(0),[duration,setDuration]=useState(0),[target,setTarget]=useState(null);
  const drag=useRef(null);
  useEffect(()=>{
    if(!video)return;
    const update=()=>{setTime(video.currentTime||0);setDuration(Number.isFinite(video.duration)?video.duration:0);};
    update();video.addEventListener('timeupdate',update);video.addEventListener('durationchange',update);
    return()=>{video.removeEventListener('timeupdate',update);video.removeEventListener('durationchange',update);};
  },[video]);
  const position=event=>{const r=event.currentTarget.getBoundingClientRect();return Math.max(0,Math.min(duration,(event.clientY-r.top)/r.height*duration));};
  const value=target??time;
  return <div role="slider" aria-label="Seek" aria-valuemin={0} aria-valuemax={duration} aria-valuenow={Math.round(value)} aria-valuetext={`${Math.floor(value)} seconds`} tabIndex={0} className="movie-landscape-timeline" style={{'--seek-percent':`${duration?value/duration*100:0}%`}}
    onPointerDown={event=>{event.preventDefault();event.stopPropagation();event.currentTarget.setPointerCapture(event.pointerId);drag.current=event.pointerId;setTarget(position(event));}}
    onPointerMove={event=>{if(drag.current===event.pointerId)setTarget(position(event));}}
    onPointerUp={event=>{if(drag.current!==event.pointerId)return;drag.current=null;video.currentTime=position(event);setTarget(null);}}
    onPointerCancel={()=>{drag.current=null;setTarget(null);}}
    onKeyDown={event=>{const steps={ArrowLeft:-10,ArrowRight:10};if(event.key in steps){event.preventDefault();event.stopPropagation();video.currentTime=Math.max(0,Math.min(duration,time+steps[event.key]));}}}>
    {target!==null&&<span className="movie-landscape-preview"><SeekPreview path={path} publicKey={publicKey} time={target} active/></span>}
    <span className="movie-landscape-track"><BufferedRanges video={video}/><span className="movie-landscape-played"/><i/></span>
  </div>;
}

export default function MoviePlayerSkin({ children, name, originalName, quality, loading, onClose, tracks, audio, onAudioChange,
  subtitles, subtitle, onSubtitleChange, subtitleSearch, alternateAudio, route, compatibility, onCompatibility,
  connection, softwareAvailable, softwareVideo, onSoftwareVideo, error, videoRef, videoElement, queue, currentPath,
  episodeIndex, onEpisodeSelect, autoNext, onAutoNextChange, publicKey, downloadUrl, sourceControls, remote=false }) {
  const [settingsOpen,setSettingsOpen]=useState(false),[episodesOpen,setEpisodesOpen]=useState(false);
  const dismissPointer=useRef(null),dismissDoubleUntil=useRef(0);
  function dismissMenu(event) {
    if(dismissPointer.current?.finished)dismissPointer.current=null;
    if((!settingsOpen && !episodesOpen) || event.target.closest('button,a,input,select,textarea,[role="slider"],.media-popup'))return;
    dismissPointer.current={id:event.pointerId,until:performance.now()+1000};dismissDoubleUntil.current=performance.now()+500;
    setSettingsOpen(false);setEpisodesOpen(false);event.preventDefault();event.stopPropagation();
  }
  function consumeDismissal(event) {
    const pointer=dismissPointer.current;
    if(!pointer || performance.now()>pointer.until)return;
    if(event.type!=="click" && event.pointerId!==pointer.id)return;
    event.preventDefault();event.stopPropagation();
    if(event.type==="click")dismissPointer.current=null;else pointer.finished=true;
  }
  const [subtitleQuery,setSubtitleQuery]=useState("");
  const [seekPreview,setSeekPreview]=useState({time:0,active:false});
  const containerRef = useRef(null);
  const menuOpenRef=useRef(false);menuOpenRef.current=settingsOpen || episodesOpen;
  useEffect(()=>{
    const dismiss=event=>{
      const root=containerRef.current;
      if(!menuOpenRef.current || !root?.contains(event.target) || event.target.closest('button,a,input,select,textarea,[role="slider"],.media-popup'))return;
      dismissPointer.current={id:event.pointerId,until:performance.now()+1000};
      menuOpenRef.current=false;setSettingsOpen(false);setEpisodesOpen(false);
      event.preventDefault();event.stopImmediatePropagation();
    };
    window.addEventListener('pointerdown',dismiss,true);
    return()=>window.removeEventListener('pointerdown',dismiss,true);
  },[]);
  const toggleControls = usePlayer(state => state.toggleControls);
  usePlayerEdgeControls(containerRef,toggleControls,()=>{
    setSettingsOpen(false);setEpisodesOpen(false);
    setSeekPreview(value=>({...value,active:false}));
  });
  const lockControls = usePlayer(state => state.requestControlsLock);
  const {fullscreen,rotated,toggle:toggleFullscreen}=usePlayerFullscreen(containerRef,videoElement);
  const touchControls=useTouchPlayerControls(containerRef,videoElement,settingsOpen||episodesOpen,toggleControls);
  const hud = usePlayerGestures(containerRef, videoRef, touchControls.toggle, lockControls, toggleFullscreen,videoElement);
  const audioLabel = tracks.find(track => String(track.id) === audio)?.label || "Default";
  const subtitleLabel = subtitles.find(track => track.path === subtitle)?.name || "Off";
  return <Container onPointerDownCapture={dismissMenu} onPointerUpCapture={consumeDismissal} onClickCapture={consumeDismissal} onDoubleClick={event=>event.preventDefault()} ref={containerRef} className="media-skin media-container video-skin movie-player" data-theme="neutral" data-preset="video" data-playback-route={route} data-landscape={rotated ? "" : undefined} data-touch-controls={touchControls.touch ? (touchControls.visible ? "visible" : "hidden") : undefined}>
    {children}
    {hud && <div className="movie-gesture-hud" role="status">{hud}</div>}
    {loading && <div className="movie-startup-loading" role="status" aria-label="Loading video"><SpinnerIcon className="media-buffering-indicator-spinner-icon" /></div>}
    {!loading && <BufferingIndicator className="media-buffering-indicator"><SpinnerIcon className="media-buffering-indicator-spinner-icon" /></BufferingIndicator>}
    <Controls.Root visibility={touchControls.touch ? "always" : "auto"}>
      <Controls.Backdrop className="video-controls-backdrop" />
      <Controls.Content className="movie-player-top">
        <span className="movie-player-name" title={originalName}>{name}</span>
        <button type="button" className="media-button movie-player-close" aria-label="Close player" onClick={onClose}><FiX size={20} /></button>
      </Controls.Content>
      <Controls.Content className="video-controls video-controls-content video-controls-wrap">
        <Controls.Group className="video-controls-start">
          {queue.entries.length > 1 && <button type="button" className="media-button movie-previous" aria-label="Previous episode" disabled={episodeIndex <= 0} onClick={() => onEpisodeSelect(queue.entries[episodeIndex - 1])}><FiSkipBack size={18} /></button>}
          <PlayButton className="media-button media-play-button">
            <RestartIcon className="media-button-icon media-play-button-restart-icon" />
            <PlayIcon className="media-button-icon media-play-button-play-icon" /><PauseIcon className="media-button-icon media-play-button-pause-icon" />
          </PlayButton>
          {queue.entries.length > 1 && <button type="button" className="media-button movie-next" aria-label="Next episode" disabled={episodeIndex < 0 || episodeIndex >= queue.entries.length - 1} onClick={() => onEpisodeSelect(queue.entries[episodeIndex + 1])}><FiSkipForward size={18} /></button>}
          <VolumePopover.Root openOnHover delay={200} closeDelay={100} side="right">
            <VolumePopover.Trigger render={<MuteButton className="media-button media-mute-button">
              <VolumeOffIcon className="media-button-icon media-mute-button-off-icon" /><VolumeLowIcon className="media-button-icon media-mute-button-low-icon" /><VolumeHighIcon className="media-button-icon media-mute-button-high-icon" />
            </MuteButton>} />
            <VolumePopover.Popup data-landscape-popup={rotated ? "volume" : undefined} className="media-popup media-popup-safe-area media-popup-transition media-popup-surface media-volume-popover">
              <VolumeSlider.Root className="media-slider media-volume-slider" orientation="horizontal" thumbAlignment="edge">
                <VolumeSlider.Track className="media-slider-track"><VolumeSlider.Fill className="media-slider-fill" /></VolumeSlider.Track>
                <VolumeSlider.Thumb className="media-slider-thumb media-volume-slider-thumb" />
              </VolumeSlider.Root>
            </VolumePopover.Popup>
          </VolumePopover.Root>
        </Controls.Group>
        <Controls.Group className="video-time-slider-group">
          <Time.Group className="media-time-group"><Time.Value className="media-time-toggle" type="current" toggle /><Time.Separator className="media-time-separator" /><Time.Value className="media-time-duration-value" type="duration" /></Time.Group>
          {rotated ? <LandscapeTimeline video={videoElement} publicKey={publicKey} path={currentPath}/> : <TimeSlider.Root className="media-slider media-time-slider" onPointerMove={event=>{const video=videoRef.current;if(!video||!Number.isFinite(video.duration))return;const rect=event.currentTarget.getBoundingClientRect();setSeekPreview({time:Math.max(0,Math.min(video.duration,(event.clientX-rect.left)/rect.width*video.duration)),active:true});}} onPointerLeave={()=>setSeekPreview(value=>({...value,active:false}))}>
            <TimeSlider.Track className="media-slider-track"><BufferedRanges video={videoElement}/><TimeSlider.Fill className="media-slider-fill" /></TimeSlider.Track>
            <TimeSlider.Thumb className="media-slider-thumb media-time-slider-thumb" />
            <TimeSlider.Preview className="media-slider-preview" overflow="clamp"><div className="media-slider-preview-content media-time-slider-preview-content"><SeekPreview publicKey={publicKey} path={currentPath} time={seekPreview.time} active={seekPreview.active}/><TimeSlider.Value className="media-time-slider-value" type="pointer" /></div></TimeSlider.Preview>
          </TimeSlider.Root>}
        </Controls.Group>
        <Controls.Group className="video-controls-end">
          {subtitles.length > 0 && <button type="button" className="media-button media-captions-button video-controls-captions-button" aria-label={subtitle ? "Turn subtitles off" : "Turn subtitles on"} aria-pressed={!!subtitle} data-active={subtitle ? "" : undefined} onClick={() => onSubtitleChange(subtitle ? "" : subtitles[0].path)}>
            <CaptionsOffIcon className="media-button-icon media-captions-button-off-icon" /><CaptionsOnIcon className="media-button-icon media-captions-button-on-icon" />
          </button>}
          {queue.entries.length>1 && <Menu.Root open={episodesOpen} onOpenChange={value=>setEpisodesOpen(value)} side="top" align="end">
            <Menu.Trigger className="media-button media-episodes-button" aria-label="Episode list" title="Episodes"><FiList size={20}/></Menu.Trigger>
            <Menu.Popup data-landscape-popup={rotated ? "" : undefined} className="media-popup media-popup-surface media-menu-popup movie-episodes-popup">
              <Menu.Content className="media-menu-content" aria-label="Episode list">
                <div className="movie-playback-info">Episodes</div>
                <Menu.RadioGroup className="media-menu-radio-group movie-episode-list" aria-label="Choose episode" value={currentPath || ""} onValueChange={path=>{setEpisodesOpen(false);const entry=queue.entries.find(item=>item.path===path);if(entry&&path!==currentPath)onEpisodeSelect(entry);}}>
                  {episodesOpen && queue.entries.map(entry=><RadioItem key={entry.path} value={entry.path} data-quick-episode-path={entry.path} title={entry.label}>{entry.displayName || entry.name}</RadioItem>)}
                </Menu.RadioGroup>
              </Menu.Content>
            </Menu.Popup>
          </Menu.Root>}
          <Menu.Root open={settingsOpen} onOpenChange={value=>setSettingsOpen(value)} side="top" align="end">
            <Menu.Trigger className="media-button media-settings-menu-trigger" aria-label="Settings"><GearIcon className="media-button-icon-base media-settings-menu-trigger-icon" /></Menu.Trigger>
            <Menu.Popup data-landscape-popup={rotated ? "" : undefined} className="media-popup media-popup-surface media-menu-popup media-menu-resizable-popup movie-settings-popup">
              <Menu.Content className="media-menu-content" aria-label="Player settings">
                {sourceControls && <Submenu label="Source" hint={sourceControls.label} Icon={SwitchesIcon}>
                  <Menu.RadioGroup className="media-menu-radio-group" aria-label="Playback source" value={sourceControls.active} onValueChange={id=>{const entry=sourceControls.entries.find(item=>item.id===id);if(entry)sourceControls.choose(entry);}}>
                    {sourceControls.entries.map(entry=><RadioItem key={entry.id} value={entry.id} data-source-id={entry.id}>{entry.label}{entry.quality ? ` · ${entry.quality}` : ''}</RadioItem>)}
                  </Menu.RadioGroup>
                  <button type="button" role="menuitem" data-item="" className="media-menu-trigger-item" aria-disabled={sourceControls.loading} onClick={()=>{if(!sourceControls.loading)sourceControls.load();}}>{sourceControls.loading?'Finding sources…':'Find online sources'}</button>
                  {sourceControls.error && <div className="movie-playback-info" role="status">{sourceControls.error}</div>}
                </Submenu>}
                <Submenu label="Quality" hint={quality.hint} Icon={SwitchesIcon}>
                  <Menu.RadioGroup className="media-menu-radio-group" aria-label="Quality" value={quality.preference} onValueChange={quality.choose}>
                    {QUALITY_OPTIONS.map(value => {
                      const available = value === "auto" || value === "original" || quality.versions.some(version => version.quality === value);
                      return <RadioItem key={value} value={value} disabled={!available || quality.saving} data-quality={value}>{qualityLabel(value)}{!available && <span className="movie-quality-unavailable">Unavailable</span>}</RadioItem>;
                    })}
                  </Menu.RadioGroup>
                  {quality.error && <div className="movie-playback-info movie-quality-error" role="alert">{quality.error}</div>}
                </Submenu>
                {(queue.loading || queue.limited || queue.entries.length > 1) && <Submenu label="Episodes" hint={queue.loading ? "Loading" : `${episodeIndex + 1} / ${queue.entries.length}`} Icon={FiList}>
                  <Menu.Item className="media-menu-trigger-item" role="menuitemcheckbox" aria-checked={autoNext} onSelect={onAutoNextChange}>Autoplay next<span className="media-menu-hint">{autoNext ? "On" : "Off"}</span></Menu.Item>
                  <Menu.Separator className="media-menu-separator" />
                  <Menu.RadioGroup className="media-menu-radio-group movie-episode-list" aria-label="Episode" value={currentPath || ""} onValueChange={path => { const entry = queue.entries.find(item => item.path === path); if (entry && path !== currentPath) onEpisodeSelect(entry); }}>
                    {settingsOpen && queue.entries.map(entry => <RadioItem key={entry.path} value={entry.path} data-episode-path={entry.path} title={entry.label}>{entry.displayName || entry.name}</RadioItem>)}
                  </Menu.RadioGroup>
                  {(queue.loading || queue.limited) && <div className="movie-playback-info">{queue.loading ? "Loading episodes…" : "Showing available episodes (up to 500 files in 64 folders)."}</div>}
                </Submenu>}
                {<Submenu label="Audio" hint={audioLabel} Icon={SpeechIcon}>
                  <Menu.RadioGroup className="media-menu-radio-group" aria-label="Audio track" value={alternateAudio.choice ? "" : audio} onValueChange={onAudioChange}>
                    {tracks.map(track => <RadioItem key={track.id} value={String(track.id)} data-audio-id={track.id}>{track.label} · {track.codec || "unknown"}</RadioItem>)}
                  </Menu.RadioGroup>
                  {!publicKey && !remote && <AlternateAudioControls audio={alternateAudio} name={name}/>}
                </Submenu>}
                {<Submenu label="Subtitles" hint={subtitleLabel} Icon={CaptionsOffIcon}>
                  <Menu.RadioGroup className="media-menu-radio-group" aria-label="Subtitles" value={subtitle} onValueChange={onSubtitleChange}>
                    <RadioItem value="" data-subtitle-id="">Off</RadioItem>
                    {subtitles.map(track => <RadioItem key={track.path} value={track.path} data-subtitle-id={track.path}>{track.name}</RadioItem>)}
                  </Menu.RadioGroup>
                  {!publicKey && !remote && <form className="movie-playback-info" onSubmit={event=>{event.preventDefault();subtitleSearch.search(subtitleQuery);}} onKeyDown={event=>event.stopPropagation()}>
                    <label className="mb-2 block">Language<select aria-label="Subtitle language" value={subtitleSearch.language} onChange={event=>subtitleSearch.setLanguage(event.target.value)} className="ml-2 rounded border border-white/20 bg-neutral-900 p-1">{[['en','English'],['hi','Hindi'],['es','Spanish'],['fr','French'],['de','German'],['it','Italian'],['pt','Portuguese'],['ar','Arabic'],['ja','Japanese'],['ko','Korean'],['zh','Chinese'],['ta','Tamil'],['te','Telugu'],['pa','Punjabi'],['bn','Bengali']].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
                    <input aria-label="Subtitle search" placeholder="Search OpenSubtitles" value={subtitleQuery} onChange={event=>setSubtitleQuery(event.target.value)} className="w-full rounded border border-white/20 bg-transparent p-2" />
                    <button type="submit" disabled={subtitleSearch.busy} className="mt-2 text-blue-400">{subtitleSearch.busy ? "Searching…" : "Search subtitles"}</button>
                    {subtitleSearch.error && <p role="status">{subtitleSearch.error}</p>}
                  </form>}
                </Submenu>}
                <Menu.Root><PlaybackRateRadioGroup.Root>
                  <Menu.Trigger className="media-menu-trigger-item" aria-label="Speed"><SpeedIcon className="media-menu-trigger-item-icon" />Speed<span className="media-menu-hint"><PlaybackRateRadioGroup.Value className="media-menu-hint-label" /><ChevronIcon className="movie-menu-chevron" /></span></Menu.Trigger>
                  <Menu.Content className="media-menu-content" aria-label="Speed"><Menu.Item className="media-menu-back-item"><ChevronIcon className="movie-menu-chevron movie-menu-back" />Speed</Menu.Item><Menu.Separator className="media-menu-separator" />
                    <PlaybackRateRadioGroup.Options className="media-menu-radio-group" renderItem={(props, item) => <RadioItem {...props}>{item.label}</RadioItem>} />
                  </Menu.Content>
                </PlaybackRateRadioGroup.Root></Menu.Root>
                <Submenu label="Playback" hint={softwareVideo ? "This device" : compatibility ? "Compatible" : "Auto"} Icon={SwitchesIcon}>
                  <Menu.Item className="media-menu-trigger-item" onSelect={onCompatibility}>Client compatibility playback</Menu.Item>
                  {softwareAvailable && <Menu.Item className="media-menu-trigger-item" onSelect={onSoftwareVideo}>Play using this device</Menu.Item>}
                  <div className="movie-playback-info" role="status">{connection?.label || (route === "direct" ? "Direct connection" : "Public proxy")}{softwareVideo && <p>Processing on this device may use more battery. HDR colors may differ.</p>}</div>
                </Submenu>
                {downloadUrl && (<><Menu.Separator className="media-menu-separator" /><Menu.Item render={<a href={downloadUrl}/>} className="media-menu-trigger-item" aria-label="Download video"><FiDownload className="media-menu-trigger-item-icon"/><span className="movie-menu-label">Download</span></Menu.Item></>)}
              </Menu.Content>
            </Menu.Popup>
          </Menu.Root>
          <Controls.Group className="video-controls-trailing">
            <CastButton title="Cast requires a compatible browser, receiver and remotely playable source" className="media-button media-cast-button"><CastEnterIcon className="media-button-icon media-cast-button-enter-icon" /><CastExitIcon className="media-button-icon media-cast-button-exit-icon" /></CastButton>
            <AirPlayButton title="AirPlay requires Safari, an available receiver and a supported playback source" className="media-button media-airplay-button"><AirPlayEnterIcon className="media-button-icon media-airplay-button-enter-icon" /><AirPlayExitIcon className="media-button-icon media-airplay-button-exit-icon" /></AirPlayButton>
            <PiPButton className="media-button media-pip-button"><PipEnterIcon className="media-button-icon media-pip-button-enter-icon" /><PipExitIcon className="media-button-icon media-pip-button-exit-icon" /></PiPButton>
            <button type="button" aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"} data-fullscreen={fullscreen ? "" : undefined} onClick={toggleFullscreen} className="media-button media-fullscreen-button"><FullscreenEnterIcon className="media-button-icon media-fullscreen-button-enter-icon" /><FullscreenExitIcon className="media-button-icon media-fullscreen-button-exit-icon" /></button>
          </Controls.Group>
        </Controls.Group>
      </Controls.Content>
    </Controls.Root>
    <Hotkey keys="Space k" action="togglePaused" /><Hotkey keys="i" action="togglePictureInPicture" />
    {error && <div className="movie-player-error" role="alert"><p>{error.replace("Try client video compatibility.", "Open Settings → Playback to play using this device.")}</p></div>}
  </Container>;
}
