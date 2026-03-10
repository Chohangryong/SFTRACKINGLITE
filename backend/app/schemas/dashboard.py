from __future__ import annotations

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_orders: int
    total_trackings: int
    no_tracking_orders: int
    in_progress_trackings: int
    delivered_trackings: int
    exception_trackings: int
    query_failed_trackings: int


class ChartDatum(BaseModel):
    label: str
    value: int


class ChartSeries(BaseModel):
    series: list[ChartDatum]
