from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
BACKEND_DEPS = BACKEND_ROOT / ".deps"
for candidate in [str(BACKEND_DEPS), str(BACKEND_ROOT)]:
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import pandas as pd

from app.core.config import Settings
from app.services.sf_client import SFClient, SFClientCredentials, SFClientError
from app.services.status_mapping_service import DEFAULT_STATUS_MAPPINGS
from app.utils.crypto import SecretCipher


REQUIRED_COLUMNS = {"Order Number", "Tracking Number"}


@dataclass
class TrackingRow:
    tracking_number: str
    order_number: str
    source_delivery_status: str
    source_order_status: str
    delivery_method: str


def parse_args() -> argparse.Namespace:
    default_excel = REPO_ROOT / "data" / "uploads" / "1d8f1f4f27a048e6bd743c3742da01ad.xls"
    parser = argparse.ArgumentParser(description="Analyze SF tracking event combinations from an Excel export.")
    parser.add_argument("--excel-path", type=Path, default=default_excel)
    parser.add_argument("--sheet-name", type=str, default=None)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--delay-seconds", type=float, default=0.2)
    parser.add_argument("--language", type=str, default="0")
    parser.add_argument("--tracking-number-format", choices=["list", "csv"], default="list")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data" / "analysis")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = Settings()
    selected_sheet, data_frame = load_source_frame(args.excel_path, args.sheet_name)
    normalized = normalize_frame(data_frame)
    sample_pool = build_tracking_pool(normalized)
    sampled_rows, sample_plan = sample_tracking_rows(sample_pool, args.sample_size, args.seed)
    client = build_sf_client(settings)

    output_root = args.output_dir
    run_dir = output_root / f"sf_mapping_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    run_dir.mkdir(parents=True, exist_ok=True)

    fetch_result = fetch_routes(
        client=client,
        tracking_rows=sampled_rows,
        batch_size=args.batch_size,
        delay_seconds=args.delay_seconds,
        language=args.language,
        tracking_number_format=args.tracking_number_format,
    )
    analysis = analyze_routes(
        selected_sheet=selected_sheet,
        source_frame=normalized,
        sample_pool=sample_pool,
        sampled_rows=sampled_rows,
        sample_plan=sample_plan,
        fetch_result=fetch_result,
    )

    write_outputs(run_dir, sampled_rows, fetch_result, analysis)
    print(run_dir)
    return 0


def load_source_frame(excel_path: Path, sheet_name: str | None) -> tuple[str, pd.DataFrame]:
    workbook = pd.ExcelFile(excel_path)
    if sheet_name:
        return sheet_name, pd.read_excel(excel_path, sheet_name=sheet_name, dtype=str, keep_default_na=False)

    best_sheet = None
    best_frame = None
    best_score = -1
    for candidate in workbook.sheet_names:
        frame = pd.read_excel(excel_path, sheet_name=candidate, dtype=str, keep_default_na=False)
        columns = {str(column).strip() for column in frame.columns}
        if not REQUIRED_COLUMNS.issubset(columns):
            continue
        order_count = frame["Order Number"].astype(str).str.strip().replace({"": pd.NA}).dropna().shape[0]
        if order_count > best_score:
            best_sheet = candidate
            best_frame = frame
            best_score = order_count

    if best_sheet is None or best_frame is None:
        raise ValueError("No sheet with required columns was found.")
    return best_sheet, best_frame


def normalize_frame(data_frame: pd.DataFrame) -> pd.DataFrame:
    normalized = data_frame.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]
    for column in normalized.columns:
        normalized[column] = normalized[column].astype(str).str.strip()
        normalized.loc[normalized[column].isin(["", "nan", "None"]), column] = ""
    return normalized


