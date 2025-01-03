import threading
import traceback
import time


class TorrentCallBack:
    def __init__(self):
        self.callback_thread_running = False
        self.lock = threading.Lock()

    def set_callback(self, callback, callback_interval=1):
        """Set callback function

        Args:
            callback (function): callback function
            callback_interval (int, optional): callback interval in seconds. Defaults to 1.
        """
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
            t = threading.Thread(target=self.handle_callback)
            t.start()

    def stop_callback(self):
        self.callback_thread_running = False

    def handle_callback(self):
        """Handle callback, this can be used to update to db in the background"""
        while self.callback_thread_running:
            props = self.props()

            if not props.ok:
                time.sleep(1)
                continue

            try:
                with self.lock:
                    self.callback(props)
            except Exception:
                time.sleep(1)
                traceback.print_exc()

            if props.is_finished:
                self.callback_thread_running = False

            time.sleep(self.callback_interval)
