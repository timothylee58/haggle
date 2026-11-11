import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.events.log import EventLog
from app.events.stream import ENDED, EventBus
from app.main import app
from app.shield.desk import DealDesk, DeskError
from app.shield.gateway import FakeGateway, GatewayError
from app.shield.service import ShieldService
from tests.test_events import BODY, TEST_DB, migrated, parse_sse  # noqa: F401


class Harness:
    def __init__(self, bus: EventBus, gateway: FakeGateway, desk: DealDesk) -> None:
        self.bus, self.gateway, self.desk = bus, gateway, desk
        self.now = datetime(2026, 1, 1, tzinfo=UTC)

    async def deal(self, price: int = 888, cap: int = 950, status: str = "deal"):  # type: ignore[no-untyped-def]
        deal_id = uuid4()
        await self.bus.log.save_terms(deal_id, cap * 100)
        await self.bus.publish(deal_id, "negotiation_started", {"currency": "MYR"})
        await self.bus.publish(deal_id, ENDED, {"status": status, "final_price": price})
        return deal_id


@pytest.fixture
async def h() -> AsyncIterator[Harness]:
    engine = create_async_engine(TEST_DB)
    redis = aioredis.from_url(settings.redis_url)
    bus = EventBus(EventLog(async_sessionmaker(engine, expire_on_commit=False)), redis)
    gateway = FakeGateway()
    harness: Harness
    service = ShieldService(gateway, clock=lambda: harness.now)
    harness = Harness(bus, gateway, DealDesk(bus, gateway, "simulated", service=service))
    yield harness
    await redis.aclose()
    await engine.dispose()


async def test_buyer_returns_to_the_deal_page_after_paypal(h: Harness) -> None:
    deal = await h.deal()
    await h.desk.run(deal, "approve")
    assert h.gateway.return_urls == [f"{settings.frontend_url}/deals/{deal}"]


async def test_repeated_approve_logs_once_and_makes_one_order(h: Harness) -> None:
    deal = await h.deal()
    await asyncio.gather(*(h.desk.run(deal, "approve") for _ in range(3)))
    steps = [e.payload["step"] for e in await h.bus.log.read_after(deal) if e.type == "shield"]
    assert steps == ["approve"]
    assert h.gateway.calls.count("create_order") == 1
    # Asking again later is still fine and still changes nothing.
    assert (await h.desk.run(deal, "approve"))["state"] == "negotiated"


async def test_state_view_reports_the_last_step_taken(h: Harness) -> None:
    deal = await h.deal()
    assert (await h.desk.view(deal))["step"] == "negotiated"
    await h.desk.run(deal, "approve")
    await h.desk.run(deal, "authorize")
    assert (await h.desk.view(deal))["step"] == "authorize"


async def test_full_flow_survives_reload_from_log(h: Harness) -> None:
    deal = await h.deal()
    assert (await h.desk.run(deal, "approve"))["state"] == "negotiated"
    assert (await h.desk.run(deal, "authorize"))["state"] == "authorized"
    await h.desk.run(deal, "ship", tracking_number="TRK1", carrier="POSLAJU")
    # A new desk has no memory, so this proves state really comes from the log.
    fresh = DealDesk(
        h.bus,
        h.gateway,
        "simulated",
        service=ShieldService(h.gateway, clock=lambda: h.now),
    )
    result = await fresh.run(deal, "deliver")
    assert result["state"] == "captured"
    assert result["amount_minor"] == 88_800
    assert (await fresh.run(deal, "refund"))["state"] == "refunded"
    assert h.gateway.calls.count("capture") == 1


async def test_no_shield_without_a_deal(h: Harness) -> None:
    deal = await h.deal(status="no_deal")
    with pytest.raises(DeskError) as caught:
        await h.desk.run(deal, "approve")
    assert caught.value.status == 409
    with pytest.raises(DeskError) as caught:
        await h.desk.run(uuid4(), "approve")
    assert caught.value.status == 404


