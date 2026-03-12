from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.lite_job_store import LiteJobStore
from app.services.runtime_session_store import RuntimeSessionStore
from app.services.shutdown_coordinator import ShutdownCoordinator


def build_runtime_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        data_dir=tmp_path / "data",
        frontend_dist_dir=tmp_path / "dist",
        enable_scheduler=False,
        runtime_auto_shutdown_enabled=True,
        runtime_shutdown_grace_seconds=30,
        runtime_session_stale_seconds=90,
    )
    app = create_app(settings)
    return TestClient(app)


def test_runtime_session_end_schedules_shutdown_and_reconnect_cancels(tmp_path: Path) -> None:
    with build_runtime_client(tmp_path) as client:
        start_response = client.post("/api/runtime/session/start")
        assert start_response.status_code == 200
        session_id = start_response.json()["session_id"]

        assert client.get("/api/health").json()["shutting_down"] is False

        end_response = client.post("/api/runtime/session/end", json={"session_id": session_id})
        assert end_response.status_code == 200

        shutting_down_payload = client.get("/api/health").json()
        assert shutting_down_payload["shutting_down"] is True
        assert shutting_down_payload["shutdown_deadline"] is not None

        restart_response = client.post("/api/runtime/session/start")
        assert restart_response.status_code == 200

        assert client.get("/api/health").json()["shutting_down"] is False


def test_shutdown_waits_for_active_job_completion() -> None:
    requested_reasons: list[str] = []
    job_store = LiteJobStore()
    coordinator = ShutdownCoordinator(
        auto_shutdown_enabled=True,
        session_store=RuntimeSessionStore(),
        job_store=job_store,
        heartbeat_seconds=15,
        stale_seconds=90,
        grace_seconds=0,
        request_shutdown=requested_reasons.append,
    )
    job_store.set_job_state_callback(coordinator.on_job_state_changed)

    session = coordinator.start_session()
    queued_job = job_store.create(file_name="orders.csv")

    coordinator.end_session(session.session_id)
    coordinator.run_maintenance()

    assert requested_reasons == []
    assert coordinator.snapshot()["shutting_down"] is True

    job_store.mark_failed(queued_job.job_id, "done")

    assert requested_reasons
    assert "active jobs=0" in requested_reasons[0]


def test_stale_session_cleanup_triggers_shutdown() -> None:
    requested_reasons: list[str] = []
    coordinator = ShutdownCoordinator(
        auto_shutdown_enabled=True,
        session_store=RuntimeSessionStore(),
        job_store=LiteJobStore(),
        heartbeat_seconds=15,
        stale_seconds=0,
        grace_seconds=30,
        request_shutdown=requested_reasons.append,
    )

    coordinator.start_session()
    time.sleep(0.01)
    coordinator.run_maintenance()

    snapshot = coordinator.snapshot()
    assert snapshot["shutting_down"] is True
    assert snapshot["shutdown_deadline"] is not None
    assert requested_reasons == []
