"""Read-only large-file audit on a public HTTPS origin mapped to an isolated app.

The browser retains only the advertised LAN candidate to avoid the test container
shortcut. No production account, playback position or library file is modified.
"""
import hashlib,json,time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
layout=json.loads(Path('/data/avatar-lan-layout.json').read_text());f=json.loads(Path('/data/cinema-fixture.json').read_text());moov=next(box for box in layout['boxes'] if box['type']=='moov')
options=webdriver.ChromeOptions()
for flag in ['--headless=new','--no-sandbox','--disable-dev-shm-usage','--ignore-certificate-errors','--no-proxy-server','--host-resolver-rules=MAP autolycus.algofly.ai 127.0.0.1','--window-size=1440,1000']:options.add_argument(flag)
options.set_capability('goog:loggingPrefs',{'browser':'ALL'})
base='https://autolycus.algofly.ai'
with webdriver.Chrome(options=options) as b:
 b.set_script_timeout(90);w=WebDriverWait(b,45)
 b.get(base+'/');w.until(EC.visibility_of_element_located((By.CSS_SELECTOR,'input[placeholder="Enter your email"]'))).send_keys(f['username']);b.find_element(By.CSS_SELECTOR,'input[placeholder="Enter your password"]').send_keys(f['password']);b.find_element(By.XPATH,"//button[.//p[text()='Sign in']]").click();w.until(lambda _:'/account/' not in b.current_url)
 result=b.execute_async_script(r'''
 const [path,start,size,done]=arguments;
 (async()=>{
  const t0=performance.now(),pc=new RTCPeerConnection({iceServers:[]}),pending=new Map();let sequence=0,lease;
  const channel=pc.createDataChannel('autolycus-bytes-v1',{ordered:true});channel.binaryType='arraybuffer';
  const opened=new Promise((resolve,reject)=>{channel.onopen=resolve;channel.onerror=reject;});
  channel.onmessage=({data})=>{const id=new DataView(data).getUint32(0),p=pending.get(id);if(!p)return;p.bytes.set(new Uint8Array(data,4),p.offset);p.offset+=data.byteLength-4;if(p.offset===p.bytes.length){pending.delete(id);clearTimeout(p.timer);p.resolve(p.bytes);}};
  const read=(offset,length)=>new Promise((resolve,reject)=>{const id=++sequence,p={bytes:new Uint8Array(length),offset:0,resolve,reject,timer:setTimeout(()=>reject(Error('Read timed out')),10000)};pending.set(id,p);channel.send(JSON.stringify({id,start:offset,length}));});
  try{
   await pc.setLocalDescription(await pc.createOffer());
   if(pc.iceGatheringState!=='complete')await Promise.race([new Promise(resolve=>pc.addEventListener('icegatheringstatechange',()=>{if(pc.iceGatheringState==='complete')resolve();})),new Promise(resolve=>setTimeout(resolve,1500))]);
   const response=await fetch('/api/files/playback/offer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path,sdp:pc.localDescription.sdp})});
   if(!response.ok)throw Error('Offer HTTP '+response.status);
   const answer=await response.json();lease=answer.id;
   answer.answer.sdp=answer.answer.sdp.split('\r\n').filter(line=>!line.startsWith('a=candidate:')||line.split(' ')[4]==='192.168.0.3').join('\r\n');
   await pc.setRemoteDescription(answer.answer);await Promise.race([opened,new Promise((_,reject)=>setTimeout(()=>reject(Error('LAN channel timed out')),10000))]);
   const connected=performance.now(),header=await read(0,32),bytes=new Uint8Array(size);
   for(let offset=0;offset<size;offset+=262144)bytes.set(await read(start+offset,Math.min(262144,size-offset)),offset);
   const finished=performance.now(),hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
   const stats=[...(await pc.getStats()).values()],pair=stats.find(s=>s.type==='candidate-pair'&&s.state==='succeeded'&&(s.nominated||s.selected)),remote=stats.find(s=>s.id===pair?.remoteCandidateId);
   done({origin:location.origin,secure:isSecureContext,connection_ms:Math.round(connected-t0),metadata_ms:Math.round(finished-connected),metadata_bytes:size,metadata_sha256:hash,ftyp:String.fromCharCode(...header.slice(4,8)),remote:remote?.address||remote?.ip,remote_port:remote?.port,received:pair?.bytesReceived,reads:sequence});
  }finally{if(lease)await fetch('/api/files/playback/lease',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:lease,close:true})});pc.close();}
 })().catch(e=>done({error:e.message}));
 ''',layout['path'],moov['offset'],moov['size'])
 assert 'error' not in result,result
 assert result['origin']==base and result['secure'] and result['ftyp']=='ftyp',result
 assert result['remote']=='192.168.0.3' and 10155<=result['remote_port']<=10162,result
 assert result['metadata_sha256']==layout['moov_sha256'],result
 assert result['received']>=moov['size'],result
 Path('/data/avatar-lan-result.json').write_text(json.dumps(result,indent=2))
 print('PASS: real 38.6 GB read-only Avatar; public HTTPS origin; host-LAN UDP candidate; 15.4 MB end index SHA-256 exact; bounded 256 KiB requests; '+json.dumps(result),flush=True)
