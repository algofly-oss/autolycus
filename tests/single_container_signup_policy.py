"""Disposable app: env-gated registration, no bypass and existing-user sign-in."""
import json,os,time
from pathlib import Path
import requests
from pymongo import MongoClient
base='http://127.0.0.1'
for _ in range(50):
 try:
  if requests.get(base+'/api/ping',timeout=1).status_code==200:break
 except requests.RequestException:pass
 time.sleep(1)
disabled=os.environ.get('SIGNUP_DISABLED','false').lower()=='true'
r=requests.get(base+'/api/auth/settings');r.raise_for_status();assert r.json()=={'signup_disabled':disabled,'signup_enabled':not disabled};assert 'no-store' in r.headers['cache-control']
h=json.loads(Path('/run/autolycus/health.json').read_text());db=MongoClient(h['mongo_uri'])[h['database']];before=db.users.count_documents({})
payload={'name':'Signup fixture','username':'signup-policy@example.test','password':'Signup-policy-fixture-123!'};s=requests.Session()
if disabled:
 for username in [payload['username'],'disabled-registration@example.test']:
  r=s.post(base+'/api/auth/signup',json={**payload,'username':username,'signup_enabled':True});assert r.status_code==403 and r.json()['detail']=='Sign up is disabled';assert not r.cookies
 assert db.users.count_documents({})==before
else:
 r=s.post(base+'/api/auth/signup',json=payload);r.raise_for_status();assert r.json()['msg'] in ['success','user already exists']
 assert db.users.count_documents({})==before+(0 if r.json()['msg']=='user already exists' else 1)
 if r.json()['msg']=='success':assert s.cookies
r=s.post(base+'/api/auth/signin',json={k:payload[k] for k in ['username','password']});r.raise_for_status();assert r.json()['msg']=='success'
assert s.get(base+'/api/auth/me').json()['username']==payload['username']
Path('/data/signup-fixture.json').write_text(json.dumps(payload))
print('PASS: '+('SIGNUP_DISABLED=true rejects direct and forged registration before account/session creation; existing account sign-in works' if disabled else 'SIGNUP_DISABLED=false exposes registration, creates account/session, and permits sign-in')+'; public policy is uncached')
