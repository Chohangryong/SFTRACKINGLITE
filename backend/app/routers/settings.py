from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.dependencies import get_session, get_settings
from app.schemas.common import MessageResponse
from app.schemas.settings import (
    ApiKeyCreateRequest,
    ApiKeyMasked,
    ApiKeyTestResult,
    ApiKeyUpdateRequest,
    PollingSettings,
    StatusMappingItem,
    StatusMappingsUpdateRequest,
)
from app.services.settings_service import SettingsService
from app.services.sf_client import SFClient, SFClientCredentials
from app.services.status_mapping_service import StatusMappingService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/api-keys", response_model=list[ApiKeyMasked])
def list_api_keys(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[ApiKeyMasked]:
    return SettingsService(session, settings).list_api_keys()


@router.post("/api-keys", response_model=ApiKeyMasked)
def create_api_key(
    request: ApiKeyCreateRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ApiKeyMasked:
    return SettingsService(session, settings).create_api_key(request)


@router.put("/api-keys/{api_key_id}", response_model=ApiKeyMasked)
def update_api_key(
    api_key_id: int,
    request: ApiKeyUpdateRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ApiKeyMasked:
    try:
        return SettingsService(session, settings).update_api_key(api_key_id, request)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/api-keys/{api_key_id}", response_model=MessageResponse)
def delete_api_key(
    api_key_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    try:
        SettingsService(session, settings).delete_api_key(api_key_id)
        return MessageResponse(message="API key deleted")
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/api-keys/{api_key_id}/test", response_model=ApiKeyTestResult)
def test_api_key(
    api_key_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ApiKeyTestResult:
    service = SettingsService(session, settings)
    try:
        record, secret_fields = service.get_api_key_by_id(api_key_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    client = SFClient(
        settings,
        SFClientCredentials(
            partner_id=secret_fields["partner_id"],
            checkword=secret_fields["checkword"],
            environment=record.environment,
        ),
    )
    try:
        payload = client.search_routes(["000000000000"])
        service.mark_api_key_test(api_key_id, True, "Request completed")
        return ApiKeyTestResult(ok=True, detail="Request completed", payload=payload)
    except Exception as error:
        service.mark_api_key_test(api_key_id, False, str(error))
        return ApiKeyTestResult(ok=False, detail=str(error))


@router.get("/polling", response_model=PollingSettings)
def get_polling_settings(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PollingSettings:
    return SettingsService(session, settings).get_polling_settings()


@router.put("/polling", response_model=PollingSettings)
def update_polling_settings(
    request: PollingSettings,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PollingSettings:
    return SettingsService(session, settings).update_polling_settings(request)


@router.get("/mappings", response_model=list[StatusMappingItem])
def get_status_mappings(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[StatusMappingItem]:
    mappings = StatusMappingService(session).list_mappings()
    return [
        StatusMappingItem(
            id=item.id,
            carrier_code=item.carrier_code,
            opcode=item.opcode,
            first_status_code=item.first_status_code,
            secondary_status_code=item.secondary_status_code,
            mapped_status=item.mapped_status,
            is_terminal=item.is_terminal,
            priority=item.priority,
            note=item.note,
        )
        for item in mappings
    ]


@router.put("/mappings", response_model=list[StatusMappingItem])
def update_status_mappings(
    request: StatusMappingsUpdateRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[StatusMappingItem]:
    mappings = StatusMappingService(session).replace_mappings(request.mappings)
    return [
        StatusMappingItem(
            id=item.id,
            carrier_code=item.carrier_code,
            opcode=item.opcode,
            first_status_code=item.first_status_code,
            secondary_status_code=item.secondary_status_code,
            mapped_status=item.mapped_status,
            is_terminal=item.is_terminal,
            priority=item.priority,
            note=item.note,
        )
        for item in mappings
    ]
