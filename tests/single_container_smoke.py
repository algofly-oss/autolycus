#!/usr/bin/env python3
"""Build-independent, isolated integration check: python3 tests/single_container_smoke.py."""
import argparse
import json
import subprocess
import time
from pathlib import Path


def docker(*args, **kwargs):
    return subprocess.run(["docker", *args], check=True, text=True, **kwargs)


def wait_ready(name, seconds=420):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = docker("inspect", "--format", "{{json .State}}", name, capture_output=True)
        state = json.loads(result.stdout)
        if not state["Running"]:
            raise RuntimeError("Test container stopped unexpectedly")
        if state.get("Health", {}).get("Status") == "healthy":
            return
        time.sleep(3)
    docker("logs", "--tail", "100", name)
    raise RuntimeError("Test container did not become healthy")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="autolycus:single")
    parser.add_argument("--keep", action="store_true", help="retain the disposable container and test volumes")
    parser.add_argument("--live-tor", action="store_true", help="verify external Tor exits through all three proxy routes")
    options = parser.parse_args()
    suffix = str(int(time.time()))
    name = "autolycus-single-smoke-" + suffix
    volumes = [name + "-data", name + "-downloads"]
    try:
        for volume in volumes:
            docker("volume", "create", volume, capture_output=True)
        # Exercise migrated-style Tor settings too: Jackett reserves a local
        # SOCKS bridge port that must not collide with the browser redirector.
        seed = "from pathlib import Path; import json; p=Path('/data/jackett/Jackett'); p.mkdir(parents=True); (p/'ServerConfig.json').write_text(json.dumps(dict(ProxyType=2, ProxyUrl='tor', ProxyPort=9050, ProxyIsAnonymous=True)))"
        docker("run", "--rm", "--entrypoint", "python", "-v", volumes[0] + ":/data",
               options.image, "-c", seed, capture_output=True)
        docker("run", "-d", "--name", name, "--cap-add", "NET_ADMIN", "--shm-size", "256m",
               "-p", "127.0.0.1::80", "-p", "127.0.0.1::443", "-e", "CELERY_NUM_WORKERS=2",
               "-v", volumes[0] + ":/data", "-v", volumes[1] + ":/downloads", options.image, capture_output=True)
        print("Isolated container:", name, flush=True)
        wait_ready(name)
        checks = Path(__file__).with_name("single_container_checks.py").read_text()
        docker("exec", "-i", name, "python", "-", input=checks)
        if options.live_tor:
            tor_checks = Path(__file__).with_name("single_container_tor.py").read_text()
            docker("exec", "-i", name, "python", "-", input=tor_checks)
        speed_checks = Path(__file__).with_name("single_container_search_speed.py").read_text()
        docker("exec", "-i", name, "python", "-", input=speed_checks)
        poster_checks = Path(__file__).with_name("single_container_poster_checks.py").read_text()
        docker("exec", "-i", name, "python", "-", input=poster_checks)
        browser_checks = Path(__file__).with_name("single_container_browser.py").read_text()
        docker("exec", "-i", name, "/opt/flare-python/bin/python", "-", input=browser_checks)
        poster_browser = Path(__file__).with_name("single_container_poster_browser.py").read_text()
        docker("exec", "-i", name, "/opt/flare-python/bin/python", "-", input=poster_browser)
        before = docker("exec", name, "sha256sum", "/data/secrets.json", "/data/tls/server.crt", capture_output=True).stdout
        docker("restart", "-t", "90", name, capture_output=True)
        wait_ready(name)
        after = docker("exec", name, "sha256sum", "/data/secrets.json", "/data/tls/server.crt", capture_output=True).stdout
        assert before == after, "Secrets and TLS identity changed across restart"
        docker("exec", "-i", name, "python", "-", input=checks)
        # Kill one dependency and verify the Rust supervisor restarts it.
        old_pid = docker("exec", name, "cat", "/run/autolycus/services/redis", capture_output=True).stdout.strip()
        docker("exec", name, "kill", "-9", old_pid)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            result = subprocess.run(["docker", "exec", name, "cat", "/run/autolycus/services/redis"], text=True, capture_output=True)
            if result.returncode == 0 and result.stdout.strip() != old_pid:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Supervisor did not replace killed Redis process")
        wait_ready(name)
        docker("exec", name, "python", "/opt/autolycus/healthcheck.py")
        print("PASS: restart preserves user/data/secrets/TLS; killed Redis recovers", flush=True)
        docker("stats", "--no-stream", "--format", "{{.Name}} {{.MemUsage}} CPU={{.CPUPerc}}", name)
        docker("port", name)
    finally:
        if options.keep:
            print("Retained test container and volumes:", name, ", ".join(volumes), flush=True)
        else:
            subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL)
            for volume in volumes:
                subprocess.run(["docker", "volume", "rm", volume], stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
