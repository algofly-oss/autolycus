"""Configure one-container storage and local endpoints, then exec Rust supervisor."""
import json
import os
import re
import secrets
import subprocess
from pathlib import Path
from urllib.parse import quote

DATA = Path("/data")
RUN = Path("/run/autolycus")


def initialize():
    os.umask(0o027)
    if os.environ.get("AUTOLYCUS_REQUIRE_EXISTING_DATA", "").lower() in ("1", "true", "yes"):
        if not (DATA / "secrets.json").is_file():
            raise RuntimeError("The existing data mount is unavailable; refusing to initialize an empty installation")
    DATA.mkdir(parents=True, exist_ok=True)
    os.chown(DATA, 0, 10001)
    DATA.chmod(0o750)
    RUN.mkdir(parents=True, exist_ok=True)
    os.chown(RUN, 0, 10001)
    RUN.chmod(0o750)
    secret_path = DATA / "secrets.json"
    stored = json.loads(secret_path.read_text()) if secret_path.exists() else {}
    for key in ("API_SECRET_KEY", "MONGO_INITDB_ROOT_PASSWORD", "REDIS_PASSWORD",
                "MEILI_SEARCH_API_KEY", "JACKETT_API_KEY", "FTP_HOOK_SECRET"):
        os.environ[key] = os.environ.get(key) or stored.get(key) or secrets.token_hex(24)
        stored[key] = os.environ[key]
    temporary = secret_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(stored))
    temporary.chmod(0o600)
    temporary.replace(secret_path)

    for name in ("mongodb", "redis", "meilisearch", "sftpgo", "jackett", "tor", "home", "tls"):
        directory = DATA / name
        directory.mkdir(parents=True, exist_ok=True)
        if name != "tls":
            os.chown(directory, 10001, 10001)
    # Existing bind mounts can have different UIDs. Convert service data only,
    # never the potentially very large downloads tree.
    subprocess.run(["chown", "-R", "10001:10001", *[
        str(DATA / name) for name in ("mongodb", "redis", "meilisearch", "jackett")]], check=True)
    for directory in (DATA / "home/.config", DATA / "jackett/Jackett"):
        directory.mkdir(parents=True, exist_ok=True)
        os.chown(directory, 10001, 10001)

    username = os.environ.setdefault("MONGO_INITDB_ROOT_USERNAME", "autolycus")
    database = os.environ.setdefault("MONGO_DATABASE_NAME", "autolycus")
    os.environ.update({
        "MONGO_DATABASE_URI": "mongodb://{}:{}@127.0.0.1:27017/{}?authSource=admin".format(
            quote(username, safe=""), quote(stored["MONGO_INITDB_ROOT_PASSWORD"], safe=""), quote(database, safe="")),
        "REDIS_HOST": "127.0.0.1", "REDIS_PORT": "6379",
        "MEILI_SEARCH_HOST": "http://127.0.0.1:7700",
        "JACKETT_URL": "http://127.0.0.1:9117",
        "TOR_PROXY_URL": "http://127.0.0.1:8118",
        "API_DEBUG": "False", "NODE_ENV": "production", "BUILD_ENV": "prod",
        "API_SECRET_KEY": stored["API_SECRET_KEY"],
    })
    os.environ.setdefault("CELERY_NUM_WORKERS", "2")
    os.environ.setdefault("SESSION_COOKIE_NAME", "autolycus_session")
    health_config = RUN / "health.json"
    health_config.write_text(json.dumps({"mongo_uri": os.environ["MONGO_DATABASE_URI"], "database": database}))
    health_config.chmod(0o600)

    config_path = DATA / "jackett/Jackett/ServerConfig.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    config.update({"Port": 9117, "AllowExternal": False, "APIKey": stored["JACKETT_API_KEY"],
                   "UpdateDisabled": True, "FlareSolverrUrl": "http://127.0.0.1:8191"})
    if config.get("ProxyUrl") == "tor":
        config["ProxyUrl"] = "127.0.0.1"
    config_path.write_text(json.dumps(config, indent=2))
    os.chown(config_path, 10001, 10001)

    cert, key = DATA / "tls/server.crt", DATA / "tls/server.key"
    if cert.exists() != key.exists():
        raise RuntimeError("Provide both /data/tls/server.crt and server.key, or neither")
    if not cert.exists():
        subprocess.run(["openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048",
                        "-days", "365", "-subj", "/CN=autolycus.local",
                        "-keyout", str(key), "-out", str(cert)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    key.chmod(0o600)
    nginx = Path("/opt/autolycus/nginx.template").read_text()
    for token, value in {"API_ADDRESS": "127.0.0.1:8080", "UI_ADDRESS": "127.0.0.1:3000",
                         "BROWSER_PROXY_ADDRESS": "127.0.0.1:18080"}.items():
        nginx = nginx.replace("${" + token + "}", value)
    nginx = nginx.replace("/etc/ssl/certs/server.crt", str(cert)).replace("/etc/ssl/certs/server.key", str(key))
    nginx = nginx.replace("error.log debug;", "error.log warn;").replace("rewrite_log on;", "rewrite_log off;")
    Path("/etc/nginx/conf.d/autolycus.conf").write_text(nginx)
    Path("/etc/nginx/conf.d/ui.conf").write_text("""
server {
    listen 127.0.0.1:3000;
    root /opt/ui;
    index index.html;
    location / { try_files $uri $uri.html $uri/ =404; }
}
""")
    Path("/etc/nginx/conf.d/jackett.conf").write_text("""
server {
    # Compose publishes this management listener on the host loopback only.
    listen 9118;
    location / {
        proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_pass http://127.0.0.1:9117;
    }
}
""")
    main_nginx = Path("/etc/nginx/nginx.conf")
    main_nginx.write_text(re.sub(r"worker_processes\s+auto;", "worker_processes 2;", main_nginx.read_text()))

    # Redis quoting accepts arbitrary passwords without interpolating a shell.
    (RUN / "redis.conf").write_text("\n".join([
        "bind 127.0.0.1", "port 6379", "dir /data/redis", "save 20 1", "appendonly no",
        "loglevel warning", "requirepass " + json.dumps(stored["REDIS_PASSWORD"]), ""]))
    os.chown(RUN / "redis.conf", 10001, 10001)
    (RUN / "redsocks.conf").write_text("""
base { log_debug = off; log_info = on; log = "stderr"; daemon = off; redirector = iptables; }
redsocks { local_ip = 127.0.0.1; local_port = 12346; ip = 127.0.0.1; port = 9050; type = socks5; }
""")
    (RUN / "privoxy.conf").write_text("""
listen-address 127.0.0.1:8118
forward-socks5t / 127.0.0.1:9050 .
""")
    setup_tor_routing()


def setup_tor_routing():
    def iptables(*args, **kwargs):
        return subprocess.run(["iptables", "-w", "5", "-t", "nat", *args], **kwargs)
    iptables("-N", "AUTOLYCUS_TOR", stderr=subprocess.DEVNULL)
    iptables("-F", "AUTOLYCUS_TOR", check=True)
    # Match only Womginx worker sockets. Other services and Arti keep their own
    # routing; an unavailable Tor proxy fails closed instead of bypassing Tor.
    for network in ("0.0.0.0/8", "10.0.0.0/8", "127.0.0.0/8", "169.254.0.0/16",
                    "172.16.0.0/12", "192.168.0.0/16", "224.0.0.0/4", "240.0.0.0/4"):
        iptables("-A", "AUTOLYCUS_TOR", "-d", network, "-j", "RETURN", check=True)
    # Jackett's SOCKS-to-HTTP bridge reserves 12345 when a SOCKS proxy is saved.
    iptables("-A", "AUTOLYCUS_TOR", "-p", "tcp", "-j", "REDIRECT", "--to-ports", "12346", check=True)
    rule = ("OUTPUT", "-p", "tcp", "-m", "owner", "--uid-owner", "10002", "-j", "AUTOLYCUS_TOR")
    if iptables("-C", *rule, stderr=subprocess.DEVNULL).returncode:
        iptables("-A", *rule, check=True)
    # Womginx resolves IPv4 only; reject IPv6 for its UID to prevent a fallback
    # route from ever connecting outside Arti.
    ipv6_rule = ("OUTPUT", "-p", "tcp", "-m", "owner", "--uid-owner", "10002", "-j", "REJECT")
    command = ["ip6tables", "-w", "5"]
    if subprocess.run(command + ["-C", *ipv6_rule], stderr=subprocess.DEVNULL).returncode:
        subprocess.run(command + ["-A", *ipv6_rule], check=True)


if __name__ == "__main__":
    initialize()
    os.execvp("autolycus-runtime", ["autolycus-runtime", "supervise", "/opt/autolycus/services.toml"])
