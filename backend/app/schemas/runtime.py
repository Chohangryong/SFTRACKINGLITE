from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RuntimeSessionStartResponse(BaseModel):
    session_id: str
    started_at: datetime


class RuntimeSessionHeartbeatRequest(BaseModel):
    session_id: str


class RuntimeSessionHeartbeatResponse(BaseModel):
    ok: bool = True
    shutting_down: bool = False


class RuntimeSessionEndRequest(BaseModel):
    session_id: str


class RuntimeSessionEndResponse(BaseModel):
    ok: bool = True