def build_tracking_pool(data_frame: pd.DataFrame) -> list[TrackingRow]:
    deduped_pairs = data_frame[["Order Number", "Tracking Number", "Delivery Status", "Order Status", "Delivery Method"]].drop_duplicates()
    deduped_pairs = deduped_pairs[deduped_pairs["Tracking Number"] != ""]
    grouped: dict[str, TrackingRow] = {}
    for row in deduped_pairs.itertuples(index=False):
        tracking_number = str(row[1]).upper().strip()
        if not tracking_number:
            continue
        grouped.setdefault(
            tracking_number,
            TrackingRow(
                tracking_number=tracking_number,
                order_number=str(row[0]).strip(),
                source_delivery_status=str(row[2]).strip() or "UNKNOWN",
                source_order_status=str(row[3]).strip() or "UNKNOWN",
                delivery_method=str(row[4]).strip(),
            ),
        )
    return sorted(grouped.values(), key=lambda item: item.tracking_number)


def sample_tracking_rows(tracking_rows: list[TrackingRow], sample_size: int, seed: int) -> tuple[list[TrackingRow], dict[str, int]]:
    groups: dict[str, list[TrackingRow]] = defaultdict(list)
    for row in tracking_rows:
        groups[row.source_delivery_status].append(row)

    allocations = allocate_samples({status: len(rows) for status, rows in groups.items()}, sample_size)
    randomizer = random.Random(seed)
    sampled_rows: list[TrackingRow] = []
    for status, rows in sorted(groups.items()):
        target = allocations.get(status, 0)
        if target <= 0:
            continue
        sampled_rows.extend(randomizer.sample(rows, k=target))
    sampled_rows.sort(key=lambda item: (item.source_delivery_status, item.tracking_number))
    return sampled_rows, allocations


def allocate_samples(group_sizes: dict[str, int], sample_size: int) -> dict[str, int]:
    sample_size = min(sample_size, sum(group_sizes.values()))
    allocations: dict[str, int] = {}
    remaining = sample_size
    large_groups: dict[str, int] = {}
    small_groups: dict[str, int] = {}

    for status, count in group_sizes.items():
        if count <= 10:
            small_groups[status] = count
        else:
            large_groups[status] = count

    if sum(small_groups.values()) > sample_size:
        return proportional_allocate(small_groups, sample_size)

    for status, count in small_groups.items():
        allocations[status] = count
        remaining -= count

    if remaining <= 0 or not large_groups:
        return allocations

    for status, value in proportional_allocate(large_groups, remaining).items():
        allocations[status] = value

    return allocations


def proportional_allocate(group_sizes: dict[str, int], sample_size: int) -> dict[str, int]:
    total = sum(group_sizes.values())
    raw_targets = {status: sample_size * count / total for status, count in group_sizes.items()}
    floors = {status: int(value) for status, value in raw_targets.items()}
    allocations = dict(floors)
    leftovers = sample_size - sum(floors.values())
    remainders = sorted(
        group_sizes,
        key=lambda status: (raw_targets[status] - floors[status], group_sizes[status], status),
        reverse=True,
    )
    for status in remainders[:leftovers]:
        allocations[status] += 1
    return allocations


def build_sf_client(settings: Settings) -> SFClient:
    db_path = settings.database_path
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """
        select environment, key_fields
        from api_keys
        where service = 'sf_express' and is_active = 1
        order by created_at desc
        limit 1
        """
    ).fetchone()
    conn.close()
    if row is None:
        raise RuntimeError("No active SF API key found in data/app.db")

    secret_cipher = SecretCipher(settings.dev_cipher_key_path)
    secrets = json.loads(secret_cipher.decrypt(row[1]))
    credentials = SFClientCredentials(
        partner_id=secrets["partner_id"],
        checkword=secrets["checkword"],
        environment=row[0],
    )
    return SFClient(settings, credentials)


