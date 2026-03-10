from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TrackingListRow(BaseModel):
    order_number: str
    tracking_number: str | None
    current_status: str
    current_status_code: str | None = None
    current_status_detail: str | None = None
    last_event_location: str | None = None
    last_event_time: datetime | None = None
    last_event_desc: str | None = None
    last_queried_at: datetime | None = None
    linked_at: datetime | None = None


class TrackingListResponse(BaseModel):
    items: list[TrackingListRow]
    total: int
    page: int
    page_size: int


class TrackingOrderLink(BaseModel):
    order_number: str
    linked_at: datetime


class TrackingDetail(BaseModel):
    tracking_number: str
    current_status: str
    current_status_code: str | None = None
    current_status_detail: str | None = None
    last_event_time: datetime | None = None
    last_event_location: str | None = None
    last_event_desc: str | None = None
    last_opcode: str | None = None
    last_success_at: datetime | None = None
    last_queried_at: datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    retry_count: int
    is_terminal: bool
    linked_orders: list[TrackingOrderLink]
    latest_raw_event: dict[str, Any] | None = None


class TrackingEventItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_time: datetime
    event_location: str | None = None
    opcode: str | None = None
    first_status_code: str | None = None
    secondary_status_code: str | None = None
    first_status_name: str | None = None
    secondary_status_name: str | None = None
    event_desc: str | None = None
    mapped_status: str | None = None
    raw_event_json: dict[str, Any] | None = None


class TrackingRefreshRequest(BaseModel):
    tracking_numbers: list[str]
