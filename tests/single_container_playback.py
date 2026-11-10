"""Run only inside a disposable smoke container. Uses generated media, no real files."""
import hashlib
import json
import subprocess
import shutil
import time
from pathlib import Path

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

ROOT = Path('/downloads/playback-fixtures')
ROOT.mkdir(exist_ok=True)
BASE = 'http://127.0.0.1'
PASSWORD = 'Playback-fixture-123!'
USERNAME = 'playback-fixture@example.test'
session = requests.Session()
for action in ('signup', 'signin'):
    response = session.post(BASE+'/api/auth/'+action, json={'name':'Playback fixture','username':USERNAME,'password':PASSWORD})
    response.raise_for_status()
session.patch(BASE+'/api/auth/preferences',json={'video_audio_language':'en','video_subtitles':{'enabled':False,'language':'en','auto_match':True}}).raise_for_status()

subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=24','-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
    '-f','lavfi','-i','sine=frequency=880:sample_rate=48000','-t','36','-map','0:v','-map','1:a','-map','2:a','-c:v','libx264','-threads','1','-preset','ultrafast','-g','48',
    '-c:a','aac','-metadata:s:a:0','language=eng','-metadata:s:a:1','language=hin','-movflags','+faststart',str(ROOT/'tracks.mp4')],check=True)
for filename,codec,extra in [('dolby.mkv','ac3',[]),('dts.mkv','dca',['-strict','-2'])]:
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(ROOT/'tracks.mp4'),'-map','0:v','-map','0:a','-c:v','copy','-c:a',codec,*extra,str(ROOT/filename)],check=True)
(ROOT/'tracks.en.srt').write_text('1\n00:00:00,000 --> 00:00:35,000\nPlayback subtitle fixture\n')
subprocess.run(['ffmpeg','-v','error','-y','-i',str(ROOT/'tracks.mp4'),'-t','8','-vf','crop=320:136','-c:v','libx264','-threads','1','-preset','ultrafast','-c:a','copy',str(ROOT/'wide.mp4')],check=True)
(ROOT/'embedded.en.srt').write_text(''.join(f'{i+1}\n00:00:{i*2:02d},000 --> 00:00:{i*2+2:02d},000\nEmbedded English {i}\n\n' for i in range(18)))
(ROOT/'embedded.hi.srt').write_text(''.join(f'{i+1}\n00:00:{i*2:02d},000 --> 00:00:{i*2+2:02d},000\nहिंदी परीक्षण {i}\n\n' for i in range(18)))
subprocess.run(['ffmpeg','-v','error','-y','-i',str(ROOT/'tracks.mp4'),'-i',str(ROOT/'embedded.en.srt'),'-i',str(ROOT/'embedded.hi.srt'),
    '-map','0','-map','1','-map','2','-c','copy','-c:s','srt','-metadata:s:s:0','language=eng','-metadata:s:s:1','language=hin',str(ROOT/'embedded.mkv')],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(ROOT/'tracks.mp4'),'-t','8','-map','0:v','-map','0:a:0','-c:v','libx265','-threads','1','-preset','ultrafast',
    '-x265-params','pools=1:frame-threads=1:log-level=error','-pix_fmt','yuv420p10le','-c:a','ac3',str(ROOT/'hevc.mkv')],check=True)

episodes = ROOT/'Season 2'
episodes.mkdir(exist_ok=True)
for episode in ['Episode 10.mp4', 'Episode 2.mp4', 'Episode 1.mp4']:
    shutil.copyfile(ROOT/'tracks.mp4', episodes/episode)

url = BASE+'/api/files/stream?path=playback-fixtures/tracks.mp4'
original = (ROOT/'tracks.mp4').read_bytes()
for header,expected in [('bytes=0-2',original[:3]),('bytes=-32',original[-32:]),('bytes=4096-8191',original[4096:8192])]:
    response = session.get(url,headers={'Range':header})
    assert response.status_code == 206 and response.content == expected, header
