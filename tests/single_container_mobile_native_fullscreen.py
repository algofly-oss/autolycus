"""Real Chromium fullscreen entry on a Play gesture, with orientation API spy."""
import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
f=json.loads(Path('/data/mobile-fixture.json').read_text());o=webdriver.ChromeOptions()
for flag in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required']:o.add_argument(flag)
with webdriver.Chrome(options=o) as b:
 b.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True});b.execute_cdp_cmd('Emulation.setTouchEmulationEnabled',{'enabled':True})
 b.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',{'source':'''Object.defineProperty(navigator,'maxTouchPoints',{get:()=>1});Object.defineProperty(screen.orientation,'lock',{value:async mode=>{window.__orientationRequest=mode}});Object.defineProperty(screen.orientation,'unlock',{value:()=>{window.__orientationRequest=null}});'''})
 w=WebDriverWait(b,35)
 b.get('http://127.0.0.1/account/signin');w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys(f['username']);b.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys(f['password']);b.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click();w.until(lambda _:'/account/' not in b.current_url)
 w.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'.cinema-card[aria-label^="Play "]'))).click()
 w.until(lambda _:b.execute_script('return !!document.fullscreenElement&&window.__orientationRequest==="landscape"'))
 w.until(lambda _:b.execute_script('const v=document.querySelector("video");return v&&v.currentTime>0&&!v.paused'))
 b.save_screenshot('/data/mobile-native-fullscreen.png')
 b.find_element(By.CSS_SELECTOR,'[aria-label="Close player"]').click();w.until(lambda _:b.execute_script('return !document.fullscreenElement&&!document.querySelector(".movie-player")&&window.__orientationRequest===null'))
 print('PASS: Play enters actual Chromium fullscreen from user activation; player requests landscape orientation; generated A/V plays; closing exits fullscreen and releases orientation. Orientation API is spied, not a physical-device rotation test.')
