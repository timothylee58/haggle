"""Week 1 gate: agents agree, authorize, mark shipped, mark delivered, capture.

uv run python -m scripts.gate                  # rule agents, fake gateway, offline
uv run python -m scripts.gate --cancel         # same, but void the hold instead of capturing
uv run python -m scripts.gate --paypal [--llm] # real PayPal sandbox, needs keys in .env
"""

import argparse
import asyncio
import uuid
from collections.abc import Awaitable, Callable

from app.config import settings
from app.engine.policy import SpendGuard
from app.negotiation.agents import Agent, LLMAgent, RuleAgent
from app.negotiation.graph import NegotiationConfig, run_negotiation
from app.shield.gateway import FakeGateway, PaymentGateway, PayPalGateway
from app.shield.service import ShieldService
from app.shield.state_machine import Deal, DealState

CONFIG = NegotiationConfig(
    "Vintage Yamaha guitar", budget_cap=950, seller_floor=700, opening_ask=1288
)


async def _no_approval_needed(_: str | None) -> None:
    return None


async def run_gate(
    gateway: PaymentGateway,
    agent: Agent,
    approve: Callable[[str | None], Awaitable[None]] = _no_approval_needed,
    cancel: bool = False,
) -> Deal:
    """Runs one deal to its final state. The caps are checked again at every money call."""
    final_price: int | None = None
    async for event in run_negotiation(CONFIG, agent, agent):
        print(f"{event.turn:>2} {event.side:<6} {event.action:<6} price={event.price}")
        final_price = event.final_price if event.final_price is not None else final_price
    if final_price is None:
        raise SystemExit("GATE FAILED: the agents did not agree a price")
    if not CONFIG.seller_floor <= final_price <= CONFIG.budget_cap:
        raise SystemExit(f"GATE FAILED: {final_price} is outside both caps")
    print(f"[ok] agreed {CONFIG.currency} {final_price}")

    run = uuid.uuid4().hex[:10]
    guard = SpendGuard(cap_minor=CONFIG.budget_cap * 100, approved=True)
    service = ShieldService(gateway)
    deal = Deal(run, final_price * 100, CONFIG.currency)

    deal, approve_url = await service.create_order(deal, guard)
    print(f"[ok] order {deal.order_id}")
    await approve(approve_url)
    deal = await service.authorize(deal)
    print(f"[ok] authorized {deal.authorization_id}")

    if cancel:
        deal = await service.cancel(deal)
        print(f"[ok] voided, state={deal.state}")
        return deal

    deal = await service.ship(deal, f"GATE{run}", "OTHER")
    print(f"[ok] shipped {deal.tracking_number}")
    deal = await service.confirm_delivery(deal)
    print("[ok] delivery confirmed")
    deal = await service.capture(deal, guard)
    print(f"[ok] captured {deal.capture_id}")
    assert deal.order_id is not None
    print(f"[ok] tracking on order: {await gateway.get_shipment_tracking(deal.order_id)}")
    return deal


async def _buyer_approves(url: str | None) -> None:
    print(f"Approve as the sandbox buyer:\n  {url}")
    await asyncio.to_thread(input, "Press Enter after approving... ")


async def main(use_paypal: bool, use_llm: bool, cancel: bool) -> None:
    if use_llm and not settings.anthropic_api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY in .env")
    agent: Agent = (
        LLMAgent(settings.anthropic_api_key, settings.llm_model) if use_llm else RuleAgent()
    )
    if not use_paypal:
        deal = await run_gate(FakeGateway(), agent, cancel=cancel)
    else:
        if not settings.paypal_client_id or not settings.paypal_client_secret:
            raise SystemExit("Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env")
        gateway = PayPalGateway(settings.paypal_client_id, settings.paypal_client_secret)
        try:
            deal = await run_gate(gateway, agent, _buyer_approves, cancel)
        finally:
            await gateway.aclose()
    expected = DealState.VOIDED if cancel else DealState.CAPTURED
    if deal.state is not expected:
        raise SystemExit(f"GATE FAILED: ended in {deal.state}")
    source = "PayPal sandbox" if use_paypal else "FAKE gateway, no money API was called"
    print(f"GATE PASSED: {deal.state} ({source})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--paypal", action="store_true")
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--cancel", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.paypal, args.llm, args.cancel))
