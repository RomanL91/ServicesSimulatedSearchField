from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.provider import ProviderInfo

PROVIDERS_DIR = Path(__file__).parent.parent.parent / "providers"


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    meili_url: str = "http://localhost:7700"
    meili_master_key: str = "YOUR_MASTER_KEY"
    log_level: str = "INFO"

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None
    redis_database: int = 0


class ProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    provider_name: str
    provider_url: str
    supplier_full_name: str
    supplier_short_name: str
    supplier_inn: str
    sync_period_minutes: int = 60
    currency: str = "RUR"
    vat_rate: int = 20

    def to_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.provider_name,
            url=self.provider_url,
            supplier_full_name=self.supplier_full_name,
            supplier_short_name=self.supplier_short_name,
            supplier_inn=self.supplier_inn,
            currency=self.currency,
            vat_rate=self.vat_rate,
            sync_period_minutes=self.sync_period_minutes,
        )


def load_provider(env_file: Path) -> ProviderSettings:
    return ProviderSettings(_env_file=str(env_file))


def load_all_providers() -> list[ProviderSettings]:
    return [load_provider(f) for f in sorted(PROVIDERS_DIR.glob("env.*"))]


settings = AppSettings()
