"""Local swarm: only selected bytes, including native restart and a fresh session."""
import hashlib,os,tempfile,time
from pathlib import Path
import libtorrent as lt
from shared.modules.libtorrentx import LibTorrentSession

def wait(predicate,seconds=25):
 deadline=time.monotonic()+seconds
 while time.monotonic()<deadline:
  if predicate():return
  time.sleep(.1)
 raise AssertionError('Local selected download timed out')

with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);seed_root=root/'seed';(seed_root/'Course').mkdir(parents=True)
 files=lt.file_storage();payloads=[]
 for name in ['unused.bin','wanted.mp4']:
  data=os.urandom(2*1024*1024);payloads.append(data);(seed_root/'Course'/name).write_bytes(data);files.add_file('Course/'+name,len(data))
 creator=lt.create_torrent(files,16384);lt.set_piece_hashes(creator,str(seed_root));encoded=lt.bencode(creator.generate());ti=lt.torrent_info(encoded);magnet=lt.make_magnet_uri(ti)
 settings={'listen_interfaces':'127.0.0.1:0','enable_dht':False,'enable_lsd':False,'enable_upnp':False,'enable_natpmp':False}
 seed=lt.session(settings);seed.add_torrent({'ti':ti,'save_path':str(seed_root),'flags':lt.torrent_flags.seed_mode})
 session=LibTorrentSession();session.session.apply_settings(settings)
 wrapper=session.add_torrent(magnet,str(root/'download'),file_indices=[1],metadata=ti,download_speed=128*1024)
 wrapper.handle.connect_peer(('127.0.0.1',seed.listen_port()))
 wait(lambda:wrapper.handle.status().total_payload_download>0)
 wrapper.stop();wrapper.start();wrapper.handle.connect_peer(('127.0.0.1',seed.listen_port()))
 assert wrapper.handle.get_file_priorities()==[0,1]
 wrapper.handle.set_download_limit(0)
 wait(lambda:wrapper.handle.is_finished())
 target=Path(wrapper.save_dir)/'Course/wanted.mp4';assert hashlib.sha256(target.read_bytes()).digest()==hashlib.sha256(payloads[1]).digest()
 unused=Path(wrapper.save_dir)/'Course/unused.bin';assert not unused.exists() or unused.stat().st_size==0
 props=wrapper.props().asdict();assert props['selected_files']==[1] and props['total_bytes']==len(payloads[1]) and props['downloaded_bytes']==len(payloads[1]),props
 session._stop(wrapper.info_hash)
 resumed=LibTorrentSession();resumed.session.apply_settings(settings)
 second=resumed.add_torrent(magnet,str(root/'download'),file_indices=[1],metadata=lt.torrent_info(encoded))
 second.handle.connect_peer(('127.0.0.1',seed.listen_port()));wait(lambda:second.handle.is_finished())
 assert second.handle.get_file_priorities()==[0,1]
 assert second.props().total_bytes==len(payloads[1]);resumed._stop(second.info_hash)
 print('PASS: selected file SHA-256 exact; unselected file absent; chosen-only progress totals; native stop/start and fresh-session resume preserve priorities')
