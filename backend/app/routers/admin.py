from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.dependencies import get_session, get_settings
from app.models.polling_run import PollingRun
from app.schemas.admin import PollingRunItem, UnmappedStatusItem
from app.schemas.common import MessageResponse
from app.services.status_mapping_service import StatusMappingService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/polling-runs", response_model=list[PollingRunItem])
def list_polling_runs(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[PollingRunItem]:
    runs = list(session.scalars(select(PollingRun).order_by(PollingRun.started_at.desc()).limit(50)))
    return [PollingRunItem.model_validate(run) for run in runs]


@router.get("/unmapped-statuses", response_model=list[UnmappedStatusItem])
def list_unmapped_statuses(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[UnmappedStatusItem]:
    items = StatusMappingService(session).get_unmapped_statuses()
    return [UnmappedStatusItem(**item) for item in items]
