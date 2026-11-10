import json,time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
f=json.loads(Path('/data/cinema-fixture.json').read_text());row=json.loads(Path('/data/torrent-preview-browser-row.json').read_text())
o=webdriver.ChromeOptions()
for arg in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000']:o.add_argument(arg)
o.set_capability('goog:loggingPrefs',{'browser':'ALL'})
script='const original=window.fetch;window.fetch=(url,opts)=>String(url).includes("/torrent/search?")?Promise.resolve(new Response('+json.dumps(json.dumps(row)+'\n')+')):original(url,opts);'
with webdriver.Chrome(options=o) as b:
 w=WebDriverWait(b,45)
 def js(code):return b.execute_script(code)
 def click(selector):w.until(EC.element_to_be_clickable((By.CSS_SELECTOR,selector))).click()
 try:
  b.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',{'source':script})
  b.get('http://127.0.0.1/');w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys(f['username']);b.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys(f['password']);b.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click();w.until(lambda _:'/account/' not in b.current_url)
  b.execute_async_script('const done=arguments[0];fetch("/api/auth/preferences",{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({search_view_mode:"list"})}).then(()=>done())')
  b.get('http://127.0.0.1/home?tab=search&q=Course');click('[aria-label="Browse torrent files"]')
  w.until(lambda _:len(b.find_elements(By.CSS_SELECTOR,'[data-torrent-files] input[type="checkbox"]'))==3)
  assert [e.text for e in b.find_elements(By.CSS_SELECTOR,'[data-torrent-files] label>span:first-child')][:2]==['Episode.02.mp4','Episode.10.mp4']
  query=b.find_element(By.CSS_SELECTOR,'[aria-label="Filter torrent files"]');query.send_keys('notes');w.until(lambda _:len(b.find_elements(By.CSS_SELECTOR,'[data-torrent-files] input[type="checkbox"]'))==1);query.send_keys(Keys.CONTROL,'a');query.send_keys(Keys.BACKSPACE);w.until(lambda _:len(b.find_elements(By.CSS_SELECTOR,'[data-torrent-files] input[type="checkbox"]'))==3)
  for width in [390,320,768]:
   b.set_window_size(width,844);assert js('return document.documentElement.scrollWidth<=innerWidth')
   assert b.execute_script('return arguments[0].scrollWidth<=arguments[0].clientWidth',b.find_element(By.CSS_SELECTOR,'[aria-label="Torrent contents"]'))
   b.save_screenshot(f'/data/torrent-contents-{width}.png')
  b.set_window_size(390,844);click('[aria-label="Preview Episode.02.mp4"]')
  w.until(lambda _:js('const v=document.querySelector("video");return v&&v.videoWidth>0&&!v.paused&&v.currentTime>2'))
  assert not b.find_elements(By.CSS_SELECTOR,'.movie-player-error')
  b.save_screenshot('/data/torrent-preview-player-phone.png')
  ActionChains(b).move_to_element(b.find_element(By.CSS_SELECTOR,'video')).perform();click('[aria-label="Close player"]')
  w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'[aria-label="Torrent contents"]')))
  click('input[aria-label="Select Course/Episode.02.mp4"]');click('[aria-label="Torrent contents"] button.bg-blue-600')
  w.until(lambda _:not b.find_elements(By.CSS_SELECTOR,'[aria-label="Torrent contents"]'))
  w.until(lambda _:'Selected files added' in b.find_element(By.TAG_NAME,'body').text)
  def finished():
   return b.execute_async_script('const done=arguments[0];fetch("/api/torrent/all?page_size=100").then(r=>r.json()).then(d=>done(d.data.find(t=>t.info_hash==='+json.dumps(row['InfoHash'])+'))).catch(()=>done(null))')
  w.until(lambda _:bool((finished() or {}).get('is_finished')))
  result=finished();assert len(result['selected_files'])==1 and result['total_bytes']==row['Size']//2 and 'torrent_metadata' not in result
  click('[aria-label="Search result view"] button[aria-label="Thumbnail view"]')
  click('[aria-label="Search result actions"]')
  w.until(lambda _:[e for e in b.find_elements(By.CSS_SELECTOR,'[role="menuitem"]') if e.text=='Browse files and preview'])[0].click()
  w.until(lambda _:len(b.find_elements(By.CSS_SELECTOR,'[data-torrent-files] input[type="checkbox"]'))==3)
  click('[aria-label="Close torrent files"]')
  w.until(lambda _:not b.find_elements(By.CSS_SELECTOR,'[aria-label="Torrent contents"]'))
  print('PASS: real local-swarm search result → contents; natural file list/filter; 320/390/768px dialog; original video in shared player; close returns to file list; selected download completes with chosen-only totals; poster menu browsing')
 except:
  b.save_screenshot('/data/torrent-preview-browser-failure.png');print('URL',b.current_url);print('TEXT',b.find_element(By.TAG_NAME,'body').text[-2200:]);print('ERRORS',b.get_log('browser')[-8:]);raise
