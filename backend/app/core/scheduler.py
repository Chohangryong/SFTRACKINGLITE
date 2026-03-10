from __future__ import annotations

from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import Settings
from app.core.db import DatabaseManager
from app.services.polling_service import PollingService
from app.services.settings_service import SettingsService


def build_scheduler(database: DatabaseManager, settings: Settings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")

    def polling_job(force_all: bool = False) -> None:
        with database.session() as session:
            PollingService(session, settings).run(force_all=force_all)

    with database.session() as session:
        polling_settings = SettingsService(session, settings).get_polling_settings()

    if polling_settings.enabled:
        scheduler.add_job(
            polling_job,
            "date",
            run_date=datetime.utcnow(),
            kwargs={"force_all": False},
            id="startup-polling",
            replace_existing=True,
        )
        scheduler.add_job(
            polling_job,
            "interval",
            hours=polling_settings.interval_hours,
            kwargs={"force_all": False},
            id="interval-polling",
            replace_existing=True,
        )
    return scheduler
