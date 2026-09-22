import os
import asyncio
import logging
import httpx
from typing import AsyncIterator, List, Optional, Tuple
from .torrent_name_parser import parse


logger = logging.getLogger(__name__)


class AsyncJackett:
    def __init__(
        self,
        apikey: str,
        base_url: str = "http://jackett:9117",
        max_concurrency: int = 20,
        timeout: float = 20.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.apikey = apikey
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.timeout = httpx.Timeout(timeout)

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
                return index, results, None

            except asyncio.CancelledError:
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

    # -------------------------------
    # Streaming async search
    # -------------------------------
    async def search(
        self,
        query: str,
        indexes: Optional[List[str]] = None,
        cancel_event: Optional[asyncio.Event] = None,
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

        async with httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
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

                        if item.get("Seeders", 0) > 0:
                            try:
                                item["parsed"] = parse(item["Title"])
                            except Exception:
                                logger.exception(
                                    "Failed to parse torrent title from %s: %r",
                                    item.get("TrackerId") or item.get("Tracker"),
                                    item.get("Title"),
                                )
                            yield item

            finally:
                cancel_event.set()
                for task in tasks:
                    task.cancel()


async def main(query):
    jackett_instance = AsyncJackett(apikey=os.environ.get("JACKETT_API_KEY"))
    async for result in jackett_instance.search(query):
        print(result)


if __name__ == "__main__":
    asyncio.run(main(query="2025"))
