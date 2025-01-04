import threading
import traceback
import time
import asyncio


class TorrentCallBack:
    def __init__(self):
        self.callback_thread_running = False
        self.lock = threading.Lock()
        self.stop_event = asyncio.Event()

    def set_callback(self, callback, callback_interval=1, user_id=None):
        """Set callback function

        Args:
            callback (function): callback function
            callback_interval (int, optional): callback interval in seconds. Defaults to 1.
        """
        self.user_id = user_id
        self.callback = callback
        self.callback_interval = callback_interval
        self.start_callback()

    def remove_callback(self):
        """Remove callback function"""
        self.callback = None
        self.callback_thread_running = False

    def start_callback(self):
        if self.callback and (not self.callback_thread_running):
            self.callback_thread_running = True
            thread = threading.Thread(target=self.handle_callback)
            thread.daemon = True
            thread.start()

    def stop_callback(self):
        self.callback_thread_running = False

    def handle_callback(self):
        """Handle callback, this can be used to update to db in the background"""
        while self.callback_thread_running:
            props = self.props()

            if not props.ok:
                time.sleep(1)
                continue

            key = f"{self.user_id}/{self.info_hash}/stop"
            if self.session.redis.get(key) == b"1":
                self.session.redis.delete(key)
                self.callback(self.props(paused=True))
                self.stop()
                break

            try:
                with self.lock:
                    self.callback(props)
            except Exception:
                time.sleep(1)
                traceback.print_exc()

            if props.is_finished:
                self.callback_thread_running = False

            time.sleep(self.callback_interval)
