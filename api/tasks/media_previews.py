import os
import time
from datetime import datetime
from pathlib import Path
import celery_worker
from bson.binary import Binary
from pymongo import MongoClient
from shared.factory import redis
from shared.modules.preview_sprites import generate_sprite,fingerprint
from shared.modules.preview_cache import prune_deleted_previews

VIDEO_SUFFIXES={'.mp4','.mkv','.webm','.avi','.mov','.m4v','.ts','.m2ts'}

def queue_missing_previews(path,collection,budget=2):
    """Coarse first, then five-second TV previews; leases bound duplicate work."""
    queued=0
    for detail in (False,True):
        if queued>=budget:break
        key=fingerprint(path,detail)
        if collection.find_one({'_id':key},{'_id':1}) or redis.exists('preview-failed:'+key):continue
        lease='preview-job:'+key
        if redis.set(lease,1,nx=True,ex=3600):
            try:generate_preview.delay(str(path),detail=detail)
            except Exception:
                redis.delete(lease)
                raise
            queued+=1
    return queued

@celery_worker.app.task(bind=True,queue='previews',max_retries=120)
def generate_preview(self,path,detail=False):
    if os.getenv('MEDIA_PREVIEWS_ENABLED','1')=='0':return
    key=fingerprint(path,detail)
    redis.set('preview-job:'+key,1,ex=3600)
    if detail:
        # A long dense build must not delay the first usable thumbnail sheet.
        coarse_key=fingerprint(path)
        with MongoClient(os.environ['MONGO_DATABASE_URI']) as probe:
            collection=probe[os.environ['MONGO_DATABASE_NAME']].media_previews
            if not collection.find_one({'_id':coarse_key},{'_id':1}) and not redis.exists('preview-failed:'+coarse_key):
                queue_missing_previews(path,collection,budget=1)
                raise self.retry(countdown=30)
    lock=redis.lock('media-preview:slot',timeout=180)
    if redis.exists('media-playback-active') or any(redis.exists(f'transcode:slot:{i}') for i in range(4)) or not lock.acquire(blocking=False):raise self.retry(countdown=30)
    renewed_at=time.monotonic()
    def cooperate():
        if redis.exists('media-playback-active') or any(redis.exists(f'transcode:slot:{i}') for i in range(4)):raise RuntimeError('Yield to playback or transcoding')
        # Polling a frame must not renew the Redis lock four times per second.
        nonlocal renewed_at
        if time.monotonic()-renewed_at>=30:
            lock.extend(180,replace_ttl=True)
            redis.expire('preview-job:'+key,3600)
            renewed_at=time.monotonic()
    client=MongoClient(os.environ['MONGO_DATABASE_URI'])
    try:
        collection=client[os.environ['MONGO_DATABASE_NAME']].media_previews
        if collection.find_one({'_id':key},{'_id':1}):
            redis.delete('preview-job:'+key)
            return
        sprite=generate_sprite(path,cooperate,detail=detail);sprite['data']=Binary(sprite['data']);sprite['accessed_at']=datetime.utcnow()
        sprite['source_path']=str(Path(path).resolve())
        if fingerprint(path,detail)!=key:return
        collection.create_index('accessed_at',expireAfterSeconds=30*86400)
        cache_limit=max(64,int(os.getenv('MEDIA_PREVIEWS_CACHE_MB','512')))*1024*1024
        used=sum(doc.get('bytes',0) for doc in collection.find({},{'bytes':1}))
        for doc in collection.find({}, {'bytes':1}).sort('accessed_at',1):
            if used+sprite['bytes']<=cache_limit:break
            collection.delete_one({'_id':doc['_id']});used-=doc.get('bytes',0)
        collection.replace_one({'_id':key},sprite,upsert=True)
        redis.delete('preview-job:'+key)
    except RuntimeError:
        raise self.retry(countdown=30)
    except Exception:
        redis.setex('preview-failed:'+key,3600,1)
        raise
    finally:
        client.close()
        try:lock.release()
        except Exception:pass

@celery_worker.app.task(queue='previews')
def preview_download_tree(root):
    if os.getenv('MEDIA_PREVIEWS_ENABLED','1')=='0':return
    if not root:return
    client=MongoClient(os.environ['MONGO_DATABASE_URI'])
    try:
        collection=client[os.environ['MONGO_DATABASE_NAME']].media_previews
        count=0
        for path in completed_video_paths([Path(root)]):
            if count>=8:break
            count+=queue_missing_previews(path,collection,8-count)
    finally:client.close()

def completed_video_paths(roots):
    """Never follow symlinks or leave the configured download tree."""
    base=Path(os.getenv('DOWNLOAD_PATH','/downloads')).resolve()
    for root in sorted(set(roots)):
        if root.is_symlink() or not root.is_dir() or not root.resolve().is_relative_to(base):continue
        for folder,dirs,files in os.walk(root,followlinks=False):
            dirs[:]=sorted(d for d in dirs if not d.startswith('.') and not (Path(folder)/d).is_symlink())
            for name in sorted(files):
                path=Path(folder)/name
                if not name.startswith('.') and path.suffix.lower() in VIDEO_SUFFIXES and not path.is_symlink() and path.is_file():yield path

@celery_worker.app.task(queue='previews',ignore_result=True)
def backfill_missing_previews():
    """Bound each pass; a persistent cursor prevents large libraries starving."""
    if os.getenv('MEDIA_PREVIEWS_ENABLED','1')=='0':return
    lock=redis.lock('media-preview:scan',timeout=120)
    if not lock.acquire(blocking=False):return
    client=MongoClient(os.environ['MONGO_DATABASE_URI'])
    try:
        database=client[os.environ['MONGO_DATABASE_NAME']]
        prune_deleted_previews(database.media_previews)
        base=Path(os.getenv('DOWNLOAD_PATH','/downloads')).resolve()
        roots=[]
        for doc in database.torrents.find({'is_finished':True},{'user_id':1,'info_hash':1,'url_hash':1}):
            identity=doc.get('info_hash') or doc.get('url_hash')
            if identity and doc.get('user_id'):roots.append(base/str(doc['user_id'])/str(identity))
        cursor=int(redis.get('media-preview:scan-cursor') or 0)
        queued=checked=0
        for index,path in enumerate(completed_video_paths(roots)):
            if index<cursor:continue
            queued+=queue_missing_previews(path,database.media_previews,8-queued)
            redis.set('media-preview:scan-cursor',index+1)
            checked+=1
            if queued>=8 or checked>=128:return {'queued':queued,'checked':checked}
        redis.delete('media-preview:scan-cursor')
        return {'queued':queued,'checked':checked}
    finally:
        client.close()
        try:lock.release()
        except Exception:pass
