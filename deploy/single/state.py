"""Compare migrated identities without exporting credentials or session tokens."""
import hashlib
import json
import os
import re
from pathlib import Path

from bson.json_util import dumps
from pymongo import MongoClient
from redis import Redis


def snapshot():
    health_path = Path('/run/autolycus/health.json')
    if health_path.exists():
        config = json.loads(health_path.read_text())
        uri, database = config['mongo_uri'], config['database']
        password = json.loads(Path('/data/secrets.json').read_text())['REDIS_PASSWORD']
        host = '127.0.0.1'
    else:
        uri, database = os.environ['MONGO_DATABASE_URI'], os.environ['MONGO_DATABASE_NAME']
        password, host = os.environ['REDIS_PASSWORD'], os.environ['REDIS_HOST']
    with MongoClient(uri) as client:
        db = client[database]
        users = list(db.users.find({}, {
            '_id': 1, 'username': 1, 'password': 1, 'salt': 1,
            'preferences.ftp.password_encrypted': 1,
        }).sort('_id', 1))
        torrents = list(db.torrents.find({}, {
            '_id': 1, 'user_id': 1, 'info_hash': 1, 'url_hash': 1, 'save_dir': 1,
        }).sort('_id', 1))
    redis = Redis(host=host, password=password)
    sessions = []
    for key in sorted(redis.scan_iter()):
        if re.fullmatch(rb'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', key):
            sessions.append(key + b':' + (redis.get(key) or b''))
    return {
        'users': len(users),
        'user_auth_digest': hashlib.sha256(dumps(users, sort_keys=True).encode()).hexdigest(),
        'torrents': len(torrents),
        'torrent_identity_digest': hashlib.sha256(dumps(torrents, sort_keys=True).encode()).hexdigest(),
        'sessions': len(sessions),
        'session_digest': hashlib.sha256(b'\n'.join(sessions)).hexdigest(),
    }


if __name__ == '__main__':
    print(json.dumps(snapshot(), sort_keys=True))
