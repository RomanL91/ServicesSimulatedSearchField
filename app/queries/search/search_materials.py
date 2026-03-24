import asyncio
import logging

from meilisearch_python_sdk import AsyncClient

from app.api.schemas.search import MaterialResult, SearchRequest, SearchResponse
from app.queries.base import BaseQuery

logger = logging.getLogger(__name__)


class SearchMaterialsQuery(BaseQuery):
    """
    Read-сторона CQRS: поиск материалов по одному или нескольким RAW-индексам.

    Запросы к индексам выполняются параллельно.
    Результаты сливаются и сортируются по ranking_score Meilisearch.
    """

    def __init__(
        self,
        meili_url: str,
        meili_api_key: str,
        available_providers: list[str],
    ) -> None:
        self._meili_url = meili_url
        self._meili_api_key = meili_api_key
        self._available_providers = available_providers

    async def handle(self, request: SearchRequest) -> SearchResponse:
        providers = self._resolve_providers(request.providers)
        index_names = [f"RAW_{p}" for p in providers]

        hits = await self._search_all(request.query, index_names, request.limit)

        hits.sort(key=lambda h: h.get("_rankingScore", 0.0), reverse=True)
        top_hits = hits[: request.limit]

        return SearchResponse(
            query=request.query,
            total=len(hits),
            providers_searched=providers,
            results=[self._to_result(h) for h in top_hits],
        )

    def _resolve_providers(self, requested: list[str] | None) -> list[str]:
        if not requested:
            return self._available_providers
        return [p.upper() for p in requested if p.upper() in self._available_providers]

    async def _search_all(
        self,
        query: str,
        index_names: list[str],
        limit: int,
    ) -> list[dict]:
        async with AsyncClient(self._meili_url, self._meili_api_key) as client:
            tasks = [
                self._search_index(client, idx, query, limit) for idx in index_names
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        hits: list[dict] = []
        for idx, result in zip(index_names, results):
            if isinstance(result, Exception):
                logger.warning("Search failed for index '%s': %s", idx, result)
                continue
            hits.extend(result)

        return hits

    @staticmethod
    async def _search_index(
        client: AsyncClient,
        index_name: str,
        query: str,
        limit: int,
    ) -> list[dict]:
        index = client.index(index_name)
        result = await index.search(
            query,
            limit=limit,
            show_ranking_score=True,
        )
        return result.hits

    @staticmethod
    def _to_result(hit: dict) -> MaterialResult:
        return MaterialResult(
            id=hit.get("id", ""),
            name=hit.get("name", ""),
            price=hit.get("price", 0.0),
            currency=hit.get("currency", ""),
            is_active=hit.get("is_active", True),
            provider=hit.get("provider", ""),
            url=hit.get("url"),
            price_with_vat=hit.get("price_with_vat", 0.0),
            vat_rate=hit.get("vat_rate", 0),
            vat_amount=hit.get("vat_amount", 0.0),
            supplier_full_name=hit.get("supplier_full_name", ""),
            supplier_short_name=hit.get("supplier_short_name", ""),
            supplier_inn=hit.get("supplier_inn", ""),
            unit=hit.get("unit"),
            ranking_score=hit.get("_rankingScore"),
        )
