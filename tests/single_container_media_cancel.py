"""Disposable-container regressions for real running cancellation and URL failures."""
import hashlib,http.server,json,subprocess,threading,time
from pathlib import Path
from pymongo import MongoClient
import requests
from redis import Redis
health=json.loads(Path('/run/autolycus/health.json').read_text());client=MongoClient(health['mongo_uri']);db=client[health['database']]
secrets=json.loads(Path('/data/secrets.json').read_text());cache=Redis(host='127.0.0.1',password=secrets['REDIS_PASSWORD'])
s=requests.Session();s.post('http://127.0.0.1/api/auth/signin',json={'username':'subtitle-fixture@example.test','password':'Subtitle-fixture-123!'}).raise_for_status()
uid=str(db.users.find_one({'username':'subtitle-fixture@example.test'})['_id']);base='http://127.0.0.1/api'
def until(check,seconds=30):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if check():return
        time.sleep(.2)
    raise AssertionError('Timed out waiting for job state')
source=Path('/downloads')/uid/'real-media/WallE.mkv';output=source.with_name('WallE_144p.mp4');partial=source.with_name('.autolycus-transcode-'+output.name)
for p in [output,partial]:
    if p.exists():p.unlink()
r=s.post(base+'/files/transcode/start',params={'path':str(source),'resolution':'144p'});r.raise_for_status()
until(lambda:partial.exists())
r=s.post(base+'/files/transcode/bulk',json={'paths':[str(source)],'action':'cancel'});r.raise_for_status();assert r.json()['results'][0]['ok'],r.text
until(lambda:not partial.exists() and not output.exists())
assert not cache.exists('transcoding_progress/'+str(output))
print('PASS: actual running NVENC encode cancelled through bulk source selection; partial output removed and slot released',flush=True)

release=threading.Event();started=threading.Event()
class Handler(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200);self.send_header('Content-Length','10485760');self.end_headers()
    def do_GET(self):
        if self.path=='/broken.bin':self.send_error(404);return
        self.send_response(200);self.send_header('Content-Length','10485760');self.end_headers();started.set();release.wait(20)
    def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',18767),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
try:
    url='http://127.0.0.1:18767/broken.bin';url_hash=hashlib.md5(url.encode()).hexdigest()
    db.torrents.delete_many({'url_hash':url_hash})
    s.post(base+'/torrent/add-url',json={'url':url}).raise_for_status()
    until(lambda:bool(db.torrents.find_one({'url_hash':url_hash}).get('download_error')))
    record=db.torrents.find_one({'url_hash':url_hash});assert not record['is_finished'] and record['is_paused']
    print('PASS: failed aria2 GET records an error and never reports a completed download',flush=True)
    url='http://127.0.0.1:18767/quiet.bin';url_hash=hashlib.md5(url.encode()).hexdigest();db.torrents.delete_many({'url_hash':url_hash})
    s.post(base+'/torrent/add-url',json={'url':url}).raise_for_status();assert started.wait(15)
    before=time.monotonic();s.post(base+'/torrent/pause',params={'info_hash':'url_hash_'+url_hash}).raise_for_status()
    until(lambda:not cache.exists(f'{uid}/{url_hash}/stop'),seconds=5)
    assert time.monotonic()-before<5
    print('PASS: a quiet URL transfer cancels promptly without waiting for another aria2 output line',flush=True)
finally:release.set();server.shutdown()
