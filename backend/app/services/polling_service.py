from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.polling_run import PollingRun
from app.services.tracking_service import TrackingService


class PollingService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def run(self, force_all: bool = False) -> dict:
        run = PollingRun(started_at=datetime.utcnow(), status="running")
        self.session.add(run)
        self.session.commit()

        try:
            refresh_result = TrackingService(self.session, self.settings).refresh_pollable_trackings(force_all=force_all)
            run.finished_at = datetime.utcnow()
            run.total_targets = refresh_result.requested
            run.success_count = refresh_result.refreshed
            run.failed_count = refresh_result.failed
            run.status = "completed"
            run.error_message = None if not refresh_result.errors else refresh_result.errors[0]["message"]
            self.session.commit()
            return refresh_result.model_dump()
        except Exception as error:
            run.finished_at = datetime.utcnow()
            run.status = "failed"
            run.error_message = str(error)
            self.session.commit()
            raise
