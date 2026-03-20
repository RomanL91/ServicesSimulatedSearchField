from dataclasses import dataclass, field


@dataclass
class Material:
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
    unit: str | None = field(default=None)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "price": self.price,
            "currency": self.currency,
            "is_active": self.is_active,
            "provider": self.provider,
            "url": self.url,
            "price_with_vat": self.price_with_vat,
            "vat_rate": self.vat_rate,
            "vat_amount": self.vat_amount,
            "supplier_full_name": self.supplier_full_name,
            "supplier_short_name": self.supplier_short_name,
            "supplier_inn": self.supplier_inn,
            "unit": self.unit,
        }
