import re
import os
import celery_worker
import subprocess as sp
from shared.factory import redis
import json

PRESETS = {
    "144p": "--width 256 --height 144 -e x264 --encopts preset=medium -q 27 --auto-anamorphic -f mp4 --aencoder av_aac --ab 96 --mixdown stereo",
    "240p": "--width 426 --height 240 -e x264 --encopts preset=medium -q 26 --auto-anamorphic -f mp4 --aencoder av_aac --ab 64 --mixdown stereo",
    "360p": "--width 640 --height 360 -e x264 --encopts preset=medium -q 25 --auto-anamorphic -f mp4 --aencoder av_aac --ab 128 --mixdown stereo",
    "480p": "--width 854 --height 480 -e x264 --encopts preset=medium -q 24 --auto-anamorphic -f mp4 --aencoder av_aac --ab 256 --mixdown stereo",
    "720p": "--width 1280 --height 720 -e x264 --encopts preset=medium -q 23 --auto-anamorphic -f mp4 --aencoder av_aac --ab 320 --mixdown stereo",
    "1080p": "--width 1920 --height 1080 -e x264 --encopts preset=medium -q 22 --auto-anamorphic -f mp4 --aencoder av_aac --ab 320 --mixdown stereo",
    "1440p": "--width 2560 --height 1440 -e x264 --encopts preset=medium -q 21 --auto-anamorphic -f mp4 --aencoder av_aac --ab 320 --mixdown stereo",
    "2160p": "--width 3840 --height 2160 -e x264 --encopts preset=medium -q 20 --auto-anamorphic -f mp4 --aencoder av_aac --ab 320 --mixdown stereo",
}

ETA_PATTERN = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")


def convert_to_seconds(time_str):
    match = ETA_PATTERN.match(time_str)
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    seconds = int(match.group(3)) if match.group(3) else 0
    return hours * 3600 + minutes * 60 + seconds


@celery_worker.app.task(queue="transcoding")
def transcode_video(input_path, output_path, resolution, user_id):
    cp = sp.Popen(
        f"HandBrakeCLI -i '{input_path}' -o '{output_path}' {PRESETS[resolution]}",
        stdout=sp.PIPE,
        stderr=sp.STDOUT,
        text=True,
        shell=True,
    )

    key = f"transcoding_progress/{output_path}"

    while True:
        line = cp.stdout.readline()
        if not line or redis.get(f"{key}/kill"):
            break

        # print(line, end='')
        progress_match = re.search(r"(\d+\.\d+) %", line)
        eta_match = re.search(r"ETA (\d+h\d+m\d+s)", line)

        if progress_match and eta_match:
            progress = float(progress_match.group(1))  # 1-100
            eta = convert_to_seconds(eta_match.group(1))
            redis.set(key, json.dumps({"progress": progress, "eta": eta}))
            # print(f"\nProgress: {progress}% | ETA: {eta / 60:.2f} min")

    if redis.get(f"{key}/kill"):
        redis.delete(f"{key}/kill")
        cp.terminate()
        cp.kill()
        cp.wait()
        return {"message": "terminated"}
    else:
        cp.stdout.close()
        cp.wait()
        redis.delete(key)

        if os.path.exists(output_path):
            return {"message": "success"}
        else:
            redis.delete(key)
            raise Exception("Transcoding failed: Unable to generate output file")
