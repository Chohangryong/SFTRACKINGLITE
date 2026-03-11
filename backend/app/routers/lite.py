from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.dependencies import get_session, get_settings
from app.schemas.lite import (
    LiteAnalyzeResponse,
    LiteExportRequest,
    LiteRunJobCreateResponse,
    LiteRunJobResponse,
    LiteRunResponse,
)
from app.services.lite_job_store import LiteJobStore
from app.services.lite_result_store import LiteResultExpiredError, LiteResultNotFoundError, LiteResultStore
from app.services.lite_service import LiteService

router = APIRouter(prefix="/lite", tags=["lite"])


@router.post("/analyze", response_model=LiteAnalyzeResponse)
async def analyze_lite_upload(
    file: UploadFile = File(...),
    mapping_json: str | None = Form(default=None),
    sheet_name: str | None = Form(default=None),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> LiteAnalyzeResponse:
    try:
        return await LiteService(session, settings).analyze_upload(
            upload_file=file,
            mapping_override=parse_mapping(mapping_json),
            sheet_name=sheet_name,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/run", response_model=LiteRunResponse)
async def run_lite_upload(
    file: UploadFile = File(...),
    mapping_json: str | None = Form(default=None),
    sheet_name: str | None = Form(default=None),
    batch_size: int = Form(default=10),
    delay_seconds: float = Form(default=0.0),
    language: str = Form(default="0"),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> LiteRunResponse:
    try:
        return await LiteService(session, settings).run_upload(
            upload_file=file,
            mapping_override=parse_mapping(mapping_json),
            sheet_name=sheet_name,
            batch_size=batch_size,
            delay_seconds=delay_seconds,
            language=language,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/jobs", response_model=LiteRunJobCreateResponse)
async def create_lite_run_job(
    request: Request,
    file: UploadFile = File(...),
    mapping_json: str | None = Form(default=None),
    sheet_name: str | None = Form(default=None),
    batch_size: int = Form(default=10),
    delay_seconds: float = Form(default=0.0),
    language: str = Form(default="0"),
    settings: Settings = Depends(get_settings),
) -> LiteRunJobCreateResponse:
    file_name = file.filename or "uploaded-file"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    mapping_override = parse_mapping(mapping_json)
    job_store: LiteJobStore = request.app.state.lite_job_store
    job = job_store.create(file_name=file_name)

    # 조회는 오래 걸릴 수 있으므로 job만 먼저 만들고 백그라운드에서 실행한다.
    asyncio.create_task(
        _run_lite_job(
            app=request.app,
            job_id=job.job_id,
            settings=settings,
            file_name=file_name,
            content=content,
            mapping_override=mapping_override,
            sheet_name=sheet_name,
            batch_size=batch_size,
            delay_seconds=delay_seconds,
            language=language,
        )
    )
    return LiteRunJobCreateResponse(job_id=job.job_id)


@router.get("/jobs/{job_id}", response_model=LiteRunJobResponse)
def get_lite_run_job(job_id: str, request: Request) -> LiteRunJobResponse:
    job_store: LiteJobStore = request.app.state.lite_job_store
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Lite run job not found")

    return LiteRunJobResponse(
        job_id=record.job_id,
        file_name=record.file_name,
        status=record.status,
        selected_sheet=record.selected_sheet,
        total_rows=record.total_rows,
        deduped_rows=record.deduped_rows,
        query_target_count=record.query_target_count,
        no_tracking_rows=record.no_tracking_rows,
        completed_targets=record.completed_targets,
        remaining_targets=record.remaining_targets,
        progress_percent=record.progress_percent,
        error_message=record.error_message,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        expires_at=record.expires_at,
        result=record.result,
    )


@router.get("/jobs/{job_id}/download")
def download_lite_run_result(
    job_id: str,
    file_format: str = Query(default="xlsx"),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    service = LiteService(session, settings)
    result_store = LiteResultStore(settings)

    try:
        filename, content, content_type = result_store.export_result(
            job_id=job_id,
            file_format=file_format,
            exporter=service.export_rows,
        )
    except LiteResultExpiredError as error:
        raise HTTPException(status_code=410, detail=str(error)) from error
    except LiteResultNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export")
async def export_lite_upload(
    file: UploadFile = File(...),
    mapping_json: str | None = Form(default=None),
    sheet_name: str | None = Form(default=None),
    file_format: str = Form(default="xlsx"),
    batch_size: int = Form(default=10),
    delay_seconds: float = Form(default=0.0),
    language: str = Form(default="0"),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    try:
        filename, payload, content_type = await LiteService(session, settings).export_upload(
            upload_file=file,
            mapping_override=parse_mapping(mapping_json),
            sheet_name=sheet_name,
            file_format=file_format,
            batch_size=batch_size,
            delay_seconds=delay_seconds,
            language=language,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return Response(
        content=payload,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export-result")
def export_lite_result(
    payload: LiteExportRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    try:
        filename, content, content_type = LiteService(session, settings).export_rows(
            rows=[row.model_dump(mode="json") for row in payload.rows],
            file_format=payload.file_format,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _run_lite_job(
    app: Any,
    job_id: str,
    settings: Settings,
    file_name: str,
    content: bytes,
    mapping_override: dict[str, str | None] | None,
    sheet_name: str | None,
    batch_size: int,
    delay_seconds: float,
    language: str,
) -> None:
    job_store: LiteJobStore = app.state.lite_job_store
    result_store = LiteResultStore(settings)

    def worker() -> None:
        # 요청 생명주기와 분리된 백그라운드 작업이라 worker 안에서 별도 세션을 만든다.
        with app.state.database.session() as session:
            service = LiteService(session, settings)
            prepared = service.prepare_content(
                file_name=file_name,
                content=content,
                mapping_override=mapping_override,
                sheet_name=sheet_name,
                validate_required_mapping=True,
            )
            job_store.mark_running(job_id, prepared)
            result = service.run_prepared(
                prepared=prepared,
                batch_size=batch_size,
                delay_seconds=delay_seconds,
                language=language,
                progress_callback=lambda completed, total: job_store.update_progress(job_id, completed, total),
            )
            expires_at = result_store.save_result(job_id, result)
            job_store.mark_completed(job_id, summarize_job_result(result), expires_at)

    try:
        await asyncio.to_thread(worker)
    except Exception as error:  # pragma: no cover - defensive background path
        job_store.mark_failed(job_id, str(error))


def summarize_job_result(result: LiteRunResponse) -> LiteRunResponse:
    # 화면 요약에는 rows 전체가 필요 없어서 메모리에는 빈 리스트만 남긴다.
    return LiteRunResponse(
        file_name=result.file_name,
        selected_sheet=result.selected_sheet,
        detected_mapping=result.detected_mapping,
        summary=result.summary,
        rows=[],
    )


def parse_mapping(mapping_json: str | None) -> dict[str, str | None] | None:
    if not mapping_json:
        return None
    try:
        payload = json.loads(mapping_json)
    except json.JSONDecodeError as error:
        raise ValueError("mapping_json must be valid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("mapping_json must be a JSON object")
    parsed: dict[str, str | None] = {}
    for key, value in payload.items():
        parsed[str(key)] = None if value in {None, ""} else str(value)
    return parsed
