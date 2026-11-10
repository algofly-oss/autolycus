"""Local swarm: metadata browsing must not request payload or expose other users."""
import os,tempfile,time
from pathlib import Path
import libtorrent as lt
from shared.modules.torrent_preview import TorrentPreviews,PreviewError
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);seed_root=root/'seed';(seed_root/'Course').mkdir(parents=True)
 files=lt.file_storage()
 for name in ['Episode.01.mp4','Episode.02.mp4','notes.txt']:
  data=os.urandom(512*1024);(seed_root/'Course'/name).write_bytes(data);files.add_file('Course/'+name,len(data))
 creator=lt.create_torrent(files,16384);lt.set_piece_hashes(creator,str(seed_root));ti=lt.torrent_info(lt.bencode(creator.generate()))
 seed=lt.session({'listen_interfaces':'127.0.0.1:0','enable_dht':False,'enable_lsd':False,'enable_upnp':False,'enable_natpmp':False})
 seed.add_torrent({'ti':ti,'save_path':str(seed_root),'flags':lt.torrent_flags.seed_mode})
 manager=TorrentPreviews(root/'preview');token=None
 try:
  token=manager.create('alice',lt.make_magnet_uri(ti));manager.engine.session.apply_settings({'enable_dht':False,'enable_lsd':False})
  manager.leases[token]['handle'].connect_peer(('127.0.0.1',seed.listen_port()))
  deadline=time.monotonic()+20
  while time.monotonic()<deadline:
   status=manager.status('alice',token)
   if status['status']=='ready':break
   time.sleep(.1)
  else:raise AssertionError('Local peer metadata exchange timed out')
  assert len(status['files'])==3,status
  assert sum(f['video'] for f in status['files'])==2
  spec=manager.download_spec('alice',token,[status['files'][0]['index']])
  restored=lt.torrent_info(spec['metadata']);assert restored.num_files()==manager.leases[token]['handle'].torrent_file().num_files()
  assert spec['indices']==[status['files'][0]['index']]
  time.sleep(1);status=manager.status('alice',token)
  assert status['payload_downloaded']==0,status
  assert all(p==0 for p in manager.leases[token]['handle'].get_file_priorities())
  assert manager.create('alice',lt.make_magnet_uri(ti))==token
  try:manager.status('bob',token)
  except PreviewError:pass
  else:raise AssertionError('Cross-account preview access')
  manager.close('alice',token)
  assert token not in manager.leases
  print('PASS: real peer metadata exchange; 3-file listing; video classification; zero payload bytes; zero file priorities; same-account reuse; cross-account denial; explicit close')
 finally:manager.shutdown()
