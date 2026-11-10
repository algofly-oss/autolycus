"""Short-lived, account-confined torrent metadata/preview leases.

Uses the installed libtorrent engine, not a second download service. Metadata
leases keep upload_mode enabled so inspecting contents requests no file pieces.
"""
import os
from pathlib import Path,PurePosixPath
import secrets
import shutil
import threading
import time
import libtorrent as lt
from .libtorrentx import LibTorrentSession

MAX_FILES=4000
TTL=15*60
BUDGET=2*1024**3

class PreviewError(Exception):pass

class TorrentPreviews:
    def __init__(self,root='/downloads/.previews'):
        self.root=Path(root)
        self.lock=threading.RLock();self.leases={};self.engine=None;self.stopping=False
        self.worker=None

    def _start(self):
        if self.engine is not None:return
        if self.root.is_symlink():raise PreviewError('Invalid preview directory')
        self.root.mkdir(parents=True,exist_ok=True)
        # This namespace contains only abandoned temporary leases from earlier processes.
        for old in self.root.iterdir():
            if old.is_dir() and not old.is_symlink():shutil.rmtree(old)
        self.engine=LibTorrentSession()
        self.engine.session.apply_settings({'connections_limit':80,'close_redundant_connections':False,'max_metadata_size':4*1024*1024,'aio_threads':1,'hashing_threads':1,'max_queued_disk_bytes':1024*1024,'enable_upnp':False,'enable_natpmp':False,'listen_interfaces':'0.0.0.0:0','send_buffer_watermark':65536,'send_buffer_low_watermark':16384,'download_rate_limit':8*1024*1024,'upload_rate_limit':256*1024})
        self.engine.session.apply_settings({'alert_mask':self.engine.session.get_settings()['alert_mask']|lt.alert.category_t.connect_notification})
        if self.worker is None:
            self.worker=threading.Thread(target=self._maintain,daemon=True,name='torrent-preview-cleanup');self.worker.start()

    def create(self,user,magnet):
        if not isinstance(magnet,str) or len(magnet)>16384 or not magnet.startswith('magnet:?'):raise PreviewError('A valid magnet is required')
        try:params=lt.parse_magnet_uri(magnet)
        except Exception:raise PreviewError('Invalid magnet')
        info_hash=str(params.info_hashes.v1) if params.info_hashes.has_v1() else str(params.info_hashes.v2)
        with self.lock:
            for token,lease in self.leases.items():
                if lease['hash']==info_hash:
                    if lease['user']!=str(user):raise PreviewError('This torrent is already being previewed. Please try again later.')
                    lease['accessed']=time.monotonic();return token
            if len(self.leases)>=4 or sum(v['user']==str(user) for v in self.leases.values())>=2:raise PreviewError('Close an existing torrent preview first')
            self._start();token=secrets.token_hex(24);folder=self.root/token;folder.mkdir()
            params.save_path=str(folder)
            params.flags |= lt.torrent_flags.upload_mode
            params.flags &= ~lt.torrent_flags.auto_managed
            params.flags &= ~lt.torrent_flags.paused
            params.file_priorities=[0]*MAX_FILES
            try:handle=self.engine.session.add_torrent(params)
            except Exception:
                shutil.rmtree(folder);raise PreviewError('Could not start metadata lookup')
            self.leases[token]={'user':str(user),'hash':info_hash,'handle':handle,'folder':folder,'created':time.monotonic(),'accessed':time.monotonic(),'files':None,'magnet':magnet,'io_lock':threading.Lock(),'requested':set(),'active_file':None,'last_range':0,'metadata_peers':[]}
            self.engine.install_tracker_routes(handle)
            return token

    def _pump(self):
        for alert in self.engine.pump_alerts():
            if isinstance(alert,lt.peer_connect_alert):
                for lease in self.leases.values():
                    if alert.handle==lease['handle'] and len(lease['metadata_peers'])<8 and alert.ip not in lease['metadata_peers']:
                        lease['metadata_peers'].append(alert.ip)

    def _lease(self,user,token,touch=True):
        lease=self.leases.get(token)
        if not lease or lease['user']!=str(user):raise PreviewError('Preview expired or not found')
        if touch:lease['accessed']=time.monotonic()
        return lease

    def _catalog(self,lease):
        if lease['files'] is not None:return lease['files']
        handle=lease['handle']
        if not handle.has_metadata():return None
        ti=handle.torrent_file();storage=ti.files()
        if storage.num_files()>MAX_FILES or ti.num_pieces()>2_000_000:raise PreviewError('Torrent is too large to preview')
        files=[]
        for index in range(storage.num_files()):
            path=storage.file_path(index);parts=PurePosixPath(path).parts
            if not parts or path.startswith('/') or '\\' in path or any(p in ('..','.') for p in parts) or len(parts)>16 or len(path)>4096 or storage.file_flags(index)&lt.file_storage.flag_symlink:raise PreviewError('Torrent contains unsafe file paths')
            if storage.file_flags(index)&lt.file_storage.flag_pad_file:continue
            files.append({'index':index,'path':path,'name':parts[-1],'size':storage.file_size(index),'previewable':ti.piece_length()<=32*1024*1024,'video':Path(path).suffix.lower() in {'.mp4','.mkv','.webm','.avi','.mov','.m4v','.ts','.m2ts'}})
        handle.prioritize_files([0]*storage.num_files())
        self._pump()
        for peer in handle.get_peer_info():
            if len(lease['metadata_peers'])<8 and peer.ip not in lease['metadata_peers']:lease['metadata_peers'].append(peer.ip)
        lease['files']=files
        return files

    def status(self,user,token):
        with self.lock:
            lease=self._lease(user,token)
            try:files=self._catalog(lease)
            except PreviewError:
                self._close(token);raise
            status=lease['handle'].status()
            if files is None and time.monotonic()-lease['created']>60:
                self._close(token);raise PreviewError('No peers supplied torrent metadata. Try again later.')
            return {'id':token,'status':'ready' if files is not None else 'metadata','name':lease['handle'].torrent_file().name() if files is not None else status.name,'files':files or [],'peers':status.num_peers,'expires_in':TTL,'preview_budget':BUDGET,'payload_downloaded':status.total_payload_download}

    def file_info(self,user,token,index):
        with self.lock:
            lease=self._lease(user,token);files=self._catalog(lease)
            file=next((f for f in files or [] if f['index']==index),None)
            if not file or not file['video'] or file['size']<=0:raise PreviewError('Choose a playable video file')
            if not file['previewable']:raise PreviewError('This torrent uses oversized pieces. Download the file to play it.')
            return dict(file)

    def suspend(self,user,token):
        with self.lock:
            lease=self._lease(user,token,False)
            if not lease['io_lock'].acquire(blocking=False):return
            try:
                handle=lease['handle'];handle.set_flags(lt.torrent_flags.upload_mode)
                handle.clear_piece_deadlines()
                for piece in lease['requested']:handle.piece_priority(piece,0)
                lease['requested']=set();lease['last_range']=0
            finally:lease['io_lock'].release()

    def read(self,user,token,index,start,length,cancelled=None):
        file=self.file_info(user,token,index)
        if type(start) is not int or type(length) is not int or start<0 or length<1 or length>256*1024 or start+length>file['size']:raise PreviewError('Invalid preview range')
        with self.lock:lease=self._lease(user,token)
        waiting_until=time.monotonic()+20
        while not lease['io_lock'].acquire(timeout=.05):
            if cancelled is not None and cancelled.is_set():raise PreviewError('Preview cancelled')
            with self.lock:
                if token not in self.leases:raise PreviewError('Preview expired')
            if time.monotonic()>waiting_until:raise PreviewError('Preview is busy. Try again.')
        try:
            handle=lease['handle'];ti=handle.torrent_file();storage=ti.files();deadline=time.monotonic()+20
            def check():
                if cancelled is not None and cancelled.is_set():raise PreviewError('Preview cancelled')
                with self.lock:
                    if token not in self.leases or not handle.is_valid():raise PreviewError('Preview expired')
                    lease['accessed']=time.monotonic();lease['last_range']=time.monotonic()
                if time.monotonic()>deadline:raise PreviewError('Peers could not supply this part of the video in time')
            check()
            if lease['active_file']!=index:
                handle.set_flags(lt.torrent_flags.upload_mode)
                priorities=[1 if i==index else 0 for i in range(storage.num_files())]
                handle.prioritize_files(priorities)
                while handle.get_file_priorities()!=priorities:
                    check();time.sleep(.05)
                handle.prioritize_pieces([0]*ti.num_pieces())
                lease['requested']=set();lease['active_file']=index
            offset=storage.file_offset(index);piece_size=ti.piece_length()
            first=(offset+start)//piece_size;last=(offset+start+length-1)//piece_size
            ahead=min(offset+file['size']-1,offset+start+length+2*1024*1024-1)//piece_size
            requested=set(range(first,ahead+1))
            for piece in lease['requested']-requested:handle.piece_priority(piece,0)
            for piece in requested-lease['requested']:handle.piece_priority(piece,1)
            lease['requested']=requested;handle.clear_piece_deadlines()
            for piece in range(first,last+1):handle.set_piece_deadline(piece,(piece-first)*100)
            handle.unset_flags(lt.torrent_flags.upload_mode);handle.resume()
            if not handle.status().num_peers:
                for peer in lease['metadata_peers']:handle.connect_peer(peer)
                handle.force_reannounce();handle.force_dht_announce()
            while not all(handle.have_piece(piece) for piece in range(first,last+1)):
                check();time.sleep(.05)
            check()
            path=lease['folder']/file['path']
            if path.is_symlink() or lease['folder'].resolve() not in path.resolve().parents:raise PreviewError('Invalid preview file')
            # have_piece guarantees verified, completely written disk data.
            with path.open('rb') as stream:stream.seek(start);data=stream.read(length)
            if len(data)!=length:raise PreviewError('Incomplete preview range')
            return data
        except (OSError,RuntimeError) as error:
            raise PreviewError('Preview data is no longer available') from error
        finally:
            lease['io_lock'].release()
            if cancelled is not None and cancelled.is_set():
                try:self.suspend(user,token)
                except PreviewError:pass

    def handoff(self,user,token):
        with self.lock:
            lease=self._lease(user,token)
            lease['handle'].pause()
            # Drain the native command queue so its peer disconnects precede
            # connections from the permanent download's separate session.
            self.engine.session.get_torrents()

    def download_spec(self,user,token,indices):
        with self.lock:
            lease=self._lease(user,token);files=self._catalog(lease)
            if files is None:raise PreviewError('Torrent metadata is not ready yet')
            allowed={file['index'] for file in files}
            if not indices or len(indices)>MAX_FILES or any(type(i) is not int or i not in allowed for i in indices):raise PreviewError('Select valid files to download')
            ti=lease['handle'].torrent_file()
            if not ti.info_hashes().has_v1():raise PreviewError('This download currently requires a v1 or hybrid torrent')
            encoded=lt.bencode(lt.create_torrent(ti).generate())
            if len(encoded)>4*1024*1024:raise PreviewError('Torrent metadata exceeds the download limit')
            return {'magnet':lease['magnet'],'metadata':encoded,'indices':sorted(set(indices)),'info_hash':str(ti.info_hashes().v1)}

    def _close(self,token):
        lease=self.leases.pop(token,None)
        if lease:
            self.engine.session.remove_torrent(lease['handle'],lt.options_t.delete_files)
            # Deletion is performed asynchronously by libtorrent; do not race it
            # by recreating this random directory for another lease.

    def close(self,user,token):
        with self.lock:
            self._lease(user,token,False);self._close(token)

    def _maintain(self):
        while not self.stopping:
            time.sleep(1)
            with self.lock:
                if self.engine is None:continue
                self._pump()
                for token,lease in list(self.leases.items()):
                    expired=time.monotonic()-lease['accessed']>TTL
                    timed_out=lease['files'] is None and time.monotonic()-lease['created']>90
                    if expired or timed_out:self._close(token)
                    elif lease['last_range'] and time.monotonic()-lease['last_range']>3:self.suspend(lease['user'],token)
                downloaded=sum(lease['handle'].status().total_payload_download for lease in self.leases.values())
                # A conservative traffic budget bounds sparse-file allocation too;
                # reserve room for one maintenance interval and queued disk writes.
                if downloaded>BUDGET-16*1024*1024 and self.leases:
                    oldest=min(self.leases,key=lambda token:self.leases[token]['accessed'])
                    self._close(oldest)
                if not self.leases:self.engine=None

    def shutdown(self):
        with self.lock:
            self.stopping=True
            for token in list(self.leases):self._close(token)
            self.engine=None

previews=TorrentPreviews()
