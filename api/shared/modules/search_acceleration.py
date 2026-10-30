"""Bounded shared search snapshots and adaptive source scheduling."""
import asyncio
import hashlib
import json
import logging
import time

logger = logging.getLogger(__name__)
CACHE_SECONDS = 600
MAX_CACHE_BYTES = 1024 * 1024
MAX_CACHE_QUERIES = 16
PREFIX = 'search_acceleration:v1:'


class SearchAcceleration:
    def __init__(self, store=None):
        self.store = store
        self.metrics = {}
        self.loaded = False

    @property
    def enabled(self):
        return self.store is not None

    async def load_metrics(self):
        if not self.enabled or self.loaded:
            return
        try:
            values = await asyncio.to_thread(self.store.hgetall, PREFIX + 'metrics')
            self.metrics.update({(k.decode() if isinstance(k, bytes) else k): json.loads(v) for k, v in values.items()})
            self.loaded = True
        except Exception:
            logger.warning('Search timing history unavailable; using default source order')

    def order(self, indexes):
        def score(index):
            metric = self.metrics.get(index)
            return metric['latency'] / max(0.1, metric['success']) if metric else 5.0
        return sorted(indexes, key=score)

    async def observe(self, index, seconds, success):
        if not self.enabled:
            return
        previous = self.metrics.get(index)
        alpha = 0.25
        metric = {
            'latency': max(0.001, seconds) if not previous else previous['latency'] * (1-alpha) + max(0.001, seconds) * alpha,
            'success': float(success) if not previous else previous['success'] * (1-alpha) + float(success) * alpha,
        }
        self.metrics[index] = metric
        try:
            await asyncio.to_thread(self.store.hset, PREFIX + 'metrics', index, json.dumps(metric))
        except Exception:
            logger.warning('Could not persist source timing history')

    def cache_key(self, base_url, query, indexes, deep):
        scope = [base_url, ' '.join(query.strip().split()).casefold(), sorted(indexes), bool(deep)]
        return PREFIX + 'query:' + hashlib.sha256(json.dumps(scope).encode()).hexdigest()

    async def read(self, key):
        if not self.enabled:
            return {}
        try:
            value = await asyncio.to_thread(self.store.get, key)
            data = json.loads(value) if value else {}
            cutoff = time.time() - CACHE_SECONDS
            return {source: entry for source, entry in data.items() if entry['time'] > cutoff}
        except Exception:
            logger.warning('Search cache unavailable; continuing with live search')
            return {}

    async def write(self, key, snapshot):
        if not self.enabled or not snapshot:
            return
        try:
            def encode():
                # Cache only complete source batches, preserving source replacement.
                limited, size = {}, 2
                cutoff = time.time() - CACHE_SECONDS
                for source, entry in sorted(snapshot.items(), key=lambda item: item[1]['time'], reverse=True):
                    if entry['time'] <= cutoff:
                        continue
                    encoded = json.dumps({source: entry}, separators=(',', ':'))
                    length = len(encoded.encode())
                    if size + length <= MAX_CACHE_BYTES:
                        limited[source] = entry
                        size += length
                return json.dumps(limited, separators=(',', ':'))
            payload = await asyncio.to_thread(encode)
            # One atomic write bounds all query snapshots to 16 MiB plus metadata.
            script = '''
            redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
            redis.call('ZADD', KEYS[2], ARGV[3], KEYS[1])
            local old = redis.call('ZRANGE', KEYS[2], 0, -tonumber(ARGV[4])-1)
            for _, key in ipairs(old) do
                redis.call('DEL', key)
                redis.call('ZREM', KEYS[2], key)
            end
            redis.call('EXPIRE', KEYS[2], ARGV[2])
            return 1
            '''
            await asyncio.to_thread(self.store.eval, script, 2, key, PREFIX + 'queries', payload, CACHE_SECONDS, time.time(), MAX_CACHE_QUERIES)
        except Exception:
            logger.warning('Could not persist search snapshot; live results remain available')


def result_key(item, source):
    identity = [source, item.get('InfoHash') or item.get('Details') or [item.get('Title'), item.get('Size'), item.get('PublishDate')]]
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
