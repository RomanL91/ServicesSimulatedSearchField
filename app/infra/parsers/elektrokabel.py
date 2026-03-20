import pandas as pd

from app.domain.material import Material
from app.infra.parsers.base import BaseXLSParser

# Структура файла Prais-list_kabel.xls (Электрокабель):
#
# Строка 0 (заголовок):
#   Наименование | Ед. изм. | Цена за ед. руб (с НДС) | Минимальная длина ...
#
# Цены уже включают НДС — используем _reverse_vat() для получения чистой цены.
# Числа в формате "62 164,92" (пробел = тысячи, запятая = десятичный) — обрабатывает _to_float().


class ElektrokabelParser(BaseXLSParser):
    HEADER_ROW: int = 0
    SHEET_NAME: int | str = 0

    # Точные названия колонок в файле (первая строка).
    # Если в реальном файле заголовок "Цена за ед. руб\nс НДС" (многострочный),
    # pandas объединит их через \n — тогда исправить _COL_PRICE ниже.
    _COL_NAME: str = "Наименование"
    _COL_UNIT: str = "Ед. изм."
    _COL_PRICE: str = "Цена за ед. руб"   # может быть "Цена за ед. руб\nс НДС"

    def _build_material(self, row: pd.Series) -> Material | None:
        name = self._to_str(row.get(self._COL_NAME))
        if not name:
            return None

        # Ищем цену: сначала точное совпадение, потом частичное
        raw_price = row.get(self._COL_PRICE)
        if raw_price is None:
            raw_price = self._find_column(row, "цена", "price")

        price_with_vat = self._to_float(raw_price)
        if price_with_vat is None or price_with_vat <= 0:
            return None

        # Цена в файле уже включает НДС
        price_net, vat_amount = self._reverse_vat(price_with_vat)

        unit = self._to_str(row.get(self._COL_UNIT)) or None

        return Material(
            id=self._generate_id(name),
            name=name,
            price=price_net,
            currency=self._provider.currency,
            is_active=True,
            provider=self._provider.name,
            url=None,
            price_with_vat=price_with_vat,
            vat_rate=self._provider.vat_rate,
            vat_amount=vat_amount,
            supplier_full_name=self._provider.supplier_full_name,
            supplier_short_name=self._provider.supplier_short_name,
            supplier_inn=self._provider.supplier_inn,
            unit=unit,
        )
