"""Run inside the isolated stack: real Redis, controlled local Jackett fixture."""
import asyncio
import http.server
import json
import threading
import time
from pathlib import Path
from redis import Redis
from shared.modules.jackett import AsyncJackett
from shared.modules.search_acceleration import PREFIX, SearchAcceleration

seen = []
class Fixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        source = self.path.split('/indexers/')[1].split('/')[0]
        seen.append(source)
        time.sleep(0.3 if source == 'test-slow' else 0.02)
        payload = json.dumps({'Results':[{'Title':'Ubuntu fixture','Tracker':source,'TrackerId':source,'InfoHash':('a' if source=='test-slow' else 'b')*40}]}).encode()
        self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(payload)
    def log_message(self,*args): pass

async def main():
    secrets=json.loads(Path('/data/secrets.json').read_text())
    store=Redis(host='127.0.0.1',password=secrets['REDIS_PASSWORD'])
    server=http.server.ThreadingHTTPServer(('127.0.0.1',18766),Fixture)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    client=AsyncJackett('fixture',base_url='http://127.0.0.1:18766',max_concurrency=1,store=store)
    indexes=['test-slow','test-fast']
    key=client.acceleration.cache_key(client.base_url,'Ubuntu',indexes,False)
    store.delete(key);store.hdel(PREFIX+'metrics',*indexes)
    async def measure():
        started=time.monotonic(); first=None; items=[]
        async for row in client.search('Ubuntu',indexes=indexes):
            items.append(row)
            if row.get('Title') and first is None: first=time.monotonic()-started
        return first,items
    try:
        baseline,_=await measure()
        assert seen[:2]==indexes,seen
        seen.clear();store.delete(key)
        priority,_=await measure()
        assert seen==list(reversed(indexes)),seen
        assert priority<baseline/2,(baseline,priority)
        seen.clear()
        cached,rows=await measure()
        assert rows[0]['__type']=='cache_status' and rows[1]['SearchCached']
        assert cached<0.05,cached
        assert 590<store.ttl(key)<=600
        # Verify the actual Lua retention bound, not just the unit-store substitute.
        for i in range(20):
            await client.acceleration.write(PREFIX+'fixture:'+str(i),{'source':{'time':time.time(),'rows':[]}})
        assert store.zcard(PREFIX+'queries')<=16
        print(json.dumps({'controlled_first_result_ms':round(baseline*1000,2),'prioritized_first_result_ms':round(priority*1000,2),'cached_first_result_ms':round(cached*1000,2),'all_sources_searched':True,'redis_cache_bound_verified':True}))
    finally:
        server.shutdown()
        keys=[key]+[PREFIX+'fixture:'+str(i) for i in range(20)]
        store.delete(*keys);store.zrem(PREFIX+'queries',*keys);store.hdel(PREFIX+'metrics',*indexes)

asyncio.run(main())
