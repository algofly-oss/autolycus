"""Filename-only inventory for combined folder progress; no media reads/probes."""
import hashlib,json,os,re,time
from pathlib import Path
from .media_filename import episode_identity
VIDEO={'.mp4','.mkv','.avi','.mov','.webm','.m4v','.ts','.m2ts','.ogv'}
VARIANT=re.compile(r'_(144|240|360|480|720|1080|1440|2160)p$',re.I)

def inventory(directory,root):
    pending=[(directory,0)];paths=[];count=0;started=time.monotonic()
    while pending:
        folder,depth=pending.pop()
        if depth>16:continue
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    count+=1
                    if count>20000 or len(paths)>=4000 or time.monotonic()-started>3:return None
                    if entry.is_symlink() or entry.name.startswith('.'):continue
                    file=Path(entry.path)
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name.casefold() not in {'sample','samples','extras','trailers'}:pending.append((file,depth+1))
                    elif file.suffix.lower() in VIDEO and entry.is_file(follow_symlinks=False) and not re.search(r'(?:^|[ ._-])sample(?:[ ._-]|$)',file.stem,re.I):paths.append(str(file.relative_to(root)))
        except OSError:continue
    stems={str(Path(p).with_suffix('')):p for p in paths};groups={}
    for path in paths:
        file=Path(path);stem=str(file.with_suffix(''));base=VARIANT.sub('',stem)
        canonical=stems.get(base,path) if base!=stem else path
        info=episode_identity(canonical)
        key=(re.sub(r'\W+',' ',info['series'].casefold()).strip(),info['season'],info['episode']) if info else canonical
        groups.setdefault(key,[]).append(canonical)
    return [list(set(group)) for group in groups.values()]

def cached_inventory(directory,root,redis):
    key='watch-inventory:v1:'+hashlib.sha256(str(directory).encode()).hexdigest()
    cached=redis.get(key)
    if cached:return json.loads(cached)
    groups=inventory(directory,root)
    if groups is not None:redis.setex(key,90,json.dumps(groups))
    return groups

def combine(path,groups,docs):
    if not groups:return None
    by_path={doc['path']:doc for doc in docs}
    fractions=[]
    for members in groups:
        fractions.append(max((1.0 if by_path[p].get('completed') else min(1,by_path[p].get('position',0)/by_path[p]['duration']) for p in members if p in by_path and by_path[p].get('duration',0)>0),default=0))
    value=sum(fractions)
    return {'path':path,'position':value,'duration':len(groups),'completed':value>=len(groups)-1e-8,'files_count':len(groups),'watched_count':sum(x>=1 for x in fractions),'aggregate':True}
