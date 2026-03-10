from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.dependencies import get_session, get_settings
from app.schemas.export import ExportDownloadRequest, ExportPreset, ExportPresetCreateRequest
from app.services.export_service import ExportService

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/presets", response_model=list[ExportPreset])
def list_export_presets(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[ExportPreset]:
    return ExportService(session, settings).list_presets()


@router.post("/presets", response_model=ExportPreset)
def create_export_preset(
    request: ExportPresetCreateRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ExportPreset:
    return ExportService(session, settings).create_preset(request)


@router.post("/download")
def download_export(
    request: ExportDownloadRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    try:
        filename, payload, media_type = ExportService(session, settings).generate_export(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    response = StreamingResponse(BytesIO(payload), media_type=media_type)
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
