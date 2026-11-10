"""Fresh CPU-only distribution: public starter indexers, Tor, sign-in and assets."""
import json
from pathlib import Path
import requests
config=json.loads(Path('/data/jackett/Jackett/ServerConfig.json').read_text())
assert (config.get('ProxyType'),config.get('ProxyUrl'),config.get('ProxyPort'))==(2,'127.0.0.1',9050)
s=requests.Session();s.get('http://127.0.0.1:9117/UI/Dashboard',timeout=10)
r=s.get('http://127.0.0.1:9117/api/v2.0/indexers',params={'apikey':config['APIKey']},timeout=10);r.raise_for_status()
active={row['id'] for row in r.json() if row.get('configured')};assert active=={'filemood','torrentscsv'},active
assert requests.get('http://127.0.0.1/api/ping',timeout=5).status_code==200
image=requests.get('http://127.0.0.1/images/signin-cinema.jpg');assert image.status_code==200 and image.content[:2]==b'\xff\xd8'
username='distribution-defaults@example.test';password='Distribution-fixture-123!'
r=s.post('http://127.0.0.1/api/auth/signup',json={'name':'Distribution fixture','username':username,'password':password});r.raise_for_status()
s.post('http://127.0.0.1/api/auth/signin',json={'username':username,'password':password}).raise_for_status()
user=s.get('http://127.0.0.1/api/auth/me');user.raise_for_status();assert user.json()['role']=='user'
# Preserve an intentional direct-proxy setting and removed indexer on restart.
config['ProxyType']=0;Path('/data/jackett/Jackett/ServerConfig.json').write_text(json.dumps(config))
Path('/data/jackett/Jackett/Indexers/filemood.json').unlink()
Path('/data/distribution-restart-fixture.json').write_text(json.dumps({'cookies':s.cookies.get_dict(),'user':user.json().get('id') or user.json().get('_id')}))
print('PASS: fresh CPU-only boot, two configured verified public sources, Tor proxy defaults, new user sign-in and locally served JPEG; restart preservation fixture prepared')
