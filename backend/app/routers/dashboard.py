from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.dependencies import get_session, get_settings
from app.models.order import Order
from app.models.order_tracking import OrderTracking
from app.models.tracking import Tracking
from app.models.tracking_event import TrackingEvent
from app.schemas.dashboard import ChartDatum, ChartSeries, DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DashboardSummary:
    total_orders = session.scalar(select(func.count()).select_from(Order)) or 0
    total_trackings = session.scalar(select(func.count()).select_from(Tracking)) or 0
    no_tracking_orders = session.scalar(
        select(func.count()).select_from(Order).outerjoin(OrderTracking).where(OrderTracking.id.is_(None))
    ) or 0
    status_counts = Counter(
        session.scalars(select(Tracking.current_status))
    )
    return DashboardSummary(
        total_orders=total_orders,
        total_trackings=total_trackings,
        no_tracking_orders=no_tracking_orders,
        in_progress_trackings=status_counts.get("IN_TRANSIT", 0) + status_counts.get("OUT_FOR_DELIVERY", 0),
        delivered_trackings=status_counts.get("DELIVERED", 0),
        exception_trackings=status_counts.get("EXCEPTION", 0),
        query_failed_trackings=status_counts.get("QUERY_FAILED", 0),
    )


@router.get("/chart/status-distribution", response_model=ChartSeries)
def status_distribution(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ChartSeries:
    counts = Counter(session.scalars(select(Tracking.current_status)))
    return ChartSeries(series=[ChartDatum(label=label, value=value) for label, value in counts.items()])


@router.get("/chart/daily-delivered", response_model=ChartSeries)
def daily_delivered(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ChartSeries:
    return _daily_status_series(session, "DELIVERED")


@router.get("/chart/daily-exceptions", response_model=ChartSeries)
def daily_exceptions(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ChartSeries:
    return _daily_status_series(session, "EXCEPTION")


@router.get("/chart/daily-new-trackings", response_model=ChartSeries)
def daily_new_trackings(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ChartSeries:
    rows = session.execute(select(Tracking.created_at)).scalars().all()
    bucket = defaultdict(int)
    for created_at in rows:
        bucket[created_at.date().isoformat()] += 1
    return ChartSeries(series=[ChartDatum(label=label, value=bucket[label]) for label in sorted(bucket)])


def _daily_status_series(session: Session, status: str) -> ChartSeries:
    rows = session.execute(
        select(TrackingEvent.event_time).where(TrackingEvent.mapped_status == status)
    ).scalars().all()
    bucket = defaultdict(int)
    for event_time in rows:
        bucket[event_time.date().isoformat()] += 1
    return ChartSeries(series=[ChartDatum(label=label, value=bucket[label]) for label in sorted(bucket)])
