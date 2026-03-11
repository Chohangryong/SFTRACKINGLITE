from __future__ import annotations

from typing import Any
from datetime import datetime

from pydantic import BaseModel


class LitePreviewRow(BaseModel):
    order_number: str
    tracking_number: str | None = None


class LiteAnalyzeResponse(BaseModel):
    file_name: str
    selected_sheet: str | None = None
    columns: list[str]
    detected_mapping: dict[str, str | None]
    total_rows: int
    missing_order_rows: int
    duplicate_pairs_removed: int
    deduped_rows: int
    query_target_count: int
    no_tracking_rows: int
    preview_rows: list[LitePreviewRow]


class LiteResultRow(BaseModel):
    order_number: str
    tracking_number: str | None = None
    status: str
    sf_express_code: str | None = None
    sf_express_remark: str | None = None
    last_event_time: datetime | None = None
    latest_event: dict[str, Any] | None = None


class LiteRunSummary(BaseModel):
    total_rows: int
    missing_order_rows: int
    duplicate_pairs_removed: int
    deduped_rows: int
    query_target_count: int
    no_tracking_rows: int
    status_counts: dict[str, int]


class LiteRunResponse(BaseModel):
    file_name: str
    selected_sheet: str | None = None
    detected_mapping: dict[str, str | None]
    summary: LiteRunSummary
    rows: list[LiteResultRow]


class LiteExportRequest(BaseModel):
    file_format: str = "xlsx"
    rows: list[LiteResultRow]


class LiteRunJobCreateResponse(BaseModel):
    job_id: str


class LiteRunJobResponse(BaseModel):
    job_id: str
    file_name: str
    status: str
    selected_sheet: str | None = None
    total_rows: int = 0
    deduped_rows: int = 0
    query_target_count: int = 0
    no_tracking_rows: int = 0
    completed_targets: int = 0
    remaining_targets: int = 0
    progress_percent: int = 0
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    expires_at: datetime | None = None
    result: LiteRunResponse | None = None
