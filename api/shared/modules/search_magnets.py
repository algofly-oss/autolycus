"""Resolve only server-issued Jackett download references; never fetch arbitrary URLs."""
import base64
import html
import json
import re
import secrets
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
import libtorrent as lt

MAX_TORRENT_BYTES = 4 * 1024 * 1024


def canonical_hash(value):
    value = str(value or '').strip()
    if re.fullmatch(r'[0-9a-fA-F]{40}', value):
        return value.lower()
    if re.fullmatch(r'[A-Za-z2-7]{32}', value):
        return base64.b32decode(value.upper()).hex()
    return None


def normalize_magnet(value):
    value = html.unescape(str(value or '').strip())
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme.lower() != 'magnet':
        return None
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    for key, topic in pairs:
        if key == 'xt' and topic.lower().startswith('urn:btih:'):
            info_hash = canonical_hash(topic[9:])
            if info_hash:
                extra = urlencode([(k, v) for k, v in pairs if k != 'xt'])
                return 'magnet:?xt=urn:btih:' + info_hash + ('&' + extra if extra else '')
    return None


def local_download_path(link, base_url, indexer):
    try:
        base, target = urlsplit(base_url), urlsplit(str(link or ''))
        if target.scheme not in ('http', 'https') or target.netloc != base.netloc or target.username or target.password:
            return None
        if not re.fullmatch(r'[A-Za-z0-9_-]+', str(indexer or '')):
            return None
        if target.path.rstrip('/') != '/dl/' + indexer:
            return None
        # Keep the indexer's signed download parameters; supply our own API key.
        pairs = [(k, v) for k, v in parse_qsl(target.query, keep_blank_values=True)
                 if k.lower() not in ('apikey', 'jackett_apikey')]
        return target.path + ('?' + urlencode(pairs) if pairs else '')
    except ValueError:
        return None


def attach_resolution(item, base_url, user_id):
    path = local_download_path(item.get('Link'), base_url, item.get('TrackerId'))
    if path:
        item['Link'] = None
    if not user_id or normalize_magnet(item.get('MagnetUri')) or canonical_hash(item.get('InfoHash')):
        return
    if path:
        from shared.factory import redis
        token = secrets.token_urlsafe(24)
        redis.set('search_magnet/' + token, json.dumps({'path': path, 'indexer': item['TrackerId'], 'user_id': str(user_id)}), ex=3600)
        item['ResolveToken'] = token
        # Internal download URLs carry Jackett credentials and are not source-page links.
        item['Link'] = None


async def fetch_magnet(base_url, api_key, path, indexer, transport=None):
    headers = {'User-Agent': 'Autolycus-MagnetResolver/1'}
    timeout = httpx.Timeout(65, connect=5)
    async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=False,
                                trust_env=False, transport=transport) as client:
        for _ in range(4):
            target = urljoin(base_url.rstrip('/') + '/', path)
            parts = urlsplit(target)
            query = urlencode(parse_qsl(parts.query, keep_blank_values=True) + [('jackett_apikey', api_key)])
            target = urlunsplit((parts.scheme, parts.netloc, parts.path, query, ''))
            async with client.stream('GET', target) as response:
                if response.is_redirect:
                    location = response.headers.get('location', '')
                    magnet = normalize_magnet(location)
                    if magnet:
                        return magnet
                    path = local_download_path(urljoin(target, location), base_url, indexer)
                    if not path:
                        raise ValueError('Indexer returned a download redirect it cannot resolve. Open the source page.')
                    continue
                response.raise_for_status()
                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    payload.extend(chunk)
                    if len(payload) > MAX_TORRENT_BYTES:
                        raise ValueError('Source returned an oversized torrent metadata file.')
            try:
                magnet = normalize_magnet(lt.make_magnet_uri(lt.torrent_info(lt.bdecode(bytes(payload)))))
                if magnet:
                    return magnet
            except (RuntimeError, ValueError, TypeError):
                pass
            # Some indexers return a magnet in a text or HTML response.
            for value in re.findall(r'magnet:\?[^\s\"\'<>]+', payload.decode('utf-8', errors='ignore'), flags=re.I):
                magnet = normalize_magnet(value)
                if magnet:
                    return magnet
            raise ValueError('Source did not provide a usable magnet or torrent file. Open the source page.')
    raise ValueError('Indexer returned too many redirects.')
