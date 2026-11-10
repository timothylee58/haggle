import json

import httpx

from app.config import PAYPAL_SANDBOX_URL
from app.negotiation.agents import RuleAgent
from app.negotiation.graph import NegotiationConfig, run_negotiation
from app.shield.gateway import FakeGateway, PayPalGateway
from app.shield.state_machine import DealState
from scripts.gate import run_gate


async def test_gate_captures_and_reads_tracking_back() -> None:
    gateway = FakeGateway()
    deal = await run_gate(gateway, RuleAgent())
    assert deal.state is DealState.CAPTURED
    assert gateway.calls == ["create_order", "authorize", "capture", "tracking"]
    assert deal.order_id is not None
    assert await gateway.get_shipment_tracking(deal.order_id) == [deal.tracking_number]


async def test_gate_cancel_voids_without_capturing() -> None:
    gateway = FakeGateway()
    deal = await run_gate(gateway, RuleAgent(), cancel=True)
    assert deal.state is DealState.VOIDED
    assert gateway.calls == ["create_order", "authorize", "void"]


async def test_rule_agents_replay_the_same_negotiation() -> None:
    config = NegotiationConfig("Guitar", budget_cap=950, seller_floor=700, opening_ask=1288)
    first = [event async for event in run_negotiation(config, RuleAgent(), RuleAgent())]
    second = [event async for event in run_negotiation(config, RuleAgent(), RuleAgent())]
    assert first == second


async def test_paypal_tracking_read_uses_the_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "token"})
        assert request.url.path == "/v2/checkout/orders/ORDER-1"
        body = {"purchase_units": [{"shipping": {"trackers": [{"id": "CAP-1-TRACK"}]}}]}
        return httpx.Response(200, content=json.dumps(body))

    assert PAYPAL_SANDBOX_URL
    gateway = PayPalGateway("id", "secret", transport=httpx.MockTransport(handler))
    assert await gateway.get_shipment_tracking("ORDER-1") == ["CAP-1-TRACK"]
    await gateway.aclose()
