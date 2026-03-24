from fastapi import HTTPException

from app.core.config import load_all_providers
from app.domain.strategies.sync_provider import SyncProviderStrategy
from app.infra.parsers.registry import PARSER_REGISTRY
from app.infra.strategy_factory import sync_strategy_factory

_PROVIDERS = {p.provider_name.upper(): p for p in load_all_providers()}


def get_sync_strategy(provider_name: str) -> SyncProviderStrategy:
    name = provider_name.upper()
    provider_settings = _PROVIDERS.get(name)

    if provider_settings is None:
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{name}' not found. Available: {list(_PROVIDERS)}",
        )

    if name not in PARSER_REGISTRY:
        raise HTTPException(
            status_code=422,
            detail=f"No parser registered for provider '{name}'",
        )

    return sync_strategy_factory.create(provider_settings)


def validate_provider(provider_name: str) -> None:
    get_sync_strategy(provider_name)


def get_available_providers() -> list[str]:
    return list(_PROVIDERS.keys())
