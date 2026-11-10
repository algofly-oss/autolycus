"""Disposable Cinema flow: root auth, shelves, phone layout, episodes and player."""
import json,time
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
f=json.loads(Path('/data/cinema-fixture.json').read_text());base='http://127.0.0.1'
o=webdriver.ChromeOptions()
for a in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000']:o.add_argument(a)
o.set_capability('goog:loggingPrefs',{'browser':'ALL'})
with webdriver.Chrome(options=o) as b:
 w=WebDriverWait(b,40)
 def js(code,*args):return b.execute_script(code,*args)
 def playing():return js('const v=document.querySelector("video");return v&&v.currentTime>0&&!v.paused&&v.videoWidth>0')
 def controls():ActionChains(b).move_to_element(b.find_element(By.CSS_SELECTOR,'video')).perform()
 try:
  b.get(base+'/');w.until(EC.url_contains('/account/signin'))
  w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys(f['username'])
  b.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys(f['password']);b.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click()
  w.until(lambda _:urlsplit(b.current_url).path=='/');w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'.cinema-hero')))
  assert not b.find_elements(By.CSS_SELECTOR,'input[placeholder="Magnet Link or Download URL"]')
  assert b.find_element(By.CSS_SELECTOR,'.cinema-manage').get_attribute('href')==base+'/home'
  b.save_screenshot('/data/cinema-desktop.png')
  assert b.title=='Autolycus'
  assert b.find_element(By.CSS_SELECTOR,'.cinema-brand').text=='Autolycus'
  b.find_element(By.CSS_SELECTOR,'[aria-label="Search movies and series"]').click()
  search=b.find_element(By.CSS_SELECTOR,'[aria-label="Search your library"]');search.send_keys('Night Journey')
  w.until(lambda _:len(b.find_elements(By.CSS_SELECTOR,'.cinema-search-view [aria-label="Play Night Journey"]'))==1);assert 'Night Journey' in b.find_element(By.CSS_SELECTOR,'.cinema-search-view [aria-label="Play Night Journey"]').text
  b.find_element(By.CSS_SELECTOR,'[aria-label="Clear library search"]').click();b.find_element(By.CSS_SELECTOR,'[aria-label="Close library search"]').click()
  for width in [390,320,768]:
   b.set_window_size(width,844);assert js('return document.documentElement.scrollWidth<=innerWidth')
   assert js('return document.querySelector(".cinema-app").scrollWidth<=innerWidth'),width
   b.save_screenshot(f'/data/cinema-{width}.png')
  b.set_window_size(390,844)
  card=w.until(EC.presence_of_element_located((By.CSS_SELECTOR,'.cinema-card-info[aria-label="Info about Orbit"]')));js('arguments[0].scrollIntoView({block:"center",inline:"center"});arguments[0].focus()',card);card.click()
  w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'.cinema-detail')))
  episodes=b.find_elements(By.CSS_SELECTOR,'.cinema-episodes>button');assert len(episodes)==3
  assert ['E01' in episodes[0].text,'E02' in episodes[1].text,'E10' in episodes[2].text]==[True]*3
  b.save_screenshot('/data/cinema-episodes-phone.png');episodes[1].click();w.until(lambda _:playing())
  assert f['series']['files'][1]['path']==parse_qs(urlsplit(b.current_url).query)['video'][0]
  controls();w.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'[aria-label="Episode list"]'))).click()
  rows=w.until(lambda _:b.find_elements(By.CSS_SELECTOR,'[data-quick-episode-path]'));assert len(rows)==3
  rows[2].click();w.until(lambda _:playing() and parse_qs(urlsplit(b.current_url).query)['video'][0]==f['series']['files'][2]['path'])
  assert not b.find_elements(By.CSS_SELECTOR,'.movie-connection-badge')
  assert 'Local network' not in b.find_element(By.CSS_SELECTOR,'.movie-player-top').text
  controls();b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]').click()
  w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'[aria-label="Player settings"]')))
  assert not b.find_elements(By.CSS_SELECTOR,'a[aria-label="Download video"]')
  b.find_element(By.CSS_SELECTOR,'[aria-label="Quality"].media-menu-trigger-item').click()
  quality=w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'.media-menu-content[aria-label="Quality"]')))
  assert 'Auto · Original' not in quality.text
  group=b.find_element(By.CSS_SELECTOR,'[data-quality="auto"]').find_element(By.XPATH,'..')
  assert js('return getComputedStyle(arguments[0]).maxHeight',group)=='none'
  row=b.find_element(By.CSS_SELECTOR,'[data-quality="720p"]');js('arguments[0].scrollIntoView({block:"center"})',row)
  b.save_screenshot('/data/player-quality-720p.png')
  b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]').click()
  captions=b.find_elements(By.CSS_SELECTOR,'[aria-label="Turn subtitles on"]')
  if captions:captions[0].click()
  w.until(lambda _:js('return [...document.querySelector("video").textTracks].some(t=>t.mode==="showing"&&t.activeCues?.length)'))
  b.save_screenshot('/data/player-captions-phone.png')
  js('const v=document.querySelector("video");v.currentTime=10;v.pause()');w.until(lambda _:'t=10' in b.current_url)
  b.refresh();w.until(lambda _:playing() and js('return document.querySelector("video").currentTime>=10'))
  controls();b.find_element(By.CSS_SELECTOR,'[aria-label="Close player"]').click();w.until(lambda _:'video=' not in b.current_url)
  b.get(base+'/home');link=w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'a[aria-label="Autolycus home"]')));assert link.get_attribute('href')==base+'/'
  link.click();w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'.cinema-hero')))
  errors=[e for e in b.get_log('browser') if e['level']=='SEVERE' and ('TypeError' in e['message'] or 'ReferenceError' in e['message'] or 'Hydration failed' in e['message'])];assert not errors,errors
  print('PASS: anonymous root redirects to login, post-login root Cinema, local-title search, shelves, 320/390/768px layouts, parsed episode detail, private player without downloads, episode switching, URL refresh/resume and Home logo→root link',flush=True)
 except:
  b.save_screenshot('/data/cinema-failure.png');print('URL',b.current_url,flush=True);print('TEXT',b.find_element(By.TAG_NAME,'body').text[-1400:],flush=True);print('ERRORS',b.get_log('browser')[-6:],flush=True);raise
