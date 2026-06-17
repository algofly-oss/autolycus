import asyncio
import time

import requests

from shared.env import (
    MEILI_SEARCH_API_KEY,
    MEILI_SEARCH_HOST,
    MEILI_SEARCH_INDEX_NAME_PREFIX,
    MEILI_SEARCH_MAX_TOTAL_HITS,
)


class MeiliTask:
    def __init__(self, task_uid):
        self.task_uid = task_uid


class MeiliIndex:
    def __init__(self, client, uid):
        self.client = client
        self.uid = uid

    def _request(self, method, path, **kwargs):
        return self.client.request(method, f"/indexes/{self.uid}{path}", **kwargs)

    def update_searchable_attributes(self, attributes):
        data = self._request("put", "/settings/searchable-attributes", json=attributes)
        return MeiliTask(data.get("taskUid"))

    def update_filterable_attributes(self, attributes):
        data = self._request("put", "/settings/filterable-attributes", json=attributes)
        return MeiliTask(data.get("taskUid"))

    def update_sortable_attributes(self, attributes):
        data = self._request("put", "/settings/sortable-attributes", json=attributes)
        return MeiliTask(data.get("taskUid"))

    def update_pagination_settings(self, settings):
        data = self._request("patch", "/settings/pagination", json=settings)
        return MeiliTask(data.get("taskUid"))

    def update_typo_tolerance_settings(self, settings):
        data = self._request("patch", "/settings/typo-tolerance", json=settings)
        return MeiliTask(data.get("taskUid"))

    def update_documents(self, documents):
        data = self._request("post", "/documents", json=documents)
        return MeiliTask(data.get("taskUid"))

    def delete_documents(self, document_ids):
        data = self._request("post", "/documents/delete-batch", json=document_ids)
        return MeiliTask(data.get("taskUid"))

    def search(self, query, options=None):
        payload = {"q": query, **(options or {})}
        return self._request("post", "/search", json=payload)

    def wait_for_task(self, task_uid, timeout_in_ms=20000):
        return self.client.wait_for_task(task_uid, timeout_in_ms=timeout_in_ms)


class MeiliSearchClient:
    def __init__(self, host: str, api_key, index_name_prefix: str):
        self.host = str(host or "").rstrip("/")
        self.api_key = api_key
        self.index_name_prefix = index_name_prefix
        self.available = bool(self.host)

    def headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def request(self, method, path, **kwargs):
        if not self.available:
            raise RuntimeError("Meilisearch is not configured")

        response = requests.request(
            method,
            f"{self.host}{path}",
            headers=self.headers(),
            timeout=10,
            **kwargs,
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    def wait_for_task(self, task_uid, timeout_in_ms=20000):
        if not task_uid:
            return {}

        deadline = time.time() + timeout_in_ms / 1000
        while time.time() < deadline:
            data = self.request("get", f"/tasks/{task_uid}")
            if data.get("status") in {"succeeded", "failed", "canceled"}:
                return data
            time.sleep(0.1)
        return {}

    def file_index_uid(self):
        return f"{self.index_name_prefix}_files"

    def file_index(self):
        if not self.available:
            return None
        return MeiliIndex(self, self.file_index_uid())

    def ensure_file_index(self):
        if not self.available:
            return None

        index_uid = self.file_index_uid()
        try:
            self.request("get", f"/indexes/{index_uid}")
        except Exception:
            task = self.request("post", "/indexes", json={"uid": index_uid, "primaryKey": "id"})
            self.wait_for_task(task.get("taskUid"), timeout_in_ms=20000)

        index = self.file_index()
        tasks = [
            index.update_searchable_attributes(
                [
                    "name",
                    "stem",
                    "extension",
                    "relative_path",
                    "directory_path",
                    "directory_names",
                    "torrent_title",
                    "content",
                ]
            ),
            index.update_filterable_attributes(
                [
                    "user_id",
                    "torrent_id",
                    "torrent_title",
                    "item_type",
                    "is_torrent_root",
                    "extension",
                    "relative_path",
                    "directory_path",
                ]
            ),
            index.update_sortable_attributes(["name", "size", "last_modified_ts"]),
            index.update_pagination_settings(
                {"maxTotalHits": MEILI_SEARCH_MAX_TOTAL_HITS}
            ),
            index.update_typo_tolerance_settings(
                {
                    "enabled": True,
                    "minWordSizeForTypos": {
                        "oneTypo": 4,
                        "twoTypos": 8,
                    },
                }
            ),
        ]
        for task in tasks:
            index.wait_for_task(task.task_uid, timeout_in_ms=20000)

        return index

    async def ensure_file_index_async(self):
        return await asyncio.to_thread(self.ensure_file_index)


meili = MeiliSearchClient(
    host=MEILI_SEARCH_HOST,
    api_key=MEILI_SEARCH_API_KEY,
    index_name_prefix=MEILI_SEARCH_INDEX_NAME_PREFIX,
)
