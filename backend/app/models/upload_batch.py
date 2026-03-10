from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    total_rows: Mapped[int] = mapped_column(nullable=False, default=0)
    success_rows: Mapped[int] = mapped_column(nullable=False, default=0)
    skipped_rows: Mapped[int] = mapped_column(nullable=False, default=0)
    error_rows: Mapped[int] = mapped_column(nullable=False, default=0)
    parsed_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    column_mapping: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    errors = relationship("UploadError", back_populates="batch", cascade="all, delete-orphan")
