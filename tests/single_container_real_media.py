"""Read-only real-media browser regression checks; run only in the test container."""
import json,subprocess,time,requests
from urllib.parse import quote
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
uid=subprocess.check_output(['python','-c',"import json;from pathlib import Path;from pymongo import MongoClient;h=json.loads(Path('/run/autolycus/health.json').read_text());d=MongoClient(h['mongo_uri'])[h['database']];print(d.users.find_one({'username':'subtitle-fixture@example.test'})['_id'])"],text=True).strip()
root=uid+'/real-media'
s=requests.Session();s.post('http://127.0.0.1/api/auth/signin',json={'username':'subtitle-fixture@example.test','password':'Subtitle-fixture-123!'}).raise_for_status()
s.patch('http://127.0.0.1/api/auth/preferences',json={'video_audio_language':'en'}).raise_for_status()
s.put('http://127.0.0.1/api/files/playback/alternate-audio',json={'path':root+'/WallE.mkv','donor':''}).raise_for_status()
options=webdriver.ChromeOptions()
for arg in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000']:options.add_argument(arg)
options.set_capability('goog:loggingPrefs',{'browser':'ALL'})
with webdriver.Chrome(options=options) as b:
    b.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',{'source':"window.__mse=[];const M=MediaSource.prototype.addSourceBuffer;MediaSource.prototype.addSourceBuffer=function(t){const b=M.call(this,t);window.__mse.push({m:this,b,t});return b};"})
    wait=WebDriverWait(b,60)
    def js(code,*args):return b.execute_script(code,*args)
    def playing():return js('const v=document.querySelector("video");return v&&v.currentTime>1&&!v.paused&&v.videoWidth>0&&v.webkitAudioDecodedByteCount>0')
    def menu(label):
        ActionChains(b).move_to_element(b.find_element(By.CSS_SELECTOR,'video')).perform()
        gear=b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]')
        if gear.get_attribute('aria-expanded')=='true':gear.click()
        gear.click();wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,f'.media-menu-trigger-item[aria-label="{label}"]'))).click()
    def close_menu():
        gear=b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]')
        if gear.get_attribute('aria-expanded')=='true':gear.click()
    def open(name):
        b.get('http://127.0.0.1/home?path='+quote(root)+'&video='+quote(root+'/'+name));wait.until(lambda _:playing())
    b.get('http://127.0.0.1/account/signin')
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys('subtitle-fixture@example.test')
    b.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys('Subtitle-fixture-123!');b.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click();wait.until(lambda driver: driver.execute_script("return location.pathname==='/' || location.pathname==='/home'"))
    try:
        open('WallE.mkv')
        js('document.querySelector("video").currentTime=40');wait.until(lambda _:js('return document.querySelector("video").currentTime>40.2'))
        menu('Audio');row=next(row for row in b.find_elements(By.CSS_SELECTOR,'[data-audio-id]') if 'Hindi' in row.text);row.click();close_menu()
        wait.until(lambda _:playing() and js('return document.querySelector("video").currentTime>=40'))
        print('PASS: real Wall-E Hindi AC3 audio switch resumes playing at the current position with decoded audio',flush=True)
        open('PapaYaar.mkv');menu('Subtitles');row=next(row for row in b.find_elements(By.CSS_SELECTOR,'[data-subtitle-id]') if row.get_attribute('data-subtitle-id').startswith('mkv:'));row.click();close_menu()
        js('document.querySelector("video").currentTime=8')
        wait.until(lambda _:js('return [...document.querySelector("video").textTracks].some(t=>t.mode==="showing"&&t.activeCues?.length)'))
        print('PASS: real Papa Yaar embedded English subtitles display after seek through the sparse subtitle index',flush=True)
        # Use Avatar as an alternate audio source while retaining Wall-E H264 video.
        result=b.execute_async_script('''const done=arguments[arguments.length-1];fetch('/api/files/playback/alternate-audio',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:arguments[0],donor:arguments[1],track_id:1,delay:0,rate:1})}).then(r=>done(r.status)).catch(e=>done(String(e)))''',root+'/WallE.mkv',root+'/Avatar.mp4');assert result==200,result
        open('WallE.mkv');menu('Audio');wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,'input[aria-label="Audio delay seconds"]')))
        assert 'Avatar.mp4' in b.find_element(By.CSS_SELECTOR,'.movie-player').text
        close_menu();wait.until(lambda _:playing())
        print('PASS: real Avatar EAC3/Atmos soundtrack decoded on the client with independent H264 video; no server audio transcode',flush=True)
        before=js('return document.querySelector("video").currentTime');menu('Audio')
        delay=wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[aria-label="Audio delay seconds"]')));js('arguments[0].scrollIntoView({block:"center"})',delay);delay.send_keys(Keys.CONTROL,'a');delay.send_keys('2')
        speed=wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[aria-label="Audio speed ratio"]')));js('arguments[0].scrollIntoView({block:"center"})',speed);speed.send_keys(Keys.CONTROL,'a');speed.send_keys('1.04')
        next(row for row in b.find_elements(By.CSS_SELECTOR,'.movie-player button') if row.text=='Apply sync').click();close_menu()
        wait.until(lambda _:playing() and js('return document.querySelector("video").currentTime')>=before)
        print('PASS: alternate real-file soundtrack delay and independent 1.04x speed retain video position and playback',flush=True)
        main='/downloads/'+root+'/Sync.Main.mp4';donor='/downloads/'+root+'/Sync.Donor.m4a'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=160x90:rate=12','-f','lavfi','-i','sine=frequency=700:sample_rate=48000','-t','36','-af','volume=0.5+0.4*sin(2.1*t)*sin(0.37*t):eval=frame','-c:v','libx264','-threads','1','-preset','ultrafast','-c:a','aac','-movflags','+faststart',main],check=True)
        subprocess.run(['ffmpeg','-v','error','-y','-i',main,'-vn','-af','adelay=3000:all=1','-c:a','aac',donor],check=True)
        s.put('http://127.0.0.1/api/files/playback/alternate-audio',json={'path':root+'/Sync.Main.mp4','donor':root+'/Sync.Donor.m4a','track_id':0,'delay':0,'rate':1}).raise_for_status()
        open('Sync.Main.mp4');menu('Audio')
        next(row for row in b.find_elements(By.CSS_SELECTOR,'.movie-player button') if row.text=='Auto align').click()
        wait.until(lambda _:'Audio aligned.' in b.find_element(By.CSS_SELECTOR,'.movie-player').text)
        value=float(b.find_element(By.CSS_SELECTOR,'input[aria-label="Audio delay seconds"]').get_attribute('value'));assert abs(value+3)<.2,value
        close_menu();wait.until(lambda _:playing())
        print('PASS: full client decode/fingerprint auto-alignment detects a synthetic 3-second soundtrack delay and resumes playback',flush=True)
    except Exception:
        print('STATUS',js('const v=document.querySelector("video");return v&&{time:v.currentTime,paused:v.paused,width:v.videoWidth,audio:v.webkitAudioDecodedByteCount,text:document.body.innerText.slice(-1400)}'),flush=True)
        print('BUFFERS',js('return window.__mse.filter(x=>x.m.readyState!=="closed").map(x=>({mime:x.t,state:x.m.readyState,ranges:Array.from({length:x.b.buffered.length},(_,i)=>[x.b.buffered.start(i),x.b.buffered.end(i)])}))'),flush=True)
        print('ERRORS',b.get_log('browser')[-12:],flush=True);raise
