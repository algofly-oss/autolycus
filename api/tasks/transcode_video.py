import re
import os
import celery_worker
import subprocess as sp
from shared.factory import redis
import json

ETA_PATTERN = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")


def convert_to_seconds(time_str):
    match = ETA_PATTERN.match(time_str)
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    seconds = int(match.group(3)) if match.group(3) else 0
    return hours * 3600 + minutes * 60 + seconds


@celery_worker.app.task(bind=True, queue="transcoding", max_retries=None)
def transcode_video(self, input_path, output_path, resolution, user_id):
    import selectors
    import signal
    import time
    from pathlib import Path
    from shared.modules.transcode_backend import gpu_enabled, gpu_ready, encoding_command, probe
    key = f"transcoding_progress/{output_path}"
    slots = min(4, max(1, int(os.getenv("TRANSCODE_MAX_CONCURRENT", "2"))))
    lock = None
    for slot in range(slots):
        candidate = redis.lock(f"transcode:slot:{slot}", timeout=90)
        if candidate.acquire(blocking=False):
            lock = candidate
            break
    if lock is None:
        redis.set(key, json.dumps({"progress": 0, "eta": 0, "status": "queued"}))
        raise self.retry(countdown=5)
    partial = str(Path(output_path).with_name(".autolycus-transcode-" + Path(output_path).name))
    cp = None
    try:
        if redis.get(f"{key}/kill"):
            return {"message": "terminated"}
        metadata = probe(input_path)
        duration = float(metadata.get("format", {}).get("duration", 0) or 0)
        use_gpu = gpu_enabled()
        if use_gpu and not gpu_ready():
            raise RuntimeError("GPU transcoding requested but NVENC is unavailable. Enable the optional GPU Compose override or set TRANSCODE_USE_GPU=0.")
        command = ["nice", "-n", "10", *encoding_command(input_path, partial, resolution, metadata.get("streams", []), use_gpu)]
        cp = sp.Popen(command, stdout=sp.PIPE, stderr=sp.STDOUT, start_new_session=True)
        selector = selectors.DefaultSelector()
        selector.register(cp.stdout, selectors.EVENT_READ)
        renewed = time.monotonic()
        tail = ""
        cancelled = False
        while cp.poll() is None:
            if redis.get(f"{key}/kill"):
                cancelled = True
                break
            if time.monotonic() - renewed > 20:
                lock.extend(90, replace_ttl=True)
                renewed = time.monotonic()
            if not selector.select(timeout=1):
                continue
            data = os.read(cp.stdout.fileno(), 8192).decode(errors="replace")
            tail = (tail + data)[-8192:]
            progress = re.findall(r"(\d+\.\d+) %", data)
            encoded = re.findall(r"out_time_us=(\d+)", data)
            value = float(progress[-1]) if progress else min(99.9, int(encoded[-1])/1000000/duration*100) if encoded and duration > 0 else None
            if value is not None:
                redis.set(key, json.dumps({"progress": value, "eta": 0, "file_size": os.path.getsize(partial) if os.path.exists(partial) else 0, "encoder": "nvenc" if use_gpu else "x264"}))
        selector.close()
        if cancelled:
            os.killpg(cp.pid, signal.SIGTERM)
            try:
                cp.wait(timeout=5)
            except sp.TimeoutExpired:
                os.killpg(cp.pid, signal.SIGKILL)
                cp.wait()
            return {"message": "terminated"}
        cp.wait()
        if cp.returncode != 0 or not os.path.exists(partial) or os.path.getsize(partial) == 0:
            raise RuntimeError("Transcoding failed: " + tail[-1000:])
        # Publish only completed files. Partial outputs never become qualities.
        os.replace(partial, output_path)
        return {"message": "success", "encoder": "nvenc" if use_gpu else "x264"}
    except Exception as error:
        redis.setex(f"{key}/error", 3600, str(error))
        if cp and cp.poll() is None:
            os.killpg(cp.pid, signal.SIGKILL)
            cp.wait()
        raise
    finally:
        if cp and cp.stdout:
            cp.stdout.close()
        if os.path.exists(partial):
            os.unlink(partial)
        if os.path.exists(output_path) and os.path.getsize(output_path) == 0:
            os.unlink(output_path)
        redis.delete(key, f"{key}/kill")
        try:
            lock.release()
        except Exception:
            pass
