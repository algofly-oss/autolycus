"""Configured online adapter + generated local library file: bidirectional source continuity."""
import json,time
from pathlib import Path
from urllib.parse import urlencode
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
f=json.loads(Path('/data/cinema-fixture.json').read_text());path=f['series']['files'][0]['path'].split('/')[0]+'/source-switch/WALL-E.2008.mp4'
o=webdriver.ChromeOptions()
for flag in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000']:o.add_argument(flag)
o.set_capability('goog:loggingPrefs',{'browser':'ALL'})
with webdriver.Chrome(options=o) as b:
 w=WebDriverWait(b,60)
 def js(code):return b.execute_script(code)
 def playing():return js('const v=document.querySelector("video");return v&&v.currentTime>1&&!v.paused&&v.videoWidth>0')
 def menu():
  ActionChains(b).move_to_element(b.find_element(By.CSS_SELECTOR,'video')).perform();gear=b.find_element(By.CSS_SELECTOR,'.movie-player [aria-label="Settings"]')
  if gear.get_attribute('aria-expanded')=='true':gear.click()
  gear.click();w.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'.media-menu-trigger-item[aria-label="Source"]'))).click()
 def choose(local):
  menu();rows=w.until(lambda _:b.find_elements(By.CSS_SELECTOR,'[data-source-id]'))
  next(row for row in rows if (row.get_attribute('data-source-id')=='library')==local).click()
 try:
  b.get('http://127.0.0.1/');w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys(f['username']);b.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys(f['password']);b.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click();w.until(lambda _:'/account/' not in b.current_url)
  b.get('http://127.0.0.1/?'+urlencode({'video':path}));w.until(lambda _:playing())
  js('const v=document.querySelector("video");v.currentTime=5;v.playbackRate=1.25');w.until(lambda _:js('return document.querySelector("video").currentTime>5.2'))
  menu();w.until(EC.element_to_be_clickable((By.XPATH,"//*[contains(@class,'media-menu-trigger-item') and normalize-space()='Find online sources']"))).click();w.until(lambda _:len(b.find_elements(By.CSS_SELECTOR,'[data-source-id]'))>1)
  before=js('return document.querySelector("video").currentTime')
  next(row for row in b.find_elements(By.CSS_SELECTOR,'[data-source-id]') if row.get_attribute('data-source-id')!='library').click()
  w.until(lambda _:'online=' in b.current_url and playing())
  assert js('return document.querySelector("video").currentTime')>=before-1
  assert js('return document.querySelector("video").playbackRate')==1.25
  before=js('return document.querySelector("video").currentTime');choose(True);w.until(lambda _:'online=' not in b.current_url and playing())
  assert js('return document.querySelector("video").currentTime')>=before-1
  js('const v=document.querySelector("video");v.currentTime=10;v.pause();v.playbackRate=1.5')
  choose(False);w.until(lambda _:'online=' in b.current_url and js('const v=document.querySelector("video");return v&&v.readyState>0&&v.currentTime>=9'))
  assert js('return document.querySelector("video").paused')
  assert js('return document.querySelector("video").playbackRate')==1.5
  def saved_position():
   return b.execute_async_script('const done=arguments[1];fetch("/api/files/playback/progress?path="+encodeURIComponent(arguments[0])).then(r=>r.json()).then(d=>done(d.progress?.position||0)).catch(()=>done(0))',path)
  w.until(lambda _:saved_position()>=9)
  choose(True);w.until(lambda _:'online=' not in b.current_url and js('const v=document.querySelector("video");return v&&v.readyState>0&&v.currentTime>=9'))
  assert js('return document.querySelector("video").paused')
  assert js('return document.querySelector("video").playbackRate')==1.5
  menu();next(row for row in b.find_elements(By.CSS_SELECTOR,'[data-source-id]') if row.get_attribute('data-source-id')=='fixture-unavailable').click()
  w.until(lambda _:b.find_elements(By.CSS_SELECTOR,'.movie-player-error'))
  choose(True);w.until(lambda _:'online=' not in b.current_url and js('const v=document.querySelector("video");return v&&v.readyState>0&&v.currentTime>=9'))
  assert js('return document.querySelector("video").paused') and js('return document.querySelector("video").playbackRate')==1.5
  print('PASS: library → online source → library retains timeline, playing state and 1.25×; both directions also preserve paused state and 1.5×; online playback updates the library server bookmark; failed-source return preserves position')
 except:
  b.save_screenshot('/data/source-continuity-failure.png');print('URL',b.current_url);print('TEXT',b.find_element(By.TAG_NAME,'body').text[-1000:]);print('ERRORS',b.get_log('browser')[-8:]);raise