def fetch_routes(
    client: SFClient,
    tracking_rows: list[TrackingRow],
    batch_size: int,
    delay_seconds: float,
    language: str,
    tracking_number_format: str,
) -> dict[str, Any]:
    results: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    requested = [row.tracking_number for row in tracking_rows]

    for start in range(0, len(requested), batch_size):
        batch = requested[start : start + batch_size]
        try:
            response = query_routes(
                client=client,
                tracking_numbers=batch,
                language=language,
                tracking_number_format=tracking_number_format,
            )
            route_resps, payload = client.extract_route_payload(response)
            route_map = {
                str(item.get("mailNo") or item.get("trackingNumber") or "").strip(): item
                for item in route_resps
            }
            for tracking_number in batch:
                results[tracking_number] = {
                    "route_resp": route_map.get(tracking_number, {"mailNo": tracking_number, "routes": []}),
                    "payload_meta": {
                        "apiResultCode": response.get("apiResultCode"),
                        "errorCode": payload.get("errorCode"),
                    },
                }
        except SFClientError as error:
            errors.append({"batch": batch, "error": str(error), "type": "SFClientError"})
            for tracking_number in batch:
                results[tracking_number] = {
                    "route_resp": {"mailNo": tracking_number, "routes": []},
                    "payload_meta": {"error": str(error)},
                }
        except Exception as error:  # pragma: no cover - one-off analysis script
            errors.append({"batch": batch, "error": str(error), "type": type(error).__name__})
            for tracking_number in batch:
                results[tracking_number] = {
                    "route_resp": {"mailNo": tracking_number, "routes": []},
                    "payload_meta": {"error": str(error)},
                }

        if start + batch_size < len(requested):
            time.sleep(delay_seconds)

    return {"results": results, "errors": errors}


def query_routes(
    client: SFClient,
    tracking_numbers: list[str],
    language: str,
    tracking_number_format: str,
) -> dict[str, Any]:
    msg_data = {
        "trackingType": "1",
        "trackingNumber": tracking_numbers if tracking_number_format == "list" else ",".join(tracking_numbers),
        "methodType": "1",
        "language": language,
    }
    return client.call("EXP_RECE_SEARCH_ROUTES", msg_data)


