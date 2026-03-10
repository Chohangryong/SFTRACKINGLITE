from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.dependencies import get_session, get_settings
from app.schemas.uploads import (
    UploadBatchCreateResponse,
    UploadConfirmRequest,
    UploadConfirmResult,
    UploadErrorItem,
    UploadPreview,
)
from app.services.upload_service import UploadService

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=UploadBatchCreateResponse)
async def create_upload_batch(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UploadBatchCreateResponse:
    try:
        return await UploadService(session, settings).create_batch(file)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/{batch_id}/preview", response_model=UploadPreview)
def get_upload_preview(
    batch_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UploadPreview:
    try:
        return UploadService(session, settings).get_preview(batch_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{batch_id}/confirm", response_model=UploadConfirmResult)
def confirm_upload_batch(
    batch_id: str,
    request: UploadConfirmRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UploadConfirmResult:
    try:
        return UploadService(session, settings).confirm_batch(
            batch_id,
            mapping_override=request.mapping,
            save_preset_name=request.save_preset_name,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/{batch_id}/errors", response_model=list[UploadErrorItem])
def get_upload_errors(
    batch_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[UploadErrorItem]:
    return UploadService(session, settings).get_errors(batch_id)
