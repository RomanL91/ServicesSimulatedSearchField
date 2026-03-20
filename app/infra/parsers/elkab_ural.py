import pandas as pd

from app.domain.material import Material
from app.infra.parsers.base import BaseXLSParser

# Структура файла price.xls (Элкаб-Урал):
#
# Файл отдаётся как HTML с расширением .xls — xlrd падает с CompDocError,
# читаем через HTML-fallback (pd.read_html).
#
# HTML-таблица с данными содержит заголовок:
#   Название | Ед. изм. | Цена, (руб.)
#
# Особенности:
# - Цена БЕЗ НДС → используем _calculate_vat()
# - Заголовок "Название / Ед. изм. / Цена" повторяется внутри данных
#   (новые секции) — такие строки фильтруем
# - Возможна двухколоночная HTML-вёрстка: данные идут парами
#   (Название | Ед.изм. | Цена | Название.1 | Ед.изм..1 | Цена.1)


class ElkabUralParser(BaseXLSParser):
    SHEET_NAME: int = 0
    # Не фиксируем HEADER_ROW — файл содержит шапку с контактами перед таблицей.
    # Парсер сам найдёт строку с "Название".
    HEADER_DETECT_COLUMN: str = "Название"

    _COL_NAME: str = "Название"
    _COL_UNIT: str = "Ед. изм."
    _COL_PRICE: str = "Цена, (руб.)"

    # Заголовочные строки, которые повторяются внутри данных
    _SKIP_NAME_VALUES: frozenset[str] = frozenset({"название", "наименование"})

    def _build_material(self, row: pd.Series) -> Material | None:
        name = self._to_str(row.get(self._COL_NAME))
        if not name or name.lower() in self._SKIP_NAME_VALUES:
            return None

        price = self._to_float(row.get(self._COL_PRICE))
        if price is None or price <= 0:
            return None

        price_with_vat, vat_amount = self._calculate_vat(price)
        unit = self._to_str(row.get(self._COL_UNIT)) or None

        return Material(
            id=self._generate_id(name),
            name=name,
            price=price,
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

    def _process_dataframe(self, df: pd.DataFrame) -> list[Material]:
        # Если HTML-таблица двухколоночная — обрабатываем обе половины
        materials = super()._process_dataframe(df)

        second_col = f"{self._COL_NAME}.1"
        if second_col in df.columns:
            df_right = df.rename(columns={
                f"{self._COL_NAME}.1": self._COL_NAME,
                f"{self._COL_UNIT}.1": self._COL_UNIT,
                f"{self._COL_PRICE}.1": self._COL_PRICE,
            })
            materials += super()._process_dataframe(df_right)

        return materials
