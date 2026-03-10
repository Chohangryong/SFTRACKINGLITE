from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PollingRunItem(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None = None
    total_targets: int
    success_count: int
    failed_count: int
    status: str
    error_message: str | None = None


class UnmappedStatusItem(BaseModel):
    opcode: str | None = None
    first_status_code: str | None = None
    secondary_status_code: str | None = None
    count: int
