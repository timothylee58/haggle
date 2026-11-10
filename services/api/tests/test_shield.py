import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

from app.config import PAYPAL_SANDBOX_URL, Settings
from app.engine.policy import GuardrailViolation, SpendGuard
from app.shield.gateway import FakeGateway, GatewayError, PayPalGateway, to_decimal_string
from app.shield.service import ShieldService
from app.shield.state_machine import Deal, DealEvent, DealState, InvalidTransition, transition

T0 = datetime(2026, 1, 1, tzinfo=UTC)
GUARD = SpendGuard(cap_minor=100_000, approved=True)


class Clock:
    now = T0

    def __call__(self) -> datetime:
        return self.now


def make() -> tuple[ShieldService, FakeGateway, Clock]:
    gateway, clock = FakeGateway(), Clock()
    return ShieldService(gateway, clock=clock), gateway, clock


async def authorized(service: ShieldService) -> Deal:
    deal, _ = await service.create_order(Deal("d1", 88_800, "MYR"), GUARD)
    return await service.authorize(deal)


async def test_happy_path_then_refund() -> None:
    service, gateway, _ = make()
    deal = await service.ship(await authorized(service), "TRK1", "POSLAJU")
    deal = await service.confirm_delivery(deal)
    deal = await service.capture(deal, GUARD)
    assert deal.state is DealState.CAPTURED
    assert "tracking" in gateway.calls
    assert (await service.refund(deal)).state is DealState.REFUNDED


async def test_no_capture_before_delivery_and_no_gateway_call() -> None:
    service, gateway, _ = make()
    deal = await service.ship(await authorized(service), "TRK1", "POSLAJU")
    with pytest.raises(InvalidTransition):
        await service.capture(deal, GUARD)
    assert "capture" not in gateway.calls


def test_ship_requires_tracking() -> None:
    deal = Deal("d", 1, "MYR", state=DealState.AUTHORIZED, authorized_at=T0)
    with pytest.raises(InvalidTransition):
        transition(deal, DealEvent.SHIP, T0, tracking_number="  ")


@pytest.mark.parametrize("state", [DealState.DELIVERED, DealState.CAPTURED, DealState.VOIDED])
def test_cancel_refused_late(state: DealState) -> None:
    with pytest.raises(InvalidTransition):
        transition(Deal("d", 1, "MYR", state=state), DealEvent.CANCEL, T0)


async def test_missed_ship_deadline_voids() -> None:
    service, gateway, clock = make()
    deal = await authorized(service)
    assert (await service.expire_if_overdue(deal)).state is DealState.AUTHORIZED
    clock.now = T0 + timedelta(days=4)
    with pytest.raises(InvalidTransition):
        await service.ship(deal, "TRK", "POSLAJU")
    assert (await service.expire_if_overdue(deal)).state is DealState.VOIDED
    assert "void" in gateway.calls


async def test_missed_delivery_deadline_voids() -> None:
    service, _, clock = make()
    deal = await service.ship(await authorized(service), "TRK", "POSLAJU")
    clock.now = T0 + timedelta(days=15)
    with pytest.raises(InvalidTransition):
        await service.confirm_delivery(deal)
    assert (await service.expire_if_overdue(deal)).state is DealState.VOIDED


async def test_failed_tracking_push_does_not_lose_capture() -> None:
    service, gateway, _ = make()
    gateway.fail_tracking = True
    deal = await service.ship(await authorized(service), "TRK", "POSLAJU")
    deal = await service.capture(await service.confirm_delivery(deal), GUARD)
    assert deal.state is DealState.CAPTURED and deal.capture_id


async def test_gateway_rechecks_guard() -> None:
    service, gateway, _ = make()
    with pytest.raises(GuardrailViolation):
        await service.create_order(Deal("d", 200_000, "MYR"), GUARD)
    with pytest.raises(GuardrailViolation):
        await service.create_order(Deal("d", 100, "MYR"), SpendGuard(cap_minor=1000))
    assert gateway.calls == []


def test_live_mode_cannot_be_configured() -> None:
    with pytest.raises(ValidationError):
        Settings(paypal_env="live")  # type: ignore[arg-type]
    assert "sandbox" in PAYPAL_SANDBOX_URL


def test_decimal_string() -> None:
    assert to_decimal_string(88_800) == "888.00"
    assert to_decimal_string(5) == "0.05"


async def test_paypal_requests_are_correct() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "tok"})
        if path == "/v2/checkout/orders":
            links = [{"rel": "payer-action", "href": "https://approve"}]
            return httpx.Response(201, json={"id": "O1", "links": links})
        if path.endswith("/O1/authorize"):
            auth = {"authorizations": [{"id": "A1"}]}
            return httpx.Response(201, json={"purchase_units": [{"payments": auth}]})
        if path.endswith("/A1/capture"):
            return httpx.Response(201, json={"id": "C1"})
        if path.endswith("/A1/void"):
            return httpx.Response(204)
        return httpx.Response(422, text="nope")

    gateway = PayPalGateway("id", "secret", transport=httpx.MockTransport(handler))
    order = await gateway.create_order(88_800, "MYR", GUARD, "k1")
    assert (order.order_id, order.approve_url) == ("O1", "https://approve")
    body = json.loads(seen[1].content)
    assert body["intent"] == "AUTHORIZE"
    assert body["purchase_units"][0]["amount"] == {"currency_code": "MYR", "value": "888.00"}
    experience = body["payment_source"]["paypal"]["experience_context"]
    assert experience["return_url"] == experience["cancel_url"] == "http://localhost:3000/"
    assert seen[1].headers["PayPal-Request-Id"] == "k1"
    assert seen[1].url.host == "api-m.sandbox.paypal.com"
    assert await gateway.authorize_order("O1", "k2") == "A1"
    assert await gateway.capture("A1", 88_800, "MYR", GUARD, "k3") == "C1"
    await gateway.void("A1", "k4")
    with pytest.raises(GatewayError):
        await gateway.refund("C1", "k5")
    with pytest.raises(GuardrailViolation):
        await gateway.capture("A1", 999_999, "MYR", GUARD, "k6")
    await gateway.aclose()
