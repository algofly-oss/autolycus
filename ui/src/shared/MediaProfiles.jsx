import { createContext, useContext, useEffect, useRef, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useRouter } from "next/router";
import axios from "axios";
import { Menu, useMantineColorScheme } from "@mantine/core";
import { FiUser, FiFilm, FiMoon, FiSun, FiMusic, FiStar, FiCheck, FiEdit3, FiArrowRight, FiChevronDown } from "react-icons/fi";
import { authActions, authSelector } from "@/redux/features/authSlice";
import { activeMediaProfile, setActiveMediaProfile, PROFILE_PREF_KEYS } from "./mediaProfile";

const Context=createContext(null);
const avatars={user:FiUser,film:FiFilm,moon:FiMoon,sun:FiSun,music:FiMusic,star:FiStar};
export function ProfileAvatar({avatar="user",size=20}) { const Icon=avatars[avatar] || FiUser;return <Icon size={size} />; }
export const useMediaProfiles=()=>useContext(Context);

export function MediaProfilesProvider({children}) {
  const user=useSelector(authSelector),dispatch=useDispatch(),router=useRouter();
  const userRef=useRef(user);userRef.current=user;
  const defaults=useRef({}),activeRef=useRef(null);
  const [profiles,setProfiles]=useState([]),[active,setActive]=useState(null),[loadedFor,setLoadedFor]=useState(""),[error,setError]=useState("");
  function preferences(profile) {
    const merged={...(userRef.current.preferences||{})};
    for(const key of PROFILE_PREF_KEYS){delete merged[key];const value=profile?.preferences?.[key]??defaults.current[key];if(value!==undefined)merged[key]=value;}
    merged.video_quality ??= "auto";
    return merged;
  }
  function apply(profile) {
    activeRef.current=profile;setActiveMediaProfile(profile.id);setActive(profile);
    dispatch(authActions.updateAccountInfo({preferences:preferences(profile)}));
  }
  async function reload() {
    const response=await axios.get('/api/auth/profiles');setProfiles(response.data.profiles);
    const selected=response.data.profiles.find(profile=>profile.id===activeRef.current?.id)||response.data.profiles[0];
    if(selected)apply(selected);
    return response.data.profiles;
  }
  useEffect(()=>{
    const request=axios.interceptors.request.use(config=>{
      if(typeof window!=="undefined" && new URL(config.url,location.href).origin===location.origin && config.url.includes('/auth/preferences'))config.headers['X-Profile-ID']=activeMediaProfile();
      return config;
    });
    const response=axios.interceptors.response.use(result=>{
      if(result.config.url.includes('/auth/preferences') && result.data?.preferences && (result.config.headers['X-Profile-ID']||'default')===activeMediaProfile()) {
        const current=activeRef.current;
        if(current){const values={...current.preferences};for(const key of PROFILE_PREF_KEYS)if(result.data.preferences[key]!==undefined)values[key]=result.data.preferences[key];const next={...current,preferences:values};activeRef.current=next;setActive(next);setProfiles(rows=>rows.map(row=>row.id===next.id?next:row));}
      }
      return result;
    });
    return ()=>{axios.interceptors.request.eject(request);axios.interceptors.response.eject(response);};
  },[]);
  useEffect(()=>{
    if(!user?.username){setLoadedFor("");setActive(null);activeRef.current=null;setActiveMediaProfile('default');return;}
    let cancelled=false;setError("");defaults.current={...(user.preferences||{})};
    axios.get('/api/auth/profiles').then(response=>{
      if(cancelled)return;
      let stored='default';try{stored=localStorage.getItem('autolycus:profile:'+user.username)||'default';}catch{}
      const list=response.data.profiles,chosen=list.find(profile=>profile.id===stored)||list[0];
      setProfiles(list);apply(chosen);setLoadedFor(user.username);
    }).catch(()=>{if(!cancelled)setError('Could not load profiles. Refresh to try again.');});
    return ()=>{cancelled=true;};
  },[user?.username]);
  useEffect(()=>{
    if(!activeRef.current || loadedFor!==user?.username)return;
    const expected=preferences(activeRef.current);
    if(PROFILE_PREF_KEYS.some(key=>expected[key]!==user?.preferences?.[key]))dispatch(authActions.updateAccountInfo({preferences:expected}));
  },[user?.preferences,loadedFor]);
  async function switchProfile(id) {
    const chosen=profiles.find(profile=>profile.id===id);if(!chosen||chosen.id===activeRef.current?.id)return;
    const query={...router.query};delete query.video;delete query.t;
    await router.replace({pathname:router.pathname,query},undefined,{shallow:true,scroll:false}).catch(()=>{});
    try{localStorage.setItem('autolycus:profile:'+user.username,id);}catch{}
    apply(chosen);
  }
  if(user?.username && loadedFor!==user.username)return <div className="grid min-h-screen place-content-center bg-white px-6 text-sm settings-secondary dark:bg-neutral-900" role="status">{error||'Loading profile…'}</div>;
  return <Context.Provider value={{profiles,active,switchProfile,reload}}><div key={`${user?.username||''}:${active?.id||'default'}`} className="contents">{children}</div></Context.Provider>;
}