def analyze_routes(
    selected_sheet: str,
    source_frame: pd.DataFrame,
    sample_pool: list[TrackingRow],
    sampled_rows: list[TrackingRow],
    sample_plan: dict[str, int],
    fetch_result: dict[str, Any],
) -> dict[str, Any]:
    source_delivery_counts = Counter(row.source_delivery_status for row in sample_pool)
    sampled_delivery_counts = Counter(row.source_delivery_status for row in sampled_rows)
    sampled_map = {row.tracking_number: row for row in sampled_rows}
    default_opcode_map = {
        mapping["opcode"]: {
            "mapped_status": mapping["mapped_status"],
            "note": mapping["note"],
        }
        for mapping in DEFAULT_STATUS_MAPPINGS
        if mapping.get("opcode")
    }

    latest_rows: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    latest_combo_groups: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    all_combo_counter: Counter[tuple[str, str, str, str, str]] = Counter()
    uncovered_latest_opcodes: Counter[str] = Counter()
    route_length_counter: list[int] = []

    for tracking_number, payload in fetch_result["results"].items():
        sample_meta = sampled_map[tracking_number]
        routes = payload["route_resp"].get("routes") or []
        route_length_counter.append(len(routes))
        sorted_routes = sorted(routes, key=event_sort_key)

        for event in sorted_routes:
            row = event_to_row(sample_meta, event, is_latest=False)
            all_rows.append(row)
            all_combo_counter[event_combo_key(event)] += 1

        latest_event = sorted_routes[-1] if sorted_routes else None
        latest_row = event_to_row(sample_meta, latest_event, is_latest=True)
        latest_rows.append(latest_row)
        if latest_event:
            combo = event_combo_key(latest_event)
            latest_combo_groups[combo].append(latest_row)
            opcode = latest_row["opcode"]
            if opcode and opcode not in default_opcode_map:
                uncovered_latest_opcodes[opcode] += 1

    latest_combo_summary = []
    for combo, rows in sorted(latest_combo_groups.items(), key=lambda item: len(item[1]), reverse=True):
        statuses = Counter(row["source_delivery_status"] for row in rows)
        op_code = combo[0]
        latest_combo_summary.append(
            {
                "opcode": op_code,
                "first_status_code": combo[1],
                "secondary_status_code": combo[2],
                "first_status_name": combo[3],
                "secondary_status_name": combo[4],
                "sample_count": len(rows),
                "source_delivery_status_counts": dict(statuses),
                "suggested_status": suggested_status(statuses),
                "current_default_mapping": default_opcode_map.get(op_code),
                "sample_tracking_numbers": [row["tracking_number"] for row in rows[:10]],
                "sample_remarks": unique_non_empty(row["remark"] for row in rows)[:5],
            }
        )

    all_combo_summary = []
    for combo, count in all_combo_counter.most_common():
        all_combo_summary.append(
            {
                "opcode": combo[0],
                "first_status_code": combo[1],
                "secondary_status_code": combo[2],
                "first_status_name": combo[3],
                "secondary_status_name": combo[4],
                "event_count": count,
            }
        )

    no_route_count = sum(1 for row in latest_rows if not row["has_route"])

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "selected_sheet": selected_sheet,
        "source_overview": {
            "source_row_count": int(source_frame.shape[0]),
            "unique_tracking_count": len(sample_pool),
            "source_delivery_status_counts": dict(source_delivery_counts),
        },
        "sample_overview": {
            "sample_size": len(sampled_rows),
            "sample_plan": sample_plan,
            "sampled_delivery_status_counts": dict(sampled_delivery_counts),
        },
        "fetch_overview": {
            "error_count": len(fetch_result["errors"]),
            "errors": fetch_result["errors"],
            "no_route_count": no_route_count,
        },
        "route_length_stats": summarize_route_lengths(route_length_counter),
        "latest_combo_summary": latest_combo_summary,
        "all_combo_summary": all_combo_summary[:100],
        "uncovered_latest_opcodes": dict(uncovered_latest_opcodes),
    }
    return {
        "summary": summary,
        "latest_rows": latest_rows,
        "all_rows": all_rows,
        "latest_combo_summary": latest_combo_summary,
        "all_combo_summary": all_combo_summary,
    }


def event_sort_key(event: dict[str, Any]) -> tuple[datetime, str, str]:
    raw_time = (
        event.get("acceptTime")
        or event.get("eventTime")
        or event.get("event_time")
        or "1970-01-01 00:00:00"
    )
    parsed = pd.to_datetime(raw_time, errors="coerce")
    if pd.isna(parsed):
        dt = datetime(1970, 1, 1)
    elif hasattr(parsed, "to_pydatetime"):
        dt = parsed.to_pydatetime()
    else:
        dt = datetime(1970, 1, 1)
    return (
        dt.replace(tzinfo=None),
        str(event.get("opCode") or event.get("opcode") or ""),
        str(event.get("remark") or event.get("eventDesc") or ""),
    )


def event_combo_key(event: dict[str, Any] | None) -> tuple[str, str, str, str, str]:
    if not event:
        return ("", "", "", "", "")
    return (
        str(event.get("opCode") or event.get("opcode") or ""),
        str(event.get("firstStatusCode") or event.get("first_status_code") or ""),
        str(event.get("secondaryStatusCode") or event.get("secondStatusCode") or event.get("secondary_status_code") or ""),
        str(event.get("firstStatusName") or event.get("firstStatusDesc") or ""),
        str(event.get("secondaryStatusName") or event.get("secondStatusDesc") or ""),
    )


