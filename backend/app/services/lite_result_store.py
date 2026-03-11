from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from app.core.config import Settings
from app.schemas.lite import LiteRunResponse

RESULT_JSON_NAME = "result.json"
META_JSON_NAME = "meta.json"
EXPORT_FILE_NAMES = {
    "xlsx": "result.xlsx",
    "csv": "result.csv",
}


class LiteResultNotFoundError(FileNotFoundError):
    pass


class LiteResultExpiredError(RuntimeError):
    pass


@dataclass
class LiteStoredResultMeta:
    job_id: str
    file_name: str
    selected_sheet: str | None
    created_at: datetime
    expires_at: datetime


class LiteResultStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root_dir = settings.lite_job_dir
        self.ttl = timedelta(minutes=settings.lite_result_ttl_minutes)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save_result(self, job_id: str, result: LiteRunResponse) -> datetime:
        self.cleanup_expired()
        job_dir = self._job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)

        created_at = datetime.now(UTC)
        expires_at = created_at + self.ttl
        meta = {
            "job_id": job_id,
            "file_name": result.file_name,
            "selected_sheet": result.selected_sheet,
            "created_at": created_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        self._meta_path(job_dir).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._result_path(job_dir).write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        for file_name in EXPORT_FILE_NAMES.values():
            export_path = job_dir / file_name
            if export_path.exists():
                export_path.unlink()

        return expires_at

    def load_result(self, job_id: str) -> LiteRunResponse:
        job_dir, _ = self._require_live_job(job_id)
        result_path = self._result_path(job_dir)
        if not result_path.exists():
            raise LiteResultNotFoundError(f"Stored lite result not found for job {job_id}")
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        return LiteRunResponse.model_validate(payload)

    def export_result(
        self,
        job_id: str,
        file_format: str,
        exporter: Callable[[list[dict[str, Any]], str], tuple[str, bytes, str]],
    ) -> tuple[str, bytes, str]:
        file_format = file_format.lower()
        if file_format not in EXPORT_FILE_NAMES:
            raise ValueError("file_format must be csv or xlsx")

        job_dir, _ = self._require_live_job(job_id)
        cached_path = job_dir / EXPORT_FILE_NAMES[file_format]
        if cached_path.exists():
            return self._response_from_file(cached_path, file_format)

        result = self.load_result(job_id)
        filename, content, content_type = exporter(
            [row.model_dump(mode="json") for row in result.rows],
            file_format,
        )
        cached_path.write_bytes(content)
        return filename, content, content_type

    def cleanup_expired(self) -> None:
        now = datetime.now(UTC)
        for job_dir in self.root_dir.iterdir():
            if not job_dir.is_dir():
                continue
            try:
                meta = self._read_meta(job_dir)
            except Exception:
                shutil.rmtree(job_dir, ignore_errors=True)
                continue
            if meta.expires_at <= now:
                shutil.rmtree(job_dir, ignore_errors=True)

    def _require_live_job(self, job_id: str) -> tuple[Path, LiteStoredResultMeta]:
        job_dir = self._job_dir(job_id)
        if not job_dir.exists():
            raise LiteResultNotFoundError(f"Stored lite result not found for job {job_id}")

        meta = self._read_meta(job_dir)
        if meta.expires_at <= datetime.now(UTC):
            shutil.rmtree(job_dir, ignore_errors=True)
            raise LiteResultExpiredError(f"Stored lite result expired for job {job_id}")
        return job_dir, meta

    def _read_meta(self, job_dir: Path) -> LiteStoredResultMeta:
        meta_path = self._meta_path(job_dir)
        if not meta_path.exists():
            raise LiteResultNotFoundError(f"Stored lite meta not found in {job_dir}")
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        return LiteStoredResultMeta(
            job_id=str(payload["job_id"]),
            file_name=str(payload["file_name"]),
            selected_sheet=payload.get("selected_sheet"),
            created_at=datetime.fromisoformat(payload["created_at"]),
            expires_at=datetime.fromisoformat(payload["expires_at"]),
        )

    def _response_from_file(self, file_path: Path, file_format: str) -> tuple[str, bytes, str]:
        content_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if file_format == "xlsx"
            else "text/csv"
        )
        return (
            f"lite-tracking-results.{file_format}",
            file_path.read_bytes(),
            content_type,
        )

    def _job_dir(self, job_id: str) -> Path:
        return self.root_dir / job_id

    def _meta_path(self, job_dir: Path) -> Path:
        return job_dir / META_JSON_NAME

    def _result_path(self, job_dir: Path) -> Path:
        return job_dir / RESULT_JSON_NAME
