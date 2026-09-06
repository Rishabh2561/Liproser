from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings

BOOTSTRAP_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProfileImport(Base):
    __tablename__ = "profile_imports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="PENDING_CONFIRMATION")
    sections: Mapped[dict[str, Any]] = mapped_column(JSON)
    confidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProviderConfiguration(Base):
    __tablename__ = "provider_configurations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    provider: Mapped[str] = mapped_column(String(24))
    model: Mapped[str] = mapped_column(String(200))
    ready: Mapped[bool] = mapped_column(default=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    import_id: Mapped[str] = mapped_column(ForeignKey("profile_imports.id"), unique=True)
    sections: Mapped[dict[str, Any]] = mapped_column(JSON)
    target_role: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(Text, default="")
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProfileAnalysis(Base):
    __tablename__ = "profile_analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id"))
    rubric_version: Mapped[str] = mapped_column(String(32), default="profile-rubric@1")
    total_score: Mapped[float] = mapped_column(Float)
    criteria: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProfileSuggestion(Base):
    __tablename__ = "profile_suggestions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    analysis_id: Mapped[str] = mapped_column(ForeignKey("profile_analyses.id"))
    section: Mapped[str] = mapped_column(String(32))
    before: Mapped[str] = mapped_column(Text)
    after: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    preserved_facts: Mapped[list[str]] = mapped_column(JSON)
    proposed_claims: Mapped[list[str]] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decided_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiBudgetPeriod(Base):
    __tablename__ = "ai_budget_periods"
    period: Mapped[str] = mapped_column(String(7), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    limit_usd: Mapped[float] = mapped_column(Float)
    actual_usd: Mapped[float] = mapped_column(Float, default=0)
    reserved_usd: Mapped[float] = mapped_column(Float, default=0)


class AiCostReservation(Base):
    __tablename__ = "ai_cost_reservations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id"), default=BOOTSTRAP_WORKSPACE_ID
    )
    period: Mapped[str] = mapped_column(ForeignKey("ai_budget_periods.period"))
    provider: Mapped[str] = mapped_column(String(24))
    estimated_usd: Mapped[float] = mapped_column(Float)
    actual_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="RESERVED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def make_engine(database_url: str | None = None):
    url = database_url or get_settings().database_url
    if url == "sqlite:///:memory:":
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url)


engine = make_engine()
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def create_schema() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        if session.get(Workspace, BOOTSTRAP_WORKSPACE_ID) is None:
            session.add(
                Workspace(
                    id=BOOTSTRAP_WORKSPACE_ID,
                    name=get_settings().bootstrap_workspace_name,
                )
            )
            session.commit()
