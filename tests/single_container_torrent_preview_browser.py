"""Run with container Python: keep a local swarm alive while Selenium uses the UI."""
import json,os,subprocess,tempfile,time,shutil,secrets
from pathlib import Path
import libtorrent as lt
source=Path('/downloads/playback-fixtures/tracks.mp4');assert source.exists()
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);(root/'Course').mkdir();files=lt.file_storage()
 for name in ['Episode.02.mp4','Episode.10.mp4','notes.txt']:
  target=root/'Course'/name
  if name.endswith('.mp4'):shutil.copyfile(source,target)
  else:target.write_text('Course notes '+secrets.token_hex(8)+'\n')
  files.add_file('Course/'+name,target.stat().st_size)
 creator=lt.create_torrent(files,16384);lt.set_piece_hashes(creator,str(root));ti=lt.torrent_info(lt.bencode(creator.generate()))
 seed=lt.session({'listen_interfaces':'127.0.0.1:0','enable_dht':False,'enable_lsd':False,'enable_upnp':False,'enable_natpmp':False});seed.add_torrent({'ti':ti,'save_path':str(root),'flags':lt.torrent_flags.seed_mode})
 row={'Title':'Course preview fixture','MagnetUri':lt.make_magnet_uri(ti)+'&x.pe=127.0.0.1:'+str(seed.listen_port()),'InfoHash':str(ti.info_hashes().v1),'Seeders':1,'Size':source.stat().st_size*2,'Tracker':'Local fixture','SearchResultKey':'local-course-preview','Category':[{'ID':8000}]}
 Path('/data/torrent-preview-browser-row.json').write_text(json.dumps(row))
 result=subprocess.run(['/opt/flare-python/bin/python','/tmp/torrent-preview-driver.py'],timeout=180)
 raise SystemExit(result.returncode)
