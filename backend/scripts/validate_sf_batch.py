from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from analyze_sf_mapping import (  # noqa: E402
    REPO_ROOT,
    build_sf_client,
    build_tracking_pool,
    load_source_frame,
    normalize_frame,
    sample_tracking_rows,
)
from app.services.sf_client import SFClientError  # noqa: E402


OFFICIAL_DOC_URL = (
    "https://qiao.sf-express.com/doc/download/"
    "%E4%B8%B0%E6%A1%A5%E5%B9%B3%E5%8F%B0%E6%96%B0API%E6%8E%A5%E5%8F%A3%E8%A7%84%E8%8C%83.pdf"
)


def parse_args() -> argparse.Namespace:
    default_excel = REPO_ROOT / "data" / "uploads" / "1d8f1f4f27a048e6bd743c3742da01ad.xls"
    parser = argparse.ArgumentParser(description="Validate 10-tracking batch request formats against SF.")
    parser.add_argument("--excel-path", type=Path, default=default_excel)
    parser.add_argument("--sheet-name", type=str, default=None)
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--delay-seconds", type=float, default=0.5)
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data" / "analysis")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_sheet, data_frame = load_source_frame(args.excel_path, args.sheet_name)
    normalized = normalize_frame(data_frame)
    tracking_pool = build_tracking_pool(normalized)
    sampled_rows, sample_plan = sample_tracking_rows(tracking_pool, args.sample_size, args.seed)
    client = build_sf_client_from_active_settings()

    run_dir = args.output_dir / f"sf_batch_validation_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    run_dir.mkdir(parents=True, exist_ok=True)

    batches = chunked([row.tracking_number for row in sampled_rows], args.batch_size)
    variants = build_variants()
    raw_results: list[dict[str, Any]] = []

    for batch_index, batch in enumerate(batches, start=1):
        for variant in variants:
            result = execute_variant(client, batch, variant)
            result["batch_index"] = batch_index
            raw_results.append(result)
            time.sleep(args.delay_seconds)

    summary = summarize_results(
        selected_sheet=selected_sheet,
        sample_plan=sample_plan,
        sampled_rows=sampled_rows,
        raw_results=raw_results,
        batch_size=args.batch_size,
    )
    write_outputs(run_dir, summary, raw_results, sampled_rows)
    print(run_dir)
    return 0


def build_sf_client_from_active_settings():
    from app.core.config import Settings

    return build_sf_client(Settings())


def build_variants() -> list[dict[str, Any]]:
    return [
        {
            "name": "doc_list_lang0",
            "language": "0",
            "tracking_number_format": "list",
        },
        {
            "name": "doc_list_zh_cn",
            "language": "zh-CN",
            "tracking_number_format": "list",
        },
        {
            "name": "csv_lang0",
            "language": "0",
            "tracking_number_format": "csv",
        },
        {
            "name": "csv_zh_cn",
            "language": "zh-CN",
            "tracking_number_format": "csv",
        },
    ]


def execute_variant(client, batch: list[str], variant: dict[str, Any]) -> dict[str, Any]:
    msg_data = {
        "trackingType": "1",
        "trackingNumber": batch if variant["tracking_number_format"] == "list" else ",".join(batch),
        "methodType": "1",
        "language": variant["language"],
    }
    result: dict[str, Any] = {
        "variant": variant["name"],
        "requested_tracking_numbers": batch,
        "msg_data": msg_data,
    }

    try:
        response = client.call("EXP_RECE_SEARCH_ROUTES", msg_data)
        result["raw_response"] = response
        route_resps, payload = client.extract_route_payload(response)
        result["extract_ok"] = True
        result["payload_error_code"] = payload.get("errorCode")
        result["route_resps"] = route_resps
    except SFClientError as error:
        result["extract_ok"] = False
        result["error_type"] = "SFClientError"
        result["error"] = str(error)
        result["route_resps"] = []
    except Exception as error:  # pragma: no cover - one-off diagnostic script
        result["extract_ok"] = False
        result["error_type"] = type(error).__name__
        result["error"] = str(error)
        result["route_resps"] = []

    result["diagnostics"] = diagnose_batch_result(batch, result["route_resps"])
    return result


