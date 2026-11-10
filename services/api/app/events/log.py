"""Append-only deal event log. Postgres is the source of truth."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid


class Base(DeclarativeBase):
    pass


class DealEventRow(Base):
    __tablename__ = "deal_events"
    __table_args__ = (UniqueConstraint("deal_id", "seq", name="uq_deal_events_deal_seq"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    deal_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DealTermsRow(Base):
    """Private. Never streamed, because the budget cap must stay hidden from spectators."""

    __tablename__ = "deal_terms"

    deal_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    budget_cap_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)


@dataclass(frozen=True)
class StoredEvent:
    deal_id: UUID
    seq: int
    type: str
    payload: dict[str, Any]


class EventLog:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def append(self, deal_id: UUID, type_: str, payload: dict[str, Any]) -> StoredEvent:
        async with self._sessions() as session, session.begin():
            # Serializes writers per deal, so seq has no gaps or duplicates.
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": str(deal_id)},
            )
            current = await session.scalar(
                select(func.coalesce(func.max(DealEventRow.seq), 0)).where(
                    DealEventRow.deal_id == deal_id
                )
            )
            seq = int(current or 0) + 1
            session.add(DealEventRow(deal_id=deal_id, seq=seq, type=type_, payload=payload))
        return StoredEvent(deal_id, seq, type_, payload)

    async def read_after(self, deal_id: UUID, after: int = 0) -> list[StoredEvent]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(DealEventRow)
                .where(DealEventRow.deal_id == deal_id, DealEventRow.seq > after)
                .order_by(DealEventRow.seq)
            )
            return [StoredEvent(r.deal_id, r.seq, r.type, r.payload) for r in rows]

    async def latest(self, deal_id: UUID, type_: str) -> StoredEvent | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(DealEventRow)
                .where(DealEventRow.deal_id == deal_id, DealEventRow.type == type_)
                .order_by(DealEventRow.seq.desc())
                .limit(1)
            )
            return StoredEvent(row.deal_id, row.seq, row.type, row.payload) if row else None

    async def deals_with(self, type_: str) -> list[UUID]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(DealEventRow.deal_id).where(DealEventRow.type == type_).distinct()
            )
            return list(rows)

    async def save_terms(self, deal_id: UUID, budget_cap_minor: int) -> None:
        async with self._sessions() as session, session.begin():
            session.add(DealTermsRow(deal_id=deal_id, budget_cap_minor=budget_cap_minor))

    async def budget_cap(self, deal_id: UUID) -> int | None:
        async with self._sessions() as session:
            row = await session.get(DealTermsRow, deal_id)
            return row.budget_cap_minor if row else None

    @asynccontextmanager
    async def locked(self, deal_id: UUID) -> AsyncIterator[None]:
        """Held across a gateway call, so two requests cannot move one deal at once."""
        async with self._sessions() as session, session.begin():
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"shield:{deal_id}"},
            )
            yield
