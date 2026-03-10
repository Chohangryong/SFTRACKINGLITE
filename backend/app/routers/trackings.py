from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.dependencies import get_session, get_settings
from app.schemas.common import MessageResponse
from app.schemas.trackings import (
    TrackingDetail,
    TrackingEventItem,
    TrackingListResponse,
    TrackingRefreshRequest,
)
from app.services.tracking_service import TrackingService

router = APIRouter(prefix="/trackings", tags=["trackings"])


@router.get("", response_model=TrackingListResponse)
def list_trackings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    query: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TrackingListResponse:
    return TrackingService(session, settings).list_trackings(
        page=page,
        page_size=page_size,
        query=query,
        status=status,
    )


@router.get("/{tracking_number}", response_model=TrackingDetail)
def get_tracking_detail(
    tracking_number: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TrackingDetail:
    try:
        return TrackingService(session, settings).get_tracking_detail(tracking_number)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{tracking_number}/events", response_model=list[TrackingEventItem])
def get_tracking_events(
    tracking_number: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[TrackingEventItem]:
    try:
        return TrackingService(session, settings).get_tracking_events(tracking_number)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/refresh")
def refresh_selected_trackings(
    request: TrackingRefreshRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    result = TrackingService(session, settings).refresh_tracking_numbers(request.tracking_numbers)
    return result.model_dump()


@router.post("/refresh-all")
def refresh_all_trackings(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    result = TrackingService(session, settings).refresh_pollable_trackings(force_all=True)
    return result.model_dump()
