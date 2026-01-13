import os
import asyncio
import httpx
from typing import AsyncIterator, List, Optional
from .torrent_name_parser import parse


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

            return [x["id"] for x in r.json() if x.get("configured") is True]

    # -------------------------------
    # Search one index
    # -------------------------------
    async def _search_index(
        self,
        client: httpx.AsyncClient,
        query: str,
        index: str,
        cancel_event: asyncio.Event,
    ) -> List[dict]:
        if cancel_event.is_set():
            return []

        async with self.semaphore:
            if cancel_event.is_set():
                return []

            try:
                r = await client.get(
                    f"{self.base_url}/api/v2.0/indexers/{index}/results",
                    params={
                        "apikey": self.apikey,
                        "Query": query,
                    },
                )
                r.raise_for_status()
                return r.json().get("Results", [])

            except asyncio.CancelledError:
                raise

            except Exception:
                return []

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
            indexes = await self.list_indexes()

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

                    results = await coro
                    for item in results:
                        if cancel_event.is_set():
                            return

                        if item.get("Seeders", 0) > 0:
                            try:
                                item["parsed"] = parse(item["Title"])
                            except Exception as e:
                                print(e)
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
