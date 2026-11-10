"""Run inside the disposable playback fixture container after playback tests."""
import json, subprocess, time
import requests
from pathlib import Path
base='http://127.0.0.1'
s=requests.Session()
s.post(base+'/api/auth/signin',json={'username':'playback-fixture@example.test','password':'Playback-fixture-123!'}).raise_for_status()
# Different authenticated session cannot renew someone else's peer capability.
other=requests.Session();other.post(base+'/api/auth/signin',json={'username':'playback-fixture@example.test','password':'Playback-fixture-123!'}).raise_for_status()
# Build an SDP data-channel offer in an isolated browser, never a production account.
from selenium import webdriver
opt=webdriver.ChromeOptions()
for arg in ['--headless=new','--no-sandbox','--disable-dev-shm-usage']:opt.add_argument(arg)
with webdriver.Chrome(options=opt) as b:
 b.get(base+'/account/signin')
 offer=b.execute_async_script('const done=arguments[0];const p=new RTCPeerConnection();p.createDataChannel("autolycus-bytes-v1");p.createOffer().then(o=>p.setLocalDescription(o)).then(()=>done(p.localDescription.sdp));')
 peers=[]
 for i in range(8):
  r=s.post(base+'/api/files/playback/offer',json={'path':'playback-fixtures/tracks.mp4','sdp':offer})
  assert r.status_code==200,(i,r.status_code,r.text)
  peers.append(r.json()['id'])
 assert s.post(base+'/api/files/playback/offer',json={'path':'playback-fixtures/tracks.mp4','sdp':offer}).status_code==503
 assert other.post(base+'/api/files/playback/lease',json={'id':peers[0]}).status_code==404
 for peer in peers: assert s.post(base+'/api/files/playback/lease',json={'id':peer,'close':True}).status_code==200
 time.sleep(2)
 r=s.post(base+'/api/files/playback/offer',json={'path':'playback-fixtures/tracks.mp4','sdp':offer});assert r.status_code==200,r.text
 peer=r.json()['id']
 assert s.post(base+'/api/files/playback/lease',json={'id':peer}).status_code==200
 s.post(base+'/api/auth/signout')
 assert s.post(base+'/api/files/playback/lease',json={'id':peer}).status_code>=400
 print('PASS: eight-peer cap, capacity released on close, session-bound grants and renewal auth')
