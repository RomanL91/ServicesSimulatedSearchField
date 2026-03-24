from fastapi import APIRouter, Depends

from app.api.dependencies.queries import get_search_query
from app.api.schemas.search import SearchRequest, SearchResponse
from app.queries.search.search_materials import SearchMaterialsQuery

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/", response_model=SearchResponse)
async def search_materials(
    request: SearchRequest,
    query_handler: SearchMaterialsQuery = Depends(get_search_query),
) -> SearchResponse:
    """
    Поиск материалов по одному или нескольким провайдерам.

    Если `providers` не указан — ищет по всем доступным индексам.
    Результаты отсортированы по релевантности (ranking_score Meilisearch).
    """
    return await query_handler.handle(request)
