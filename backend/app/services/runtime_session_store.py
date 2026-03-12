from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4


@dataclass
class RuntimeSessionRecord:
    session_id: str
    started_at: datetime
    last_seen_at: datetime


class RuntimeSessionStore:
    """브라우저 탭 단위 세션을 메모리에만 유지한다."""

    def __init__(self) -> None:
        self._sessions: dict[str, RuntimeSessionRecord] = {}
        self._lock = Lock()

    def start(self) -> RuntimeSessionRecord:
        now = datetime.now(UTC)
        record = RuntimeSessionRecord(
            session_id=uuid4().hex,
            started_at=now,
            last_seen_at=now,
        )
        with self._lock:
            self._sessions[record.session_id] = record
        return RuntimeSessionRecord(**record.__dict__)

    def heartbeat(self, session_id: str) -> RuntimeSessionRecord | None:
        now = datetime.now(UTC)
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            record.last_seen_at = now
            return RuntimeSessionRecord(**record.__dict__)

    def end(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def cleanup_stale(self, stale_before: datetime) -> list[str]:
        with self._lock:
            stale_ids = [
                session_id
                for session_id, record in self._sessions.items()
                if record.last_seen_at <= stale_before
            ]
            for session_id in stale_ids:
                self._sessions.pop(session_id, None)
        return stale_ids

    def has_sessions(self) -> bool:
        with self._lock:
            return bool(self._sessions)

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)
