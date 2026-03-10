from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ApiKeyMasked(BaseModel):
    id: int
    service: str
    label: str
    environment: str
    is_active: bool
    key_fields: dict[str, str]
    last_tested_at: datetime | None = None
    test_result: str | None = None


class ApiKeyCreateRequest(BaseModel):
    service: str = "sf_express"
    label: str
    environment: str = Field(pattern="^(sandbox|production)$")
    partner_id: str
    checkword: str
    is_active: bool = True

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_environment(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class ApiKeyUpdateRequest(BaseModel):
    label: str | None = None
    partner_id: str | None = None
    checkword: str | None = None
    is_active: bool | None = None


class PollingSettings(BaseModel):
    enabled: bool = True
    interval_hours: int = 2
    batch_size: int = 10
    delay_between_batches_seconds: int = 1
    max_retries: int = 3


class StatusMappingItem(BaseModel):
    id: int | None = None
    carrier_code: str = "SF"
    opcode: str | None = None
    first_status_code: str | None = None
    secondary_status_code: str | None = None
    mapped_status: str
    is_terminal: bool = False
    priority: int = 100
    note: str | None = None


class StatusMappingsUpdateRequest(BaseModel):
    mappings: list[StatusMappingItem]


class ApiKeyTestResult(BaseModel):
    ok: bool
    detail: str
    payload: dict[str, Any] | None = None
