import time
from .callback import TorrentCallBack


class Utils:
    @staticmethod
    def format_bytes(b):
        """Convert byte to human readable format

        Args:
            b (int): b in bytes

        Returns:
            str: human readable b
        """

        if b > 1024**3:
            return f"{round(b / 1024 ** 3, 2)} GB"
        elif b > 1024**2:
            return f"{round(b / 1024 ** 2, 2)} MB"
        elif b > 1024:
            return f"{round(b / 1024, 2)} KB"
        else:
            return f"{round(b, 2)} B"


class TorrentProps(Utils):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return str(self.__dict__)

    @property
    def string(self):
        """Get torrent properties as string

        Returns:
            str: torrent properties
        """
        props = [
            self.__dict__.get("name", "Unknown"),
            self.format_bytes(self.__dict__.get("downloaded_bytes", 0))
            + "/"
            + self.format_bytes(self.__dict__.get("total_bytes", 0)),
            self.format_bytes(self.__dict__.get("download_speed", 0)) + "/s",
            str(self.__dict__.get("num_seeds", 0)) + " Seeds",
            str(self.__dict__.get("progress", 0)) + "%",
        ]

        return " - ".join(props)

    def asdict(self):
        """Get torrent properties as dict"""
        return self.__dict__


class TorrentHandleWrapper(TorrentCallBack, Utils):
    def __init__(
        self,
        session,
        handle,
        magnet,
        save_dir,
        sequential,
        callback=None,
        callback_interval=1,
    ):
        TorrentCallBack.__init__(self)

        self.session = session
        self.handle = handle
        self.magnet = magnet
        self.save_dir = save_dir
        self.sequential = sequential
        self.info_hash = str(self.handle.status().info_hash).lower()

        self.callback = callback
        self.callback_interval = callback_interval
        self.start_callback()

    def props(self):
        """Get torrent properties

        Returns:
            dict: torrent properties
        """

        try:
            s = self.handle.status()
            name = self.handle.name() or "Unknown"
        except Exception as e:
            return TorrentProps(ok=False)

        return TorrentProps(
            name=name,
            info_hash=self.info_hash,
            download_speed=s.download_rate + 1,
            downloaded_bytes=s.total_wanted_done,
            is_finished=self.handle.is_finished(),
            is_paused=s.paused,
            num_connections=s.num_connections,
            num_peers=s.num_peers,
            num_seeds=s.num_seeds,
            num_trackers=len(self.handle.trackers()),
            progress=int(s.progress * 100),
            queue_position=s.queue_position,
            total_bytes=s.total_wanted,
            upload_speed=s.upload_rate,
            save_dir=s.save_path,
            ok=(name != "Unknown"),
        )

    def stop(self):
        """Stop torrent download

        Returns:
            bool: True if stopped
        """

        self.stop_callback()
        time.sleep(max((self.callback_interval or 1), 1))
        return self.session._stop(self.info_hash)

    def start(self):
        """Start torrent download

        Returns:
            bool: True if started
        """

        self.handle = self.session._restart(self.magnet, self.save_dir, self.sequential)
        self.start_callback()

        if self.info_hash not in self.session.handles:
            self.session.handles[self.info_hash] = self

        return self

    def limit_download_speed(self, speed):
        """Limit download speed

        Args:
            speed (int): speed in bytes, 0 for unlimited

        Returns:
            bool: True if limited
        """

        return self.handle.set_download_limit(speed)

    def __del__(self):
        self.remove_callback()
        if self.info_hash in self.session.handles:
            del self.session.handles[self.info_hash]

    def __repr__(self):
        return f"<{self.__class__.__name__} info_hash={self.info_hash}>"
