from __future__ import annotations

"""Lite status mapping based on the 2,708-waybill production analysis.

Reference outputs:
- data/analysis/sf_mapping_20260310T020009Z/final_mapping_recommendations.md
- data/analysis/sf_mapping_20260310T020009Z/no_route_analysis.md
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

ARRIVED_REMARK_TERMS = (
    "\u987a\u4e30\u81ea\u52a9\u67dc",
)
COLLECTED_REMARK_TERMS = (
    "\u5df2\u6d3e\u9001\u81f3\u672c\u4eba",
    "\u5df2\u6d3e\u9001\u6210\u529f",
    "\u5df2\u6d3e\u9001\u81f3\uff08\u9999\u6e2f\u5916\u90e8\u8d44\u6e90\uff09",
    "\u8f6c\u5bc4\u5feb\u4ef6\u5df2\u6d3e\u9001\u6210\u529f",
)
RETURN_REMARK_TERMS = (
    "\u9000\u56de",
    "\u4f5c\u5e9f",
)
TRANSFER_REQUEST_REMARK_TERMS = (
    "\u8f6c\u5bc4\u7533\u8bf7",
    "\u8f6c\u5bc4",
)

ARRIVED_COMBOS = {
    ("125", "11", "1101"),
    ("218", "11", "1101"),
    ("642", "11", "1101"),
}
CANCELED_COMBOS = {
    ("33", "5", "501"),
}
EXCEPTION_COMBOS = {
    ("126", "11", "1101"),
}
SHIPPED_COMBOS = {
    ("30", "2", "201"),
    ("31", "2", "201"),
    ("36", "2", "201"),
    ("44", "2", "201"),
    ("50", "1", "101"),
    ("54", "1", "101"),
    ("204", "3", "301"),
    ("603", "", ""),
    ("628", "", ""),
    ("634", "3", "301"),
    ("33", "13", "1301"),
    ("70", "13", "1301"),
    ("70", "11", "1101"),
    ("648", "2", "201"),
}


@dataclass
class LiteStatusResult:
    status: str
    sf_express_code: str | None
    sf_express_remark: str | None
    last_event_time: datetime | None
    latest_event: dict[str, Any] | None


def map_route_response(route_resp: dict[str, Any] | None) -> LiteStatusResult:
    if not route_resp:
        return LiteStatusResult(
            status="NO_ROUTE",
            sf_express_code=None,
            sf_express_remark=None,
            last_event_time=None,
            latest_event=None,
        )

    routes = route_resp.get("routes") or []
    if not routes:
        reason_code = as_text(route_resp.get("reasonCode"))
        reason_remark = as_text(route_resp.get("reasonRemark"))
        if reason_code or reason_remark:
            return LiteStatusResult(
                status="QUERY_UNAVAILABLE",
                sf_express_code=reason_code,
                sf_express_remark=reason_remark,
                last_event_time=None,
                latest_event=None,
            )
        return LiteStatusResult(
            status="NO_ROUTE",
            sf_express_code=None,
            sf_express_remark=None,
            last_event_time=None,
            latest_event=None,
        )

    latest_event = latest_route_event(routes)
    combo = event_combo(latest_event)
    sf_code = combo[2] or combo[1] or combo[0]
    remark = event_remark(latest_event)
    event_time = event_datetime(latest_event)

    if combo == ("80", "4", "401"):
        if contains_any(remark, ARRIVED_REMARK_TERMS):
            status = "ARRIVED"
        elif contains_any(remark, COLLECTED_REMARK_TERMS):
            status = "COLLECTED"
        else:
            status = "UNKNOWN"
        return LiteStatusResult(status, sf_code, remark, event_time, latest_event)

    if combo in ARRIVED_COMBOS:
        return LiteStatusResult("ARRIVED", sf_code, remark, event_time, latest_event)

    if combo in CANCELED_COMBOS:
        return LiteStatusResult("CANCELED", sf_code, remark, event_time, latest_event)

    if combo in EXCEPTION_COMBOS:
        return LiteStatusResult("EXCEPTION", sf_code, remark, event_time, latest_event)

    if combo in SHIPPED_COMBOS:
        return LiteStatusResult("SHIPPED", sf_code, remark, event_time, latest_event)

    if combo[0] == "99":
        status = "EXCEPTION" if contains_any(remark, RETURN_REMARK_TERMS) else "SHIPPED"
        return LiteStatusResult(status, sf_code, remark, event_time, latest_event)

    if combo[0] == "517":
        status = "SHIPPED" if contains_any(remark, TRANSFER_REQUEST_REMARK_TERMS) else "UNKNOWN"
        return LiteStatusResult(status, sf_code, remark, event_time, latest_event)

    return LiteStatusResult("UNKNOWN", sf_code, remark, event_time, latest_event)


def latest_route_event(routes: list[dict[str, Any]]) -> dict[str, Any]:
    indexed_routes = list(enumerate(routes))
    latest_index, latest_event = max(
        indexed_routes,
        key=lambda item: (
            event_datetime(item[1]) or datetime(1970, 1, 1),
            item[0],
        ),
    )
    return routes[latest_index] if latest_index < len(routes) else latest_event


def event_combo(event: dict[str, Any]) -> tuple[str, str, str]:
    return (
        as_text(event.get("opCode") or event.get("opcode")) or "",
        as_text(event.get("firstStatusCode") or event.get("first_status_code")) or "",
        as_text(
            event.get("secondaryStatusCode")
            or event.get("secondStatusCode")
            or event.get("secondary_status_code")
        )
        or "",
    )


def event_datetime(event: dict[str, Any]) -> datetime | None:
    value = event.get("acceptTime") or event.get("eventTime") or event.get("event_time")
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    if hasattr(parsed, "to_pydatetime"):
        return parsed.to_pydatetime()
    return None


def event_remark(event: dict[str, Any]) -> str | None:
    return as_text(event.get("remark") or event.get("eventDesc") or event.get("description"))


def as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def contains_any(text: str | None, needles: tuple[str, ...]) -> bool:
    if not text:
        return False
    return any(needle in text for needle in needles)