def event_to_row(sample_meta: TrackingRow, event: dict[str, Any] | None, is_latest: bool) -> dict[str, Any]:
    combo = event_combo_key(event)
    return {
        "tracking_number": sample_meta.tracking_number,
        "order_number": sample_meta.order_number,
        "source_delivery_status": sample_meta.source_delivery_status,
        "source_order_status": sample_meta.source_order_status,
        "delivery_method": sample_meta.delivery_method,
        "is_latest": is_latest,
        "has_route": event is not None,
        "event_time": (
            str(event.get("acceptTime") or event.get("eventTime") or event.get("event_time") or "")
            if event
            else ""
        ),
        "opcode": combo[0],
        "first_status_code": combo[1],
        "secondary_status_code": combo[2],
        "first_status_name": combo[3],
        "secondary_status_name": combo[4],
        "remark": str(event.get("remark") or event.get("eventDesc") or event.get("description") or "") if event else "",
        "location": str(event.get("acceptAddress") or event.get("eventLocation") or "") if event else "",
    }


def suggested_status(status_counts: Counter[str]) -> str:
    if not status_counts:
        return "UNKNOWN"
    if len(status_counts) == 1:
        return next(iter(status_counts))
    return "MIXED"


def unique_non_empty(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def summarize_route_lengths(lengths: list[int]) -> dict[str, Any]:
    if not lengths:
        return {"min": 0, "max": 0, "avg": 0, "median": 0}
    series = pd.Series(lengths)
    return {
        "min": int(series.min()),
        "max": int(series.max()),
        "avg": round(float(series.mean()), 2),
        "median": float(series.median()),
    }


def write_outputs(
    run_dir: Path,
    sampled_rows: list[TrackingRow],
    fetch_result: dict[str, Any],
    analysis: dict[str, Any],
) -> None:
    (run_dir / "summary.json").write_text(
        json.dumps(analysis["summary"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "raw_route_responses.json").write_text(
        json.dumps(fetch_result["results"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(
        run_dir / "sampled_tracking_rows.csv",
        [
            {
                "tracking_number": row.tracking_number,
                "order_number": row.order_number,
                "source_delivery_status": row.source_delivery_status,
                "source_order_status": row.source_order_status,
                "delivery_method": row.delivery_method,
            }
            for row in sampled_rows
        ],
    )
    write_csv(run_dir / "latest_events.csv", analysis["latest_rows"])
    write_csv(run_dir / "all_events.csv", analysis["all_rows"])
    write_report(run_dir / "report.md", analysis["summary"])


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# SF Mapping Analysis",
        "",
        f"- Generated at: {summary['generated_at_utc']}",
        f"- Selected sheet: {summary['selected_sheet']}",
        f"- Source unique tracking count: {summary['source_overview']['unique_tracking_count']}",
        f"- Sample size: {summary['sample_overview']['sample_size']}",
        f"- Fetch errors: {summary['fetch_overview']['error_count']}",
        f"- No-route samples: {summary['fetch_overview']['no_route_count']}",
        "",
        "## Source Delivery Status Counts",
        "",
    ]

    for status, count in sorted(summary["source_overview"]["source_delivery_status_counts"].items()):
        lines.append(f"- {status}: {count}")

    lines.extend(["", "## Sample Delivery Status Counts", ""])
    for status, count in sorted(summary["sample_overview"]["sampled_delivery_status_counts"].items()):
        lines.append(f"- {status}: {count}")

    lines.extend(["", "## Latest Event Combination Candidates", ""])
    for item in summary["latest_combo_summary"][:20]:
        lines.append(
            (
                f"- opcode={item['opcode']}, first={item['first_status_code']}, "
                f"second={item['secondary_status_code']}, suggested={item['suggested_status']}, "
                f"count={item['sample_count']}, source={item['source_delivery_status_counts']}"
            )
        )

    lines.extend(["", "## Uncovered Latest Opcodes", ""])
    uncovered = summary["uncovered_latest_opcodes"]
    if uncovered:
        for opcode, count in sorted(uncovered.items(), key=lambda item: item[1], reverse=True):
            lines.append(f"- {opcode}: {count}")
    else:
        lines.append("- None")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
