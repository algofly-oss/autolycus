"""Isolated fixture app: long scrolling lists and phone fullscreen fallback."""
import json,time
from pathlib import Path
from urllib.parse import urlencode
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
f=json.loads(Path('/data/mobile-fixture.json').read_text());o=webdriver.ChromeOptions()
for flag in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required']:o.add_argument(flag)
o.set_capability('goog:loggingPrefs',{'browser':'ALL'})
with webdriver.Chrome(options=o) as b:
 b.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
 b.execute_cdp_cmd('Emulation.setTouchEmulationEnabled',{'enabled':True})
 b.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',{'source':'''Object.defineProperty(navigator,'maxTouchPoints',{get:()=>1});Object.defineProperty(document,'fullscreenEnabled',{get:()=>false});Element.prototype.requestFullscreen=undefined;Element.prototype.webkitRequestFullscreen=undefined;'''})
 w=WebDriverWait(b,35)
 def js(code,*args):return b.execute_script(code,*args)
 def wait_loaded(n):w.until(lambda _:js('return Number(document.querySelector("[data-infinite-media-list]")?.dataset.loadedCount||0)')>=n)
 def tap(x,y):
  b.execute_cdp_cmd('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y,'id':1}]})
  b.execute_cdp_cmd('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
 def bottom():js('const s=document.querySelector("[data-file-scroller]");s.scrollTop=s.scrollHeight')
 def load_all():
  for _ in range(20):
   bottom();time.sleep(.35)
   if js('return Number(document.querySelector("[data-infinite-media-list]")?.dataset.loadedCount||0)')==260:break
  wait_loaded(260)
  assert js('return document.querySelectorAll("[data-media-item]").length')<65
 try:
  b.get('http://127.0.0.1/account/signin');w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys(f['username']);b.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys(f['password']);b.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click();w.until(lambda _:'/account/' not in b.current_url)
  b.get('http://127.0.0.1/home');wait_loaded(50);b.find_element(By.CSS_SELECTOR,'[aria-label="List view"]').click()
  nav=b.find_element(By.CSS_SELECTOR,'nav[aria-label="Main navigation"]');assert not any(e.is_displayed() for e in nav.find_elements(By.CSS_SELECTOR,'[aria-label="Autolycus home"]'))
  icon=next(e for e in b.find_elements(By.CSS_SELECTOR,'[aria-label="Autolycus home"]') if e.is_displayed());search=b.find_element(By.CSS_SELECTOR,'input[placeholder="Search Files by Metadata"]');assert abs(icon.rect['y']-search.rect['y'])<2
  load_all();b.save_screenshot('/data/mobile-long-list.png')
  assert 'Items per page' not in b.find_element(By.TAG_NAME,'body').text
  b.find_element(By.CSS_SELECTOR,'[aria-label="Thumbnail view"]').click();time.sleep(.5);assert js('return document.documentElement.scrollWidth<=innerWidth');load_all();b.save_screenshot('/data/mobile-long-grid.png')
  js('''const open=XMLHttpRequest.prototype.open,send=XMLHttpRequest.prototype.send;window.__failedPage=false;XMLHttpRequest.prototype.open=function(method,url,...rest){this.__reviewUrl=String(url);return open.call(this,method,url,...rest)};XMLHttpRequest.prototype.send=function(...args){const fail=!window.__failedPage&&this.__reviewUrl?.includes('/api/files/search')&&this.__reviewUrl.includes('offset=50');const result=send.apply(this,args);if(fail){window.__failedPage=true;this.abort()}return result};''')
  search.send_keys('Collection');w.until(lambda _:js('return Number(document.querySelector("[data-infinite-media-list]")?.dataset.loadedCount||0)')==50);bottom();w.until(EC.element_to_be_clickable((By.XPATH,"//button[normalize-space()='Retry']"))).click();wait_loaded(100);load_all();b.save_screenshot('/data/mobile-search-infinite.png')
  search.clear();search.send_keys('No such fixture');w.until(lambda _:js('return document.querySelector("[data-infinite-media-list]")?.dataset.loadedCount==="0"'))
  b.get('http://127.0.0.1/home?tab=settings');tabs=w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'.settings-category-nav')))
  assert js('const es=[...arguments[0].querySelectorAll("button")];return es.every(e=>Math.abs(e.getBoundingClientRect().top-es[0].getBoundingClientRect().top)<2)&&arguments[0].scrollWidth>arguments[0].clientWidth',tabs)
  b.find_element(By.CSS_SELECTOR,'.settings-category-nav [aria-label="Sessions"]').click();b.save_screenshot('/data/mobile-settings-tabs.png')
  for width in [320,390]:
   b.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',{'width':width,'height':844,'deviceScaleFactor':1,'mobile':True});assert js('return document.documentElement.scrollWidth<=innerWidth')
  b.get('http://127.0.0.1/home?'+urlencode({'path':f['directory'],'video':f['path']}))
  w.until(lambda _:js('const v=document.querySelector("video");return v&&v.currentTime>0&&v.videoWidth>0'))
  assert js('const p=document.querySelector(".movie-player");return p.hasAttribute("data-landscape")&&p.clientWidth>p.clientHeight')
  js('document.querySelector("video").loop=true')
  w.until(lambda _:js('return document.querySelector(".movie-player").dataset.touchControls==="hidden"'))
  tap(195,400);w.until(lambda _:js('return document.querySelector(".movie-player").dataset.touchControls==="visible"'))
  tap(195,400);w.until(lambda _:js('return document.querySelector(".movie-player").dataset.touchControls==="hidden"'))
  assert not js('return document.querySelector("video").paused')
  def controls():
   if js('return document.querySelector(".movie-player").dataset.touchControls==="hidden"'):
    tap(195,400);w.until(lambda _:js('return document.querySelector(".movie-player").dataset.touchControls==="visible"'))
  controls();button=w.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'[aria-label="Fill screen"]')));button.click();assert js('return getComputedStyle(document.querySelector("video")).objectFit')=='cover'
  b.find_element(By.CSS_SELECTOR,'[aria-label="Fit video"]').click();assert js('return getComputedStyle(document.querySelector("video")).objectFit')=='contain'
  # The CSS-rotated timeline must use its physical vertical axis, not clientX.
  seek=b.find_element(By.CSS_SELECTOR,'.movie-landscape-timeline');js('document.querySelector("video").pause()')
  point=js('const r=arguments[0].getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height*.5}',seek);tap(point['x'],point['y'])
  w.until(lambda _:js('return document.querySelector("video").currentTime>12&&document.querySelector("video").currentTime<18'))
  tap(195,400);w.until(lambda _:js('return document.querySelector(".movie-player").dataset.touchControls==="hidden"'));assert js('return document.querySelector("video").paused')
  tap(195,400);w.until(lambda _:js('return document.querySelector(".movie-player").dataset.touchControls==="visible"'));assert js('return document.querySelector("video").paused')
  tap(195,675);time.sleep(.1);tap(195,675);w.until(lambda _:js('return document.querySelector("video").currentTime>=24'))
  js('const v=document.querySelector("video");v.currentTime=10;v.play()');b.execute_cdp_cmd('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':195,'y':400,'id':1}]});time.sleep(.55);assert js('return document.querySelector("video").playbackRate')==2
  b.execute_cdp_cmd('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});assert js('return document.querySelector("video").playbackRate')==1
  controls();b.find_element(By.CSS_SELECTOR,'[aria-label="Settings"].media-settings-menu-trigger').click();w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'[aria-label="Player settings"]')));assert js('const e=document.querySelector(".movie-settings-popup"),r=e.getBoundingClientRect(),t=getComputedStyle(e).transform;return t.startsWith("matrix(0, 1, -1, 0")&&r.left>=0&&r.top>=0&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1');b.save_screenshot('/data/mobile-landscape-player-settings.png')
  b.find_element(By.CSS_SELECTOR,'[aria-label="Settings"].media-settings-menu-trigger').click();controls();b.find_element(By.CSS_SELECTOR,'[aria-label="Exit fullscreen"]').click();assert not js('return document.querySelector(".movie-player").hasAttribute("data-landscape")')
  b.find_element(By.CSS_SELECTOR,'[aria-label="Enter fullscreen"]').click();assert js('return document.querySelector(".movie-player").hasAttribute("data-landscape")')
  b.save_screenshot('/data/mobile-landscape-player.png')
  controls();b.find_element(By.CSS_SELECTOR,'[aria-label="Close player"]').click();w.until(lambda _:not b.find_elements(By.CSS_SELECTOR,'.movie-player'))
  errors=[e for e in b.get_log('browser') if e['level']=='SEVERE' and any(s in e['message'] for s in ['TypeError','ReferenceError','Maximum update depth'])];assert not errors,errors
  print('PASS: 260 real paged/indexed collections auto-load in list/grid/search with bounded mounted cards and failed-page retry; metadata-row Cinema shortcut; one-row scrolling settings; phone landscape fallback without fullscreen API, idle control fade and tap visibility without pausing, Fit/Fill, rotated seek and double-tap, paused tap visibility, hold-to-2x, rotated settings, exit/re-enter and close; no JS exceptions')
 except:
  b.save_screenshot('/data/mobile-review-failure.png');print('URL',b.current_url);print('TEXT',b.find_element(By.TAG_NAME,'body').text[-1800:]);print('ERRORS',b.get_log('browser')[-8:]);raise
