# Disposable-only source-state fixture. Never included in the production image.
# Separate live-provider tests cover actual MovieBox resolution and media bytes.
_original_lookup=lookup
_fixture_file=__import__('pathlib').Path('/downloads/playback-fixtures/tracks.mp4')
_fixture_size=_fixture_file.stat().st_size

async def lookup(title,year,kind,season=0,episode=0):
    from shared.modules.online_sources import normalized
    if normalized(title)=='walle' and year==2008 and kind=='movie':
        return [{'id':'fixture-'+str(i),'provider':'Fixture','label':'Controlled MP4','height':height,'quality':str(height)+'p','size':_fixture_size,'format':'mp4','url':'https://cdn.hakunaymatata.com/fixture-'+str(i)+'.mp4','referer':'https://mzfi.me/fixture'} for i,height in enumerate([480,720])]+[{'id':'fixture-unavailable','provider':'Fixture','label':'Unavailable source','height':360,'quality':'360p','size':_fixture_size,'format':'mp4','url':'https://cdn.hakunaymatata.com/unavailable.mp4','referer':'https://mzfi.me/fixture'}]
    return await _original_lookup(title,year,kind,season,episode)

class _FixtureBytes(httpx.AsyncByteStream):
    def __init__(self,start,end):self.start=start;self.end=end
    async def __aiter__(self):
        with _fixture_file.open('rb') as file:
            file.seek(self.start);remaining=self.end-self.start+1
            while remaining:
                data=file.read(min(65536,remaining));remaining-=len(data);yield data

def _fixture_upstream(request):
    if 'unavailable' in request.url.path:raise httpx.ConnectTimeout('Controlled unavailable source')
    match=re.fullmatch(r'bytes=(\d+)-(\d+)',request.headers['range']);start,end=map(int,match.groups())
    return httpx.Response(206,headers={'Content-Range':f'bytes {start}-{end}/{_fixture_size}'},stream=_FixtureBytes(start,end))

def open_media_client():
    return httpx.AsyncClient(transport=httpx.MockTransport(_fixture_upstream))

redis.delete('online:sources:v2:tt0910970:movie:0:0')
