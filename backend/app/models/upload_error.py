from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UploadError(Base):
    __tablename__ = "upload_errors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    upload_batch_id: Mapped[str] = mapped_column(ForeignKey("upload_batches.id"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(nullable=False)
    error_type: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[str] = mapped_column(String, nullable=False)
    raw_row_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)

    batch = relationship("UploadBatch", back_populates="errors")
