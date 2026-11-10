"""Anonymous public custom player plus private/public download URL regression."""
import json,time
from pathlib import Path
from urllib.parse import urlencode,urlsplit,parse_qs,quote
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
fixture=json.loads(Path('/data/public-player-fixture.json').read_text());BASE='http://127.0.0.1'
options=webdriver.ChromeOptions()
for arg in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000']:options.add_argument(arg)
options.set_capability('goog:loggingPrefs',{'browser':'ALL'})
with webdriver.Chrome(options=options) as b:
    b.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',{'source':'''window.__publicRequests=[];const originalFetch=window.fetch;window.fetch=async(...args)=>{const url=String(args[0]);window.__publicRequests.push(url);const result=await originalFetch(...args);if(url.includes('/public-playback/')&&url.endsWith('/offer'))result.clone().json().then(data=>window.__publicPeer=data.id).catch(()=>{});return result;};'''})
    wait=WebDriverWait(b,45)
    def js(code,*args):return b.execute_script(code,*args)
    def playing():return js('const v=document.querySelector("video");return v&&v.currentTime>1&&!v.paused&&v.videoWidth>0&&v.webkitAudioDecodedByteCount>0')
    def controls():ActionChains(b).move_to_element(b.find_element(By.CSS_SELECTOR,'video')).perform()
    def settle():
        b.execute_async_script('const done=arguments[0];requestAnimationFrame(()=>requestAnimationFrame(()=>Promise.all([...document.querySelectorAll(".movie-player .media-menu-popup")].flatMap(p=>p.getAnimations({subtree:true})).filter(a=>a.effect?.getTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{}))).then(()=>done(true))))')
    def menu(label):
        controls();gear=b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]')
        if gear.get_attribute('aria-expanded')=='true':gear.click()
        gear.click();wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,f'.media-menu-trigger-item[aria-label="{label}"]'))).click();settle()
    def close_menu():
        gear=b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]')
        if gear.get_attribute('aria-expanded')=='true':gear.click()
    try:
        first=fixture['files'][0];b.get(BASE+'/watch?'+urlencode({'key':first['key']}));wait.until(lambda _:playing())
        assert urlsplit(b.current_url).path=='/watch'
        assert b.find_element(By.CSS_SELECTOR,'.movie-player-name').text=='Shared Movie (2025)'
        assert not b.find_elements(By.CSS_SELECTOR,'.movie-player-top a[aria-label="Download video"]')
        controls();b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]').click()
        href=wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'a[aria-label="Download video"]'))).get_attribute('href')
        settle()
        download=b.find_element(By.CSS_SELECTOR,'a[aria-label="Download video"]')
        ActionChains(b).move_to_element(download).perform()
        popup=b.find_element(By.CSS_SELECTOR,'.movie-settings-popup')
        assert download.rect['y']+download.rect['height']<=popup.rect['y']+popup.rect['height']-6,(download.rect,popup.rect)
        b.save_screenshot('/data/player-download-spacing.png')
        close_menu()
        assert urlsplit(href).path==urlsplit(first['url']).path and parse_qs(urlsplit(href).query)['download']==['1']
        assert not b.find_elements(By.CSS_SELECTOR,'[aria-label="Episode list"]')
        wait.until(lambda _:b.find_element(By.CSS_SELECTOR,'[data-playback-route]').get_attribute('data-playback-route')=='direct')
        peer=js('return window.__publicPeer');assert peer
        other=fixture['files'][1]
        assert requests.post(BASE+'/api/files/public-playback/'+quote(other['key'],safe='')+'/lease',json={'id':peer}).status_code==404
        menu('Subtitles');row=next(row for row in b.find_elements(By.CSS_SELECTOR,'[data-subtitle-id]') if row.get_attribute('data-subtitle-id').startswith('public-subtitle:'));row.click();close_menu()
        wait.until(lambda _:js('return [...document.querySelector("video").textTracks].some(t=>t.mode==="showing"&&[...(t.activeCues||[])].some(c=>c.text.includes("Public subtitle fixture")))'))
        before=js('return document.querySelector("video").currentTime');menu('Audio');rows=b.find_elements(By.CSS_SELECTOR,'[data-audio-id]');rows[1].click();close_menu();wait.until(lambda _:playing() and js('return document.querySelector("video").currentTime')>=before)
        assert not any('/api/auth/' in url or '/api/files/browse' in url or '/api/files/search' in url or '/api/files/playback/' in url or 'opensubtitles' in url for url in js('return window.__publicRequests'))
        assert not any(row.is_displayed() for row in b.find_elements(By.CSS_SELECTOR,'.media-cast-button[data-disabled],.media-cast-button[aria-disabled="true"]'))
        print('PASS: anonymous shared custom player, key-scoped real WebRTC bytes, public download button, sidecar subtitles, audio switching and no private-account requests',flush=True)
        js('const v=document.querySelector("video");v.currentTime=25;v.pause()');wait.until(lambda _:'t=25' in b.current_url)
        b.refresh();wait.until(lambda _:playing() and js('return document.querySelector("video").currentTime>=25'))
        b.set_window_size(390,844);assert js('return document.documentElement.scrollWidth<=innerWidth')
        b.save_screenshot('/data/public-player-phone.png')
        controls();b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]').click();settle()
        download=wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'a[aria-label="Download video"]')))
        js('arguments[0].scrollIntoView({block:"end"})',download)
        popup=b.find_element(By.CSS_SELECTOR,'.movie-settings-popup')
        assert download.rect['y']+download.rect['height']<=popup.rect['y']+popup.rect['height']-6
        b.save_screenshot('/data/player-download-phone.png');close_menu()
        b.get(BASE+'/watch?'+urlencode({'key':other['key']}));wait.until(lambda _:playing());menu('Subtitles')
        row=next(row for row in b.find_elements(By.CSS_SELECTOR,'[data-subtitle-id]') if row.get_attribute('data-subtitle-id').startswith('mkv:'));row.click();close_menu()
        wait.until(lambda _:js('return [...document.querySelector("video").textTracks].some(t=>t.mode==="showing"&&t.activeCues?.length)'))
        print('PASS: public refresh/timeline resume, phone layout, opaque shared MKV key and embedded subtitles',flush=True)
        b.set_window_size(1440,1000);b.get(BASE+'/account/signin')
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys(fixture['username'])
        b.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys(fixture['password']);b.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click();wait.until(lambda driver: driver.execute_script("return location.pathname==='/' || location.pathname==='/home'"))
        b.get(BASE+'/home?'+urlencode({'path':first['path'].rsplit('/',1)[0],'video':first['path']}));wait.until(lambda _:playing())
        assert not b.find_elements(By.CSS_SELECTOR,'.movie-player-top a[aria-label="Download video"]')
        controls();b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]').click()
        href=wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'a[aria-label="Download video"]'))).get_attribute('href')
        close_menu()
        assert urlsplit(href).path=='/api/files/stream' and parse_qs(urlsplit(href).query)['download']==['1'] and '/public/' not in href
        s=requests.Session();s.post(BASE+'/api/auth/signin',json={'username':fixture['username'],'password':fixture['password']}).raise_for_status()
        r=s.get(href,stream=True);assert r.status_code==200 and 'attachment' in r.headers.get('Content-Disposition','');r.close()
        menu('Quality');ActionChains(b).move_to_element(b.find_element(By.CSS_SELECTOR,'video')).click().perform()
        wait.until(lambda _:b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]').get_attribute('aria-expanded')=='false')
        time.sleep(.45)
        assert not js('return document.querySelector("video").paused')
        print('PASS: signed-in player uses only authenticated private download URL; menu dismissal preserves playback',flush=True)
        controls();wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'.movie-player-close'))).click()
        target=wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'[aria-label^="Drive "]')))
        ActionChains(b).move_to_element(target).perform()
        progress=wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'[role="tooltip"] [role="progressbar"]')))
        status=s.get(BASE+'/api/files/status').json();expected=round(status['drive_used']/status['drive_total']*100,1)
        assert abs(float(progress.get_attribute('aria-valuenow'))-expected)<=.1
        assert f'{expected:.1f}%' in b.find_element(By.CSS_SELECTOR,'[role="tooltip"]').text
        assert b.find_element(By.CSS_SELECTOR,'[role="tooltip"]').rect['width']<240
        assert b.find_element(By.CSS_SELECTOR,'[role="tooltip"]').rect['height']<=160
        assert status['used']==status['drive_used'] and status['total']==status['drive_total'] and 'app_used' in status
        assert 'Capacity' not in b.find_element(By.CSS_SELECTOR,'[role="tooltip"]').text
        b.save_screenshot('/data/storage-hover-drive.png')
        print('PASS: compact storage tooltip shows real overall drive percentage and matching progress bar',flush=True)
        downloads=Path('/data/watch-link-download');downloads.mkdir(exist_ok=True)
        for old in downloads.iterdir():old.unlink()
        b.execute_cdp_cmd('Page.setDownloadBehavior',{'behavior':'allow','downloadPath':str(downloads)})
        b.get(BASE+'/watch?'+urlencode({'key':first['key'],'download':'true','player':'1'}))
        wait.until(lambda _:any(path.suffix=='.mp4' for path in downloads.iterdir()))
        downloaded=next(path for path in downloads.iterdir() if path.suffix=='.mp4')
        assert downloaded.read_bytes()==Path('/downloads',first['path']).read_bytes()
        print('PASS: direct /watch share URL and download=true precedence download the exact file',flush=True)
    except Exception:
        b.save_screenshot('/data/public-player-failure.png');print('URL',b.current_url,flush=True);print('STATUS',js('const v=document.querySelector("video");return v?{time:v.currentTime,paused:v.paused,width:v.videoWidth,text:document.body.innerText.slice(-1200)}:document.body.innerText.slice(-1200)'),flush=True);print('ERRORS',b.get_log('browser')[-8:],flush=True);raise
