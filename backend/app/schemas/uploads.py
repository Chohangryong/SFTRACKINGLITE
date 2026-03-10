from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UploadBatchCreateResponse(BaseModel):
    batch_id: str
    file_name: str
    total_rows: int
    detected_mapping: dict[str, str | None]
    preview_rows: list[dict[str, Any]]


class UploadErrorItem(BaseModel):
    id: int
    row_number: int
    error_type: str
    error_message: str
    raw_row_json: dict[str, Any] | None = None


class UploadPreview(BaseModel):
    batch_id: str
    status: str
    file_name: str
    columns: list[str]
    detected_mapping: dict[str, str | None]
    preview_rows: list[dict[str, Any]]
    total_rows: int
    error_rows: int
    created_at: datetime


class UploadConfirmRequest(BaseModel):
    mapping: dict[str, str | None] = Field(default_factory=dict)
    save_preset_name: str | None = None


class UploadConfirmResult(BaseModel):
    batch_id: str
    status: str
    success_rows: int
    skipped_rows: int
    error_rows: int
    affected_tracking_numbers: list[str]
    refresh_summary: dict[str, Any]
