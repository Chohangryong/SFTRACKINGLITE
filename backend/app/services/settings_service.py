from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.api_key import ApiKey
from app.schemas.settings import (
    ApiKeyCreateRequest,
    ApiKeyMasked,
    ApiKeyUpdateRequest,
    PollingSettings,
)
from app.utils.crypto import SecretCipher, mask_secret


class SettingsService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.cipher = SecretCipher(settings.dev_cipher_key_path)

    def get_polling_settings(self) -> PollingSettings:
        if not self.settings.app_settings_path.exists():
            return PollingSettings()
        payload = json.loads(self.settings.app_settings_path.read_text())
        return PollingSettings(**payload.get("polling", {}))

    def update_polling_settings(self, polling_settings: PollingSettings) -> PollingSettings:
        payload = {"polling": polling_settings.model_dump()}
        self.settings.app_settings_path.write_text(json.dumps(payload, indent=2))
        return polling_settings

    def list_api_keys(self) -> list[ApiKeyMasked]:
        records = list(self.session.scalars(select(ApiKey).order_by(ApiKey.created_at.desc())))
        return [self._serialize_api_key(record) for record in records]

    def create_api_key(self, request: ApiKeyCreateRequest) -> ApiKeyMasked:
        if request.is_active:
            self._deactivate_existing(request.service)
        encrypted = self.cipher.encrypt(
            json.dumps({"partner_id": request.partner_id, "checkword": request.checkword})
        )
        record = ApiKey(
            service=request.service,
            label=request.label,
            key_fields=encrypted,
            environment=request.environment,
            is_active=request.is_active,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return self._serialize_api_key(record)

    def update_api_key(self, api_key_id: int, request: ApiKeyUpdateRequest) -> ApiKeyMasked:
        record = self.session.get(ApiKey, api_key_id)
        if record is None:
            raise ValueError("API key not found")
        secret_fields = self._decrypt_api_key(record)
        if request.partner_id:
            secret_fields["partner_id"] = request.partner_id
        if request.checkword:
            secret_fields["checkword"] = request.checkword
        if request.label is not None:
            record.label = request.label
        if request.is_active is not None:
            record.is_active = request.is_active
            if request.is_active:
                self._deactivate_existing(record.service, exclude_id=record.id)
        record.key_fields = self.cipher.encrypt(json.dumps(secret_fields))
        self.session.commit()
        self.session.refresh(record)
        return self._serialize_api_key(record)

    def delete_api_key(self, api_key_id: int) -> None:
        record = self.session.get(ApiKey, api_key_id)
        if record is None:
            raise ValueError("API key not found")
        self.session.delete(record)
        self.session.commit()

    def get_active_api_key(self, service: str = "sf_express") -> tuple[ApiKey, dict[str, str]] | None:
        record = self.session.scalar(
            select(ApiKey).where(ApiKey.service == service, ApiKey.is_active.is_(True)).order_by(ApiKey.created_at.desc())
        )
        if record is None:
            return None
        return record, self._decrypt_api_key(record)

    def get_api_key_by_id(self, api_key_id: int) -> tuple[ApiKey, dict[str, str]]:
        record = self.session.get(ApiKey, api_key_id)
        if record is None:
            raise ValueError("API key not found")
        return record, self._decrypt_api_key(record)

    def mark_api_key_test(self, api_key_id: int, ok: bool, detail: str) -> ApiKeyMasked:
        record = self.session.get(ApiKey, api_key_id)
        if record is None:
            raise ValueError("API key not found")
        record.last_tested_at = datetime.utcnow()
        record.test_result = detail if ok else f"ERROR: {detail}"
        self.session.commit()
        self.session.refresh(record)
        return self._serialize_api_key(record)

    def _serialize_api_key(self, record: ApiKey) -> ApiKeyMasked:
        secret_fields = self._decrypt_api_key(record)
        masked_fields = {
            "partner_id": mask_secret(secret_fields.get("partner_id", "")),
            "checkword": mask_secret(secret_fields.get("checkword", "")),
        }
        return ApiKeyMasked(
            id=record.id,
            service=record.service,
            label=record.label,
            environment=record.environment,
            is_active=record.is_active,
            key_fields=masked_fields,
            last_tested_at=record.last_tested_at,
            test_result=record.test_result,
        )

    def _decrypt_api_key(self, record: ApiKey) -> dict[str, str]:
        return json.loads(self.cipher.decrypt(record.key_fields))

    def _deactivate_existing(self, service: str, exclude_id: int | None = None) -> None:
        records = list(self.session.scalars(select(ApiKey).where(ApiKey.service == service)))
        for record in records:
            if exclude_id is not None and record.id == exclude_id:
                continue
            record.is_active = False
