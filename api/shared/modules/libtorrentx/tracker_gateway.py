"""Bounded, loopback-only HTTP tracker bridge; peer bytes never enter this code."""
import ipaddress
import os
import secrets
import threading
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, urljoin
import libtorrent as lt
import requests

MAX_RESPONSE = 1024 * 1024


class TrackerRoute:
    def __init__(self, url, allow_tor=False):
        self.url, self.allow_tor = url, allow_tor
        self.lock = threading.Lock()
        self.failures = 0
        self.route = "direct"
        self.status = "pending"
        self.tor_until = 0
        self.last_probe = -1000

    def fetch(self, query, get=None, now=None):
        client = None
        if get is None:
            client = requests.Session()
            client.trust_env = False
            get = client.get
        now = time.monotonic() if now is None else now
        target = self.url + ("&" if "?" in self.url else "?") + query
        def request(proxy=None):
            current = target
            started = time.monotonic()
            for _ in range(4):
                if client is not None and not proxy:
                    try:
                        addresses=socket.getaddrinfo(urlsplit(current).hostname,urlsplit(current).port or (443 if urlsplit(current).scheme=="https" else 80),type=socket.SOCK_STREAM)
                        if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
                            return 502,b"",True
                    except OSError:
                        return 502,b"",True
                with get(current, stream=True, timeout=(6, 12 if proxy else 6),
                         proxies={"http": proxy, "https": proxy} if proxy else {"http": None, "https": None},
                         allow_redirects=False, headers={"User-Agent": "libtorrent/2.0 Autolycus", "Accept-Encoding": "identity"}) as response:
                    status = response.status_code
                    if status in (301,302,303,307,308):
                        destination=urljoin(current,response.headers.get("Location", ""))
                        if not public_http_tracker(destination):
                            return 502,b"",False
                        if not urlsplit(destination).query and urlsplit(current).query:
                            destination += "?"+urlsplit(current).query
                        current=destination
                        continue
                    if status != 200:
                        return status, b"", status in (403, 451, 502, 503, 504)
                    payload = bytearray()
                    for chunk in response.iter_content(16384):
                        payload.extend(chunk)
                        if len(payload) > MAX_RESPONSE or time.monotonic()-started>25:
                            return 502, b"", False
                    try:
                        decoded = lt.bdecode(bytes(payload))
                        if not isinstance(decoded, dict):
                            return 502, b"", True
                        return 200, bytes(payload), False
                    except Exception:
                        return 502, b"", True
            return 502,b"",False
        try:
            with self.lock:
                try:
                    if self.tor_until > now and self.allow_tor:
                        try:
                            status, payload, _ = request(os.getenv("TOR_TRACKER_PROXY", "socks5h://127.0.0.1:9050"))
                            if status == 200:
                                self.route, self.status = "tor", "tracker_error" if b"failure reason" in lt.bdecode(payload) else "working"
                                return status, payload
                        except requests.RequestException:
                            pass
                        self.tor_until = 0
                    status, payload, retry = request()
                except requests.RequestException:
                    status, payload, retry = 502, b"", True
                if status == 200:
                    self.failures = 0
                    self.route, self.status = "direct", "tracker_error" if b"failure reason" in lt.bdecode(payload) else "working"
                    return status, payload
                self.failures += 1
                self.route, self.status = "direct", "failed"
                if retry and self.allow_tor and self.failures >= 2 and now - self.last_probe >= 60:
                    self.last_probe = now
                    try:
                        status, payload, _ = request(os.getenv("TOR_TRACKER_PROXY", "socks5h://127.0.0.1:9050"))
                        if status == 200:
                            self.tor_until = now + 900
                            self.route, self.status = "tor", "tracker_error" if b"failure reason" in lt.bdecode(payload) else "working"
                            return status, payload
                    except requests.RequestException:
                        pass
                    self.status = "unreachable"
                return 502, lt.bencode({b"failure reason": b"Tracker temporarily unreachable"})
        finally:
            if client is not None:
                client.close()

    def health(self):
        return {"host": urlsplit(self.url).hostname, "protocol": urlsplit(self.url).scheme,
                "route": self.route, "status": self.status, "failures": self.failures}


def public_http_tracker(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            return False
        if parsed.hostname.lower() == "localhost" or parsed.hostname.lower().endswith((".localhost", ".local", ".onion")):
            return False
        try:
            return ipaddress.ip_address(parsed.hostname).is_global
        except ValueError:
            return "." in parsed.hostname
    except ValueError:
        return False


class BoundedServer(ThreadingHTTPServer):
    daemon_threads = True
    slots = threading.BoundedSemaphore(4)
    def get_request(self):
        request,address=super().get_request()
        request.settimeout(10)
        return request,address
    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise
    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


class TrackerGateway:
    def __init__(self):
        self.routes = {}
        self.lock = threading.Lock()
        gateway = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass  # Never log tracker URLs, passkeys or announce query bytes.
            def do_GET(self):
                parsed = urlsplit(self.path)
                token = parsed.path.removeprefix("/announce/")
                with gateway.lock:
                    route = gateway.routes.get(token) if parsed.path.startswith("/announce/") else None
                if route is None:
                    self.send_error(404)
                    return
                if len(parsed.query) > 16384:
                    self.send_error(414)
                    return
                try:
                    status, payload = route.fetch(parsed.query)
                    self.send_response(status)
                    self.send_header("Content-Type", "application/x-bittorrent")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        self.server = BoundedServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, name="tracker-gateway", daemon=True).start()

    def register(self, url, allow_tor):
        with self.lock:
            if len(self.routes) >= 2048:
                return None
            token = secrets.token_hex(24)
            self.routes[token] = TrackerRoute(url, allow_tor)
        return token, f"http://127.0.0.1:{self.server.server_port}/announce/{token}"

    def remove(self, tokens):
        with self.lock:
            for token in tokens:
                self.routes.pop(token, None)


_gateway = None
_gateway_lock = threading.Lock()
def tracker_gateway():
    global _gateway
    with _gateway_lock:
        if _gateway is None:
            _gateway = TrackerGateway()
        return _gateway
