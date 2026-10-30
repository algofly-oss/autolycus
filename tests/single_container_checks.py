"""Runs INSIDE a disposable container; exercises real API, jobs, FTP and browser."""
import ftplib
import hashlib
import http.server
import io
import json
import os
import subprocess
import shutil
import threading
import time
import zipfile
from pathlib import Path
from http.cookies import SimpleCookie

import requests
from pymongo import MongoClient

BASE = "http://127.0.0.1"
session = requests.Session()
username = "single-container-smoke@example.test"
password = "Smoke-Test-Password-123!"


def api(method, path, **kwargs):
    response = session.request(method, BASE + "/api" + path, timeout=30, **kwargs)
    response.raise_for_status()
    api.last_response = response
    return response.json()


def eventually(check, timeout=60):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except Exception as error:
            last_error = error
        time.sleep(1)
    raise AssertionError("Timed out waiting for fixture: " + str(last_error))


def main():
    secrets = json.loads(Path("/data/secrets.json").read_text())
    os.environ.update({"REDIS_HOST": "127.0.0.1", "REDIS_PORT": "6379", "REDIS_PASSWORD": secrets["REDIS_PASSWORD"]})
    from shared.modules.auth_session import SESSION_SECONDS
    supervisor = Path("/proc/1/task/1/children").read_text().split()[0]
    status = Path("/proc") / supervisor / "status"
    threads = next(int(line.split()[1]) for line in status.read_text().splitlines() if line.startswith("Threads:"))
    assert threads <= 8, "Rust supervisor unexpectedly created a CPU-sized thread pool"
    assert api("GET", "/ping") == {"msg": "pong"}
    for route in ("/", "/home", "/account/signin", "/account/signup", "/sw.js"):
        assert session.get(BASE + route, timeout=10).status_code == 200, route
    assert session.get(BASE + "/socket.io/?EIO=4&transport=polling", timeout=10).text.startswith("0{")
    assert session.get("https://127.0.0.1/api/ping", verify=False, timeout=10).status_code == 200

    assert api("POST", "/auth/signup", json={"name": "Smoke", "username": username, "password": password})["msg"] in ("success", "user already exists")
    session.cookies.clear()
    assert api("POST", "/auth/signin", json={"username": username, "password": password})["msg"] == "success"
    cookie = next(iter(SimpleCookie(api.last_response.headers["set-cookie"]).values()))
    assert int(cookie["max-age"]) == SESSION_SECONDS and cookie["expires"]
    assert cookie["httponly"] and cookie["samesite"] == "lax" and cookie["path"] == "/"
    assert "no-store" in api.last_response.headers["cache-control"]
    from redis import Redis
    cache = Redis(host="127.0.0.1", password=secrets["REDIS_PASSWORD"])
    token = cookie.value
    assert cache.ttl(token) > SESSION_SECONDS - 60
    # Resolver references are opaque, authenticated and bound to the searching user.
    resolver_token = "fixture_token_for_search_resolution"
    magnet = "magnet:?xt=urn:btih:" + "1" * 40
    owner = cache.get(token).decode()
    reference = {"user_id": owner, "magnet": magnet}
    cache.set("search_magnet/" + resolver_token, json.dumps(reference), ex=60)
    assert api("POST", "/torrent/resolve-magnet", json={"token": resolver_token}) == {"magnet": magnet}
    reference["user_id"] = "another-user"
    cache.set("search_magnet/" + resolver_token, json.dumps(reference), ex=60)
    denied = session.post(BASE + "/api/torrent/resolve-magnet", json={"token": resolver_token}, timeout=10)
    assert denied.status_code == 404
    cache.delete("search_magnet/" + resolver_token)
    expired = session.post(BASE + "/api/torrent/resolve-magnet", json={"token": resolver_token}, timeout=10)
    assert expired.status_code == 404
    assert session.post(BASE + "/api/torrent/resolve-magnet", json={"token": "http://external/"}, timeout=10).status_code == 422
    assert requests.post(BASE + "/api/torrent/resolve-magnet", json={"token": resolver_token}, timeout=10).status_code in (400, 401, 403)
    cache.set("search_magnet/" + resolver_token, json.dumps({"user_id": owner, "magnet": magnet}), ex=600)
    # Cache loss cannot log out an otherwise valid durable session.
    cache.delete(token)
    assert api("GET", "/auth/me")["username"] == username
    assert cache.exists(token)
    # Rolling renewal refreshes both the browser cookie and server expiry.
    cache.expire(token, 5)
    assert api("GET", "/auth/me")["username"] == username
    assert "Max-Age=" in api.last_response.headers["set-cookie"]
    assert cache.ttl(token) > SESSION_SECONDS - 60
    rejected = session.post(BASE + "/api/auth/signin", json={"username": username, "password": "wrong-password"}, timeout=10)
    assert rejected.status_code == 400, "An existing cookie must not bypass credential verification"
    # A fresh account has no files, but the backing filesystem is occupied.
    drive = shutil.disk_usage("/downloads")
    storage = api("GET", "/files/status")
    assert 0 < storage["used"] < drive.used
    assert abs(storage["total"] - (drive.total - drive.used + storage["used"])) < 64 * 1024 * 1024
    import queue
    import socketio
    updates = queue.Queue()
    live = socketio.Client()
    live.on("/stc/disk-usage", lambda data: updates.put(data))
    cookie_header = "; ".join(key + "=" + value for key, value in session.cookies.get_dict().items())
    live.connect(BASE, headers={"Cookie": cookie_header}, transports=["polling"])
    try:
        api("GET", "/torrent/all")
        update = updates.get(timeout=10)
        current_drive = shutil.disk_usage("/downloads")
        assert update["used"] > 0
        assert abs(update["total"] - (current_drive.total - current_drive.used + update["used"])) < 64 * 1024 * 1024
    finally:
        live.disconnect()
    health = json.loads(Path("/run/autolycus/health.json").read_text())
    with MongoClient(health["mongo_uri"]) as client:
        user = client[health["database"]].users.find_one({"username": username})
    user_id = str(user["_id"])
    fixture = Path("/downloads") / user_id / "smoke-fixture"
    fixture.mkdir(parents=True, exist_ok=True)
    (fixture / "hello.txt").write_text("autolycus single-container fixture\n")
    # Run again after container restart to prove persistence, without deleting data.
    archive = fixture.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    path = user_id + "/smoke-fixture"
    result = api("POST", "/files/archive", params={"path": path})
    assert result["task_id"]
    eventually(lambda: archive.exists() and api("GET", "/files/archive/progress", params={"path": path}).get("status") == "complete")
    with zipfile.ZipFile(archive) as stream:
        assert any(name.endswith("hello.txt") for name in stream.namelist())

    # Verify the production media-tool versions through the actual job queue.
    video = fixture / "clip.mp4"
    transcoded = fixture / "clip_144p.mp4"
    if transcoded.exists():
        transcoded.unlink()
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "color=c=red:s=256x144:r=10", "-t", "1", "-c:v", "libx264", "-threads", "1",
                    "-pix_fmt", "yuv420p", "-y", str(video)], check=True)
    transcode = api("POST", "/files/transcode/start", params={"path": str(video), "resolution": "144p"})
    from celery_worker import app
    task = app.AsyncResult(transcode["task_id"])
    eventually(lambda: task.ready())
    assert task.successful(), str(task.result)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name",
                            "-of", "json", str(transcoded)], check=True, capture_output=True, text=True)
    assert any(stream["codec_name"] == "h264" for stream in json.loads(probe.stdout)["streams"])

    api("PATCH", "/auth/ftp", json={"enabled": True, "username": "smokeftp", "password": password, "friendly_names": False})
    with ftplib.FTP() as ftp:
        ftp.connect("127.0.0.1", 2121, timeout=15)
        ftp.login("smokeftp", password)
        assert "smoke-fixture" in ftp.nlst()
        ftp.cwd("smoke-fixture")
        content = io.BytesIO()
        ftp.retrbinary("RETR hello.txt", content.write)
        assert content.getvalue() == (fixture / "hello.txt").read_bytes()

    # Download a deterministic local file through API -> Celery -> aria2 -> disk.
    class FixtureHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            browser_page = self.path == "/browser"
            body = b"<html><body>Autolycus browser fixture</body></html>" if browser_page else b"autolycus-download-fixture\n" * 2048
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Type", "text/html" if browser_page else "application/octet-stream")
            if not browser_page:
                self.send_header("Content-Disposition", 'attachment; filename="payload.bin"')
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 18765), FixtureHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:18765/payload.bin"
    result = api("POST", "/torrent/add-url", json={"url": url})
    assert result["message"] in ("URL added", "URL Exists")
    downloaded = Path("/downloads") / user_id / hashlib.md5(url.encode()).hexdigest() / "payload.bin"
    eventually(lambda: downloaded.exists() and downloaded.read_bytes() == b"autolycus-download-fixture\n" * 2048)
    eventually(lambda: bool(api("GET", "/files/search", params={"q": "payload", "item_type": "file"})["data"]))
    public = api("POST", "/files/generate-public-url", json={"path": str(downloaded)})
    shared = requests.get(BASE + "/api/files/public/" + public["key"], timeout=15)
    shared.raise_for_status()
    assert shared.content == downloaded.read_bytes()

    # Validate real Chromium startup and local page retrieval through FlareSolverr.
    response = requests.post("http://127.0.0.1:8191/v1", json={"cmd": "request.get", "url": "http://127.0.0.1:18765/browser", "maxTimeout": 60000}, timeout=90)
    response.raise_for_status()
    assert response.json()["status"] == "ok", response.text[:500]
    server.shutdown()
    assert requests.get("http://127.0.0.1:9117/api/v2.0/server/config", params={"apikey": json.loads(Path("/data/secrets.json").read_text())["JACKETT_API_KEY"]}, timeout=10).status_code == 200
    subprocess.run(["python", "/opt/autolycus/healthcheck.py"], check=True)
    # Explicit logout revokes the durable record as well as the cached token.
    api("POST", "/auth/signout")
    assert requests.get(BASE + "/api/auth/me", cookies={cookie.key: token}, timeout=10).status_code == 400
    print("PASS: UI routes, TLS, Socket.IO, signup/signin, MongoDB, Redis, Celery archive and media transcode, FTP transfer, URL download, file search, public sharing, Chromium/FlareSolverr, Jackett, full-stack health")


if __name__ == "__main__":
    main()
