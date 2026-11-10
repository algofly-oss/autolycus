import json,time
from pathlib import Path
import requests
for _ in range(45):
 try:
  if requests.get('http://127.0.0.1/api/ping',timeout=2).status_code==200:break
 except requests.RequestException:pass
 time.sleep(1)
config=json.loads(Path('/data/jackett/Jackett/ServerConfig.json').read_text());assert config['ProxyType']==0
assert not Path('/data/jackett/Jackett/Indexers/filemood.json').exists()
assert Path('/data/jackett/Jackett/Indexers/torrentscsv.json').exists()
f=json.loads(Path('/data/distribution-restart-fixture.json').read_text());s=requests.Session();s.cookies.update(f['cookies']);r=s.get('http://127.0.0.1/api/auth/me');r.raise_for_status();assert r.json()['username']=='distribution-defaults@example.test'
print('PASS: CPU-only restart preserves user session, intentional direct proxy setting and removed starter indexer')