for header in ['bytes=7-2','bytes=0-1,4-5','bytes=-0','bytes=999999999999-']:
    assert session.get(url,headers={'Range':header}).status_code == 416, header
assert requests.get(BASE+'/api/files/playback/info?path=playback-fixtures/tracks.mp4').status_code >= 400
assert session.get(BASE+'/api/files/playback/info',params={'path':'../etc/passwd'}).status_code == 403
assert session.post(BASE+'/api/files/playback/offer',headers={'Origin':'https://foreign.invalid'},json={'path':'playback-fixtures/tracks.mp4','sdp':'invalid'}).status_code == 403
assert session.post(BASE+'/api/files/playback/lease',json={'id':'0'*64}).status_code == 404
names = session.get(BASE+'/api/files/browse',params={'path':'playback-fixtures','names_only':'true'})
names.raise_for_status()
assert all(row['size'] is None and row['public_url_key'] is None for row in names.json())
assert any(row['name']=='Season 2' and row['is_directory'] for row in names.json())
print('PASS: lightweight authenticated episode listing without folder sizing or public links',flush=True)
print('PASS: authenticated byte ranges, suffixes, invalid ranges, confinement and cross-origin controls',flush=True)

options=webdriver.ChromeOptions()
for arg in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000']:
    options.add_argument(arg)
