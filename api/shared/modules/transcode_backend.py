"""Explicit, bounded-resource transcoding backends (never used by playback)."""
import json
import os
import subprocess
from functools import lru_cache

RESOLUTIONS = {144:(256,144),240:(426,240),360:(640,360),480:(854,480),720:(1280,720),1080:(1920,1080),1440:(2560,1440),2160:(3840,2160)}

def gpu_enabled():
    return os.getenv("TRANSCODE_USE_GPU", "0").lower() in ("1","true","yes")

def thread_limit():
    return min(8,max(1,int(os.getenv("TRANSCODE_THREADS","2"))))

@lru_cache(maxsize=1)
def gpu_ready():
    try:
        result=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-f","lavfi","-i","color=size=256x144:rate=1","-frames:v","1","-c:v","h264_nvenc","-preset","p1","-f","null","-"],capture_output=True,timeout=15)
        return result.returncode == 0
    except (OSError,subprocess.TimeoutExpired):
        return False

def probe(path):
    result=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration:stream=index,codec_type,codec_name","-of","json",path],capture_output=True,text=True,timeout=20,check=True)
    return json.loads(result.stdout)

def encoding_command(source,output,resolution,streams,use_gpu=False):
    width,height=RESOLUTIONS[int(resolution.rstrip('p'))]
    args=["ffmpeg","-hide_banner","-nostdin","-y","-threads",str(thread_limit()),"-filter_threads","1","-i",source,"-map","0:v:0","-map","0:a?"]
    for stream in streams:
        if stream.get("codec_type")=="subtitle" and stream.get("codec_name") in {"subrip","ass","ssa","webvtt","mov_text","text"}:
            args += ["-map",f"0:{stream['index']}"]
    args += ["-vf",f"scale=w='min({width},iw)':h='min({height},ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,format=yuv420p",
             ]
    if use_gpu:
        args += ["-c:v","h264_nvenc","-preset","p4","-rc","vbr","-cq","23","-b:v","0","-surfaces","8","-rc-lookahead","0","-bf","0"]
    else:
        quality={144:27,240:26,360:25,480:24,720:23,1080:22,1440:21,2160:20}[height]
        args += ["-c:v","libx264","-preset","fast","-crf",str(quality),"-threads",str(thread_limit())]
    args += ["-c:a","aac","-ac","2","-b:a","192k","-c:s","mov_text","-map_metadata","0","-map_chapters","0","-movflags","+faststart","-progress","pipe:1","-nostats",output]
    return args
