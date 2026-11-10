"""Local swarm only: fallback announces via a fake SOCKS hop, direct peer bytes."""
import hashlib
import os
from pathlib import Path
import select
import socket
import socketserver
import struct
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import libtorrent as lt
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'api'))
from shared.modules.libtorrentx import LibTorrentSession
from shared.modules.libtorrentx.tracker_gateway import tracker_gateway

def wait_for(predicate,seconds=20):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if predicate():return
        time.sleep(.1)
    raise AssertionError('Timed out waiting for local torrent fixture')

with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);seed_dir=root/'seed';seed_dir.mkdir();data=os.urandom(512*1024)
    (seed_dir/'payload.bin').write_bytes(data)
    files=lt.file_storage();files.add_file('payload.bin',len(data));creator=lt.create_torrent(files,16384)
    tracker='http://tracker.blocked.invalid/Case?Passkey=AbCd'
    creator.add_tracker(tracker);lt.set_piece_hashes(creator,str(seed_dir));encoded=lt.bencode(creator.generate())
    torrent_file=root/'fixture.torrent';torrent_file.write_bytes(encoded)
    seed=lt.session({'listen_interfaces':'127.0.0.1:0','enable_dht':False,'enable_lsd':False,'enable_upnp':False,'enable_natpmp':False})
    seed_handle=seed.add_torrent({'ti':lt.torrent_info(encoded),'save_path':str(seed_dir),'flags':lt.torrent_flags.seed_mode})
    announces=[];socks_targets=[]
    class Tracker(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            announces.append(self.path)
            payload=lt.bencode({b'interval':60,b'peers':socket.inet_aton('127.0.0.1')+struct.pack('!H',seed.listen_port())})
            self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
    server=ThreadingHTTPServer(('127.0.0.1',0),Tracker);threading.Thread(target=server.serve_forever,daemon=True).start()
    def exact(sock,n):
        result=b''
        while len(result)<n:
            piece=sock.recv(n-len(result))
            if not piece:raise EOFError()
            result+=piece
        return result
    class Socks(socketserver.BaseRequestHandler):
        def handle(self):
            client=self.request
            try:
                version,n=exact(client,2);exact(client,n);client.sendall(b'\5\0')
                version,command,_,kind=exact(client,4)
                assert command==1
                host=exact(client,exact(client,1)[0]).decode() if kind==3 else socket.inet_ntoa(exact(client,4))
                port=struct.unpack('!H',exact(client,2))[0];socks_targets.append((host,port))
                upstream=socket.create_connection(server.server_address)
                client.sendall(b'\5\0\0\1'+socket.inet_aton('127.0.0.1')+b'\0\0')
                with upstream:
                    while True:
                        ready,_,_=select.select([client,upstream],[],[],5)
                        if not ready:return
                        for source in ready:
                            chunk=source.recv(65536)
                            if not chunk:return
                            (upstream if source is client else client).sendall(chunk)
            except (OSError,EOFError):pass
    class SocksServer(socketserver.ThreadingTCPServer):allow_reuse_address=True;daemon_threads=True
    proxy=SocksServer(('127.0.0.1',0),Socks);threading.Thread(target=proxy.serve_forever,daemon=True).start()
    os.environ['TOR_TRACKER_PROXY']=f'socks5h://127.0.0.1:{proxy.server_address[1]}'
    session=LibTorrentSession();session.session.apply_settings({'enable_dht':False,'enable_lsd':False,'enable_upnp':False,'enable_natpmp':False,'listen_interfaces':'127.0.0.1:0'})
    wrapper=session.add_torrent(str(torrent_file),str(root/'download'))
    for token in session._tracker_tokens:tracker_gateway().routes[token].failures=1
    wrapper.handle.force_reannounce()
    def finished():session.pump_alerts();return wrapper.handle.status().is_seeding
    wait_for(finished)
    downloaded=Path(wrapper.save_dir)/'payload.bin'
    assert hashlib.sha256(downloaded.read_bytes()).digest()==hashlib.sha256(data).digest()
    assert socks_targets and all(host=='tracker.blocked.invalid' and port==80 for host,port in socks_targets),socks_targets
    assert announces and all('Passkey=AbCd' in url and 'info_hash=' in url for url in announces),announces
    assert session.tracker_health()[0]['route']=='tor',session.tracker_health()
    assert wrapper.handle.status().num_peers>=0
    session._stop(wrapper.info_hash);server.shutdown();proxy.shutdown()
    print('PASS: native libtorrent metadata-file download, HTTP tracker fallback through SOCKS, original case/binary announce fields, SHA-256 exact direct peer transfer')
