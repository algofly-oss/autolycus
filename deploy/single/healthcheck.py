"""Readiness for the complete local stack, without depending on Internet access."""
import json
import http.cookiejar
import os
import socket
import sys
import urllib.request
from pathlib import Path


def check():
    for name in ("mongodb", "redis", "meilisearch", "api", "worker", "tor", "jackett",
                 "flaresolverr", "ftp", "redsocks", "privoxy", "womginx", "proxy"):
        pid = int((Path("/run/autolycus/services") / name).read_text())
        os.kill(pid, 0)
    secret = json.loads(Path("/data/secrets.json").read_text())
    from redis import Redis
    from pymongo import MongoClient
    Redis(host="127.0.0.1", password=secret["REDIS_PASSWORD"], socket_timeout=2).ping()
    # Use persisted boot-time environment, including custom database usernames.
    config = json.loads(Path("/run/autolycus/health.json").read_text())
    with MongoClient(config["mongo_uri"], serverSelectionTimeoutMS=2000) as client:
        client[config["database"]].list_collection_names()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    for port, path in ((80, "/api/ping"), (3000, "/"), (7700, "/health"), (8191, "/"),
                       (9117, "/api/v2.0/server/config"), (18080, "/wombat-handler.js")):
        headers = {"User-Agent": "Autolycus-Health/1", "Accept": "*/*"}
        if port == 9117:
            headers["X-Api-Key"] = secret["JACKETT_API_KEY"]
        request = urllib.request.Request("http://127.0.0.1:" + str(port) + path,
                                         headers=headers)
        with opener.open(request, timeout=2) as response:
            if response.status != 200:
                raise RuntimeError("Unexpected HTTP status on port " + str(port))
    with socket.create_connection(("127.0.0.1", 9050), timeout=2) as stream:
        stream.sendall(bytes([5, 1, 0]))
        if stream.recv(2) != bytes([5, 0]):
            raise RuntimeError("Tor SOCKS handshake failed")
    with socket.create_connection(("127.0.0.1", 2121), timeout=2) as stream:
        if not stream.recv(256).startswith(b"220"):
            raise RuntimeError("FTP listener is not ready")


if __name__ == "__main__":
    try:
        check()
    except Exception as error:
        # Do not print database URIs or credentials in Docker health logs.
        print("Stack is not ready (" + type(error).__name__ + ")", file=sys.stderr)
        sys.exit(1)