options.set_capability('goog:loggingPrefs',{'browser':'ALL'})
with webdriver.Chrome(options=options) as browser:
    browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',{'source':'''window.__peers=[];const OriginalPC=window.RTCPeerConnection;window.RTCPeerConnection=class extends OriginalPC {constructor(...args){super(...args);window.__peers.push(this)}};
      const originalMse=MediaSource.isTypeSupported.bind(MediaSource);MediaSource.isTypeSupported=c=>/hev1|hvc1/.test(c)?false:originalMse(c);
      if(window.VideoDecoder){const originalVd=VideoDecoder.isConfigSupported.bind(VideoDecoder);VideoDecoder.isConfigSupported=c=>/hev1|hvc1/.test(c.codec)?Promise.resolve({supported:false,config:c}):originalVd(c);}
    '''})
    browser.get(BASE+'/account/signin')
    wait=WebDriverWait(browser,30)
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys(USERNAME)
    browser.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys(PASSWORD)
    browser.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click()
    wait.until(lambda driver: driver.execute_script("return location.pathname==='/' || location.pathname==='/home'"))
    browser.get(BASE+'/home?path=playback-fixtures')
    browser.execute_async_script('const done=arguments[0];navigator.serviceWorker.ready.then(()=>done(true));')
    browser.refresh()
    def open_movie(name):
        item=wait.until(EC.element_to_be_clickable((By.XPATH,f"//*[text()='{name}']")))
        browser.execute_script('arguments[0].scrollIntoView({block:"center"})',item)
        item.click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,'video')))
        open_movie.initial_height=browser.execute_script('const p=document.querySelector(".movie-player"),r=p.getBoundingClientRect();if(Math.abs(r.width-innerWidth)>2||Math.abs(r.height-innerHeight)>2||Math.abs(r.x)>2||Math.abs(r.y)>2)throw new Error("Player did not start at viewport size");return r.height')
    def status():
        return browser.execute_script('const v=document.querySelector("video");return v&&{time:v.currentTime,width:v.videoWidth,ready:v.readyState,error:v.error&&v.error.message,audio:v.webkitAudioDecodedByteCount,frames:v.getVideoPlaybackQuality().totalVideoFrames,text:document.body.innerText.slice(-1500)}')
    def playing():
        result=status()
        return result and result['time']>1 and result['width']>0 and result['frames']>0
    def show_controls():
        ActionChains(browser).move_to_element(browser.find_element(By.CSS_SELECTOR,'video')).perform()
    def close_settings():
        gear=browser.find_element(By.CSS_SELECTOR,'.movie-player button[aria-label="Settings"]')
        if gear.get_attribute('aria-expanded')=='true': gear.click()
    def settings(page):
        show_controls()
        close_settings()
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'.movie-player button[aria-label="Settings"]'))).click()
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,f'.movie-player .media-menu-trigger-item[aria-label="{page}"]'))).click()
    def choose_audio(index):
        settings('Audio')
        rows=browser.find_elements(By.CSS_SELECTOR,'[data-audio-id]')
        wait.until(EC.element_to_be_clickable(rows[index])).click()
        close_settings()
    def settle_menu():
        browser.execute_async_script('const done=arguments[0];requestAnimationFrame(()=>requestAnimationFrame(()=>{const p=document.querySelector(".media-menu-popup");Promise.all((p?.getAnimations({subtree:true})||[]).filter(a=>a.effect?.getTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{}))).then(()=>requestAnimationFrame(()=>done(true)));}))')
    def subtitle_options():
        settings('Subtitles')
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'[data-subtitle-id]')))
        rows=[(row.get_attribute('data-subtitle-id'),row.text) for row in browser.find_elements(By.CSS_SELECTOR,'[data-subtitle-id]')]
        close_settings()
        return rows
    def choose_subtitle(value):
        settings('Subtitles')
        row=next(row for row in browser.find_elements(By.CSS_SELECTOR,'[data-subtitle-id]') if row.get_attribute('data-subtitle-id')==value)
        browser.execute_script('arguments[0].scrollIntoView({block:"center"})',row)
        wait.until(EC.element_to_be_clickable(row)).click()
        close_settings()
    def route():
        return browser.find_element(By.CSS_SELECTOR,'[data-playback-route]').get_attribute('data-playback-route')
    def close_movie():
        show_controls()
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'.movie-player-close'))).click()
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR,'video')))
    try:
        if not __import__("os").environ.get("PLAYBACK_CONTROLS_ONLY"):
            open_movie('tracks.mp4')
            wait.until(lambda _:playing())
            wait.until(lambda _:route()=='direct')
            assert not browser.find_elements(By.CSS_SELECTOR,'.mantine-Modal-content select')
            assert not browser.find_elements(By.CSS_SELECTOR,'.mantine-Modal-header')
            assert len(browser.find_elements(By.CSS_SELECTOR,'.movie-player-name'))==1
            assert browser.execute_script('return Math.abs(document.querySelector(".mantine-Modal-content").getBoundingClientRect().height-document.querySelector(".movie-player").getBoundingClientRect().height)<2')
            first=status(); assert first['audio']>0,first
            digest=browser.execute_async_script('const done=arguments[0];const u=document.querySelector("video").src;fetch(u,{headers:{Range:"bytes=4096-266239"}}).then(r=>r.arrayBuffer()).then(b=>crypto.subtle.digest("SHA-256",b)).then(h=>done([...new Uint8Array(h)].map(x=>x.toString(16).padStart(2,"0")).join(""))).catch(e=>done(String(e)))')
            assert digest==hashlib.sha256(original[4096:266240]).hexdigest(),digest
            stats=browser.execute_async_script('const done=arguments[0];Promise.all(window.__peers.map(async p=>[...(await p.getStats()).values()].filter(s=>s.type==="data-channel"))).then(done)')
            assert any(s.get('bytesReceived',0)>0 for peer in stats for s in peer),stats
            print('PASS: native playback, decoded video/audio, actual WebRTC movie bytes',flush=True)
            settings('Speed')
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'[data-rate="2"]'))).click()
            close_settings()
            assert browser.execute_script('return document.querySelector("video").playbackRate')==2
            settings('Speed')
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'[data-rate="1"]'))).click()
            close_settings()
            show_controls()
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'.media-fullscreen-button'))).click()
            wait.until(lambda _:browser.execute_script('return !!document.fullscreenElement'))
            browser.execute_async_script('const done=arguments[0];document.exitFullscreen().then(()=>done(true))')
            wait.until(lambda _:not browser.execute_script('return !!document.fullscreenElement'))
            assert browser.execute_script('const p=document.querySelector(".movie-player");return Math.abs(p.getBoundingClientRect().height-arguments[0])<2&&getComputedStyle(p,"::after").borderTopWidth==="0px"&&getComputedStyle(p).borderRadius==="0px"',open_movie.initial_height)
            print('PASS: stable full-window player from startup, no frame, one title, integrated settings, speed and fullscreen',flush=True)
            show_controls();browser.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]').click()
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'a[aria-label="Download video"]')))
            assert '/api/files/stream?' in browser.find_element(By.CSS_SELECTOR,'a[aria-label="Download video"]').get_attribute('href')
            assert '/public/' not in browser.find_element(By.CSS_SELECTOR,'a[aria-label="Download video"]').get_attribute('href')
            close_settings()
            settings('Quality')
            ActionChains(browser).move_to_element(browser.find_element(By.CSS_SELECTOR,'video')).click().perform()
            wait.until(lambda _:browser.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]').get_attribute('aria-expanded')=='false')
            time.sleep(.45)
            assert not browser.execute_script('return document.querySelector("video").paused'), 'Menu dismissal paused playback'
            ActionChains(browser).move_to_element(browser.find_element(By.CSS_SELECTOR,'video')).click().perform()
            wait.until(lambda _:browser.execute_script('return document.querySelector("video").paused'))
            browser.execute_script('document.querySelector("video").play()')
            print('PASS: private player download URL and dismissing settings consumes the first click without pausing',flush=True)
            browser.execute_script('document.querySelector("video").currentTime=20')
            wait.until(lambda _:status()["time"]>20.2)
            choose_audio(1)
            wait.until(lambda _:playing() and status()["time"]>=20)
            browser.execute_script('document.querySelector("video").currentTime=25')
            wait.until(lambda _:status()['time']>25.5)
            choose_subtitle(next(value for value,label in subtitle_options() if value))
            wait.until(lambda _:browser.execute_script('const v=document.querySelector("video");return [...v.textTracks].some(t=>t.mode==="showing"&&t.activeCues?.length)'))
            choose_subtitle('')
            wait.until(lambda _:browser.execute_script('return ![...document.querySelector("video").textTracks].some(t=>t.mode==="showing")'))
            print('PASS: client audio-track switch, seek to unbuffered position, SRT subtitles on/off',flush=True)
            # Break the direct link while the same media transport remains alive.
            browser.execute_script('window.__peers.forEach(p=>p.close())')
            wait.until(lambda _:route()=='public')
            browser.execute_script('const v=document.querySelector("video");v.currentTime=5;v.play().catch(()=>{})')
            wait.until(lambda _:5.5<status()['time']<15)
            print('PASS: direct connection loss falls back to HTTP and preserves seeking',flush=True)
            close_movie()
            for filename in ['dolby.mkv','dts.mkv']:
                open_movie(filename)
                wait.until(lambda _:playing())
                assert status()['audio']>0,status()
                print('PASS: client-only '+filename+' playback with decoded audio',flush=True)
                close_movie()
            open_movie('hevc.mkv')
            wait.until(lambda _:'Open Settings' in browser.find_element(By.TAG_NAME,'body').text)
            settings('Playback')
            wait.until(EC.element_to_be_clickable((By.XPATH,"//*[@role='menuitem' and text()='Play using this device']"))).click()
            close_settings()
            WebDriverWait(browser,60).until(lambda _:playing())
            assert status()['audio']>0,status()
            assert browser.execute_script('const v=document.querySelector("video"),c=document.createElement("canvas");c.width=64;c.height=36;const x=c.getContext("2d");x.drawImage(v,0,0,64,36);const d=x.getImageData(0,0,64,36).data;let low=255,high=0;for(let i=0;i<d.length;i++)if(i%4!==3){low=Math.min(low,d[i]);high=Math.max(high,d[i]);}return high-low>30'), 'Software video produced a blank frame'
            browser.execute_script('document.querySelector("video").currentTime=5')
            wait.until(lambda _:status()['time']>5.5)
            print('PASS: optional client-only 10-bit HEVC software decoding, audio and seeking',flush=True)
            close_movie()
            open_movie('embedded.mkv')
            wait.until(lambda _:playing())
            embedded_options=[value for value,label in subtitle_options() if value.startswith('mkv:')]
            assert len(embedded_options)==2,embedded_options
            choose_subtitle(embedded_options[0])
            wait.until(lambda _:browser.execute_script('return [...document.querySelector("video").textTracks].some(t=>t.mode==="showing"&&[...(t.activeCues||[])].some(c=>c.text.includes("Embedded English")))'))
            browser.execute_script('document.querySelector("video").currentTime=25')
            wait.until(lambda _:status()['time']>25.5)
            wait.until(lambda _:browser.execute_script('return [...document.querySelector("video").textTracks].some(t=>t.mode==="showing"&&t.activeCues?.length)'))
            choose_subtitle(embedded_options[1])
            wait.until(lambda _:browser.execute_script('return [...document.querySelector("video").textTracks].some(t=>t.mode==="showing"&&[...(t.activeCues||[])].some(c=>c.text.includes("हिंदी")))'))
            choose_subtitle('')
            wait.until(lambda _:browser.execute_script('return ![...document.querySelector("video").textTracks].some(t=>t.mode==="showing")'))
            print('PASS: embedded MKV English/Hindi subtitles, seek, switch and off without server extraction',flush=True)
            close_movie()
            browser.execute_script('window.__savedPC=RTCPeerConnection;window.RTCPeerConnection=function(){throw new Error("Fixture direct unavailable")}')
            previous_reads=browser.execute_script('return performance.getEntriesByType("resource").filter(e=>e.name.includes("/api/files/stream?")).length')
            open_movie('tracks.mp4')
            wait.until(lambda _:playing())
            assert route()=='public'
            assert browser.execute_script('return performance.getEntriesByType("resource").filter(e=>e.name.includes("/api/files/stream?")).length')>previous_reads
            close_movie()
            browser.execute_script('window.RTCPeerConnection=window.__savedPC')
            print('PASS: unavailable RTC starts real HTTP byte delivery and native playback',flush=True)
            for width in [320,375,390,414,768]:
                browser.set_window_size(width,844)
                open_movie('tracks.mp4')
                wait.until(lambda _:playing())
                assert browser.execute_script('return document.documentElement.scrollWidth<=innerWidth+1'),width
                choose_audio(1)
                wait.until(lambda _:playing())
                choose_subtitle(next(value for value,label in subtitle_options() if value))
                if width==390:
                    browser.save_screenshot('/data/playback-phone.png')
                    settings('Audio')
                    settle_menu()
                    browser.save_screenshot('/data/playback-phone-menu.png')
                    close_settings()
                close_movie()
            print('PASS: player phone/tablet widths 320/375/390/414/768',flush=True)
        browser.set_window_size(390,844)
        open_movie('wide.mp4')
        wait.until(lambda _:playing())
        assert browser.execute_script('const v=document.querySelector("video"),r=v.getBoundingClientRect();return Math.abs(r.height-innerHeight)<2&&Math.abs(r.width-innerWidth)<2&&getComputedStyle(v).objectFit==="contain"'), 'Widescreen did not preserve the full-window stage'
        assert browser.execute_script('return Math.abs(document.querySelector(".movie-player").getBoundingClientRect().height-arguments[0])<2',open_movie.initial_height), 'Player resized after metadata'
        browser.save_screenshot('/data/playback-widescreen-phone.png')
        close_movie()
        print('PASS: cinematic movie retains a stable full-window stage with contained aspect ratio',flush=True)
        for scheme in ['light','dark']:
            browser.execute_script('localStorage.setItem("mantine-color-scheme",JSON.stringify(arguments[0]))',scheme)
            browser.refresh()
            open_movie('tracks.mp4')
            wait.until(lambda _:playing())
            assert browser.execute_script('return [".movie-player-dialog",".movie-player-body",".movie-player"].every(s=>{const e=document.querySelector(s),c=getComputedStyle(e);return c.backgroundColor==="rgb(0, 0, 0)"&&c.borderRadius==="0px"})'),scheme
            browser.save_screenshot('/data/playback-'+scheme+'-stage.png')
            close_movie()
        print('PASS: light/dark themes keep every stage layer black with no rounded white corners',flush=True)
        browser.set_window_size(390,844)
        open_movie('tracks.mp4')
        wait.until(lambda _: playing())
        browser.execute_script('const v=document.querySelector("video");v.pause();v.currentTime=12;v.playbackRate=1.5;v.volume=.5')
        def touch(kind,x,y):
            browser.execute_cdp_cmd('Input.dispatchTouchEvent', {'type':kind,'touchPoints':[] if kind in ['touchEnd','touchCancel'] else [{'x':x,'y':y,'id':1}]})
        width,height=browser.execute_script('return [innerWidth,innerHeight]')
        x,y=int(width*.8),int(height*.4)
        touch('touchStart',x,y)
        wait.until(lambda _:browser.execute_script('return document.querySelector("video").playbackRate===2'))
        touch('touchEnd',x,y)
        assert browser.execute_script('return document.querySelector("video").playbackRate===1.5')
        touch('touchStart',x,y);time.sleep(.45)
        before=browser.execute_script('return document.querySelector("video").currentTime')
        touch('touchMove',x-60,y)
        assert browser.execute_script('return document.querySelector(".movie-player").hasAttribute("data-gesture-scrubbing")')
        assert abs(browser.execute_script('return document.querySelector("video").currentTime')-before)<.1
        touch('touchEnd',x-60,y)
        wait.until(lambda _:abs(browser.execute_script('return document.querySelector("video").currentTime')-before)>2)
        assert browser.execute_script('return document.querySelector("video").paused&&document.querySelector("video").playbackRate===1.5')
        touch('touchStart',x,y);time.sleep(.45);touch('touchCancel',x,y)
        assert browser.execute_script('return document.querySelector("video").playbackRate===1.5')
        touch('touchStart',int(width*.2),y);touch('touchMove',int(width*.2),y-80);touch('touchEnd',int(width*.2),y-80)
        assert 'brightness' in browser.execute_script('return document.querySelector("video").style.filter')
        touch('touchStart',x,y);touch('touchMove',x,y+80);touch('touchEnd',x,y+80)
        assert browser.execute_script('return document.querySelector("video").volume<.5')
        browser.execute_script('document.querySelector("video").currentTime=12')
        for _ in range(2):
            touch('touchStart',x,y);touch('touchEnd',x,y);time.sleep(.07)
        wait.until(lambda _:browser.execute_script('return document.querySelector("video").currentTime>21'))
        for _ in range(2):
            touch('touchStart',int(width*.2),y);touch('touchEnd',int(width*.2),y);time.sleep(.07)
        wait.until(lambda _:browser.execute_script('return document.querySelector("video").currentTime<13'))
        print('PASS: real touch hold 2x, restore speed/cancel, hold-drag deferred seek, brightness, volume and double-tap both sides',flush=True)
        settings('Episodes');settle_menu()
        rows=browser.find_elements(By.CSS_SELECTOR,'[data-episode-path]')
        paths=[row.get_attribute('data-episode-path') for row in rows]
        selected=[path for path in paths if '/Season 2/' in path]
        assert [path.split('/')[-1] for path in selected]==['Episode 1.mp4','Episode 2.mp4','Episode 10.mp4'],selected
        browser.save_screenshot('/data/playback-episodes-phone.png')
        row=next(row for row in rows if row.get_attribute('data-episode-path').endswith('/Episode 1.mp4'))
        browser.execute_script('arguments[0].scrollIntoView({block:"center"})',row)
        wait.until(EC.element_to_be_clickable(row)).click();close_settings()
        wait.until(lambda _:browser.find_element(By.CSS_SELECTOR,'.movie-player-name').get_attribute('title')=='Episode 1.mp4')
        wait.until(lambda _:playing())
        show_controls();browser.find_element(By.CSS_SELECTOR,'button[aria-label="Next episode"]').click()
        wait.until(lambda _:browser.find_element(By.CSS_SELECTOR,'.movie-player-name').get_attribute('title')=='Episode 2.mp4')
        wait.until(lambda _:playing())
        settings('Episodes');settle_menu()
        toggle=browser.find_element(By.CSS_SELECTOR,'[role="menuitemcheckbox"]')
        toggle.click();close_settings()
        browser.execute_script('const v=document.querySelector("video");v.currentTime=v.duration-.3;v.play()')
        wait.until(lambda _:browser.execute_script('return document.querySelector("video").ended'))
        assert browser.find_element(By.CSS_SELECTOR,'.movie-player-name').get_attribute('title')=='Episode 2.mp4'
        settings('Episodes');settle_menu()
        assert browser.find_element(By.CSS_SELECTOR,'[role="menuitemcheckbox"]').get_attribute('aria-checked')=='false'
        close_settings()
        show_controls();browser.find_element(By.CSS_SELECTOR,'button[aria-label="Next episode"]').click()
        wait.until(lambda _:browser.find_element(By.CSS_SELECTOR,'.movie-player-name').get_attribute('title')=='Episode 10.mp4')
        wait.until(lambda _:playing())
        close_movie()
        browser.set_window_size(1440,1000)
        open_movie('tracks.mp4');wait.until(lambda _:playing())
        settings('Episodes');settle_menu()
        row=browser.find_element(By.CSS_SELECTOR,'[data-episode-path="playback-fixtures/Season 2/Episode 1.mp4"]')
        browser.execute_script('arguments[0].scrollIntoView({block:"center"})',row);wait.until(EC.element_to_be_clickable(row)).click();close_settings()
        wait.until(lambda _:browser.find_element(By.CSS_SELECTOR,'.movie-player-name').get_attribute('title')=='Episode 1.mp4');wait.until(lambda _:playing())
        browser.execute_script('const v=document.querySelector("video");v.currentTime=v.duration-.3;v.play()')
        wait.until(lambda _:browser.find_element(By.CSS_SELECTOR,'.movie-player-name').get_attribute('title')=='Episode 2.mp4');wait.until(lambda _:playing())
        show_controls();browser.find_element(By.CSS_SELECTOR,'button[aria-label="Previous episode"]').click()
        wait.until(lambda _:browser.find_element(By.CSS_SELECTOR,'.movie-player-name').get_attribute('title')=='Episode 1.mp4')
        close_movie()
        browser.execute_cdp_cmd('Emulation.setTouchEmulationEnabled', {'enabled':True,'maxTouchPoints':1})
        open_movie('tracks.mp4')
        wait.until(lambda _:browser.execute_script('return !!document.fullscreenElement'))
        close_movie()
        wait.until(lambda _:browser.execute_script('return !document.fullscreenElement'))
        browser.execute_cdp_cmd('Emulation.setTouchEmulationEnabled', {'enabled':False})
        print('PASS: mobile opening tap requests fullscreen, closing releases app-owned fullscreen',flush=True)
        print('PASS: recursive natural episode ordering, in-player selection, previous/next and automatic next episode',flush=True)
        assert not {'ffmpeg','HandBrakeCLI'}.intersection(subprocess.check_output(['ps','-eo','comm'],text=True).splitlines()), 'Playback spawned a server media converter'
        print('PASS: playback starts no server media decoding/transcoding process',flush=True)
    except Exception:
        browser.save_screenshot('/data/player-ui-failure.png')
        print('PLAYBACK STATUS',json.dumps(status()),flush=True)
        print('RTC STATUS',browser.execute_script('return window.__peers.map(p=>({state:p.connectionState,ice:p.iceConnectionState,gather:p.iceGatheringState}))'),flush=True)
        print('BROWSER ERRORS',json.dumps([entry for entry in browser.get_log('browser') if entry['level']=='SEVERE'][-12:]),flush=True)
        raise
