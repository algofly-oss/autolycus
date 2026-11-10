"""Disposable-browser media UX checks, including a real throttled HTTP stream."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

NGINX=Path('/etc/nginx/conf.d/autolycus.conf')
NGINX_ORIGINAL=NGINX.read_text()
def throttle_media(enabled):
    text=NGINX_ORIGINAL
    if enabled:
        text='map $arg_path $media_test_rate { default 0; ~browser-fixture 48k; }\n'+text
        text=text.replace('    location /api {', '    location = /api/files/stream { limit_rate $media_test_rate; proxy_buffering on; proxy_set_header Host $http_host; proxy_pass http://api; }\n    location /api {')
    NGINX.write_text(text)
    subprocess.run(['nginx','-t'],check=True,capture_output=True)
    subprocess.run(['nginx','-s','reload'],check=True,capture_output=True)

BASE='http://127.0.0.1';USER='enhanced-browser@example.test';PASSWORD='Enhanced-browser-123!'
s=requests.Session()
for action in ('signup','signin'):
    r=s.post(BASE+'/api/auth/'+action,json={'name':'Browser fixture','username':USER,'password':PASSWORD});r.raise_for_status()
uid=subprocess.check_output(['python','-c',f'''import json,datetime
from pathlib import Path
from pymongo import MongoClient
h=json.loads(Path('/run/autolycus/health.json').read_text());c=MongoClient(h['mongo_uri']);d=c[h['database']]
u=d.users.find_one({{'username':{USER!r}}});uid=str(u['_id'])
d.user_sessions.delete_many({{'user_id':uid,'device_name':{{'$regex':'^Fixture phone'}}}})
for i in range(125):d.user_sessions.insert_one({{'_id':'fixture-browser-session-'+str(i),'user_id':uid,'device_name':'Fixture phone '+str(i),'browser':'Safari','os':'iOS','ip':'192.0.2.'+str(i),'created_at':datetime.datetime.utcnow(),'last_accessed_at':datetime.datetime.utcnow()-datetime.timedelta(minutes=i),'expires_at':datetime.datetime.utcnow()+datetime.timedelta(days=2),'revoked_at':None}})
print(uid)
'''],text=True).strip()
root=Path('/downloads')/uid/'browser-fixture'/'Show'/'Season 1';root.mkdir(parents=True,exist_ok=True)
names=['Show.S01E01.Pilot.1080p.mp4','Show.1x02.Second.mp4','Episode 03 - Finale.mp4']
base=Path('/downloads/playback-fixtures/tracks.mp4');assert base.exists()
source=root/names[0]
subprocess.run(['ffmpeg','-v','error','-y','-stream_loop','4','-i',str(base),'-t','180','-map','0','-c','copy','-movflags','+faststart',str(source)],check=True)
for name in names[1:]:shutil.copyfile(source,root/name)
low=source.with_name(source.stem+'_144p.mp4')
subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-vf','scale=256:144','-c:v','libx264','-threads','2','-preset','ultrafast','-crf','32','-c:a','aac','-b:a','64k','-movflags','+faststart',str(low)],check=True)
shutil.copyfile(low,root/(Path(names[2]).stem+'_144p.mp4'))
s.patch(BASE+'/api/auth/preferences',json={'video_quality':'auto'}).raise_for_status()
options=webdriver.ChromeOptions()
for arg in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000']:options.add_argument(arg)
options.set_capability('goog:loggingPrefs',{'browser':'ALL'})
with webdriver.Chrome(options=options) as b:
    b.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',{'source':'window.RTCPeerConnection=function(){throw new Error("HTTP fixture")};'})
    wait=WebDriverWait(b,45)
    def js(code,*args):return b.execute_script(code,*args)
    def video():return b.find_element(By.CSS_SELECTOR,'video')
    def ready():return js('const v=document.querySelector("video");return v&&v.videoWidth>0&&v.readyState>=2')
    def controls():ActionChains(b).move_to_element(video()).perform()
    def close_menu():
        gear=b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]')
        if gear.get_attribute('aria-expanded')=='true':gear.click()
    def settings(label):
        controls();close_menu();b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]').click()
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,f'.movie-player .media-menu-trigger-item[aria-label="{label}"]'))).click()
    def quality(value):
        settings('Quality');row=wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,f'[data-quality="{value}"]')));row.click();close_menu()
    def current_name():return b.find_element(By.CSS_SELECTOR,'.movie-player-name').get_attribute('title')
    def open_file(name):
        row=wait.until(EC.presence_of_element_located((By.XPATH,f"//div[contains(@class,'truncate') and text()='{name}']")));js('arguments[0].scrollIntoView({block:"center"})',row);row.click();wait.until(lambda _:ready())
    def close_player():
        controls();wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'.movie-player-close'))).click();wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR,'video')))
    try:
        b.get(BASE+'/account/signin')
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys(USER)
        b.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys(PASSWORD)
        b.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click()
        wait.until(lambda _: '/home' in b.current_url)
        b.get(BASE+'/home?path='+str(root.relative_to('/downloads')))
        open_file(names[0])
        wait.until(lambda _:'Show · S01 E01 · Pilot'==b.find_element(By.CSS_SELECTOR,'.movie-player-name').text)
        assert 'video=' in b.current_url
        js('const v=document.querySelector("video");v.pause();v.currentTime=1;document.querySelector(".movie-player").focus()')
        for repeat in [False,True,True]:
            b.execute_cdp_cmd('Input.dispatchKeyEvent',{'type':'keyDown','key':'ArrowRight','code':'ArrowRight','windowsVirtualKeyCode':39,'autoRepeat':repeat})
        b.execute_cdp_cmd('Input.dispatchKeyEvent',{'type':'keyUp','key':'ArrowRight','code':'ArrowRight','windowsVirtualKeyCode':39})
        wait.until(lambda _:js('return Math.abs(document.querySelector("video").currentTime-31)<.5'))
        assert b.find_element(By.CSS_SELECTOR,'.movie-gesture-hud').text=='+30s'
        b.execute_cdp_cmd('Input.dispatchKeyEvent',{'type':'keyDown','key':'ArrowLeft','code':'ArrowLeft','windowsVirtualKeyCode':37})
        b.execute_cdp_cmd('Input.dispatchKeyEvent',{'type':'keyUp','key':'ArrowLeft','code':'ArrowLeft','windowsVirtualKeyCode':37})
        assert b.find_element(By.CSS_SELECTOR,'.movie-gesture-hud').text=='−10s'
        settings('Episodes')
        entries=wait.until(lambda _:b.find_elements(By.CSS_SELECTOR,'[data-episode-path]'))
        assert len(entries)==3,[(r.text,r.get_attribute('data-episode-path')) for r in entries]
        assert [r.text for r in entries]==['Show · S01 E01 · Pilot','Show · S01 E02 · Second','Show · S01 E03 · Finale']
        close_menu()
        controls();b.find_element(By.CSS_SELECTOR,'[aria-label="Episode list"]').click()
        quick=wait.until(lambda _:(rows if rows and rows[0].text else False) if (rows:=b.find_elements(By.CSS_SELECTOR,'[data-quick-episode-path]')) else False)
        assert len(quick)==3 and 'S01 E01' in quick[0].text
        wait.until(EC.element_to_be_clickable(quick[1])).click();wait.until(lambda _:current_name()==names[1] and ready())
        controls();b.find_element(By.CSS_SELECTOR,'[aria-label="Episode list"]').click()
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'[data-quick-episode-path]'))).click()
        wait.until(lambda _:current_name()==names[0] and ready())
        print('PASS: direct control-bar episode list switches parsed episodes without opening Settings',flush=True)
        settings('Quality')
        assert len(b.find_elements(By.CSS_SELECTOR,'[data-quality]'))==10
        assert b.find_element(By.CSS_SELECTOR,'[data-quality="2160p"]').get_attribute('aria-disabled')=='true'
        assert b.find_element(By.CSS_SELECTOR,'[data-quality="720p"]').get_attribute('aria-disabled')=='true'
        close_menu()
        js('document.querySelector("video").currentTime=14')
        quality('144p');wait.until(lambda _:ready() and js('return document.querySelector("video").videoHeight===144'))
        assert abs(js('return document.querySelector("video").currentTime')-14)<3
        controls();b.find_element(By.CSS_SELECTOR,'[aria-label="Next episode"]').click()
        wait.until(lambda _:current_name()==names[1] and ready())
        assert js('return document.querySelector("video").videoHeight')==180
        settings('Quality')
        assert b.find_element(By.CSS_SELECTOR,'[data-quality="144p"]').get_attribute('aria-checked')=='true'
        assert b.find_element(By.CSS_SELECTOR,'[data-quality="144p"]').get_attribute('aria-disabled')=='true'
        close_menu();controls();b.find_element(By.CSS_SELECTOR,'[aria-label="Next episode"]').click()
        wait.until(lambda _:current_name()==names[2] and ready() and js('return document.querySelector("video").videoHeight===144'))
        js('const v=document.querySelector("video");v.currentTime=12.5;v.pause()')
        wait.until(lambda _:'t=12' in b.current_url)
        b.refresh();wait.until(lambda _:ready() and js('return document.querySelector("video").currentTime>=12'))
        assert js('return document.querySelector("video").videoHeight')==144
        close_player();wait.until(lambda _:'video=' not in b.current_url)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,'[data-file-watch-progress]')))
        open_file(names[2]);wait.until(lambda _:js('return document.querySelector("video").currentTime>=12'));close_player()
        print('PASS: parsed labels, no duplicate quality episodes, arrow/held-key accumulated seek HUD, disabled qualities, account preference fallback/return, URL refresh and resume, watch bar',flush=True)
        b.set_window_size(390,844)
        assert not b.find_elements(By.CSS_SELECTOR,'input[aria-label="Select all videos"],input[aria-label^="Select "],select[aria-label="Bulk transcode quality"]')
        assert js('return document.documentElement.scrollWidth<=innerWidth'), 'File list overflows phone'
        b.save_screenshot('/data/media-files-phone.png')
        b.get(BASE+'/home?tab=settings')
        session_tab=wait.until(EC.element_to_be_clickable((By.XPATH,'//nav[@aria-label="Settings categories"]//button[contains(.,"Sessions")]')));session_tab.click()
        wait.until(lambda _: 'Page 1 of ' in b.find_element(By.CSS_SELECTOR,'main').text if b.find_elements(By.CSS_SELECTOR,'main') else 'Page 1 of ' in b.find_element(By.TAG_NAME,'body').text)
        assert len(b.find_elements(By.XPATH,'//button[contains(text(),"Sign out")]'))<=10
        search=b.find_element(By.CSS_SELECTOR,'input[aria-label="Search sessions"]');search.send_keys('Fixture phone 124')
        wait.until(lambda _:'Fixture phone 124' in b.find_element(By.TAG_NAME,'body').text and 'Page 1 of 1' in b.find_element(By.TAG_NAME,'body').text)
        assert js('return document.documentElement.scrollWidth<=innerWidth'), 'Settings overflow phone'
        b.save_screenshot('/data/media-settings-phone.png')
        search.clear();search.send_keys('Fixture phone')
        wait.until(lambda _:'125 sessions' in b.find_element(By.TAG_NAME,'body').text)
        next_button=next(row for row in b.find_elements(By.TAG_NAME,'button') if row.text=='Next' and row.is_displayed());js('arguments[0].scrollIntoView({block:"center"})',next_button);next_button.click()
        wait.until(lambda _:'Page 2 of 13' in b.find_element(By.TAG_NAME,'body').text)
        b.set_window_size(1440,1000);b.save_screenshot('/data/media-settings-desktop.png')
        print('PASS: phone file list without selection controls, PortHub-style settings, server-paged 125-session search and paging past the old 100-session cap',flush=True)
        if os.getenv('MEDIA_CONTROLS_ONLY')=='1':raise SystemExit(0)
        # Real bandwidth-limited Auto playback, using only existing versions.
        b.get(BASE+'/home?path='+str(root.relative_to('/downloads')))
        open_file(names[0]);quality('auto')
        wait.until(lambda _:ready() and js('return document.querySelector("video").videoHeight===180'))
        close_player()
        throttle_media(True)
        open_file(names[0]);js('document.querySelector("video").play()')
        WebDriverWait(b,110).until(lambda _:ready() and js('return document.querySelector("video").videoHeight===144'))
        print('PASS: real HTTP throttling automatically steps down to an existing lower quality',flush=True)
        throttle_media(False)
        WebDriverWait(b,100).until(lambda _:ready() and js('return document.querySelector("video").videoHeight===180'))
        print('PASS: automatic quality recovers original quality when bandwidth and buffer stabilize',flush=True)
        close_player()
    except Exception:
        b.save_screenshot('/data/media-enhanced-failure.png')
        print('URL',b.current_url,flush=True)
        print('STATUS',js('const v=document.querySelector("video");return v?{time:v.currentTime,height:v.videoHeight,ready:v.readyState,error:v.error?.message,paused:v.paused,text:document.body.innerText.slice(-1600)}:document.body.innerText.slice(-1600)'),flush=True)
        print('BROWSER ERRORS',[row for row in b.get_log('browser') if row['level']=='SEVERE'][-6:],flush=True)
        raise

    finally:
        throttle_media(False)
