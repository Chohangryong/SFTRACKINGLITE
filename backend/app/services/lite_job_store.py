from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from app.schemas.lite import LiteRunResponse


@dataclass
class LiteJobRecord:
    job_id: str
    file_name: str
    status: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    selected_sheet: str | None = None
    total_rows: int = 0
    deduped_rows: int = 0
    query_target_count: int = 0
    no_tracking_rows: int = 0
    completed_targets: int = 0
    remaining_targets: int = 0
    progress_percent: int = 0
    error_message: str | None = None
    result: LiteRunResponse | None = None


class LiteJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, LiteJobRecord] = {}
        self._lock = Lock()

    def create(self, file_name: str) -> LiteJobRecord:
        record = LiteJobRecord(
            job_id=uuid4().hex,
            file_name=file_name,
            status="queued",
        )
        with self._lock:
            self._jobs[record.job_id] = record
        return record

    def mark_running(self, job_id: str, prepared: dict[str, Any]) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.status = "running"
            record.started_at = datetime.utcnow()
            record.selected_sheet = prepared["selected_sheet"]
            record.total_rows = prepared["total_rows"]
            record.deduped_rows = len(prepared["rows"])
            record.query_target_count = prepared["query_target_count"]
            record.no_tracking_rows = prepared["no_tracking_rows"]
            record.completed_targets = 0
            record.remaining_targets = prepared["query_target_count"]
            record.progress_percent = 100 if prepared["query_target_count"] == 0 else 0
            record.error_message = None

    def update_progress(self, job_id: str, completed_targets: int, total_targets: int) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.completed_targets = completed_targets
            record.remaining_targets = max(total_targets - completed_targets, 0)
            record.progress_percent = 100 if total_targets == 0 else int((completed_targets / total_targets) * 100)

    def mark_completed(self, job_id: str, result: LiteRunResponse) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.status = "completed"
            record.finished_at = datetime.utcnow()
            record.result = result
            record.selected_sheet = result.selected_sheet
            record.total_rows = result.summary.total_rows
            record.deduped_rows = result.summary.deduped_rows
            record.query_target_count = result.summary.query_target_count
            record.no_tracking_rows = result.summary.no_tracking_rows
            record.completed_targets = result.summary.query_target_count
            record.remaining_targets = 0
            record.progress_percent = 100
            record.error_message = None

    def mark_failed(self, job_id: str, error_message: str) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.status = "failed"
            record.finished_at = datetime.utcnow()
            record.error_message = error_message
            if record.query_target_count and record.completed_targets < record.query_target_count:
                record.remaining_targets = record.query_target_count - record.completed_targets

    def get(self, job_id: str) -> LiteJobRecord | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            return LiteJobRecord(
                job_id=record.job_id,
                file_name=record.file_name,
                status=record.status,
                created_at=record.created_at,
                started_at=record.started_at,
                finished_at=record.finished_at,
                selected_sheet=record.selected_sheet,
                total_rows=record.total_rows,
                deduped_rows=record.deduped_rows,
                query_target_count=record.query_target_count,
                no_tracking_rows=record.no_tracking_rows,
                completed_targets=record.completed_targets,
                remaining_targets=record.remaining_targets,
                progress_percent=record.progress_percent,
                error_message=record.error_message,
                result=record.result,
            )
