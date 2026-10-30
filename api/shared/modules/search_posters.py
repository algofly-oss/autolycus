"""Lazy, bounded poster lookup with verified alternative titles and release dates."""
import asyncio
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from functools import lru_cache
from urllib.parse import quote, urlencode, urlsplit

import requests

from .media_metadata import _tmdb_search_metadata, _search_imdb_suggestion, _search_imdb_suggestion_tv, _imdb_url
from .search_quality import words
from .torrent_name_parser import parse

logger = logging.getLogger(__name__)
MAX_POSTER_BYTES = 1024 * 1024
MAX_CACHE_BYTES = 64 * 1024 * 1024
MAX_ENTRIES = 512
MAX_NEGATIVE_ENTRIES = 128
LOOKUP_VERSION = 2
_slots = asyncio.Semaphore(3)
_pending = {}
_indexes_ready = False
_index_lock = asyncio.Lock()
_cache_lock = asyncio.Lock()


def media_identity(name, kind='movie'):
    parsed = parse(name)
    title = re.sub(r'[._]+', ' ', str(parsed.get('title') or name)).strip()
    bilingual = re.split(r'\s*/\s*', title)
    if len(bilingual) > 1:
        title = next((part for part in bilingual if re.search(r'[A-Za-z]', part)), bilingual[0]).strip()
    translated = re.match(r'^[^A-Za-z]+\s+([A-Za-z].*)$', title)
    if translated:
        title = translated.group(1).strip()
    # AKA is release-name annotation, not part of the film's main title.
    title = re.split(r'\b(?:a\s*k\s*a|also known as)\b', title, maxsplit=1, flags=re.I)[0].strip(' ()[]-')
    title = re.sub(r'\b(?:[A-Z]\s+){2,}[A-Z]\b', lambda match: ''.join(match.group().split()), title, flags=re.I)
    year = parsed.get('year')
    if isinstance(year, list):
        year = year[0] if year else None
    year = int(year) if str(year or '').isdigit() else None
    parsed.update(title=title, year=year)
    if kind == 'tv' and not parsed.get('season'):
        parsed['season'] = 1
    media_type = 'tv' if parsed.get('season') or parsed.get('episode') else 'movie'
    key = hashlib.sha256(json.dumps([' '.join(words(title)), year, media_type]).encode()).hexdigest()
    return key, parsed, media_type


def _title_matches(requested, candidate):
    def tokens(value):
        value = re.sub(r'\b(?:[A-Za-z][.\s]+){2,}[A-Za-z]\b', lambda match: ''.join(re.findall(r'[A-Za-z]', match.group())), str(value or ''))
        return words(value)
    required, available = tokens(requested), tokens(candidate)
    if not required:
        return False
    coverage = sum(any(word == other or (len(word) >= 6 and len(other) >= 6 and SequenceMatcher(None, word, other).ratio() >= 0.88)
                       for other in available) for word in required) / len(required)
    return coverage >= 0.8


def matches_identity(parsed, metadata):
    if not metadata:
        return False
    titles = [metadata.get('title'), metadata.get('original_title'), *metadata.get('aliases', [])]
    if not any(_title_matches(parsed.get('title'), title) for title in titles):
        return False
    if parsed.get('year') and metadata.get('year') and not parsed.get('season'):
        # A festival year may differ from theatrical/streaming release years.
        # Accept that only when the provider explicitly lists the requested year.
        return int(parsed['year']) in {int(metadata['year']), *metadata.get('release_years', [])}
    return True


def acceptable_match(parsed, metadata):
    if not matches_identity(parsed, metadata) or not metadata.get('poster_bytes') or len(metadata['poster_bytes']) > MAX_POSTER_BYTES:
        return False
    mime = str(metadata.get('poster_mime') or 'image/jpeg').split(';')[0].lower()
    return mime in {'image/jpeg', 'image/png', 'image/webp', 'image/avif'}


@lru_cache(maxsize=128)
def _imdb_title_details(imdb_id, hour):
    if not re.fullmatch(r'tt\d{7,12}', str(imdb_id or '')):
        return {}
    query = ('query{title(id:"' + imdb_id + '"){titleText{text}originalTitleText{text}'
             'akas(first:40){edges{node{text}}}releaseDates(first:80){edges{node{year}}}primaryImage{url}}}')
    # Percent-encoded spaces (rather than '+') are required by this endpoint.
    url = 'https://caching.graphql.imdb.com/?' + urlencode({'query': query}, quote_via=quote)
    response = requests.get(url, headers={'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0', 'x-imdb-client-name': 'imdb-web-next'}, timeout=8)
    response.raise_for_status()
    title = (response.json().get('data') or {}).get('title') or {}
    return {
        'original_title': (title.get('originalTitleText') or {}).get('text'),
        'aliases': [edge['node']['text'] for edge in (title.get('akas') or {}).get('edges', []) if edge.get('node', {}).get('text')],
        'release_years': sorted({edge['node']['year'] for edge in (title.get('releaseDates') or {}).get('edges', []) if edge.get('node', {}).get('year')}),
        'image_url': (title.get('primaryImage') or {}).get('url'),
    }


