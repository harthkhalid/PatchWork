from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FeedbackVerdict(StrEnum):
    CORRECT = "correct"
    FALSE_POSITIVE = "false_positive"


class FeedbackEntry(Base):
    __tablename__ = "feedback_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_full_name: Mapped[str] = mapped_column(String(512), index=True)
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    installation_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    comment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    finding_key: Mapped[str] = mapped_column(String(256))
    category: Mapped[str] = mapped_column(String(64), default="general")
    verdict: Mapped[str] = mapped_column(String(32))
    prompt_version: Mapped[str] = mapped_column(String(32), index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PRAnalysisRun(Base):
    __tablename__ = "pr_analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_full_name: Mapped[str] = mapped_column(String(512), index=True)
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    installation_id: Mapped[int] = mapped_column(Integer, default=0)
    health_score: Mapped[float] = mapped_column(Float, default=0.0)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    prompt_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StarCounter(Base):
    __tablename__ = "star_counter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    stars: Mapped[int] = mapped_column(Integer, default=512)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
