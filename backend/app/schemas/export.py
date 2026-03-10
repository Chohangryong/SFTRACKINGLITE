from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExportPreset(BaseModel):
    id: str
    name: str
    export_type: str
    columns: list[str]
    is_default: bool = False


class ExportPresetCreateRequest(BaseModel):
    name: str
    export_type: str
    columns: list[str]


class ExportDownloadRequest(BaseModel):
    export_type: str = Field(pattern="^(summary|event)$")
    preset_id: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    file_format: str = Field(default="xlsx", pattern="^(xlsx|csv)$")
