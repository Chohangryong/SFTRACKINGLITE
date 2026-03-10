from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.status_mapping import StatusMapping
from app.models.tracking_event import TrackingEvent
from app.schemas.settings import StatusMappingItem

DEFAULT_STATUS_MAPPINGS: list[dict[str, Any]] = [
    {"carrier_code": "SF", "opcode": "44", "mapped_status": "OUT_FOR_DELIVERY", "is_terminal": False, "priority": 10, "note": "Out for delivery"},
    {"carrier_code": "SF", "opcode": "80", "mapped_status": "DELIVERED", "is_terminal": True, "priority": 10, "note": "Delivered"},
    {"carrier_code": "SF", "opcode": "99", "mapped_status": "EXCEPTION", "is_terminal": False, "priority": 10, "note": "Return or failure"},
    {"carrier_code": "SF", "opcode": "50", "mapped_status": "IN_TRANSIT", "is_terminal": False, "priority": 20, "note": "Picked up"},
    {"carrier_code": "SF", "opcode": "30", "mapped_status": "IN_TRANSIT", "is_terminal": False, "priority": 20, "note": "In transit"},
    {"carrier_code": "SF", "opcode": "31", "mapped_status": "IN_TRANSIT", "is_terminal": False, "priority": 20, "note": "Arrived"},
    {"carrier_code": "SF", "opcode": "607", "mapped_status": "IN_TRANSIT", "is_terminal": False, "priority": 20, "note": "Customs in progress"},
    {"carrier_code": "SF", "opcode": "608", "mapped_status": "IN_TRANSIT", "is_terminal": False, "priority": 20, "note": "Customs cleared"},
]


class StatusMappingService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def seed_defaults(self) -> None:
        count = self.session.scalar(select(func.count()).select_from(StatusMapping))
        if count:
            return
        for payload in DEFAULT_STATUS_MAPPINGS:
            self.session.add(StatusMapping(**payload))
        self.session.commit()

    def list_mappings(self) -> list[StatusMapping]:
        return list(self.session.scalars(select(StatusMapping).order_by(StatusMapping.priority.asc(), StatusMapping.id.asc())))

    def replace_mappings(self, items: list[StatusMappingItem]) -> list[StatusMapping]:
        self.session.query(StatusMapping).delete()
        for item in items:
            self.session.add(StatusMapping(**item.model_dump(exclude={"id"})))
        self.session.commit()
        return self.list_mappings()

    def map_status(
        self,
        carrier_code: str,
        opcode: str | None,
        first_status_code: str | None,
        secondary_status_code: str | None,
    ) -> tuple[str, bool]:
        mappings = list(
            self.session.scalars(
                select(StatusMapping)
                .where(StatusMapping.carrier_code == carrier_code)
                .order_by(StatusMapping.priority.asc(), StatusMapping.id.asc())
            )
        )
        best_match: StatusMapping | None = None
        best_score = -1
        for mapping in mappings:
            if mapping.opcode and mapping.opcode != opcode:
                continue
            if mapping.first_status_code and mapping.first_status_code != first_status_code:
                continue
            if mapping.secondary_status_code and mapping.secondary_status_code != secondary_status_code:
                continue
            score = sum(
                1
                for value in [mapping.opcode, mapping.first_status_code, mapping.secondary_status_code]
                if value
            )
            if score > best_score:
                best_score = score
                best_match = mapping
        if best_match is None:
            return "UNKNOWN_OPCODE", False
        return best_match.mapped_status, best_match.is_terminal

    def get_unmapped_statuses(self) -> list[dict[str, Any]]:
        rows = self.session.execute(
            select(
                TrackingEvent.opcode,
                TrackingEvent.first_status_code,
                TrackingEvent.secondary_status_code,
                func.count(TrackingEvent.id).label("count"),
            )
            .where(
                (TrackingEvent.mapped_status.is_(None))
                | (TrackingEvent.mapped_status == "UNKNOWN_OPCODE")
            )
            .group_by(
                TrackingEvent.opcode,
                TrackingEvent.first_status_code,
                TrackingEvent.secondary_status_code,
            )
            .order_by(func.count(TrackingEvent.id).desc())
        ).all()
        return [
            {
                "opcode": row.opcode,
                "first_status_code": row.first_status_code,
                "secondary_status_code": row.secondary_status_code,
                "count": row.count,
            }
            for row in rows
        ]
