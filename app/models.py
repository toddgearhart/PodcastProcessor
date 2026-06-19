from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING_AUDIO = "processing_audio"
    TRANSCRIBING = "transcribing"
    GENERATING_INTRO = "generating_intro"
    UPLOADING_SLIDES = "uploading_slides"
    CREATING_DRAFT = "creating_draft"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


ACTIVE_STATUSES = {
    JobStatus.PROCESSING_AUDIO,
    JobStatus.TRANSCRIBING,
    JobStatus.GENERATING_INTRO,
    JobStatus.UPLOADING_SLIDES,
    JobStatus.CREATING_DRAFT,
}


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.QUEUED.value)
    sermon_date: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(300))
    speaker: Mapped[str] = mapped_column(String(200), default="")
    scripture: Mapped[str] = mapped_column(String(300), default="")
    series: Mapped[str] = mapped_column(String(300), default="")
    base_filename: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    source_wav: Mapped[str] = mapped_column(Text)
    slides_json: Mapped[str] = mapped_column(Text, default="[]")
    media_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    introduction: Mapped[str] = mapped_column(Text, default="")
    mp3_url: Mapped[str] = mapped_column(Text, default="")
    transcript_url: Mapped[str] = mapped_column(Text, default="")
    wordpress_post_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wordpress_edit_url: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

