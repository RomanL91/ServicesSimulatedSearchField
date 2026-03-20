from dataclasses import dataclass


@dataclass
class ProviderInfo:
    name: str
    url: str
    supplier_full_name: str
    supplier_short_name: str
    supplier_inn: str
    currency: str
    vat_rate: int
    sync_period_minutes: int

    @property
    def raw_index_name(self) -> str:
        return f"RAW_{self.name}"
