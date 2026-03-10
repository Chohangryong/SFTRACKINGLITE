from __future__ import annotations

import csv
import json
from io import BytesIO, StringIO
from pathlib import Path
from uuid import uuid4

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.tracking import Tracking
from app.models.tracking_event import TrackingEvent
from app.schemas.export import ExportDownloadRequest, ExportPreset, ExportPresetCreateRequest
from app.services.tracking_service import TrackingService
from app.utils.excel_safe import escape_excel_formula

DEFAULT_EXPORT_PRESETS = [
    {
        "id": "summary-default",
        "name": "Summary Default",
        "export_type": "summary",
        "columns": [
            "order_number",
            "tracking_number",
            "current_status",
            "current_status_code",
            "last_event_location",
            "last_event_desc",
            "last_event_time",
            "last_queried_at",
        ],
        "is_default": True,
    },
    {
        "id": "event-default",
        "name": "Event Default",
        "export_type": "event",
        "columns": [
            "tracking_number",
            "event_time",
            "event_location",
            "first_status_code",
            "secondary_status_code",
            "opcode",
            "first_status_name",
            "secondary_status_name",
            "event_desc",
            "mapped_status",
        ],
        "is_default": True,
    },
]


class ExportService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def list_presets(self) -> list[ExportPreset]:
        return [ExportPreset(**item) for item in self._load_presets()]

    def create_preset(self, request: ExportPresetCreateRequest) -> ExportPreset:
        presets = self._load_presets()
        payload = {
            "id": uuid4().hex,
            "name": request.name,
            "export_type": request.export_type,
            "columns": request.columns,
            "is_default": False,
        }
        presets.append(payload)
        self._write_presets(presets)
        return ExportPreset(**payload)

    def generate_export(self, request: ExportDownloadRequest) -> tuple[str, bytes, str]:
        preset = self._resolve_preset(request)
        rows = self._build_rows(request.export_type, request.filters, preset.columns)
        if request.file_format == "csv":
            return self._export_csv(request.export_type, preset.columns, rows)
        return self._export_xlsx(request.export_type, preset.columns, rows)

    def _build_rows(self, export_type: str, filters: dict, columns: list[str]) -> list[dict]:
        if export_type == "summary":
            tracking_service = TrackingService(self.session, self.settings)
            response = tracking_service.list_trackings(
                page=1,
                page_size=10_000,
                query=filters.get("query"),
                status=filters.get("status"),
            )
            return [item.model_dump() for item in response.items]

        events = self.session.execute(
            select(Tracking.tracking_number, TrackingEvent)
            .join(Tracking, Tracking.id == TrackingEvent.tracking_id)
            .order_by(TrackingEvent.event_time.desc())
        ).all()
        rows: list[dict] = []
        for tracking_number, event in events:
            row = {"tracking_number": tracking_number, **event.__dict__}
            row.pop("_sa_instance_state", None)
            rows.append(row)
        return rows

    def _export_xlsx(self, export_type: str, columns: list[str], rows: list[dict]) -> tuple[str, bytes, str]:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = export_type.title()
        worksheet.append(columns)
        for row in rows:
            worksheet.append([escape_excel_formula(row.get(column)) for column in columns])
        buffer = BytesIO()
        workbook.save(buffer)
        filename = f"{export_type}-export.xlsx"
        return filename, buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def _export_csv(self, export_type: str, columns: list[str], rows: list[dict]) -> tuple[str, bytes, str]:
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: escape_excel_formula(row.get(column)) for column in columns})
        filename = f"{export_type}-export.csv"
        return filename, buffer.getvalue().encode("utf-8"), "text/csv"

    def _resolve_preset(self, request: ExportDownloadRequest) -> ExportPreset:
        presets = self.list_presets()
        if request.preset_id:
            for preset in presets:
                if preset.id == request.preset_id:
                    return preset
        for preset in presets:
            if preset.export_type == request.export_type and preset.is_default:
                return preset
        raise ValueError("Export preset not found")

    def _load_presets(self) -> list[dict]:
        path = self.settings.export_presets_path
        if not path.exists():
            self._write_presets(DEFAULT_EXPORT_PRESETS)
        return json.loads(path.read_text())

    def _write_presets(self, presets: list[dict]) -> None:
        self.settings.export_presets_path.write_text(json.dumps(presets, indent=2))
