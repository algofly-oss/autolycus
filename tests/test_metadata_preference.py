"""A matched episode poster must outrank a larger unmatched season-pack record."""
import asyncio,os
from pathlib import Path
pid=Path('/run/autolycus/services/api').read_text().strip()
for entry in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
 if b'=' in entry:
  key,value=entry.split(b'=',1);os.environ[key.decode()]=value.decode()
from motor.motor_asyncio import AsyncIOMotorClient
from shared.modules.media_metadata import attach_media_metadata,media_metadata_for_torrent_ids
async def main():
 client=AsyncIOMotorClient(os.environ['MONGO_DATABASE_URI']);db=client[os.environ['MONGO_DATABASE_NAME']]
 user='metadata-priority-test';key='poster-priority-only'
 await db.movie_metadata.delete_many({'user_id':user})
 try:
  await db.movie_metadata.insert_many([{'user_id':user,'torrent_id':key,'title':'Long unmatched pack title','file_size':9000000000,'lookup_status':'local'},{'user_id':user,'torrent_id':key,'title':'Matched series','file_size':100000,'imdb_id':'tt1234567','poster_mime':'image/jpeg','poster_bytes':b'fixture'}])
  items=await attach_media_metadata(db,user,[{'info_hash':key}]);assert items[0]['media_metadata']['title']=='Matched series' and items[0]['media_metadata']['poster_url']
  lookup=await media_metadata_for_torrent_ids(db,user,[key]);assert lookup[key]['title']=='Matched series' and lookup[key]['poster_url']
  print('PASS: matched episode poster outranks larger local-only pack for home cards and catalog lookup',flush=True)
 finally:
  await db.movie_metadata.delete_many({'user_id':user});client.close()
asyncio.run(main())
