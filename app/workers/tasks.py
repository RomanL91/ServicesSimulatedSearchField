from app.core.config import load_all_providers
from app.core.logging import get_logger
from app.infra.strategy_factory import sync_strategy_factory

logger = get_logger(__name__)

_PROVIDERS = {p.provider_name: p for p in load_all_providers()}


async def sync_provider(ctx: dict, provider_name: str) -> dict:
    """ARQ-задача: синхронизация одного провайдера."""
    provider_settings = _PROVIDERS.get(provider_name)
    if not provider_settings:
        raise ValueError(f"Provider '{provider_name}' not found")

    logger.info("Worker: sync started — %s", provider_name)

    strategy = sync_strategy_factory.create(provider_settings)
    await strategy.execute()

    logger.info("Worker: sync completed — %s", provider_name)
    return {"provider": provider_name, "status": "ok"}
