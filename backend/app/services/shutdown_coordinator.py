from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Callable

from app.services.lite_job_store import LiteJobStore
from app.services.runtime_session_store import RuntimeSessionStore, RuntimeSessionRecord


class ShutdownCoordinator:
    """브라우저 세션 수와 Lite 작업 상태를 기준으로 앱 종료를 결정한다."""

    def __init__(
        self,
        *,
        auto_shutdown_enabled: bool,
        session_store: RuntimeSessionStore,
        job_store: LiteJobStore,
        heartbeat_seconds: int,
        stale_seconds: int,
        grace_seconds: int,
        request_shutdown: Callable[[str], None] | None = None,
        log_message: Callable[[str], None] | None = None,
    ) -> None:
        self._auto_shutdown_enabled = auto_shutdown_enabled
        self._session_store = session_store
        self._job_store = job_store
        self._heartbeat_seconds = heartbeat_seconds
        self._stale_seconds = stale_seconds
        self._grace_seconds = grace_seconds
        self._request_shutdown = request_shutdown or (lambda _reason: None)
        self._log_message = log_message or (lambda _message: None)
        self._lock = Lock()
        self._shutting_down = False
        self._shutdown_pending = False
        self._shutdown_requested = False
        self._shutdown_deadline: datetime | None = None
        self._last_reason = "startup"
        self._monitor_interval_seconds = max(1, min(5, heartbeat_seconds))

    async def monitor(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            self.run_maintenance()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._monitor_interval_seconds)
            except TimeoutError:
                continue

    def start_session(self) -> RuntimeSessionRecord:
        record = self._session_store.start()
        if self._auto_shutdown_enabled:
            self._cancel_shutdown("session started")
        return record

    def heartbeat(self, session_id: str) -> RuntimeSessionRecord | None:
        record = self._session_store.heartbeat(session_id)
        if record is not None and self._auto_shutdown_enabled:
            self._cancel_shutdown("session heartbeat")
        return record

    def end_session(self, session_id: str) -> bool:
        removed = self._session_store.end(session_id)
        if removed and self._auto_shutdown_enabled:
            self._evaluate("session ended", cleanup_stale=False)
        return removed

    def on_job_state_changed(self) -> None:
        if self._auto_shutdown_enabled:
            self._evaluate("job state changed", cleanup_stale=False)

    def run_maintenance(self) -> None:
        if self._auto_shutdown_enabled:
            self._evaluate("maintenance", cleanup_stale=True)

    def snapshot(self) -> dict[str, datetime | bool | int | None]:
        with self._lock:
            return {
                "shutting_down": self._shutting_down or self._shutdown_pending or self._shutdown_requested,
                "shutdown_deadline": self._shutdown_deadline,
                "active_sessions": self._session_store.count(),
            }

    def _cancel_shutdown(self, reason: str) -> None:
        with self._lock:
            if not (self._shutting_down or self._shutdown_pending):
                return
            if self._shutdown_requested:
                return
            self._shutting_down = False
            self._shutdown_pending = False
            self._shutdown_deadline = None
            self._last_reason = reason
        self._log_message(f"runtime shutdown canceled: {reason}")

    def _evaluate(self, reason: str, *, cleanup_stale: bool) -> None:
        stale_ids: list[str] = []
        shutdown_reason: str | None = None
        if cleanup_stale:
            stale_before = datetime.now(UTC) - timedelta(seconds=self._stale_seconds)
            stale_ids = self._session_store.cleanup_stale(stale_before)
            if stale_ids:
                self._log_message(
                    f"runtime stale sessions cleared count={len(stale_ids)} ids={','.join(stale_ids)}"
                )
                reason = "last session stale-cleared"

        has_sessions = self._session_store.has_sessions()
        now = datetime.now(UTC)

        with self._lock:
            if self._shutdown_requested:
                return

            if has_sessions:
                if self._shutting_down or self._shutdown_pending:
                    self._shutting_down = False
                    self._shutdown_pending = False
                    self._shutdown_deadline = None
                    self._last_reason = "session restored"
                    cancel_reason = "session restored"
                else:
                    cancel_reason = None
            else:
                cancel_reason = None
                if not self._shutting_down and not self._shutdown_pending:
                    self._shutting_down = True
                    self._shutdown_deadline = now + timedelta(seconds=self._grace_seconds)
                    self._last_reason = reason
                    self._log_message(
                        "runtime shutdown scheduled: "
                        f"reason={reason}, deadline={self._shutdown_deadline.isoformat()}"
                    )
                    return

                if self._shutdown_deadline and now < self._shutdown_deadline:
                    return

                if self._job_store.has_active_jobs():
                    if not self._shutdown_pending:
                        self._shutdown_pending = True
                        self._log_message(
                            "runtime shutdown deferred: grace elapsed, active jobs remain"
                        )
                    return

                self._shutdown_requested = True
                self._shutting_down = True
                self._shutdown_pending = False
                self._shutdown_deadline = None
                shutdown_reason = f"{self._last_reason}, grace elapsed, active jobs=0"

        if cancel_reason:
            self._log_message(f"runtime shutdown canceled: {cancel_reason}")
            return
        if has_sessions:
            return

        if shutdown_reason:
            self._log_message(f"runtime shutdown requested: {shutdown_reason}")
            self._request_shutdown(shutdown_reason)
