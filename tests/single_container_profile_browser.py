"""Disposable UI: profile choice survives refresh and playback history stays isolated."""
import json,subprocess,shutil
from pathlib import Path
from urllib.parse import quote
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
USER='profile-browser@example.test';PASSWORD='Profile-browser-123!';BASE='http://127.0.0.1'
s=requests.Session()
for action in ['signup','signin']:s.post(BASE+'/api/auth/'+action,json={'name':'Profile browser','username':USER,'password':PASSWORD}).raise_for_status()
uid=subprocess.check_output(['python','-c',"import json;from pathlib import Path;from pymongo import MongoClient;h=json.loads(Path('/run/autolycus/health.json').read_text());print(MongoClient(h['mongo_uri'])[h['database']].users.find_one({'username':'profile-browser@example.test'})['_id'])"],text=True).strip()
root=Path('/downloads')/uid/'profile-fixture';root.mkdir(parents=True,exist_ok=True);file=root/'Profile.Movie.mp4';shutil.copyfile('/downloads/playback-fixtures/tracks.mp4',file);path=str(file.relative_to('/downloads'))
profiles=s.get(BASE+'/api/auth/profiles').json()['profiles'];other=next((row for row in profiles if row['name']=='Viewer Two'),None)
if not other:other=s.post(BASE+'/api/auth/profiles',json={'name':'Viewer Two','avatar':'film'}).json();other=other.get('profile',other)
s.post(BASE+'/api/files/playback/progress',json={'path':path,'position':12,'duration':36},headers={'X-Profile-ID':'default'}).raise_for_status()
s.post(BASE+'/api/files/playback/progress',json={'path':path,'position':0,'duration':36},headers={'X-Profile-ID':other['id']}).raise_for_status()
options=webdriver.ChromeOptions()
for arg in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required','--window-size=1440,1000']:options.add_argument(arg)
with webdriver.Chrome(options=options) as b:
    wait=WebDriverWait(b,40)
    def js(code,*args):return b.execute_script(code,*args)
    def open():b.get(BASE+'/home?path='+quote(str(root.relative_to('/downloads')))+'&video='+quote(path));wait.until(lambda _:js('const v=document.querySelector("video");return v&&v.readyState>=2&&v.currentTime>0'))
    def close():
        ActionChains(b).move_to_element(b.find_element(By.CSS_SELECTOR,'video')).perform();wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,'.movie-player [aria-label="Close player"]'))).click()
    b.get(BASE+'/account/signin');wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys(USER);b.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys(PASSWORD);b.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click();wait.until(lambda driver: driver.execute_script("return location.pathname==='/' || location.pathname==='/home'"))
    open();assert js('return document.querySelector("video").currentTime')>=12;close()
    button=next(row for row in b.find_elements(By.CSS_SELECTOR,'[aria-label="Switch profile"]') if row.is_displayed());button.click();wait.until(EC.element_to_be_clickable((By.XPATH,'//*[@role="menuitem" and contains(.,"Viewer Two")]'))).click()
    wait.until(lambda _:js('return localStorage.getItem(arguments[0])','autolycus:profile:'+USER)==other['id'])
    open();assert js('return document.querySelector("video").currentTime')<10
    js('const v=document.querySelector("video");v.currentTime=5;v.pause()');close();b.refresh()
    wait.until(lambda _:any(row.is_displayed() and row.get_attribute('title')=='Viewer Two' for row in b.find_elements(By.CSS_SELECTOR,'[aria-label="Switch profile"]')))
    open();wait.until(lambda _:js('return document.querySelector("video").currentTime>=5'));close()
    default=s.get(BASE+'/api/files/playback/progress',params={'path':path},headers={'X-Profile-ID':'default'}).json()['progress'];assert default['position']>=12
    print('PASS: UI profile switching, browser-local active choice survives refresh, independent server watch histories and resumed playback',flush=True)
