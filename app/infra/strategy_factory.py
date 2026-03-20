from app.core.config import ProviderSettings, settings
from app.domain.strategies.sync_provider import SyncProviderStrategy
from app.infra.downloader import HttpxDownloader
from app.infra.meilisearch import MeilisearchIndexer
from app.infra.parsers.registry import PARSER_REGISTRY


class SyncStrategyFactory:
    """
    Фабрика для создания SyncProviderStrategy.

    Единственное место где знают о конкретных реализациях инфраструктуры.
    Используется и в API-слое, и в ARQ-воркере.
    """

    def create(self, provider_settings: ProviderSettings) -> SyncProviderStrategy:
        name = provider_settings.provider_name
        parser_class = PARSER_REGISTRY.get(name)

        if parser_class is None:
            raise ValueError(f"No parser registered for provider '{name}'")

        provider_info = provider_settings.to_provider_info()

        return SyncProviderStrategy(
            downloader=HttpxDownloader(),
            parser=parser_class(provider_info),
            indexer=MeilisearchIndexer(settings.meili_url, settings.meili_master_key),
            provider=provider_info,
        )


# Синглтон — конфигурация не меняется в рантайме
sync_strategy_factory = SyncStrategyFactory()
