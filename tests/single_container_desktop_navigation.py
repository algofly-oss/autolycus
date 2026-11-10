"""Desktop regression for virtual collections, folder lists and custom controls."""
import json,time
from pathlib import Path
from urllib.parse import urlencode
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
f=json.loads(Path('/data/mobile-fixture.json').read_text());o=webdriver.ChromeOptions()
for flag in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000']:o.add_argument(flag)
with webdriver.Chrome(options=o) as b:
 w=WebDriverWait(b,35);js=b.execute_script
 b.get('http://127.0.0.1/account/signin');w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys(f['username']);b.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys(f['password']);b.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click();w.until(lambda _:'/account/' not in b.current_url)
 b.get('http://127.0.0.1/home');w.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'[aria-label="List view"]'))).click();w.until(lambda _:js('return Number(document.querySelector("[data-infinite-media-list]")?.dataset.loadedCount)>=50'))
 assert len([e for e in b.find_elements(By.CSS_SELECTOR,'[aria-label="Autolycus home"]') if e.is_displayed()])==1
 for _ in range(15):
  js('const s=document.querySelector("[data-file-scroller]");s.scrollTop=s.scrollHeight');time.sleep(.3)
  if js('return Number(document.querySelector("[data-infinite-media-list]").dataset.loadedCount)')==260:break
 assert js('return Number(document.querySelector("[data-infinite-media-list]").dataset.loadedCount)')==260
 assert len(b.find_elements(By.CSS_SELECTOR,'[data-media-item]'))<35
 b.get('http://127.0.0.1/home?tab=settings');nav=w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'.settings-category-nav')));assert js('return getComputedStyle(arguments[0]).display',nav)=='grid'
 b.get('http://127.0.0.1/home?'+urlencode({'path':f['directory'],'video':f['path']}));w.until(lambda _:js('const v=document.querySelector("video");return v&&v.currentTime>1&&!v.paused'))
 assert not js('return document.querySelector(".movie-player").hasAttribute("data-landscape")')
 ActionChains(b).move_to_element(b.find_element(By.CSS_SELECTOR,'video')).perform();w.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'[aria-label="Fill screen"]'))).click();assert js('return getComputedStyle(document.querySelector("video")).objectFit')=='cover'
 b.find_element(By.CSS_SELECTOR,'[aria-label="Fit video"]').click();b.find_element(By.CSS_SELECTOR,'[aria-label="Close player"]').click();w.until(lambda _:not b.find_elements(By.CSS_SELECTOR,'.movie-player'))
 assert js('return document.querySelectorAll("[data-media-item]").length')<35
 js('const s=document.querySelector("[data-file-scroller]");s.scrollTop=s.scrollHeight');w.until(lambda _:'Review.Movie.2024.mp4' in b.find_element(By.TAG_NAME,'body').text)
 b.save_screenshot('/data/desktop-folder-virtualized.png')
 print('PASS: desktop collection pages auto-load, mounted cards stay bounded, one sidebar Cinema link, vertical settings retained, local video plays without forced rotation, Fit/Fill works, and long folder rows remain virtualized')
