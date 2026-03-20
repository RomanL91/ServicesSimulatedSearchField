import asyncio
import math

from meilisearch_python_sdk import AsyncClient
from meilisearch_python_sdk.index import AsyncIndex

from app.core.interfaces.indexer import AbstractIndexer
from app.domain.material import Material

_BATCH_SIZE = 1000
# Максимум параллельных запросов к Meilisearch.
# Предотвращает перегрузку при большом количестве батчей.
_MAX_CONCURRENT = 5


def _sanitize(doc: dict) -> dict:
    """Заменяет NaN/Inf на None — JSON не поддерживает эти значения."""
    return {
        k: (None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v)
        for k, v in doc.items()
    }


class MeilisearchIndexer(AbstractIndexer):
    def __init__(self, url: str, api_key: str) -> None:
        self._url = url
        self._api_key = api_key

    async def index(self, materials: list[Material], index_name: str) -> None:
        if not materials:
            return

        docs = [_sanitize(m.to_dict()) for m in materials]
        batches = [docs[i : i + _BATCH_SIZE] for i in range(0, len(docs), _BATCH_SIZE)]

        async with AsyncClient(self._url, self._api_key) as client:
            meili_index = await client.get_or_create_index(
                index_name, primary_key="id"
            )
            await self._upload_batches(meili_index, batches)

    @staticmethod
    async def _upload_batches(
        meili_index: AsyncIndex,
        batches: list[list[dict]],
    ) -> None:
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

        async def _upload(batch: list[dict]) -> None:
            async with semaphore:
                await meili_index.add_documents(batch)

        await asyncio.gather(*[_upload(batch) for batch in batches])
