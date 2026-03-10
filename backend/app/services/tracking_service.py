from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings
from app.models.order import Order
from app.models.order_tracking import OrderTracking
from app.models.tracking import Tracking
from app.models.tracking_event import TrackingEvent
from app.schemas.trackings import TrackingDetail, TrackingEventItem, TrackingListResponse, TrackingListRow, TrackingOrderLink
from app.services.settings_service import SettingsService
from app.services.sf_client import SFClient, SFClientCredentials, SFClientError
from app.services.status_mapping_service import StatusMappingService

POLLABLE_STATUSES = {
    "REGISTERED",
    "IN_TRANSIT",
    "OUT_FOR_DELIVERY",
    "EXCEPTION",
    "QUERY_FAILED",
    "UNKNOWN_OPCODE",
}


@dataclass
class RefreshResult:
    requested: int
    refreshed: int
    failed: int
    skipped: int
    errors: list[dict[str, str]]

    def model_dump(self) -> dict[str, Any]:
        return {
            "requested": self.requested,
            "refreshed": self.refreshed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
        }


class TrackingService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.settings_service = SettingsService(session, settings)
        self.status_mapping_service = StatusMappingService(session)

    def list_trackings(
        self,
        page: int = 1,
        page_size: int = 20,
        query: str | None = None,
        status: str | None = None,
    ) -> TrackingListResponse:
        relation_rows = self.session.execute(
            select(Order.order_number, Tracking, OrderTracking.linked_at)
            .join(OrderTracking, OrderTracking.order_id == Order.id)
            .join(Tracking, Tracking.id == OrderTracking.tracking_id)
        ).all()
        no_tracking_orders = self.session.execute(
            select(Order)
            .outerjoin(OrderTracking, OrderTracking.order_id == Order.id)
            .where(OrderTracking.id.is_(None))
        ).scalars()

        items: list[TrackingListRow] = []
        for order_number, tracking, linked_at in relation_rows:
            items.append(
                TrackingListRow(
                    order_number=order_number,
                    tracking_number=tracking.tracking_number,
                    current_status=tracking.current_status,
                    current_status_code=tracking.current_status_code,
                    current_status_detail=tracking.current_status_detail,
                    last_event_location=tracking.last_event_location,
                    last_event_time=tracking.last_event_time,
                    last_event_desc=tracking.last_event_desc,
                    last_queried_at=tracking.last_queried_at,
                    linked_at=linked_at,
                )
            )
        for order in no_tracking_orders:
            items.append(
                TrackingListRow(
                    order_number=order.order_number,
                    tracking_number=None,
                    current_status="NO_TRACKING",
                    linked_at=None,
                )
            )

        if query:
            needle = query.lower()
            items = [
                item
                for item in items
                if needle in item.order_number.lower()
                or (item.tracking_number and needle in item.tracking_number.lower())
            ]
        if status:
            items = [item for item in items if item.current_status == status]

        items.sort(
            key=lambda item: item.last_event_time or item.linked_at or datetime.min,
            reverse=True,
        )
        total = len(items)
        start = (page - 1) * page_size
        return TrackingListResponse(
            items=items[start : start + page_size],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_tracking_detail(self, tracking_number: str) -> TrackingDetail:
        tracking = self.session.scalar(
            select(Tracking)
            .options(joinedload(Tracking.order_trackings).joinedload(OrderTracking.order))
            .where(Tracking.tracking_number == tracking_number)
        )
        if tracking is None:
            raise ValueError("Tracking not found")
        latest_event = self.session.scalar(
            select(TrackingEvent)
            .where(TrackingEvent.tracking_id == tracking.id)
            .order_by(TrackingEvent.event_time.desc(), TrackingEvent.id.desc())
        )
        return TrackingDetail(
            tracking_number=tracking.tracking_number,
            current_status=tracking.current_status,
            current_status_code=tracking.current_status_code,
            current_status_detail=tracking.current_status_detail,
            last_event_time=tracking.last_event_time,
            last_event_location=tracking.last_event_location,
            last_event_desc=tracking.last_event_desc,
            last_opcode=tracking.last_opcode,
            last_success_at=tracking.last_success_at,
            last_queried_at=tracking.last_queried_at,
            last_error_code=tracking.last_error_code,
            last_error_message=tracking.last_error_message,
            retry_count=tracking.retry_count,
            is_terminal=tracking.is_terminal,
            linked_orders=[
                TrackingOrderLink(order_number=link.order.order_number, linked_at=link.linked_at)
                for link in tracking.order_trackings
            ],
            latest_raw_event=latest_event.raw_event_json if latest_event else None,
        )

    def get_tracking_events(self, tracking_number: str) -> list[TrackingEventItem]:
        tracking = self.session.scalar(select(Tracking).where(Tracking.tracking_number == tracking_number))
        if tracking is None:
            raise ValueError("Tracking not found")
        events = list(
            self.session.scalars(
                select(TrackingEvent)
                .where(TrackingEvent.tracking_id == tracking.id)
                .order_by(TrackingEvent.event_time.desc(), TrackingEvent.id.desc())
            )
        )
        return [TrackingEventItem.model_validate(event) for event in events]

    def refresh_tracking_numbers(self, tracking_numbers: list[str], batch_size: int | None = None, delay_seconds: int | None = None) -> RefreshResult:
        unique_numbers = list(dict.fromkeys(number for number in tracking_numbers if number))
        if not unique_numbers:
            return RefreshResult(requested=0, refreshed=0, failed=0, skipped=0, errors=[])

        active_api_key = self.settings_service.get_active_api_key()
        if active_api_key is None:
            return RefreshResult(
                requested=len(unique_numbers),
                refreshed=0,
                failed=0,
                skipped=len(unique_numbers),
                errors=[{"message": "No active SF API key configured"}],
            )

        api_key_record, secret_fields = active_api_key
        client = SFClient(
            self.settings,
            SFClientCredentials(
                partner_id=secret_fields["partner_id"],
                checkword=secret_fields["checkword"],
                environment=api_key_record.environment,
            ),
        )
        polling_settings = self.settings_service.get_polling_settings()
        actual_batch_size = batch_size or polling_settings.batch_size
        actual_delay = delay_seconds if delay_seconds is not None else polling_settings.delay_between_batches_seconds

        refreshed = 0
        failed = 0
        errors: list[dict[str, str]] = []

        for batch_index in range(0, len(unique_numbers), actual_batch_size):
            batch = unique_numbers[batch_index : batch_index + actual_batch_size]
            try:
                response = client.search_routes(batch, language=self.settings.default_language)
                route_resps, _ = client.extract_route_payload(response)
                route_map = {
                    str(route_resp.get("mailNo") or route_resp.get("trackingNumber") or ""): route_resp
                    for route_resp in route_resps
                }
                for tracking_number in batch:
                    route_resp = route_map.get(tracking_number)
                    if route_resp is None or not route_resp.get("routes"):
                        self._record_empty_route(tracking_number, route_resp)
                        continue
                    self._apply_route_response(tracking_number, route_resp)
                    refreshed += 1
            except SFClientError as error:
                failed += len(batch)
                for tracking_number in batch:
                    self._record_failure(tracking_number, "SF_CLIENT_ERROR", str(error))
                    errors.append({"tracking_number": tracking_number, "message": str(error)})
            except Exception as error:  # pragma: no cover - defensive logging path
                failed += len(batch)
                for tracking_number in batch:
                    self._record_failure(tracking_number, "UNEXPECTED_ERROR", str(error))
                    errors.append({"tracking_number": tracking_number, "message": str(error)})
            self.session.commit()
            if batch_index + actual_batch_size < len(unique_numbers):
                time.sleep(actual_delay)

        return RefreshResult(
            requested=len(unique_numbers),
            refreshed=refreshed,
            failed=failed,
            skipped=max(len(unique_numbers) - refreshed - failed, 0),
            errors=errors,
        )

    def refresh_pollable_trackings(self, force_all: bool = False) -> RefreshResult:
        trackings = list(self.session.scalars(select(Tracking).where(Tracking.current_status.in_(POLLABLE_STATUSES))))
        if not force_all:
            trackings = [tracking for tracking in trackings if self._is_due_for_polling(tracking)]
        return self.refresh_tracking_numbers([tracking.tracking_number for tracking in trackings])

    def _is_due_for_polling(self, tracking: Tracking) -> bool:
        if tracking.last_queried_at is None:
            return True
        polling_settings = self.settings_service.get_polling_settings()
        hours = polling_settings.interval_hours
        if tracking.retry_count >= 4:
            hours = max(hours, 6)
        cutoff = datetime.utcnow() - pd.Timedelta(hours=hours).to_pytimedelta()
        return tracking.last_queried_at <= cutoff

    def _apply_route_response(self, tracking_number: str, route_resp: dict[str, Any]) -> None:
        tracking = self.session.scalar(select(Tracking).where(Tracking.tracking_number == tracking_number))
        if tracking is None:
            tracking = Tracking(tracking_number=tracking_number, current_status="REGISTERED")
            self.session.add(tracking)
            self.session.flush()

        for route in route_resp.get("routes", []):
            event_payload = self._normalize_route(route)
            mapped_status, is_terminal = self.status_mapping_service.map_status(
                "SF",
                event_payload["opcode"],
                event_payload["first_status_code"],
                event_payload["secondary_status_code"],
            )
            event_payload["mapped_status"] = mapped_status
            existing = self.session.scalar(
                select(TrackingEvent).where(
                    TrackingEvent.tracking_id == tracking.id,
                    TrackingEvent.event_time == event_payload["event_time"],
                    TrackingEvent.opcode == event_payload["opcode"],
                    TrackingEvent.event_desc == event_payload["event_desc"],
                )
            )
            if existing is None:
                existing = TrackingEvent(tracking_id=tracking.id, **event_payload)
                self.session.add(existing)
            else:
                for key, value in event_payload.items():
                    setattr(existing, key, value)

        self.session.flush()
        latest_event = self.session.scalar(
            select(TrackingEvent)
            .where(TrackingEvent.tracking_id == tracking.id)
            .order_by(TrackingEvent.event_time.desc(), TrackingEvent.id.desc())
        )
        if latest_event is None:
            self._record_empty_route(tracking_number, route_resp)
            return

        mapped_status, is_terminal = self.status_mapping_service.map_status(
            "SF",
            latest_event.opcode,
            latest_event.first_status_code,
            latest_event.secondary_status_code,
        )
        tracking.current_status = mapped_status
        tracking.current_status_detail = latest_event.event_desc
        tracking.current_status_code = (
            latest_event.secondary_status_code
            or latest_event.first_status_code
            or latest_event.opcode
        )
        tracking.last_event_time = latest_event.event_time
        tracking.last_event_desc = latest_event.event_desc
        tracking.last_event_location = latest_event.event_location
        tracking.last_opcode = latest_event.opcode
        tracking.last_queried_at = datetime.utcnow()
        tracking.last_success_at = datetime.utcnow()
        tracking.last_error_code = None
        tracking.last_error_message = None
        tracking.retry_count = 0
        tracking.is_terminal = is_terminal

    def _record_failure(self, tracking_number: str, error_code: str, message: str) -> None:
        tracking = self.session.scalar(select(Tracking).where(Tracking.tracking_number == tracking_number))
        if tracking is None:
            tracking = Tracking(tracking_number=tracking_number, current_status="QUERY_FAILED")
            self.session.add(tracking)
        tracking.current_status = "QUERY_FAILED"
        tracking.last_queried_at = datetime.utcnow()
        tracking.last_error_code = error_code
        tracking.last_error_message = message
        tracking.retry_count += 1
        tracking.is_terminal = False

    def _record_empty_route(self, tracking_number: str, route_resp: dict[str, Any] | None = None) -> None:
        tracking = self.session.scalar(select(Tracking).where(Tracking.tracking_number == tracking_number))
        if tracking is None:
            tracking = Tracking(tracking_number=tracking_number, current_status="REGISTERED")
            self.session.add(tracking)
        reason_code = str(route_resp.get("reasonCode") or "") if route_resp else ""
        reason_message = str(route_resp.get("reasonRemark") or "") if route_resp else ""
        if reason_code or reason_message:
            tracking.current_status = "QUERY_UNAVAILABLE"
            tracking.current_status_code = reason_code or None
            tracking.current_status_detail = reason_message or None
            tracking.last_error_code = reason_code or None
            tracking.last_error_message = reason_message or None
        else:
            tracking.current_status = "REGISTERED"
            tracking.current_status_code = None
            tracking.current_status_detail = None
            tracking.last_error_code = None
            tracking.last_error_message = None
        tracking.last_queried_at = datetime.utcnow()
        tracking.last_success_at = datetime.utcnow()
        tracking.is_terminal = False

    def _normalize_route(self, route: dict[str, Any]) -> dict[str, Any]:
        event_time = self._parse_datetime(
            route.get("acceptTime")
            or route.get("eventTime")
            or route.get("event_time")
            or datetime.utcnow().isoformat()
        )
        opcode = route.get("opCode") or route.get("opcode")
        first_status_code = route.get("firstStatusCode") or route.get("first_status_code")
        secondary_status_code = (
            route.get("secondaryStatusCode")
            or route.get("secondStatusCode")
            or route.get("secondary_status_code")
        )
        first_status_name = route.get("firstStatusName") or route.get("firstStatusDesc")
        secondary_status_name = route.get("secondaryStatusName") or route.get("secondStatusDesc")
        return {
            "event_time": event_time,
            "event_location": route.get("acceptAddress") or route.get("eventLocation"),
            "opcode": str(opcode) if opcode is not None else None,
            "first_status_code": str(first_status_code) if first_status_code is not None else None,
            "secondary_status_code": str(secondary_status_code) if secondary_status_code is not None else None,
            "first_status_name": first_status_name,
            "secondary_status_name": secondary_status_name,
            "event_desc": route.get("remark") or route.get("eventDesc") or route.get("description"),
            "raw_event_json": route,
        }

    def _parse_datetime(self, value: Any) -> datetime:
        parsed = pd.to_datetime(value)
        if hasattr(parsed, "to_pydatetime"):
            return parsed.to_pydatetime()
        raise ValueError(f"Unsupported datetime value: {value}")
