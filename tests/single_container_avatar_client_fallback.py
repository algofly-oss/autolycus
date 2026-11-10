"""Real-file player metadata/startup audit in the isolated, read-only LAN setup."""
import json,time
from pathlib import Path
from urllib.parse import urlencode
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
f=json.loads(Path('/data/cinema-fixture.json').read_text());layout=json.loads(Path('/data/avatar-lan-layout.json').read_text())
o=webdriver.ChromeOptions()
for flag in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--ignore-certificate-errors','--no-proxy-server','--host-resolver-rules=MAP autolycus.algofly.ai 127.0.0.1','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000']:o.add_argument(flag)
o.set_capability('goog:loggingPrefs',{'browser':'ALL'})
with webdriver.Chrome(options=o) as b:
 w=WebDriverWait(b,60);base='https://autolycus.algofly.ai'
 b.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',{'source':'window.__pcs=[];window.RTCPeerConnection=new Proxy(window.RTCPeerConnection,{construct(T,args){const p=new T(...args);window.__pcs.push(p);return p;}});'})
 b.get(base+'/');w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys(f['username']);b.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys(f['password']);b.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click();w.until(lambda _:'/account/' not in b.current_url)
 started=time.monotonic();b.get(base+'/?'+urlencode({'video':layout['path']}))
 try:
  video=w.until(EC.presence_of_element_located((By.CSS_SELECTOR,'.movie-player video')))
  ActionChains(b).move_to_element(video).perform();w.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]'))).click();w.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'.media-menu-trigger-item[aria-label="Audio"]'))).click()
  w.until(lambda _:len(b.find_elements(By.CSS_SELECTOR,'[data-audio-id]'))>=2)
  metadata_seconds=round(time.monotonic()-started,2)
  result=b.execute_async_script('''const done=arguments[0];Promise.all(window.__pcs.filter(p=>p.connectionState!=="closed").map(async p=>[...(await p.getStats()).values()].filter(s=>["candidate-pair","remote-candidate"].includes(s.type)))).then(done)''')
  status=b.execute_script('const v=document.querySelector("video");return {time:v.currentTime,width:v.videoWidth,ready:v.readyState,paused:v.paused,error:v.error?.message||null,text:document.querySelector(".movie-player-error")?.innerText||null,hevcNative:MediaSource.isTypeSupported(\'video/mp4; codecs="hvc1.2.4.L153.B0"\')}')
  report={'metadata_seconds':metadata_seconds,'audio_tracks':[e.text for e in b.find_elements(By.CSS_SELECTOR,'[data-audio-id]')],'video':status,'rtc':result}
  if not status['hevcNative']:
   gear=b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]');gear.click();gear.click()
   w.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'.media-menu-trigger-item[aria-label="Playback"]'))).click()
   fallback_started=time.monotonic()
   w.until(EC.element_to_be_clickable((By.XPATH,"//*[contains(@class,'media-menu-trigger-item') and normalize-space()='Play using this device']"))).click()
   if gear.get_attribute('aria-expanded')=='true':gear.click()
   w.until(lambda _:b.execute_script('const v=document.querySelector("video");return v&&v.currentTime>1&&v.videoWidth>0&&!v.paused&&(v.getVideoPlaybackQuality?.().totalVideoFrames||v.webkitDecodedFrameCount||0)>1'))
   report['client_fallback']=b.execute_script('const v=document.querySelector("video");return {time:v.currentTime,width:v.videoWidth,height:v.videoHeight,audio:v.webkitAudioDecodedByteCount,decoded_frames:v.getVideoPlaybackQuality?.().totalVideoFrames||v.webkitDecodedFrameCount||0}')
   report['fallback_first_frame_seconds']=round(time.monotonic()-fallback_started,2)
   assert report['client_fallback']['audio']>0
   assert not b.find_elements(By.CSS_SELECTOR,'.movie-player-error')
   print('CLIENT FALLBACK',json.dumps(report['client_fallback']),flush=True)
  Path('/data/avatar-player-result.json').write_text(json.dumps(report,indent=2));b.save_screenshot('/data/avatar-player-audio.png')
  assert any(s.get('bytesReceived',0)>15_000_000 for group in result for s in group if s.get('type')=='candidate-pair'),report
  assert not b.find_elements(By.CSS_SELECTOR,'.movie-connection-badge')
  print('PASS: actual root-page Avatar player discovers both EAC3 tracks and receives the large index over RTC; '+json.dumps(report),flush=True)
 finally:
  buttons=b.find_elements(By.CSS_SELECTOR,'[aria-label="Close player"]')
  if buttons:buttons[0].click()
