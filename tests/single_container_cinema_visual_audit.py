"""Current Cinema geometry, ownership marks, title details, trailers and profiles."""
import json,time
from urllib.parse import urlsplit,parse_qs
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
f=json.loads(Path('/data/cinema-fixture.json').read_text());o=webdriver.ChromeOptions()
for flag in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--window-size=1440,1000']:o.add_argument(flag)
o.set_capability('goog:loggingPrefs',{'browser':'ALL'})
with webdriver.Chrome(options=o) as b:
 w=WebDriverWait(b,40)
 b.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',{'source':'''window.__heroHeights=[];let remaining=900;const sample=()=>{const h=document.querySelector('.cinema-hero');if(h)window.__heroHeights.push(h.getBoundingClientRect().height);if(remaining-->0)requestAnimationFrame(sample);};requestAnimationFrame(sample);'''})
 b.get('http://127.0.0.1/');w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys(f['username']);b.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys(f['password']);b.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click();w.until(lambda _:'/account/' not in b.current_url)
 path=f['series']['files'][0]['path'].split('/')[0]+'/source-switch/WALL-E.2008.mp4'
 status=b.execute_async_script('const done=arguments[1];fetch("/api/files/playback/progress",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path:arguments[0],position:36,duration:36,completed:true})}).then(r=>done(r.status))',path);assert status==200
 for width in [1440,390,320]:
  b.set_window_size(width,1000 if width==1440 else 844);b.get('http://127.0.0.1/')
  w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'.cinema-hero[aria-label="Featured title"]')))
  w.until(lambda _:b.execute_script('return window.__heroHeights.length>60'))
  heights=b.execute_script('return window.__heroHeights');assert max(heights)-min(heights)<1,(width,min(heights),max(heights))
  assert b.execute_script('return document.documentElement.scrollWidth<=innerWidth')
  assert not b.find_elements(By.CSS_SELECTOR,'.cinema-card .cinema-owned-badge')
  for marker in b.find_elements(By.CSS_SELECTOR,'.cinema-library-mark'):
   assert b.execute_script('const m=arguments[0],art=m.closest(".cinema-card").querySelector(".cinema-card-art");return m.getBoundingClientRect().top>=art.getBoundingClientRect().bottom-1',marker)
  w.until(lambda _:any('Because you watched WALL-E' in e.text for e in b.find_elements(By.CSS_SELECTOR,'.cinema-shelf h2')))
  next_feature=b.find_elements(By.CSS_SELECTOR,'[aria-label="Next featured title"]')
  if next_feature:
   next_feature[0].click()
   w.until(lambda _:b.execute_script('const i=document.querySelector(".cinema-hero-art img");return i&&i.complete&&i.naturalWidth>0&&i.classList.contains("is-loaded")&&Number(getComputedStyle(i).opacity)>.99'))
  b.save_screenshot(f'/data/cinema-current-{width}.png')
 # A real discovery detail has rating, synopsis, and a trailer iframe without wrapper bars.
 b.set_window_size(1440,1000);b.get('http://127.0.0.1/?title=tt0910970&kind=movie')
 w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'.cinema-detail')))
 assert len(b.find_element(By.CSS_SELECTOR,'.cinema-title-synopsis').text)>30
 trailers=b.find_elements(By.XPATH,"//button[normalize-space()='Trailer']")
 if trailers:
  trailers[0].click();frame=w.until(EC.presence_of_element_located((By.CSS_SELECTOR,'.cinema-trailer-dialog iframe')))
  assert 'youtube' in frame.get_attribute('src')
  assert not b.find_elements(By.CSS_SELECTOR,'.cinema-trailer-dialog header,.cinema-trailer-dialog footer')
  b.find_element(By.CSS_SELECTOR,'[aria-label="Close trailer"]').click()
 b.find_element(By.CSS_SELECTOR,'.cinema-search-title').click()
 w.until(lambda _:urlsplit(b.current_url).path=='/home' and parse_qs(urlsplit(b.current_url).query).get('tab')==['search'])
 handoff=parse_qs(urlsplit(b.current_url).query)['q'][0];assert '2008' in handoff and ''.join(c for c in handoff.lower() if c.isalpha())=='walle',handoff
 errors=[e for e in b.get_log('browser') if e['level']=='SEVERE' and any(s in e['message'] for s in ['TypeError','ReferenceError','Hydration failed'])];assert not errors,errors
 print('PASS: hero height remains stable while data/images load at desktop/390/320px; no horizontal overflow; ownership markers outside artwork; completed-title recommendations; rich real-title detail; minimal trailer iframe when available; title/year search handoff; no JS exceptions')
