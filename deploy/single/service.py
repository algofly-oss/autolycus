"""Small exec-only launchers: readiness, per-service environment and privilege drop."""
import os
import pwd
import socket
import sys
import time
from pathlib import Path


def wait_database():
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with MongoClient(os.environ["MONGO_DATABASE_URI"], serverSelectionTimeoutMS=1000) as client:
                client.admin.command("ping")
                # ping itself does not require authentication on MongoDB 5.
                client.admin.command("connectionStatus")
                client[os.environ["MONGO_DATABASE_NAME"]].list_collection_names()
            return
        except PyMongoError:
            # The localhost exception allows creating the first admin only.
            try:
                with MongoClient("mongodb://127.0.0.1:27017", serverSelectionTimeoutMS=1000) as client:
                    client.admin.command("createUser", os.environ["MONGO_INITDB_ROOT_USERNAME"],
                        pwd=os.environ["MONGO_INITDB_ROOT_PASSWORD"], roles=[{"role": "root", "db": "admin"}])
            except PyMongoError:
                pass
            time.sleep(1)
    raise RuntimeError("MongoDB authentication/readiness failed; check saved credentials")


def wait_port(port):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("Dependency did not become ready on port " + str(port))


def launch(name):
    user = "autolycus"
    directory = "/app"
    env = os.environ.copy()
    env.update({"HOME": "/data/home", "XDG_CONFIG_HOME": "/data/home/.config"})
    if name == "mongodb":
        env["LD_LIBRARY_PATH"] = "/opt/mongodb/lib"
        command = ["mongod", "--bind_ip", "127.0.0.1", "--dbpath", "/data/mongodb", "--auth",
                   "--wiredTigerCacheSizeGB", env.get("MONGO_CACHE_GB", "0.25"), "--quiet"]
    elif name == "redis":
        command = ["redis-server", "/run/autolycus/redis.conf"]
    elif name == "meilisearch":
        directory = "/data/meilisearch"
        # Bound execution CPUs for HTTP and background pools as well as the
        # explicit indexing concurrency limit.
        cpu_budget = max(1, int(env.get("MEILI_CPU_LIMIT", "2")))
        os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:cpu_budget])
        env["LD_LIBRARY_PATH"] = "/opt/meilisearch/lib"
        env.update({"MEILI_MASTER_KEY": env["MEILI_SEARCH_API_KEY"], "MEILI_ENV": "production",
                    "MEILI_NO_ANALYTICS": "true", "MEILI_HTTP_ADDR": "127.0.0.1:7700",
                    "MEILI_DB_PATH": "/data/meilisearch/data.ms",
                    "MEILI_MAX_INDEXING_MEMORY": env.get("MEILI_MAX_INDEXING_MEMORY", "256MiB"),
                    "MEILI_MAX_INDEXING_THREADS": env.get("MEILI_MAX_INDEXING_THREADS", "2")})
        command = ["meilisearch"]
    elif name in ("api", "worker"):
        # Preserve ownership semantics of the existing root-run download jobs.
        user = None
        wait_database()
        wait_port(6379)
        wait_port(7700)
        if name == "api":
            command = ["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8080"]
        else:
            command = ["celery", "-A", "celery_worker", "worker", "-Q", "transcoding,archive,file_operations",
                       "--concurrency=" + env.get("CELERY_NUM_WORKERS", "2"), "--loglevel=info", "-E"]
            env["C_FORCE_ROOT"] = "true"
    elif name == "tor":
        command = ["autolycus-runtime", "tor"]
    elif name == "jackett":
        directory = "/opt/jackett"
        env["XDG_CONFIG_HOME"] = "/data/jackett"
        command = ["/opt/jackett/jackett", "--NoUpdates", "--ListenPrivate"]
    elif name == "flaresolverr":
        directory = "/opt/flaresolverr"
        env.update({"HOST": "127.0.0.1", "PORT": "8191", "LOG_LEVEL": "info", "LOG_HTML": "false"})
        command = ["/opt/flare-python/bin/python", "-u", "flaresolverr.py"]
    elif name == "ftp":
        user = None
        directory = "/data/sftpgo"
        wait_port(8080)
        env.update({
            "SFTPGO_DATA_PROVIDER__NAME": "/data/sftpgo/sftpgo.db",
            "SFTPGO_DATA_PROVIDER__DRIVER": "sqlite",
            "SFTPGO_DATA_PROVIDER__EXTERNAL_AUTH_HOOK": "http://127.0.0.1:8080/api/auth/ftp/hook?secret=" + env["FTP_HOOK_SECRET"],
            "SFTPGO_DATA_PROVIDER__EXTERNAL_AUTH_SCOPE": "1",
            "SFTPGO_FTPD__BINDINGS__0__PORT": "2121",
            "SFTPGO_FTPD__BINDINGS__0__FORCE_PASSIVE_IP": env.get("FTP_FORCE_PASSIVE_IP", ""),
            "SFTPGO_FTPD__PASSIVE_PORT_RANGE__START": env.get("FTP_PASSIVE_PORT_START", "50000"),
            "SFTPGO_FTPD__PASSIVE_PORT_RANGE__END": env.get("FTP_PASSIVE_PORT_END", "50100"),
            "SFTPGO_SFTPD__BINDINGS__0__PORT": "0",
            "SFTPGO_HTTPD__BINDINGS__0__PORT": "0",
            "SFTPGO_COMMON__DEFENDER__ENABLED": "true",
        })
        command = ["sftpgo", "serve", "--config-dir", "/data/sftpgo", "--log-file-path", "", "--log-level", "info"]
    elif name == "redsocks":
        user = None
        command = ["redsocks", "-c", "/run/autolycus/redsocks.conf"]
    elif name == "privoxy":
        user = None
        command = ["privoxy", "--no-daemon", "/run/autolycus/privoxy.conf"]
    elif name == "womginx":
        user = None
        command = ["nginx", "-c", "/opt/womginx/nginx.conf", "-p", "/opt/womginx/"]
    elif name == "proxy":
        user = None
        wait_port(8080)
        command = ["nginx", "-g", "daemon off;"]
    else:
        raise ValueError("Unknown service " + name)
    os.chdir(directory)
    if user:
        account = pwd.getpwnam(user)
        os.initgroups(user, account.pw_gid)
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    os.execvpe(command[0], command, env)


if __name__ == "__main__":
    launch(sys.argv[1])
