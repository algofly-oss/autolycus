import os
import re
import weakref
from urllib.parse import urlsplit
from .tracker_gateway import tracker_gateway, public_http_tracker
import libtorrent as lt
from .magnet import MagnetUtils
from .handle import TorrentHandleWrapper


class LibTorrentSession(MagnetUtils):
    def __init__(self, redis=None):
        super(LibTorrentSession, self).__init__()
        self.session = lt.session()
        self.redis = redis

        settings = self.session.get_settings()
        settings.update(
            {
                "alert_mask": lt.alert.category_t.error_notification | lt.alert.category_t.status_notification | lt.alert.category_t.tracker_notification,
                "alert_queue_size": 512,
                "tracker_receive_timeout": 30,
                "tracker_completion_timeout": 45,
                "connections_limit": 500,
                "enable_outgoing_utp": True,
                "enable_incoming_utp": True,
            }
        )

        (
            self.session.apply_settings(settings)
            if hasattr(self.session, "apply_settings")
            else self.session.set_settings(settings)
        )

        self.handles = {}
        self._tracker_tokens = []
        self._tracker_routes = {}
        self._gateway = None
        self._native_health = {}

    def install_tracker_routes(self, handle):
        if os.getenv("TOR_TRACKER_FALLBACK", "1") == "0":
            return
        # Preserve private-tracker announces and unknown magnet metadata on the
        # direct route. Only confirmed public torrents may use the Tor fallback.
        allow_tor = handle.has_metadata() and not handle.torrent_file().priv()
        changed = False
        trackers = handle.trackers()
        for tracker in trackers[:64]:
            url = tracker["url"]
            if url in self._tracker_routes:
                token, _ = self._tracker_routes[url]
                if self._gateway and token in self._gateway.routes:
                    self._gateway.routes[token].allow_tor = allow_tor
                continue
            if not public_http_tracker(url):
                continue
            if self._gateway is None:
                self._gateway = tracker_gateway()
                weakref.finalize(self, self._gateway.remove, self._tracker_tokens)
            registered = self._gateway.register(url, allow_tor)
            if registered:
                token, local_url = registered
                self._tracker_tokens.append(token)
                self._tracker_routes[local_url] = (token, url)
                tracker["url"] = local_url
                changed = True
        if changed:
            handle.replace_trackers(trackers)

    def tracker_health(self):
        if self._gateway is None:
            return list(self._native_health.values())
        return [*self._native_health.values(), *[self._gateway.routes[token].health() for token in self._tracker_tokens
                if token in self._gateway.routes]]

    def pump_alerts(self):
        alerts=self.session.pop_alerts()
        for alert in alerts:
            if isinstance(alert, (lt.tracker_reply_alert, lt.tracker_error_alert)):
                url = getattr(alert, "url", "")
                if isinstance(url, str) and url not in self._tracker_routes and len(self._native_health)<128:
                    parsed=urlsplit(url)
                    self._native_health[url]={"host":parsed.hostname,"protocol":parsed.scheme,"route":"direct","status":"working" if isinstance(alert,lt.tracker_reply_alert) else "failed"}
            if isinstance(alert, lt.metadata_received_alert):
                self.install_tracker_routes(alert.handle)
        return alerts

    def _get_torrent_handle(self, info_hash):
        """Get torrent_handle from info_hash

        Args:
            info_hash (str): info_hash

        Returns:
            lt.torrent_handle: torrent_handle
        """

        for torrent_handle in self.session.get_torrents():
            if (
                str(torrent_handle.info_hashes().v1).strip().lower()
                == info_hash.strip().lower()
            ):
                return torrent_handle

    def _exist(self, info_hash):
        """Check if torrent exist in session

        Args:
            info_hash (str): info_hash

        Returns:
            bool: True if exist
        """

        return bool(self._get_torrent_handle(info_hash))

    def _get_info_hash(self, magnet):
        """Get info_hash from magnet uri or torrent_handle

        Args:
            magnet (str or lt.torrent_handle): magnet uri or torrent_handle

        Returns:
            str: info_hash
        """

        if isinstance(magnet, str):
            info_hash = re.findall(r"btih:.*", magnet)[0][5:45].lower()
            assert len(info_hash) == 40, "invalid magnet"
            return info_hash

        elif isinstance(magnet, lt.torrent_handle):
            return str(magnet.info_hashes().v1).lower()

    def _stop(self, handle):
        """Stop torrent

        Args:
            handle (str or lt.torrent_handle): info hash or torrent_handle

        Returns:
            bool: True if stopped
        """

        if isinstance(handle, str) and self._exist(handle):
            self.session.remove_torrent(self._get_torrent_handle(handle))
            self.handles.pop(handle, None)
            return True
        elif isinstance(handle, lt.torrent_handle):
            info_hash = self._get_info_hash(handle)
            self.session.remove_torrent(handle)
            self.handles.pop(info_hash, None)
            return True

    def _restart(self, magnet, save_dir, sequential=False, file_indices=None, metadata=None):
        """Add torrent to libtorrent session again

        Args:
            magnet (str): magnet link
            save_dir (str): download path
            sequential (bool, optional): download sequentially. Defaults to False.

        Returns:
            lt.torrent_handle: torrent_handle
        """

        info_hash = self._get_info_hash(magnet)
        if os.path.basename(save_dir) != info_hash:
            save_dir = os.path.realpath(os.path.join(save_dir, info_hash))
        os.makedirs(save_dir, exist_ok=True)

        handle = self._add_selected(magnet,save_dir,metadata,file_indices) if file_indices is not None else lt.add_magnet_uri(self.session, magnet, {"save_path": save_dir})
        self.install_tracker_routes(handle)
        handle.set_sequential_download(sequential)

        return handle

    def _add_selected(self,magnet,save_dir,metadata,indices):
        if metadata is None:raise ValueError("Selective downloads require validated metadata")
        count=metadata.num_files()
        if count>4000 or not indices or any(type(i) is not int or i<0 or i>=count for i in indices):raise ValueError("Invalid selected file indices")
        params=lt.parse_magnet_uri(magnet)
        params.ti=metadata;params.save_path=save_dir
        selected=set(indices);params.file_priorities=[1 if i in selected else 0 for i in range(count)]
        return self.session.add_torrent(params)

    def add_torrent(
        self,
        magnet,
        save_dir,
        sequential=False,
        callback=None,
        callback_interval=1,
        download_speed=0,
        file_indices=None,
        metadata=None,
    ):
        """Add magnet link or torrent file to libtorrent session

        Args:
            magnet (str): magnet link or torrent file
            save_dir (str): download path
            sequential (bool, optional): download sequentially. Defaults to False.
            callback (function, optional): callback function. Defaults to None.
            callback_interval (int, optional): callback interval. Defaults to 1.
            limit_download_speed (int, optional): limit download speed. Defaults to 0.

        Returns:
            TorrentHandleWrapper: TorrentHandleWrapper
        """

        torrent_info = metadata
        if magnet.strip().lower().endswith(".torrent"):
            if not os.path.exists(magnet):
                raise FileNotFoundError(f"{magnet} not found")
            torrent_info = lt.torrent_info(magnet)
            magnet = lt.make_magnet_uri(torrent_info)

        magnet = self._clean_magnet_uri(magnet)
        info_hash = self._get_info_hash(magnet)

        if info_hash in self.handles and self._exist(info_hash):
            return self.handles[info_hash]

        if os.path.basename(save_dir) != info_hash:
            save_dir = os.path.realpath(os.path.join(save_dir, info_hash))
        os.makedirs(save_dir, exist_ok=True)

        handle = self._add_selected(magnet,save_dir,torrent_info,file_indices) if file_indices is not None else (self.session.add_torrent({"ti": torrent_info, "save_path": save_dir}) if torrent_info else lt.add_magnet_uri(self.session, magnet, {"save_path": save_dir}))

        self.install_tracker_routes(handle)

        if sequential:
            handle.set_sequential_download(sequential)

        if download_speed:
            handle.set_download_limit(download_speed)  # B/s

        self.handles[info_hash] = TorrentHandleWrapper(
            session=self,
            handle=handle,
            magnet=magnet,
            save_dir=save_dir,
            sequential=sequential,
            callback=callback,
            callback_interval=callback_interval,
            file_indices=file_indices,
            metadata=torrent_info,
        )

        return self.handles[info_hash]
