from app.api.dependencies.commands import get_available_providers
from app.core.config import settings
from app.queries.search.search_materials import SearchMaterialsQuery


def get_search_query() -> SearchMaterialsQuery:
    return SearchMaterialsQuery(
        meili_url=settings.meili_url,
        meili_api_key=settings.meili_master_key,
        available_providers=get_available_providers(),
    )
