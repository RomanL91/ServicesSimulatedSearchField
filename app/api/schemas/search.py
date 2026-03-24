from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1, le=100)
    providers: list[str] | None = Field(
        default=None,
        description="Список провайдеров для поиска. None — искать по всем.",
    )


class MaterialResult(BaseModel):
    id: str
    name: str
    price: float
    currency: str
    is_active: bool
    provider: str
    url: str | None
    price_with_vat: float
    vat_rate: int
    vat_amount: float
    supplier_full_name: str
    supplier_short_name: str
    supplier_inn: str
    unit: str | None
    ranking_score: float | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    providers_searched: list[str]
    results: list[MaterialResult]
