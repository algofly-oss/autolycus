"""Real local swarm: verified random ranges, seeking and idle suspension."""
import os,tempfile,time,threading
from pathlib import Path
import libtorrent as lt
from shared.modules.torrent_preview import TorrentPreviews,PreviewError
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);(root/'seed/Course').mkdir(parents=True);storage=lt.file_storage();data=os.urandom(16*1024*1024)
 for name in ['a.mp4','b.mp4']:
  (root/'seed/Course'/name).write_bytes(data);storage.add_file('Course/'+name,len(data))
 creator=lt.create_torrent(storage,65536);lt.set_piece_hashes(creator,str(root/'seed'));ti=lt.torrent_info(lt.bencode(creator.generate()))
 seed=lt.session({'listen_interfaces':'127.0.0.1:0','enable_dht':False,'enable_lsd':False,'enable_upnp':False,'enable_natpmp':False});seed.add_torrent({'ti':ti,'save_path':str(root/'seed'),'flags':lt.torrent_flags.seed_mode})
 manager=TorrentPreviews(root/'preview')
 try:
  token=manager.create('alice',lt.make_magnet_uri(ti));manager.engine.session.apply_settings({'enable_dht':False,'enable_lsd':False})
  handle=manager.leases[token]['handle'];handle.connect_peer(('127.0.0.1',seed.listen_port()))
  deadline=time.monotonic()+20
  while manager.status('alice',token)['status']!='ready':
   assert time.monotonic()<deadline;time.sleep(.1)
  time.sleep(5)
  assert handle.status().total_payload_download==0
  for index,start,length in [(0,7000,256*1024),(0,len(data)-100000,100000),(1,111111,65536)]:
   result=manager.read('alice',token,index,start,length)
   assert result==data[start:start+length],(index,start)
  assert handle.status().total_payload_download<12*1024*1024,handle.status().total_payload_download
  cancelled=threading.Event();cancelled.set()
  try:manager.read('alice',token,0,0,1024,cancelled)
  except PreviewError:pass
  else:raise AssertionError('Cancelled request continued')
  manager.suspend('alice',token);time.sleep(.2)
  assert handle.flags()&lt.torrent_flags.upload_mode
  assert not manager.leases[token]['requested']
  assert not any(handle.get_piece_priorities())
  cache=manager.leases[token]['folder'];manager.close('alice',token);deadline=time.monotonic()+5
  while any(p.is_file() and p.stat().st_blocks for p in cache.rglob('*')) and time.monotonic()<deadline:time.sleep(.1)
  assert not any(p.is_file() and p.stat().st_blocks for p in cache.rglob('*'))
  print('PASS: byte-exact cross-piece ranges, near-end seek and file switch; bounded partial payload instead of whole torrent; cancelled read rejected; suspension clears requests')
 finally:manager.shutdown()
