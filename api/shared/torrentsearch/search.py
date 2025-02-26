import requests
import inspect
import re
# from bs4 import BeautifulSoup
import json
import traceback
import threading
import os
from os.path import join, dirname
import time
import concurrent.futures

from .tpb import TPB
from .x1337 import X1337
from .yify import YIFY
from .imdb import IMDB
import textwrap


class Thread(threading.Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None):
        threading.Thread.__init__(self, group, target, name, args, kwargs, daemon=daemon)
        self._return = None

    def run(self):
        if self._target is not None:
            self._return = self._target(*self._args, **self._kwargs)

    def join(self, timeout=None):
        threading.Thread.join(self, timeout=timeout)
        return self._return


class TorrentSearch:
    def __init__(self):
        self.services = {
            "tpb": TPB(),
            "x1337": X1337()
        }
        self.imdb = IMDB()
        self.search_timeout = 15  # 15 seconds timeout for search operations

    def search(self, keyword, max_results=None, is_retry=False):
        if not keyword: 
            return []
        
        threads = []
        results = []
        
        # Start all search threads
        for s in self.services.values():
            t = Thread(target=s.search, args=(keyword,))
            t.daemon = True  # Make threads daemon so they don't block program exit
            t.start()
            threads.append(t)
        
        # Wait for threads with timeout
        start_time = time.time()
        for t in threads:
            remaining_time = max(0, self.search_timeout - (time.time() - start_time))
            try:
                thread_results = t.join(timeout=remaining_time)
                if thread_results:
                    results.extend(thread_results)
            except Exception as e:
                print(f"Error in search thread: {str(e)}")
                continue
        
        # Sort results if we have any
        if results:
            results.sort(key=lambda k: k.get('source'))
        
        return results
    
    def get_magnet(self, r):
        try:
            return self.services.get(r['source'].lower()).get_magnet(r)
        except Exception as e:
            print(f"Error getting magnet: {str(e)}")
            return None
    
    def get_details(self, r):
        try:
            r.update({"magnet": self.get_magnet(r)})
            details = self.imdb.get_details(r.get("imdb", {}).get("url"))
            details["torrent_name"] = r["name"]
            if 'url' in details:
                del details['url']
            r.update(details)
            return r
        except Exception as e:
            print(f"Error getting details: {str(e)}")
            return r