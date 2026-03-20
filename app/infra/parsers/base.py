import asyncio
import hashlib
import io
import math
from abc import abstractmethod

import pandas as pd

from app.core.interfaces.parser import AbstractParser
from app.domain.material import Material
from app.domain.provider import ProviderInfo


class BaseXLSParser(AbstractParser):
    """
    Базовый парсер XLS/XLSX файлов.

    Subclasses реализуют _build_material() с логикой маппинга
    конкретного провайдера.
    """

    # Номер строки-заголовка (0-based). Переопределить при необходимости.
    HEADER_ROW: int = 0
    # Имя или индекс листа. Переопределить при необходимости.
    SHEET_NAME: int | str = 0
    # Для HTML-fallback: regex/строка для поиска нужной таблицы на странице.
    HTML_TABLE_MATCH: str | None = None
    # Если задан — заголовок ищется автоматически по вхождению этой строки в ячейку.
    # HEADER_ROW при этом игнорируется.
    HEADER_DETECT_COLUMN: str | None = None

    def __init__(self, provider: ProviderInfo) -> None:
        self._provider = provider

    async def parse(self, file_bytes: bytes, file_ext: str) -> list[Material]:
        return await asyncio.to_thread(self._read_and_process, file_bytes, file_ext)

    def _read_and_process(self, file_bytes: bytes, file_ext: str) -> list[Material]:
        df = self._read_dataframe(file_bytes, file_ext)
        return self._process_dataframe(df)

    def _read_dataframe(self, file_bytes: bytes, file_ext: str) -> pd.DataFrame:
        # Цепочка движков от специфичного к универсальному.
        #
        # xlrd/openpyxl — нативные, но строгие: падают на "кривых" файлах.
        # calamine      — Rust-based, читает повреждённые XLS/XLSX которые Excel открывает.
        # html          — последний шанс: поставщик отдал HTML с расширением .xls.
        primary = "xlrd" if file_ext == "xls" else "openpyxl"
        fallback = "openpyxl" if primary == "xlrd" else "xlrd"

        if self.HEADER_DETECT_COLUMN:
            return self._read_with_auto_header(file_bytes, file_ext, (primary, fallback, "calamine"))

        for engine in (primary, fallback, "calamine"):
            try:
                return pd.read_excel(
                    io.BytesIO(file_bytes),
                    engine=engine,
                    sheet_name=self.SHEET_NAME,
                    header=self.HEADER_ROW,
                    dtype=str,
                )
            except Exception:
                pass

        # HTML-таблица под .xls-расширением
        try:
            kwargs: dict = {"header": self.HEADER_ROW}
            if self.HTML_TABLE_MATCH:
                kwargs["match"] = self.HTML_TABLE_MATCH
            tables = pd.read_html(io.BytesIO(file_bytes), **kwargs)
            sheet_idx = self.SHEET_NAME if isinstance(self.SHEET_NAME, int) else 0
            return tables[sheet_idx].astype(str)
        except Exception as exc:
            raise ValueError(
                f"Cannot parse file for provider '{self._provider.name}': {exc}"
            ) from exc

    def _read_with_auto_header(
        self,
        file_bytes: bytes,
        file_ext: str,
        engines: tuple[str, ...],
    ) -> pd.DataFrame:
        """Читает файл без заголовка, ищет строку с HEADER_DETECT_COLUMN, перечитывает."""
        raw_df: pd.DataFrame | None = None

        for engine in engines:
            try:
                raw_df = pd.read_excel(
                    io.BytesIO(file_bytes),
                    engine=engine,
                    sheet_name=self.SHEET_NAME,
                    header=None,
                    dtype=str,
                )
                break
            except Exception:
                pass

        if raw_df is None:
            raise ValueError(
                f"Cannot read file for provider '{self._provider.name}'"
            )

        header_row = self._detect_header_row(raw_df)

        if header_row is None:
            raise ValueError(
                f"Cannot find header row with '{self.HEADER_DETECT_COLUMN}' "
                f"for provider '{self._provider.name}'"
            )

        # Перечитываем уже зная номер строки заголовка
        for engine in engines:
            try:
                return pd.read_excel(
                    io.BytesIO(file_bytes),
                    engine=engine,
                    sheet_name=self.SHEET_NAME,
                    header=header_row,
                    dtype=str,
                )
            except Exception:
                pass

        raise ValueError(
            f"Cannot re-read file with detected header for provider '{self._provider.name}'"
        )

    def _detect_header_row(self, raw_df: pd.DataFrame) -> int | None:
        """Ищет первую строку, содержащую HEADER_DETECT_COLUMN."""
        needle = (self.HEADER_DETECT_COLUMN or "").lower()
        for idx, row in raw_df.iterrows():
            if any(needle in str(val).lower() for val in row.values):
                return int(idx)  # type: ignore[arg-type]
        return None

    def _process_dataframe(self, df: pd.DataFrame) -> list[Material]:
        materials: list[Material] = []
        for _, row in df.iterrows():
            try:
                material = self._build_material(row)
                if material is not None:
                    materials.append(material)
            except Exception:
                continue
        return materials

    @abstractmethod
    def _build_material(self, row: pd.Series) -> Material | None:
        """Маппинг строки XLS → Material. Реализуется для каждого провайдера."""
        ...

    # ── Хелперы для subclasses ──────────────────────────────────────────────

    def _generate_id(self, name: str) -> str:
        """Детерминированный ID на основе провайдера и наименования."""
        content = f"{self._provider.name}:{name}".encode("utf-8")
        return hashlib.sha256(content).hexdigest()[:24]

    def _calculate_vat(self, price: float) -> tuple[float, float]:
        """Возвращает (price_with_vat, vat_amount)."""
        vat_amount = round(price * self._provider.vat_rate / 100, 2)
        price_with_vat = round(price + vat_amount, 2)
        return price_with_vat, vat_amount

    def _reverse_vat(self, price_with_vat: float) -> tuple[float, float]:
        """Если цена уже с НДС — вычленяем (price_net, vat_amount)."""
        price = round(price_with_vat / (1 + self._provider.vat_rate / 100), 2)
        vat_amount = round(price_with_vat - price, 2)
        return price, vat_amount

    def _find_column(self, row: pd.Series, *candidates: str) -> object:
        """Ищет первое совпадение среди вариантов названий колонки (частичное совпадение)."""
        for col in row.index:
            col_str = str(col).strip()
            for candidate in candidates:
                if candidate.lower() in col_str.lower():
                    return row[col]
        return None

    @staticmethod
    def _to_float(value: object) -> float | None:
        try:
            result = float(str(value).replace(" ", "").replace(",", ".").replace("\xa0", ""))
            return None if (math.isnan(result) or math.isinf(result)) else result
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_str(value: object) -> str:
        result = str(value).strip()
        return result if result not in ("", "nan", "None") else ""
