#!/usr/bin/env python3
"""Stop old stack, copy its state, start the single container; roll back on failure.

Run from repository root AFTER building and smoke testing:
    python3 deploy/single/migrate.py
Original containers and state directories are retained for rollback.
"""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def docker(*args, **kwargs):
    return subprocess.run(["docker", *args], check=True, text=True, **kwargs)


def inspect(name):
    return json.loads(docker("inspect", name, capture_output=True).stdout)[0]


def stop_originals(names):
    stopping = subprocess.Popen(["docker", "stop", "-t", "90", *names],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # The legacy API's shell entrypoint does not forward Docker's TERM to
    # Uvicorn/Celery. Once Docker marks the container as stopping, notify the
    # service leaders directly so they can shut down without a forced timeout.
    time.sleep(1)
    terminate = """import os, signal
from pathlib import Path
processes = {}
for directory in Path('/proc').iterdir():
    if not directory.name.isdigit(): continue
    try:
        fields = dict(line.split(':', 1) for line in (directory / 'status').read_text().splitlines() if ':' in line)
        if fields['Name'].strip() in ('uvicorn', 'celery'):
            processes[int(directory.name)] = int(fields['PPid'].strip())
    except (FileNotFoundError, ProcessLookupError): pass
for pid, parent in processes.items():
    if parent not in processes:
        try: os.kill(pid, signal.SIGTERM)
        except ProcessLookupError: pass
"""
    subprocess.run(["docker", "exec", "-i", "autolycus_api", "python", "-"],
                   input=terminate, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _, error = stopping.communicate(timeout=100)
    if stopping.returncode:
        raise RuntimeError("Unable to stop original services: " + error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "volumes/single")
    parser.add_argument("--image", default="autolycus:single")
    options = parser.parse_args()
    data = options.data.resolve()
    if data.exists() and any(data.iterdir()):
        raise RuntimeError("Migration destination must be empty: " + str(data))
    docker("image", "inspect", options.image, capture_output=True)
    old = {}
    for service in ("mongodb", "redis", "meilisearch", "ftp", "jackett", "api", "ui", "proxy", "womginx", "tor", "flaresolverr"):
        old[service] = inspect("autolycus_" + service)
    running = [entry["Name"].lstrip("/") for entry in old.values() if entry["State"]["Running"]]
    if not old["api"]["State"]["Running"]:
        raise RuntimeError("Start the original API before migration to read effective credentials")

    # Capture effective values, including the legacy API_SECRET_KEY default,
    # without printing credentials or writing them into version-controlled files.
    source = """import json, os
from shared.env import API_SECRET_KEY, JACKETT_API_KEY, FTP_HOOK_SECRET, MEILI_SEARCH_API_KEY, REDIS_PASSWORD
print(json.dumps(dict(API_SECRET_KEY=API_SECRET_KEY, JACKETT_API_KEY=JACKETT_API_KEY,
 FTP_HOOK_SECRET=FTP_HOOK_SECRET, MEILI_SEARCH_API_KEY=MEILI_SEARCH_API_KEY,
 REDIS_PASSWORD=REDIS_PASSWORD, MONGO_INITDB_ROOT_PASSWORD=os.environ['MONGO_INITDB_ROOT_PASSWORD'])))
"""
    secret = json.loads(docker("exec", "-i", "autolycus_api", "python", "-", input=source, capture_output=True).stdout)
    if not all(secret.values()):
        raise RuntimeError("Migration requires non-empty effective credentials for all services")
    activity_source = """import json, os
from celery_worker import app
from pymongo import MongoClient
db = MongoClient(os.environ['MONGO_DATABASE_URI'])[os.environ['MONGO_DATABASE_NAME']]
active = app.control.inspect(timeout=3).active()
print(json.dumps({'downloads': db.torrents.count_documents({'is_paused': False, 'is_finished': False}),
                  'jobs': sum(len(jobs) for jobs in (active or {}).values()), 'worker_replied': bool(active)}))
"""
    activity = json.loads(docker("exec", "-i", "autolycus_api", "python", "-", input=activity_source, capture_output=True).stdout)
    if activity["downloads"] or activity["jobs"] or not activity["worker_replied"]:
        raise RuntimeError("Pause active downloads and let background jobs finish; a running worker must reply before migration")
    data.mkdir(parents=True, exist_ok=True)
    os.chmod(data, 0o750)
    plan = {}
    for service, mount_path, destination in (
        ("mongodb", "/data/db", "mongodb"), ("redis", "/data", "redis"),
        ("meilisearch", "/meili_data", "meilisearch"), ("ftp", "/var/lib/sftpgo", "sftpgo"),
        ("jackett", "/config", "jackett")):
        mounts = [m for m in old[service]["Mounts"] if m["Destination"] == mount_path]
        if len(mounts) != 1 or mounts[0]["Type"] != "bind":
            raise RuntimeError("Expected one bind mount for " + service)
        plan[destination] = mounts[0]["Source"]
    certificate_mounts = {m["Destination"]: m["Source"] for m in old["proxy"]["Mounts"]}
    copies = {"tls/server.crt": certificate_mounts["/etc/ssl/certs/server.crt"],
              "tls/server.key": certificate_mounts["/etc/ssl/certs/server.key"]}
    environment = os.environ.copy()
    environment["AUTOLYCUS_DATA_PATH"] = str(data)
    environment["AUTOLYCUS_SINGLE_IMAGE"] = options.image
    compose = ["docker", "compose", "-f", str(ROOT / "compose.single.yml")]
    policies = {entry["Name"].lstrip("/"): entry["HostConfig"]["RestartPolicy"] for entry in old.values()}
    (data / "migration.json").write_text(json.dumps({"original_containers": running,
        "original_restart_policies": policies, "source_directories": plan}, indent=2))
    try:
        print("Stopping original services for a consistent state copy...", flush=True)
        # Freeze new web writes, then record identities and sessions before
        # shutting down the remaining processes. Only digests leave containers.
        if "autolycus_proxy" in running:
            docker("stop", "-t", "90", "autolycus_proxy", capture_output=True)
        state_code = Path(__file__).with_name("state.py").read_text()
        before = json.loads(docker("exec", "-i", "autolycus_api", "python", "-", input=state_code, capture_output=True).stdout)
        stop_originals(running)
        arguments = ["run", "--rm", "--entrypoint", "python", "-i", "-v", str(data) + ":/destination"]
        for destination, source_path in {**plan, **copies}.items():
            arguments += ["-v", source_path + ":/source/" + destination + ":ro"]
        arguments += [options.image, "-"]
        copy_code = """import shutil
from pathlib import Path
for name in ('mongodb', 'redis', 'meilisearch', 'sftpgo', 'jackett'):
    shutil.copytree('/source/' + name, '/destination/' + name, copy_function=shutil.copy2)
Path('/destination/tls').mkdir()
for name in ('server.crt', 'server.key'):
    shutil.copy2('/source/tls/' + name, '/destination/tls/' + name)
"""
        docker(*arguments, input=copy_code, capture_output=True)
        secret_path = data / "secrets.json"
        secret_path.write_text(json.dumps(secret))
        secret_path.chmod(0o600)
        subprocess.run(compose + ["up", "-d", "--no-build"], cwd=ROOT, env=environment, check=True)
        deadline = time.monotonic() + 420
        container_id = subprocess.check_output(compose + ["ps", "-q", "autolycus"], cwd=ROOT, env=environment, text=True).strip()
        while time.monotonic() < deadline:
            state = inspect(container_id)["State"]
            if not state["Running"]:
                raise RuntimeError("Single container exited during migration")
            if state.get("Health", {}).get("Status") == "healthy":
                after = json.loads(docker("exec", "-i", container_id, "python", "-", input=state_code, capture_output=True).stdout)
                if before != after:
                    raise RuntimeError("User, torrent, or session identities changed; rolling back")
                # Bootstrap secures /data for container users; write through
                # Docker rather than relying on the host user's permissions.
                validation_code = "from pathlib import Path; import sys; Path('/data/migration-validation.json').write_text(sys.stdin.read())"
                docker("exec", "-i", container_id, "python", "-c", validation_code,
                       input=json.dumps(after, indent=2), capture_output=True)
                # Retained rollback containers must not come back alongside the
                # replacement when the Docker daemon/host restarts.
                docker("update", "--restart=no", *policies, capture_output=True)
                print("Migration complete. Original containers and data remain available for rollback.", flush=True)
                return
            time.sleep(3)
        raise RuntimeError("Single container did not become healthy")
    except BaseException:
        print("Migration failed; restoring the original running stack.", flush=True)
        subprocess.run(compose + ["down"], cwd=ROOT, env=environment, check=False)
        for name, policy in policies.items():
            restart = policy["Name"] or "no"
            if restart == "on-failure" and policy.get("MaximumRetryCount"):
                restart += ":" + str(policy["MaximumRetryCount"])
            docker("update", "--restart=" + restart, name, capture_output=True)
        docker("start", *running, capture_output=True)
        raise


if __name__ == "__main__":
    main()
