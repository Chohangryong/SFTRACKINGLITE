from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.column_mapping_preset import ColumnMappingPreset
from app.models.order import Order
from app.models.order_tracking import OrderTracking
from app.models.tracking import Tracking
from app.models.upload_batch import UploadBatch
from app.models.upload_error import UploadError
from app.schemas.uploads import UploadBatchCreateResponse, UploadConfirmResult, UploadErrorItem, UploadPreview
from app.services.file_parser import FileParser
from app.services.tracking_service import TrackingService


class UploadService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.file_parser = FileParser(preview_rows=settings.upload_preview_rows)

    async def create_batch(self, upload_file: UploadFile) -> UploadBatchCreateResponse:
        suffix = Path(upload_file.filename or "").suffix.lower()
        if suffix not in {".csv", ".xlsx", ".xls"}:
            raise ValueError("Unsupported file type")

        content = await upload_file.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > self.settings.upload_max_size_mb:
            raise ValueError("Upload file exceeds size limit")

        batch_id = uuid4().hex
        stored_path = self.settings.upload_dir / f"{batch_id}{suffix}"
        stored_path.write_bytes(content)
        file_hash = hashlib.sha256(content).hexdigest()
        parsed = self.file_parser.parse(stored_path)
        errors = self.file_parser.validate_rows(parsed.rows, parsed.detected_mapping)

        batch = UploadBatch(
            id=batch_id,
            file_name=upload_file.filename or stored_path.name,
            file_hash=file_hash,
            file_path=str(stored_path),
            status="pending",
            total_rows=len(parsed.rows),
            error_rows=len(errors),
            parsed_data={
                "columns": parsed.columns,
                "preview_rows": parsed.preview_rows,
            },
            column_mapping=parsed.detected_mapping,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        self.session.add(batch)
        self.session.flush()
        self._replace_errors(batch.id, errors)
        self.session.commit()
        return UploadBatchCreateResponse(
            batch_id=batch.id,
            file_name=batch.file_name,
            total_rows=batch.total_rows,
            detected_mapping=parsed.detected_mapping,
            preview_rows=parsed.preview_rows,
        )

    def get_preview(self, batch_id: str) -> UploadPreview:
        batch = self._get_batch(batch_id)
        return UploadPreview(
            batch_id=batch.id,
            status=batch.status,
            file_name=batch.file_name,
            columns=batch.parsed_data.get("columns", []) if batch.parsed_data else [],
            detected_mapping=batch.column_mapping or {},
            preview_rows=batch.parsed_data.get("preview_rows", []) if batch.parsed_data else [],
            total_rows=batch.total_rows,
            error_rows=batch.error_rows,
            created_at=batch.created_at,
        )

    def get_errors(self, batch_id: str) -> list[UploadErrorItem]:
        errors = list(
            self.session.scalars(
                select(UploadError)
                .where(UploadError.upload_batch_id == batch_id)
                .order_by(UploadError.row_number.asc(), UploadError.id.asc())
            )
        )
        return [
            UploadErrorItem(
                id=error.id,
                row_number=error.row_number,
                error_type=error.error_type,
                error_message=error.error_message,
                raw_row_json=error.raw_row_json,
            )
            for error in errors
        ]

    def confirm_batch(
        self,
        batch_id: str,
        mapping_override: dict[str, str | None] | None = None,
        save_preset_name: str | None = None,
    ) -> UploadConfirmResult:
        batch = self._get_batch(batch_id)
        if batch.status == "confirmed":
            return UploadConfirmResult(
                batch_id=batch.id,
                status=batch.status,
                success_rows=batch.success_rows,
                skipped_rows=batch.skipped_rows,
                error_rows=batch.error_rows,
                affected_tracking_numbers=[],
                refresh_summary={"message": "Batch already confirmed"},
            )

        parsed = self.file_parser.parse(Path(batch.file_path))
        mapping = {**(batch.column_mapping or {}), **(mapping_override or {})}
        validation_errors = self.file_parser.validate_rows(parsed.rows, mapping)
        self._replace_errors(batch.id, validation_errors)

        success_rows = 0
        skipped_rows = 0
        error_rows = 0
        affected_tracking_numbers: list[str] = []
        known_order_tracking_pairs: set[tuple[int, int]] = set()

        for index, row in enumerate(parsed.rows, start=1):
            order_number = self.file_parser.extract_field(row, mapping, "order_number")
            tracking_number = self.file_parser.extract_field(row, mapping, "tracking_number")

            if not order_number:
                error_rows += 1
                continue

            order = self.session.scalar(select(Order).where(Order.order_number == order_number))
            if order is None:
                order = Order(order_number=order_number, raw_data=row, first_seen_at=datetime.utcnow())
                self.session.add(order)
                self.session.flush()
            else:
                order.raw_data = row

            if not tracking_number:
                success_rows += 1
                continue

            tracking = self.session.scalar(select(Tracking).where(Tracking.tracking_number == tracking_number))
            if tracking is None:
                tracking = Tracking(tracking_number=tracking_number, current_status="REGISTERED")
                self.session.add(tracking)
                self.session.flush()

            link_key = (order.id, tracking.id)
            if link_key not in known_order_tracking_pairs:
                link = self.session.scalar(
                    select(OrderTracking.id).where(
                        OrderTracking.order_id == order.id,
                        OrderTracking.tracking_id == tracking.id,
                    )
                )
                if link is None:
                    self.session.add(OrderTracking(order_id=order.id, tracking_id=tracking.id))
                known_order_tracking_pairs.add(link_key)
            affected_tracking_numbers.append(tracking_number)
            success_rows += 1

        if save_preset_name:
            self.session.add(
                ColumnMappingPreset(
                    name=save_preset_name,
                    source_hint=batch.file_name,
                    mapping_json=mapping,
                    is_default=False,
                )
            )

        batch.status = "confirmed"
        batch.success_rows = success_rows
        batch.skipped_rows = skipped_rows
        batch.error_rows = error_rows
        batch.confirmed_at = datetime.utcnow()
        batch.column_mapping = mapping
        self.session.commit()

        refresh_summary = TrackingService(self.session, self.settings).refresh_tracking_numbers(
            affected_tracking_numbers
        ).model_dump()
        self.session.commit()

        return UploadConfirmResult(
            batch_id=batch.id,
            status=batch.status,
            success_rows=success_rows,
            skipped_rows=skipped_rows,
            error_rows=error_rows,
            affected_tracking_numbers=list(dict.fromkeys(affected_tracking_numbers)),
            refresh_summary=refresh_summary,
        )

    def _replace_errors(self, batch_id: str, errors: list[dict[str, Any]]) -> None:
        self.session.execute(delete(UploadError).where(UploadError.upload_batch_id == batch_id))
        for error in errors:
            self.session.add(UploadError(upload_batch_id=batch_id, **error))

    def _get_batch(self, batch_id: str) -> UploadBatch:
        batch = self.session.get(UploadBatch, batch_id)
        if batch is None:
            raise ValueError("Upload batch not found")
        return batch
