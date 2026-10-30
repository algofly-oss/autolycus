import os
import asyncio
import logging
import time
import httpx
from typing import AsyncIterator, List, Optional, Tuple
from .torrent_name_parser import parse
from .search_acceleration import SearchAcceleration, result_key
from .search_quality import query_variants, relevance
from .search_magnets import attach_resolution


logger = logging.getLogger(__name__)


class AsyncJackett:
    def __init__(
        self,
        apikey: str,
        base_url: Optional[str] = None,
        max_concurrency: int = 20,
        timeout: Optional[float] = None,
        store=None,
    ):
        self.base_url = (base_url or os.environ.get("JACKETT_URL", "http://jackett:9117")).rstrip("/")
        self.apikey = apikey
        self.acceleration = SearchAcceleration(store)
        self._inventory = None
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.timeout = httpx.Timeout(timeout, connect=5.0)

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

    # -------------------------------
    # Index discovery
    # -------------------------------
    async def list_indexes(self) -> List[str]:
        if self._inventory and time.monotonic() - self._inventory[0] < 30:
            return list(self._inventory[1])
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=True,  # IMPORTANT
        ) as client:

            # 🔥 Prime Jackett UI session (sets cookies)
            await client.get(f"{self.base_url}/UI/Dashboard")

            r = await client.get(
                f"{self.base_url}/api/v2.0/indexers",
                params={"apikey": self.apikey},
            )

            r.raise_for_status()

            try:
                indexers = r.json()
            except ValueError:
                logger.exception(
                    "Jackett index discovery returned non-JSON response: %s",
                    r.text[:500],
                )
                raise

            configured_indexes = [
                x["id"] for x in indexers if x.get("configured") is True
            ]
            logger.info(
                "Jackett discovered %d configured indexers", len(configured_indexes)
            )
            self._inventory = (time.monotonic(), configured_indexes)
            return configured_indexes

    # -------------------------------
    # Search one index
    # -------------------------------
    async def _search_index(
        self,
        client: httpx.AsyncClient,
        query: str,
        index: str,
        cancel_event: asyncio.Event,
    ) -> Tuple[str, List[dict], Optional[str]]:
        if cancel_event.is_set():
            return index, [], None

        async with self.semaphore:
            if cancel_event.is_set():
                return index, [], None

            started, succeeded, cancelled = time.monotonic(), False, False
            try:
                r = await client.get(
                    f"{self.base_url}/api/v2.0/indexers/{index}/results",
                    params={
                        "apikey": self.apikey,
                        "Query": query,
                    },
                )
                payload = r.json()

                if r.status_code >= 400:
                    error = payload.get("error") or f"HTTP {r.status_code}"
                    logger.warning(
                        "Jackett indexer %s returned HTTP %s for query %r: %s",
                        index,
                        r.status_code,
                        query,
                        error,
                    )
                    return index, [], error

                if payload.get("result") == "error":
                    logger.warning(
                        "Jackett indexer %s failed for query %r: %s",
                        index,
                        query,
                        payload.get("error"),
                    )
                    return index, [], payload.get("error") or "Indexer failed"

                results = payload.get("Results", [])
                logger.info(
                    "Jackett indexer %s returned %d raw results for query %r",
                    index,
                    len(results),
                    query,
                )
                succeeded = True
                return index, results, None

            except asyncio.CancelledError:
                cancelled = True
                raise

            except httpx.TimeoutException:
                error = f"Timed out after {self.timeout}"
                logger.warning(
                    "Jackett indexer %s timed out for query %r: %s",
                    index,
                    query,
                    error,
                )
                return index, [], error

            except httpx.HTTPStatusError as e:
                error = f"HTTP {e.response.status_code}"
                logger.warning(
                    "Jackett indexer %s returned HTTP %s for query %r: %s",
                    index,
                    e.response.status_code,
                    query,
                    e.response.text[:500],
                )
                return index, [], error

            except ValueError:
                error = "Returned an invalid response"
                logger.exception(
                    "Jackett indexer %s returned non-JSON response for query %r",
                    index,
                    query,
                )
                return index, [], error

            except Exception as e:
                error = str(e) or e.__class__.__name__
                logger.exception(
                    "Unexpected Jackett indexer %s failure for query %r",
                    index,
                    query,
                )
                return index, [], error
            finally:
                if not cancelled:
                    await self.acceleration.observe(index, time.monotonic() - started, succeeded)

    # -------------------------------
    # Streaming async search
    # -------------------------------
    async def search(
        self,
        query: str,
        indexes: Optional[List[str]] = None,
        cancel_event: Optional[asyncio.Event] = None,
        user_id: Optional[str] = None,
        deep: bool = False,
    ) -> AsyncIterator[dict]:
        cancel_event = cancel_event or asyncio.Event()

        if not indexes:
            try:
                indexes = await self.list_indexes()
            except Exception as e:
                logger.exception("Jackett index discovery failed")
                yield {
                    "__type": "indexer_error",
                    "scope": "discovery",
                    "message": str(e) or e.__class__.__name__,
                }
                return

        acceleration = self.acceleration
        key = acceleration.cache_key(self.base_url, query, indexes, deep)
        snapshot = await acceleration.read(key)
        if snapshot:
            yield {"__type": "cache_status", "cached": True}
            for source, entry in snapshot.items():
                for raw in entry['rows']:
                    if cancel_event.is_set():
                        return
                    item = dict(raw, SearchCached=True)
                    attach_resolution(item, self.base_url, user_id)
                    yield item
        await acceleration.load_metrics()
        indexes = acceleration.order(indexes)
        variants = query_variants(query) if deep else [query]
        dirty, checkpoint = False, time.monotonic()
        round_iterator = None
        try:
            for attempt, variant in enumerate(variants):
                if cancel_event.is_set():
                    return
                if attempt:
                    yield {"__type": "search_status", "message": "Trying broader keywords: " + variant}
                found, fresh = 0, {}
                round_iterator = self._search_round(variant, indexes, cancel_event, deep)
                async for item in round_iterator:
                    kind = item.get("__type")
                    if kind == 'source_complete':
                        source = item['indexer']
                        snapshot[source] = {'time': time.time(), 'rows': fresh.pop(source, [])}
                        dirty = True
                        yield item
                        if time.monotonic() - checkpoint >= 3:
                            await acceleration.write(key, snapshot)
                            dirty, checkpoint = False, time.monotonic()
                        continue
                    if not kind:
                        found += 1
                        item["SearchRelevance"] = relevance(query, item.get("Title"))
                        if acceleration.enabled:
                            fresh.setdefault(item['SearchSource'], []).append(dict(item))
                        attach_resolution(item, self.base_url, user_id)
                    yield item
                if found:
                    return
        finally:
            if round_iterator is not None:
                await round_iterator.aclose()
            if dirty:
                await acceleration.write(key, snapshot)


    async def _search_round(self, query, indexes, cancel_event, deep=False):
        timeout = httpx.Timeout(65, connect=5) if deep else self.timeout
        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=timeout,
            follow_redirects=True,
        ) as client:

            tasks = [
                asyncio.create_task(
                    self._search_index(client, query, index, cancel_event)
                )
                for index in indexes
            ]

            try:
                for coro in asyncio.as_completed(tasks):
                    if cancel_event.is_set():
                        break

                    index, results, error = await coro
                    if error:
                        yield {
                            "__type": "indexer_error",
                            "indexer": index,
                            "message": error,
                        }
                        continue

                    for item in results:
                        if cancel_event.is_set():
                            return

                        if item.get("Title"):
                            if self.acceleration.enabled:
                                item = dict(item, SearchSource=index, SearchResultKey=result_key(item, index), SearchCached=False)
                            try:
                                item["parsed"] = parse(item["Title"])
                            except Exception:
                                logger.exception(
                                    "Failed to parse torrent title from %s: %r",
                                    item.get("TrackerId") or item.get("Tracker"),
                                    item.get("Title"),
                                )
                            yield item
                    if self.acceleration.enabled:
                        yield {"__type": "source_complete", "indexer": index}

            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)


async def main(query):
    jackett_instance = AsyncJackett(apikey=os.environ.get("JACKETT_API_KEY"))
    async for result in jackett_instance.search(query):
        print(result)


if __name__ == "__main__":
    asyncio.run(main(query="2025"))
