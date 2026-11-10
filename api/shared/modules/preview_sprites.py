"""Bounded seek-sampled sheets: legacy PNG or optional accurate, denser TV JPEG."""
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import zlib

WIDTH, HEIGHT, CELLS, COLUMNS = 160, 90, 100, 10

def _run_idle(command, yield_if_busy, timeout, input_data=None):
    """Stop even an in-flight probe/frame when foreground playback needs the host."""
    yield_if_busy()
    # A file-backed stdin avoids communicate(timeout)'s partial-pipe-input retry trap.
    # Writes remain bounded/cooperative, and the temporary file is always unlinked.
    input_stream=None
    if input_data is not None:
        input_stream=tempfile.TemporaryFile()
        try:
            for offset in range(0,len(input_data),1024*1024):
                yield_if_busy();input_stream.write(memoryview(input_data)[offset:offset+1024*1024])
            input_stream.seek(0)
        except BaseException:
            input_stream.close();raise
    try:process=subprocess.Popen(command,stdin=input_stream,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    except BaseException:
        if input_stream is not None:input_stream.close()
        raise
    deadline=time.monotonic()+timeout
    try:
        while True:
            yield_if_busy()
            remaining=deadline-time.monotonic()
            if remaining<=0:raise subprocess.TimeoutExpired(command,timeout)
            try:
                stdout,stderr=process.communicate(timeout=min(.25,remaining))
                yield_if_busy()
                return subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
            except subprocess.TimeoutExpired:
                if time.monotonic()>=deadline:raise
    except BaseException:
        process.kill()
        process.communicate()
        raise
    finally:
        if input_stream is not None:input_stream.close()

def fingerprint(path,detail=False):
    file=Path(path);stat=file.stat()
    variant='dense-v1' if detail else 'fill-v2'
    return hashlib.sha256(f'{file.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{variant}'.encode()).hexdigest()

def sample_count(duration,detail=False):
    return min(1000 if detail else CELLS,max(1,math.ceil(duration/(5 if detail else 15))))

def _jpeg(width,height,rgb,yield_if_busy):
    for quality in (5,10,18):
        command=['ionice','-c','3','nice','-n','19','ffmpeg','-v','error','-nostdin','-threads','1','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{width}x{height}','-i','pipe:0','-frames:v','1','-c:v','mjpeg','-q:v',str(quality),'-pix_fmt','yuvj420p','-threads','1','-f','image2pipe','pipe:1']
        result=_run_idle(command,yield_if_busy,30,input_data=rgb)
        result.check_returncode()
        if not result.stdout.startswith(b'\xff\xd8'):raise ValueError('Invalid preview JPEG')
        if len(result.stdout)<=5*1024*1024:return result.stdout
    raise ValueError('Preview exceeds cache limit')

def _png(width,height,rgb):
    def chunk(kind,data):return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
    compressor=zlib.compressobj(3);compressed=bytearray()
    for row in range(height):compressed.extend(compressor.compress(b'\0'+rgb[row*width*3:(row+1)*width*3]))
    compressed.extend(compressor.flush())
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',bytes(compressed))+chunk(b'IEND',b'')

def generate_sprite(path,yield_if_busy=lambda:None,detail=False):
    key=fingerprint(path,detail)
    result=_run_idle(['ionice','-c','3','nice','-n','19','ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)],yield_if_busy,20)
    result.check_returncode()
    duration=float(json.loads(result.stdout).get('format',{}).get('duration',0))
    if not math.isfinite(duration) or duration<=0:raise ValueError('No video duration')
    count=sample_count(duration,detail)
    columns=min(25 if detail else COLUMNS,count);rows=math.ceil(count/columns)
    canvas=bytearray(columns*WIDTH*rows*HEIGHT*3)
    generated=0
    for index in range(count):
        yield_if_busy()
        at=index*duration/count
        seek_options=[] if detail else ['-skip_frame','nokey','-noaccurate_seek']
        command=['ionice','-c','3','nice','-n','19','ffmpeg','-v','error','-nostdin','-threads','1',*seek_options,'-ss',str(at),'-i',str(path),'-map','0:v:0','-an','-sn','-frames:v','1','-filter_threads','1','-vf',f'scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT}','-f','rawvideo','-pix_fmt','rgb24','pipe:1']
        result=_run_idle(command,yield_if_busy,12)
        if result.returncode or len(result.stdout)!=WIDTH*HEIGHT*3:continue
        frame=result.stdout;column=index%columns;row=index//columns
        for line in range(HEIGHT):
            target=((row*HEIGHT+line)*columns*WIDTH+column*WIDTH)*3
            canvas[target:target+WIDTH*3]=frame[line*WIDTH*3:(line+1)*WIDTH*3]
        generated+=1
    if not generated or fingerprint(path,detail)!=key:raise ValueError('Video changed or could not be previewed')
    image=_jpeg(columns*WIDTH,rows*HEIGHT,canvas,yield_if_busy) if detail else _png(columns*WIDTH,rows*HEIGHT,canvas)
    if len(image)>5*1024*1024:raise ValueError('Preview exceeds cache limit')
    return {'_id':key,'duration':duration,'width':WIDTH,'height':HEIGHT,'columns':columns,'rows':rows,'count':count,'bytes':len(image),'content_type':'image/jpeg' if detail else 'image/png','data':image}