def _imdb_search_metadata(parsed):
    suggestion = _search_imdb_suggestion_tv if parsed.get('season') or parsed.get('episode') else _search_imdb_suggestion
    result = suggestion(parsed.get('title'), parsed.get('year')) or {}
    metadata = {'title': result.get('l'), 'year': result.get('y'), 'imdb_url': _imdb_url(result.get('id'))}
    url = (result.get('i') or {}).get('imageUrl') or ''
    if not matches_identity(parsed, metadata) or not url:
        details = _imdb_title_details(result.get('id'), int(time.time() // 3600))
        metadata.update({key: value for key, value in details.items() if key != 'image_url'})
        url = url or details.get('image_url') or ''
    if not matches_identity(parsed, metadata):
        return {}
    # Preserve a verified local/alternative name instead of relabelling the card.
    if not _title_matches(parsed.get('title'), result.get('l')):
        metadata['provider_title'] = metadata['title']
        metadata['title'] = parsed['title']
    target = urlsplit(url)
    if target.scheme != 'https' or target.hostname not in {'m.media-amazon.com', 'ia.media-imdb.com', 'images-na.ssl-images-amazon.com'}:
        return {}
    url = re.sub(r'\._V1_.*(?=\.[A-Za-z]+$)', '._V1_SX360_', url)
    with requests.get(url, timeout=12, stream=True) as response:
        response.raise_for_status()
        image = bytearray()
        for chunk in response.iter_content(65536):
            image.extend(chunk)
            if len(image) > MAX_POSTER_BYTES:
                raise ValueError('Poster exceeds thumbnail limit')
        mime = response.headers.get('content-type', 'image/jpeg')
    return dict(metadata, poster_bytes=bytes(image), poster_mime=mime)


def lookup_metadata(parsed):
    for provider in (_tmdb_search_metadata, _imdb_search_metadata):
        try:
            metadata = provider(parsed)
            if acceptable_match(parsed, metadata):
                return metadata
        except Exception:
            logger.info('Search poster provider unavailable')
    return {}


def public_poster(doc):
    return {
        'id': doc['_id'], 'title': doc.get('title'), 'year': doc.get('year'),
        'media_type': doc.get('media_type'), 'overview': doc.get('overview'),
        'vote_average': doc.get('vote_average'), 'imdb_url': doc.get('imdb_url'),
        'poster_url': '/api/torrent/search-poster/' + doc['_id'] if doc.get('has_poster') else None,
    }


def cached_query(key):
    return {'_id': key, 'expires_at': {'$gt': datetime.utcnow()},
            '$or': [{'has_poster': True}, {'lookup_version': LOOKUP_VERSION}]}


async def touch_poster(collection, key, size=None):
    now = datetime.utcnow()
    stale = [{'last_accessed': {'$exists': False}}, {'last_accessed': {'$lt': now - timedelta(minutes=10)}}]
    updates = {'last_accessed': now}
    if size is not None:
        stale.append({'poster_size': {'$exists': False}})
        updates['poster_size'] = size
    await collection.update_one({'_id': key, '$or': stale}, {'$set': updates})


def eviction_keys(entries, now=None, max_bytes=MAX_CACHE_BYTES, max_entries=MAX_ENTRIES):
    now = now or datetime.utcnow()
    ordered = sorted(entries, key=lambda entry: entry.get('last_accessed') or entry.get('updated_at') or datetime.min, reverse=True)
    total, count, negative, obsolete = 0, 0, 0, []
    for entry in ordered:
        size = entry.get('poster_size', MAX_POSTER_BYTES if entry.get('has_poster') else 0)
        no_image = not entry.get('has_poster')
        if entry.get('expires_at', now) <= now or count >= max_entries or total + size > max_bytes or (no_image and negative >= MAX_NEGATIVE_ENTRIES):
            obsolete.append(entry['_id'])
            continue
        total += size
        count += 1
        negative += int(no_image)
    return obsolete


async def prune_cache(collection):
    entries = await collection.find({}, {'_id': 1, 'last_accessed': 1, 'updated_at': 1, 'expires_at': 1, 'poster_size': 1, 'has_poster': 1}).to_list(length=None)
    obsolete = eviction_keys(entries)
    if obsolete:
        await collection.delete_many({'_id': {'$in': obsolete}})


async def _ensure_indexes(collection):
    global _indexes_ready
    if _indexes_ready:
        return
    async with _index_lock:
        if not _indexes_ready:
            await collection.create_index('expires_at', expireAfterSeconds=0)
            await collection.create_index([('last_accessed', -1)])
            async with _cache_lock:
                await prune_cache(collection)
            _indexes_ready = True


async def _lookup_and_cache(collection, key, parsed, media_type):
    async with _slots:
        existing = await collection.find_one(cached_query(key), {'poster_bytes': False})
        if existing:
            await touch_poster(collection, key)
            return public_poster(existing)
        metadata = await asyncio.to_thread(lookup_metadata, parsed)
        now = datetime.utcnow()
        doc = dict(metadata, _id=key, title=metadata.get('title') or parsed['title'],
                   year=metadata.get('year') or parsed.get('year'), media_type=media_type,
                   has_poster=bool(metadata.get('poster_bytes')), updated_at=now, last_accessed=now,
                   poster_size=len(metadata.get('poster_bytes') or b''), lookup_version=LOOKUP_VERSION,
                   expires_at=now + (timedelta(days=7) if metadata else timedelta(minutes=5)))
        async with _cache_lock:
            await collection.replace_one({'_id': key}, doc, upsert=True)
            await prune_cache(collection)
        return public_poster(doc)


async def search_poster(collection, name, kind='movie'):
    await _ensure_indexes(collection)
    key, parsed, media_type = media_identity(name, kind)
    existing = await collection.find_one(cached_query(key), {'poster_bytes': False})
    if existing:
        await touch_poster(collection, key)
        return public_poster(existing)
    task = _pending.get(key)
    if task is None:
        if len(_pending) >= 64:
            return public_poster({'_id': key, **parsed, 'media_type': media_type})
        task = asyncio.create_task(_lookup_and_cache(collection, key, parsed, media_type))
        _pending[key] = task
        def finished(done):
            if _pending.get(key) is done:
                _pending.pop(key, None)
            if not done.cancelled():
                done.exception()
        task.add_done_callback(finished)
    return await asyncio.shield(task)