async def test_cap_rechecked_against_logged_price(h: Harness) -> None:
    deal = await h.deal(price=1000, cap=950)
    with pytest.raises(DeskError) as caught:
        await h.desk.run(deal, "approve")
    assert caught.value.status == 403
    assert h.gateway.calls == []


async def test_no_capture_before_delivery(h: Harness) -> None:
    deal = await h.deal()
    await h.desk.run(deal, "approve")
    await h.desk.run(deal, "authorize")
    with pytest.raises(DeskError) as caught:
        await h.desk.run(deal, "capture")
    assert caught.value.status == 409
    assert "capture" not in h.gateway.calls


async def test_failed_capture_keeps_delivery_and_can_retry(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    deal = await h.deal()
    await h.desk.run(deal, "approve")
    await h.desk.run(deal, "authorize")
    await h.desk.run(deal, "ship", tracking_number="T", carrier="X")
    original = h.gateway.capture

    async def fail(*_: object, **__: object) -> str:
        raise GatewayError("down")

    monkeypatch.setattr(h.gateway, "capture", fail)
    with pytest.raises(DeskError) as caught:
        await h.desk.run(deal, "deliver")
    assert caught.value.status == 502
    assert (await h.desk.view(deal))["state"] == "delivered"
    monkeypatch.setattr(h.gateway, "capture", original)
    assert (await h.desk.run(deal, "capture"))["state"] == "captured"


async def test_concurrent_requests_move_money_once(h: Harness) -> None:
    deal = await h.deal()
    await h.desk.run(deal, "approve")
    await h.desk.run(deal, "authorize")
    await h.desk.run(deal, "ship", tracking_number="T", carrier="X")
    results = await asyncio.gather(
        *(h.desk.run(deal, "deliver") for _ in range(5)), return_exceptions=True
    )
    assert sum(isinstance(r, dict) for r in results) == 1
    assert h.gateway.calls.count("capture") == 1


async def test_sweep_voids_only_overdue_holds(h: Harness) -> None:
    deal = await h.deal()
    await h.desk.run(deal, "approve")
    await h.desk.run(deal, "authorize")
    await h.desk.sweep()
    assert (await h.desk.view(deal))["state"] == "authorized"
    h.now += timedelta(days=4)
    await h.desk.sweep()
    assert (await h.desk.view(deal))["state"] == "voided"
    assert "void" in h.gateway.calls


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "database_url", TEST_DB)
    monkeypatch.setattr(settings, "paypal_client_id", "")
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            yield c


async def test_api_flow_and_public_stream_hides_private_data(client: httpx.AsyncClient) -> None:
    deal = (await client.post("/negotiations", json=BODY)).json()["deal_id"]
    await client.get(f"/negotiations/{deal}/events")  # waits for the negotiation to end
    base = f"/deals/{deal}/shield"
    assert (await client.post(f"{base}/capture")).status_code == 409
    assert (await client.post(f"{base}/approve")).status_code == 200
    assert (await client.post(f"{base}/authorize")).status_code == 200
    assert (await client.post(f"{base}/ship", json={"tracking_number": ""})).status_code == 422
    assert (await client.post(f"{base}/ship", json={"tracking_number": "TRK"})).status_code == 200
    assert (await client.post(f"{base}/deliver")).json()["state"] == "captured"
    assert (await client.post(f"{base}/refund")).json()["state"] == "refunded"

    response = await client.get(f"{base}/events")
    frames = parse_sse(response.text)
    states = [json.loads(f["data"])["state"] for f in frames]
    assert states[-1] == "refunded" and "authorized" in states
    for secret in ("budget", "order_id", "authorization_id", "capture_id", "approve", "951"):
        assert secret not in "".join(f["data"] for f in frames).replace('"step": "approve"', "")
    assert "951" not in (await client.get(base)).text


async def test_api_rejects_unknown_deal(client: httpx.AsyncClient) -> None:
    assert (await client.post(f"/deals/{uuid4()}/shield/approve")).status_code == 404
    assert (await client.get(f"/deals/{uuid4()}/shield/events")).status_code == 404
