"""Disposable real-provider playback through the shared custom player."""
import json,time
from urllib.parse import urlsplit,parse_qs
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
f=json.loads(Path('/data/cinema-fixture.json').read_text());options=webdriver.ChromeOptions()
for a in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000']:options.add_argument(a)
options.set_capability('goog:loggingPrefs',{'browser':'ALL'})
with webdriver.Chrome(options=options) as b:
 w=WebDriverWait(b,75)
 def js(code):return b.execute_script(code)
 def playing():return js('const v=document.querySelector("video");return v&&v.currentTime>2&&!v.paused&&v.videoWidth>0')
 try:
  b.get('http://127.0.0.1/');w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys(f['username']);b.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys(f['password']);b.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click();w.until(lambda _:'/account/' not in b.current_url)
  b.get('http://127.0.0.1/?title=tt0910970&kind=movie');w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'.cinema-detail')))
  w.until(EC.element_to_be_clickable((By.XPATH,"//button[normalize-space()='Watch now']"))).click()
  w.until(lambda _:playing())
  assert not b.find_elements(By.CSS_SELECTOR,'.movie-connection-badge')
  assert not b.find_elements(By.CSS_SELECTOR,'.movie-player-error')
  js('document.querySelector("video").currentTime=40');w.until(lambda _:js('return document.querySelector("video").currentTime>=40'))
  ActionChains(b).move_to_element(b.find_element(By.CSS_SELECTOR,'video')).perform();b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]').click();w.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'[aria-label="Source"].media-menu-trigger-item'))).click()
  rows=w.until(lambda _:b.find_elements(By.CSS_SELECTOR,'[data-source-id]'));assert len(rows)>1
  previous=parse_qs(urlsplit(b.current_url).query)['source'][0]
  alternative=next(row for row in rows if row.get_attribute('data-source-id')!=previous);alternative.click();w.until(lambda _:parse_qs(urlsplit(b.current_url).query).get('source',[''])[0]!=previous and playing() and js('return document.querySelector("video").currentTime>=39'))
  checkpoint=js('return document.querySelector("video").currentTime');w.until(lambda _:js('return document.querySelector("video").currentTime')>checkpoint+1)
  w.until(lambda _:'t=4' in b.current_url)
  b.refresh();w.until(lambda _:playing() and js('return document.querySelector("video").currentTime>=39'))
  checkpoint=js('return document.querySelector("video").currentTime');w.until(lambda _:js('return document.querySelector("video").currentTime')>checkpoint+1)
  w.until(lambda _:not b.find_elements(By.CSS_SELECTOR,'[aria-label="Loading video"]'))
  b.set_window_size(390,844);assert js('return document.documentElement.scrollWidth<=innerWidth');b.save_screenshot('/data/online-player-phone.png')
  assert not b.find_elements(By.CSS_SELECTOR,'a[aria-label="Download video"]')
  for _ in range(4):
   if 'online=' not in b.current_url:break
   previous_url=b.current_url;b.back();w.until(lambda _:b.current_url!=previous_url)
  w.until(lambda _:not b.find_elements(By.CSS_SELECTOR,'.movie-player video'))
  assert not b.find_elements(By.CSS_SELECTOR,'.cinema-online-opening')
  severe=[e for e in b.get_log('browser') if e['level']=='SEVERE' and any(x in e['message'] for x in ['TypeError','ReferenceError','Hydration failed'])];assert not severe,severe
  print('WARNINGS:',[e['message'] for e in b.get_log('browser') if e['level']=='WARNING' and 'inspection' in e['message']])
  print('PASS: real source discovery, Watch now, decoded video playback, source menu switching preserving timeline/autoplay, 390px layout, custom player and no top network badge')
 except:
  b.save_screenshot('/data/online-browser-failure.png');print('URL:',b.current_url);print('TEXT:',b.find_element(By.TAG_NAME,'body').text[-1600:]);print('ERRORS:',b.get_log('browser')[-6:]);raise
