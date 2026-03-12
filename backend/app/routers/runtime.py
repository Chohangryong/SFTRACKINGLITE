from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.schemas.runtime import (
    RuntimeSessionEndRequest,
    RuntimeSessionEndResponse,
    RuntimeSessionHeartbeatRequest,
    RuntimeSessionHeartbeatResponse,
    RuntimeSessionStartResponse,
)
from app.services.shutdown_coordinator import ShutdownCoordinator

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.post("/session/start", response_model=RuntimeSessionStartResponse)
def start_runtime_session(request: Request) -> RuntimeSessionStartResponse:
    coordinator: ShutdownCoordinator = request.app.state.shutdown_coordinator
    record = coordinator.start_session()
    return RuntimeSessionStartResponse(
        session_id=record.session_id,
        started_at=record.started_at,
    )


@router.post("/session/heartbeat", response_model=RuntimeSessionHeartbeatResponse)
def heartbeat_runtime_session(
    payload: RuntimeSessionHeartbeatRequest,
    request: Request,
) -> RuntimeSessionHeartbeatResponse:
    coordinator: ShutdownCoordinator = request.app.state.shutdown_coordinator
    record = coordinator.heartbeat(payload.session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Runtime session not found")
    snapshot = coordinator.snapshot()
    return RuntimeSessionHeartbeatResponse(shutting_down=bool(snapshot["shutting_down"]))


@router.post("/session/end", response_model=RuntimeSessionEndResponse)
def end_runtime_session(
    payload: RuntimeSessionEndRequest,
    request: Request,
) -> RuntimeSessionEndResponse:
    coordinator: ShutdownCoordinator = request.app.state.shutdown_coordinator
    coordinator.end_session(payload.session_id)
    return RuntimeSessionEndResponse()
