# Disposable-container hook, appended only to its writable preview module.
# Connect the local seed explicitly; do not depend on public DHT/LSD discovery.
_original_preview_create=TorrentPreviews.create
_original_download_add=LibTorrentSession.add_torrent

def _fixture_peer():
    import json
    from urllib.parse import urlsplit,parse_qs
    row=json.loads(Path('/data/torrent-preview-browser-row.json').read_text())
    address=parse_qs(urlsplit(row['MagnetUri']).query)['x.pe'][0]
    host,port=address.rsplit(':',1)
    return row['InfoHash'],(host,int(port))

def _fixture_create(self,user,magnet):
    token=_original_preview_create(self,user,magnet)
    key,peer=_fixture_peer()
    if self.leases[token]['hash']==key:self.leases[token]['handle'].connect_peer(peer)
    return token

def _fixture_add(self,*args,**kwargs):
    wrapper=_original_download_add(self,*args,**kwargs)
    key,peer=_fixture_peer()
    if wrapper.info_hash==key:wrapper.handle.connect_peer(peer)
    return wrapper

TorrentPreviews.create=_fixture_create
LibTorrentSession.add_torrent=_fixture_add
