import asyncio
import json
import os
import subprocess
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest
import redis.asyncio as aioredis
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql import text

from app.config import settings
from app.events.log import EventLog
from app.events.runner import NegotiationRunner
from app.events.stream import ENDED, EventBus
from app.main import app
from app.negotiation.agents import RuleAgent
from app.negotiation.graph import NegotiationConfig

TEST_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://haggle:haggle@localhost:5432/haggle_test"
)
BODY = {"item": "Guitar", "budget_cap": 951, "seller_floor": 703, "opening_ask": 1288}


@pytest.fixture(scope="session", autouse=True)
def migrated() -> None:
    env = {**os.environ, "DATABASE_URL": TEST_DB}
    result = subprocess.run(
        ["alembic", "upgrade", "head"], check=False, env=env, capture_output=True, text=True
    )
    if result.returncode != 0:
        pytest.skip(f"test database unavailable: {result.stderr[-300:]}")


@pytest.fixture
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(TEST_DB)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "database_url", TEST_DB)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            yield c


def parse_sse(body: str) -> list[dict[str, str]]:
    frames = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in block.splitlines() if ": " in line and line[0] != ":"
        )
        if "event" in fields:
            frames.append(fields)
    return frames


async def test_seq_is_gapless_under_concurrency(sessions) -> None:  # type: ignore[no-untyped-def]
    log, deal = EventLog(sessions), uuid4()
    await asyncio.gather(*(log.append(deal, "x", {"n": n}) for n in range(20)))
    assert [e.seq for e in await log.read_after(deal)] == list(range(1, 21))
    assert [e.seq for e in await log.read_after(deal, 18)] == [19, 20]


@pytest.mark.parametrize(
    "sql",
    ["UPDATE deal_events SET type='hacked'", "DELETE FROM deal_events", "TRUNCATE deal_events"],
)
async def test_log_is_append_only(sessions, sql: str) -> None:  # type: ignore[no-untyped-def]
    await EventLog(sessions).append(uuid4(), "x", {})
    async with sessions() as session:
        with pytest.raises(DBAPIError, match="append-only"):
            await session.execute(text(sql))
        await session.rollback()


async def test_stream_replays_then_follows_live(sessions) -> None:  # type: ignore[no-untyped-def]
    redis = aioredis.from_url(settings.redis_url)
    bus, deal = EventBus(EventLog(sessions), redis), uuid4()
    await bus.publish(deal, "a", {})

    async def collect() -> list[str]:
        return [e.type async for e in bus.stream(deal)]

    reader = asyncio.create_task(collect())
    await asyncio.sleep(0.2)
    await bus.publish(deal, "b", {})
    await bus.publish(deal, ENDED, {})
    # Well under the poll interval, so this passes only if Redis woke the reader.
    assert await asyncio.wait_for(reader, 2) == ["a", "b", ENDED]
    await redis.aclose()


async def test_redis_down_still_stores_and_streams(sessions) -> None:  # type: ignore[no-untyped-def]
    dead = aioredis.from_url("redis://localhost:1/0")
    bus, deal = EventBus(EventLog(sessions), dead), uuid4()
    await bus.publish(deal, "a", {})
    await bus.publish(deal, ENDED, {})
    assert [e.type async for e in bus.stream(deal)] == ["a", ENDED]
    await dead.aclose()


async def test_failed_negotiation_still_ends(sessions, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def crash(*_: object) -> AsyncIterator[None]:
        raise RuntimeError("graph crashed")
        yield

    monkeypatch.setattr("app.events.runner.run_negotiation", crash)
    redis = aioredis.from_url(settings.redis_url)
    bus = EventBus(EventLog(sessions), redis)
    config = NegotiationConfig("x", 900, 700, 1000)
    deal = await NegotiationRunner(bus).start(config, RuleAgent(), RuleAgent())
    events = [e async for e in bus.stream(deal)]
    assert events[-1].type == ENDED
    assert events[-1].payload == {"status": "failed", "final_price": None}
    await redis.aclose()


async def test_api_streams_whole_negotiation_without_private_limits(client) -> None:  # type: ignore[no-untyped-def]
    started = await client.post("/negotiations", json=BODY)
    assert started.status_code == 201
    deal = started.json()["deal_id"]
    response = await client.get(f"/negotiations/{deal}/events")
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = parse_sse(response.text)
    assert frames[0]["event"] == "negotiation_started"
    assert frames[-1]["event"] == ENDED
    assert [int(f["id"]) for f in frames] == list(range(1, len(frames) + 1))
    assert any(f["event"] == "turn" for f in frames)
    payloads = [json.loads(f["data"]) for f in frames]
    assert "budget_cap" not in json.dumps(payloads) and "seller_floor" not in json.dumps(payloads)
    assert json.loads(frames[-1]["data"])["status"] == "deal"

    resumed = await client.get(
        f"/negotiations/{deal}/events", headers={"Last-Event-ID": str(len(frames) - 1)}
    )
    assert [f["event"] for f in parse_sse(resumed.text)] == [ENDED]


async def test_api_rejects_bad_requests(client) -> None:  # type: ignore[no-untyped-def]
    assert (await client.get(f"/negotiations/{uuid4()}/events")).status_code == 404
    assert (await client.post("/negotiations", json={**BODY, "opening_ask": 1})).status_code == 422
    assert (
        await client.post("/negotiations", json={**BODY, "budget_cap": 10**12})
    ).status_code == 422
