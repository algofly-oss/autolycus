"""Delete cached artwork only; never modifies source media."""
import re
from pathlib import Path
from shared.modules.preview_sprites import fingerprint

def preview_keys_for_tree(target):
    target=Path(target)
    paths=[target] if target.is_file() else target.rglob('*')
    keys=[]
    for path in paths:
        if path.is_file() and not path.is_symlink():
            try:keys.extend(fingerprint(path,detail) for detail in (False,True))
            except OSError:pass
    return keys

def delete_cached_previews(collection,target,keys):
    source=str(Path(target).resolve())
    collection.delete_many({'$or':[{'_id':{'$in':keys}},
        {'source_path':source},{'source_path':{'$regex':'^'+re.escape(source)+'/'}}]})

def prune_deleted_previews(collection):
    # Metadata only: never load image blobs while checking the cache.
    for doc in collection.find({'source_path':{'$exists':True}},{'source_path':1}):
        if not Path(doc['source_path']).is_file():collection.delete_one({'_id':doc['_id']})
