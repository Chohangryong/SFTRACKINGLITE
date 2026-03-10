from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


FIELD_ALIASES: dict[str, list[str]] = {
    "order_number": [
        "order_number",
        "order no",
        "order_no",
        "orderno",
        "ordernumber",
        "주문번호",
        "주문 번호",
        "订单号",
    ],
    "tracking_number": [
        "tracking_number",
        "tracking no",
        "tracking_no",
        "trackingnumber",
        "waybill",
        "waybill_no",
        "운송장번호",
        "송장번호",
        "tracking",
        "mailno",
    ],
    "customer_name": ["customer_name", "customer", "name", "수령인", "고객명", "consignee"],
    "product_name": ["product_name", "product", "상품명", "품목", "item"],
    "order_datetime": ["order_datetime", "order_date", "주문일시", "주문일", "created_at"],
}

REQUIRED_FIELDS = {"order_number"}


@dataclass
class ParsedFile:
    columns: list[str]
    rows: list[dict[str, Any]]
    preview_rows: list[dict[str, Any]]
    detected_mapping: dict[str, str | None]


class FileParser:
    def __init__(self, preview_rows: int = 100) -> None:
        self.preview_rows = preview_rows

    def parse(self, file_path: Path) -> ParsedFile:
        data_frame = self._read_dataframe(file_path)
        data_frame.columns = [str(column).strip() for column in data_frame.columns]
        rows = [self._serialize_row(row) for row in data_frame.to_dict(orient="records")]
        columns = list(data_frame.columns)
        detected_mapping = self.detect_mapping(columns)
        return ParsedFile(
            columns=columns,
            rows=rows,
            preview_rows=rows[: self.preview_rows],
            detected_mapping=detected_mapping,
        )

    def detect_mapping(self, columns: list[str]) -> dict[str, str | None]:
        normalized = {self._normalize(column): column for column in columns}
        mapping: dict[str, str | None] = {}
        for target_field, aliases in FIELD_ALIASES.items():
            mapping[target_field] = None
            for alias in aliases:
                if self._normalize(alias) in normalized:
                    mapping[target_field] = normalized[self._normalize(alias)]
                    break
        return mapping

    def validate_rows(
        self,
        rows: list[dict[str, Any]],
        mapping: dict[str, str | None],
    ) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            order_number = self.extract_field(row, mapping, "order_number")
            if not order_number:
                errors.append(
                    {
                        "row_number": index,
                        "error_type": "missing_order_number",
                        "error_message": "order_number is required",
                        "raw_row_json": row,
                    }
                )
        return errors

    def extract_field(
        self,
        row: dict[str, Any],
        mapping: dict[str, str | None],
        field_name: str,
    ) -> str | None:
        column_name = mapping.get(field_name)
        if not column_name:
            return None
        value = row.get(column_name)
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return None
        return text

    def _read_dataframe(self, file_path: Path) -> pd.DataFrame:
        suffix = file_path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(file_path, dtype=str, keep_default_na=False)
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(file_path, dtype=str, keep_default_na=False)
        raise ValueError(f"Unsupported file type: {suffix}")

    def _serialize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        serialized: dict[str, Any] = {}
        for key, value in row.items():
            if pd.isna(value):
                serialized[str(key)] = None
            elif hasattr(value, "isoformat"):
                serialized[str(key)] = value.isoformat()
            else:
                serialized[str(key)] = str(value).strip() if isinstance(value, str) else value
        return serialized

    def _normalize(self, value: str) -> str:
        return "".join(character.lower() for character in value if character.isalnum())
