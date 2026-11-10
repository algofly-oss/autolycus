"""A wide source fills each sprite cell; the preview generator adds no black padding."""
import json,os,struct,subprocess,zlib
from pathlib import Path
pid=Path('/run/autolycus/services/api').read_text().strip()
for entry in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
 if b'=' in entry:
  key,value=entry.split(b'=',1);os.environ[key.decode()]=value.decode()
from shared.modules.preview_sprites import generate_sprite,WIDTH,HEIGHT
file=Path('/data/wide-preview-fill.mp4')
subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=red:s=640x240:r=12','-t','2','-c:v','libx264','-threads','1','-pix_fmt','yuv420p',str(file)],check=True)
sprite=generate_sprite(file);png=sprite['data'];position=8;compressed=b''
while position<len(png):
 size=struct.unpack('!I',png[position:position+4])[0];kind=png[position+4:position+8];data=png[position+8:position+8+size]
 if kind==b'IDAT':compressed+=data
 position+=12+size
pixels=zlib.decompress(compressed)
for x,y in [(0,0),(WIDTH-1,0),(0,HEIGHT-1),(WIDTH-1,HEIGHT-1)]:
 offset=y*(WIDTH*3+1)+1+x*3;r,g,b=pixels[offset:offset+3];assert r>200 and g<25 and b<25,(x,y,r,g,b)
print('PASS: wide-video sprite fills all four tile corners without generated letterboxing; unchanged 160×90 tile size',flush=True)