export function ProfileSwitcher({collapsed=false,appearance}) {
  const profiles=useMediaProfiles(),router=useRouter();
  const {colorScheme}=useMantineColorScheme();
  if(!profiles?.active)return null;
  return <Menu withinPortal position="top-end" width={288} shadow="md" offset={10}>
    <Menu.Target><button type="button" aria-label="Switch profile" title={profiles.active.name} className={appearance==='dark'?'profile-trigger profile-trigger-cinema':`flex min-h-[44px] items-center justify-center gap-2 rounded-md px-2 text-neutral-600 hover:bg-neutral-200 dark:text-neutral-300 dark:hover:bg-neutral-900 ${collapsed?'w-10':'md:justify-start md:px-4'}`}>
      <span className={appearance==='dark'?'profile-trigger-avatar':'contents'} data-avatar={profiles.active.avatar}><ProfileAvatar avatar={profiles.active.avatar}/></span>
      {(appearance==='dark'||!collapsed)&&<span className={appearance==='dark'?'profile-trigger-name':'hidden truncate text-sm md:block'}>{profiles.active.name}</span>}
      {appearance==='dark'&&<FiChevronDown size={13}/>}</button></Menu.Target>
    <Menu.Dropdown className="profile-switcher-menu" data-profile-theme={appearance || colorScheme}>
      <div className="profile-switcher-heading"><span>Profiles</span><span>Choose who’s watching</span></div>
      <div className="profile-switcher-list">{profiles.profiles.map(profile=>{
        const active=profile.id===profiles.active.id;
        return <Menu.Item key={profile.id} className={`profile-switcher-item ${active?'is-active':''}`} aria-label={`Use profile ${profile.name}`} onClick={()=>profiles.switchProfile(profile.id)}>
          <span className="profile-switcher-row"><span className="profile-switcher-avatar" data-avatar={profile.avatar}><ProfileAvatar avatar={profile.avatar} size={28}/>{active&&<span className="profile-avatar-selected"><FiCheck size={12}/></span>}</span><span className="profile-switcher-name">{profile.name}{active&&<span>Watching as</span>}</span></span>
        </Menu.Item>;
      })}</div>
      <div className="profile-switcher-footer"><Menu.Item className="profile-switcher-manage" onClick={()=>router.push('/home?tab=settings&category=profiles')}><span><FiEdit3 size={16}/>Manage profiles<FiArrowRight size={16}/></span></Menu.Item></div>
    </Menu.Dropdown>
  </Menu>;
}

export function ProfileSettings() {
  const context=useMediaProfiles();const [editing,setEditing]=useState(null),[name,setName]=useState(''),[avatar,setAvatar]=useState('user'),[busy,setBusy]=useState(false),[error,setError]=useState('');
  if(!context)return null;
  async function save(event){event.preventDefault();setBusy(true);setError('');try{if(editing)await axios.patch('/api/auth/profiles/'+editing,{name,avatar});else await axios.post('/api/auth/profiles',{name,avatar});await context.reload();setName('');setAvatar('user');setEditing(null);}catch(reason){setError(reason.response?.data?.detail||'Could not save profile');}finally{setBusy(false);}}
  return <section className="min-w-0" aria-label="Profiles">
    <div className="settings-intro"><h2>Profiles</h2><p >Separate watch history and playback preferences. Downloads and account access stay shared.</p></div>
    <div className="settings-divided-list">{context.profiles.map(profile=><div key={profile.id} className="settings-profile-row"><span className="settings-profile-avatar"><ProfileAvatar avatar={profile.avatar}/></span><span className="min-w-0 flex-1 truncate text-sm">{profile.name}{profile.id===context.active.id&&<span className="ml-2 text-xs text-neutral-400">Active</span>}</span><button type="button" className="min-h-[40px] px-2 text-xs settings-secondary" onClick={()=>{setEditing(profile.id);setName(profile.name);setAvatar(profile.avatar);}}>Edit</button><button type="button" className="min-h-[40px] px-2 text-xs text-blue-600 disabled:text-neutral-400 dark:text-blue-400" disabled={profile.id===context.active.id} onClick={()=>context.switchProfile(profile.id)}>Use profile</button></div>)}</div>
    <form onSubmit={save} className="settings-profile-form"><h3 className="text-sm font-medium">{editing?'Edit profile':'Add profile'}</h3><label className="block text-xs settings-secondary">Name<input required maxLength={40} aria-label="Profile alias" value={name} onChange={event=>setName(event.target.value)} className="settings-input"/></label><div className="flex flex-wrap gap-2" role="group" aria-label="Profile avatar">{Object.keys(avatars).map(value=><button key={value} type="button" aria-label={`Avatar ${value}`} aria-pressed={avatar===value} onClick={()=>setAvatar(value)} className={`grid h-10 w-10 place-items-center rounded-md border ${avatar===value?'border-blue-500 text-blue-500':'border-neutral-200 settings-secondary settings-border'}`}><ProfileAvatar avatar={value}/></button>)}</div>{error&&<p role="alert" className="text-xs text-red-500">{error}</p>}<div className="flex gap-2"><button disabled={busy} className="settings-button settings-button-primary">{busy?'Saving…':editing?'Save profile':'Create profile'}</button>{editing&&<button type="button" className="min-h-[40px] px-3 text-sm settings-secondary" onClick={()=>{setEditing(null);setName('');setAvatar('user');}}>Cancel</button>}</div></form>
  </section>;
}