def diagnose_batch_result(requested_tracking_numbers: list[str], route_resps: list[dict[str, Any]]) -> dict[str, Any]:
    requested_set = set(requested_tracking_numbers)
    mail_nos = [str(item.get("mailNo") or item.get("trackingNumber") or "").strip() for item in route_resps]
    matched = sorted(mail_no for mail_no in mail_nos if mail_no in requested_set)
    unmatched = [tracking for tracking in requested_tracking_numbers if tracking not in matched]
    combined = [mail_no for mail_no in mail_nos if "," in mail_no]
    nonempty_route_counts = [len(item.get("routes") or []) for item in route_resps]
    total_routes = sum(nonempty_route_counts)

    return {
        "route_resp_count": len(route_resps),
        "mail_nos": mail_nos,
        "matched_tracking_numbers": matched,
        "unmatched_tracking_numbers": unmatched,
        "combined_mail_no_entries": combined,
        "nonempty_route_resp_count": sum(1 for count in nonempty_route_counts if count > 0),
        "total_route_count": total_routes,
        "full_coverage": len(matched) == len(requested_tracking_numbers),
        "collapsed_batch_response": bool(combined) and len(route_resps) == 1,
    }


def summarize_results(
    selected_sheet: str,
    sample_plan: dict[str, int],
    sampled_rows,
    raw_results: list[dict[str, Any]],
    batch_size: int,
) -> dict[str, Any]:
    variant_groups: dict[str, list[dict[str, Any]]] = {}
    for result in raw_results:
        variant_groups.setdefault(result["variant"], []).append(result)

    variant_summaries = {}
    for variant, items in variant_groups.items():
        extract_ok_count = sum(1 for item in items if item["extract_ok"])
        full_coverage_count = sum(1 for item in items if item["diagnostics"]["full_coverage"])
        collapsed_count = sum(1 for item in items if item["diagnostics"]["collapsed_batch_response"])
        total_matched = sum(len(item["diagnostics"]["matched_tracking_numbers"]) for item in items)
        total_requested = sum(len(item["requested_tracking_numbers"]) for item in items)
        total_nonempty_route_resps = sum(item["diagnostics"]["nonempty_route_resp_count"] for item in items)
        total_routes = sum(item["diagnostics"]["total_route_count"] for item in items)
        variant_summaries[variant] = {
            "requests": len(items),
            "extract_ok_count": extract_ok_count,
            "full_coverage_count": full_coverage_count,
            "collapsed_batch_response_count": collapsed_count,
            "requested_tracking_count": total_requested,
            "matched_tracking_count": total_matched,
            "nonempty_route_resp_count": total_nonempty_route_resps,
            "total_route_count": total_routes,
            "coverage_rate": round(total_matched / total_requested, 4) if total_requested else 0,
        }

    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "selected_sheet": selected_sheet,
        "batch_size": batch_size,
        "sample_size": len(sampled_rows),
        "sample_plan": sample_plan,
        "sampled_delivery_status_counts": dict(Counter(row.source_delivery_status for row in sampled_rows)),
        "official_doc_url": OFFICIAL_DOC_URL,
        "official_doc_notes": {
            "trackingNumber_type": "List<String>",
            "language_values": ["0", "1", "2"],
            "example_msg_data": {
                "language": "0",
                "trackingType": "1",
                "trackingNumber": ["444003077898", "441003077850"],
                "methodType": "1",
            },
        },
        "variant_summaries": variant_summaries,
    }


def chunked(values: list[str], chunk_size: int) -> list[list[str]]:
    return [values[index : index + chunk_size] for index in range(0, len(values), chunk_size)]


def write_outputs(
    run_dir: Path,
    summary: dict[str, Any],
    raw_results: list[dict[str, Any]],
    sampled_rows,
) -> None:
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "raw_results.json").write_text(json.dumps(raw_results, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "input_tracking_numbers.json").write_text(
        json.dumps(
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
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "report.md").write_text(build_report(summary), encoding="utf-8")


def build_report(summary: dict[str, Any]) -> str:
    lines = [
        "# SF Batch Validation",
        "",
        f"- Generated at: {summary['generated_at_utc']}",
        f"- Selected sheet: {summary['selected_sheet']}",
        f"- Sample size: {summary['sample_size']}",
        f"- Batch size: {summary['batch_size']}",
        f"- Official doc: {summary['official_doc_url']}",
        "",
        "## Sample Status Mix",
        "",
    ]
    for status, count in sorted(summary["sampled_delivery_status_counts"].items()):
        lines.append(f"- {status}: {count}")

    lines.extend(["", "## Variant Results", ""])
    for variant, stats in summary["variant_summaries"].items():
        lines.append(f"- {variant}")
        lines.append(f"  requests={stats['requests']}")
        lines.append(f"  extract_ok={stats['extract_ok_count']}")
        lines.append(f"  full_coverage={stats['full_coverage_count']}")
        lines.append(f"  collapsed_batch_response={stats['collapsed_batch_response_count']}")
        lines.append(f"  matched_tracking_count={stats['matched_tracking_count']}/{stats['requested_tracking_count']}")
        lines.append(f"  nonempty_route_resp_count={stats['nonempty_route_resp_count']}")
        lines.append(f"  total_route_count={stats['total_route_count']}")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
