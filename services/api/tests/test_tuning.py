"""Measures rule-agent negotiations across scenarios, not just one demo match."""

import pytest

from app.engine.lucky import MALAYSIAN_CHINESE, NEUTRAL
from app.negotiation.agents import RuleAgent
from app.negotiation.graph import NegotiationConfig, TurnEvent, run_negotiation
from app.negotiation.referee import Status

SCENARIOS = [
    (cap, floor, ask, rounds, culture)
    for cap, floor, ask in [
        (950, 700, 1288),
        (120, 80, 200),
        (5200, 4000, 6800),
        (888, 880, 900),
        (30, 12, 58),
    ]
    for rounds in (3, 6, 10)
    for culture in (MALAYSIAN_CHINESE, NEUTRAL)
]


async def play(cap: int, floor: int, ask: int, rounds: int, culture) -> list[TurnEvent]:  # type: ignore[no-untyped-def]
    config = NegotiationConfig("x", cap, floor, ask, culture=culture, max_rounds=rounds)
    return [e async for e in run_negotiation(config, RuleAgent(), RuleAgent())]


@pytest.mark.parametrize("cap,floor,ask,rounds,culture", SCENARIOS)
async def test_overlap_always_deals_within_limits(cap, floor, ask, rounds, culture) -> None:  # type: ignore[no-untyped-def]
    last = (await play(cap, floor, ask, rounds, culture))[-1]
    assert last.status is Status.DEAL
    assert floor <= last.final_price <= cap


@pytest.mark.parametrize("cap,floor,ask,rounds,culture", SCENARIOS)
async def test_gap_keeps_closing_until_someone_hits_a_limit(
    cap, floor, ask, rounds, culture
) -> None:  # type: ignore[no-untyped-def]
    events = await play(cap, floor, ask, rounds, culture)
    offers = [e for e in events if e.action == "offer"]
    gaps = [e.gap for e in offers if e.gap is not None]
    assert gaps == sorted(gaps, reverse=True)
    for earlier, later in zip(offers, offers[2:], strict=False):
        if later.side == "buyer" and earlier.price < cap:
            assert later.price > earlier.price
        if later.side == "seller" and earlier.price > floor:
            assert later.price < earlier.price


@pytest.mark.parametrize("cap,floor,ask,rounds,culture", SCENARIOS)
async def test_face_does_not_saturate(cap, floor, ask, rounds, culture) -> None:  # type: ignore[no-untyped-def]
    last = (await play(cap, floor, ask, rounds, culture))[-1]
    assert last.buyer_face < 100 and last.seller_face < 100


async def test_no_overlap_never_deals() -> None:
    last = (await play(600, 700, 800, 6, NEUTRAL))[-1]
    assert last.status is not Status.DEAL and last.final_price is None


async def test_buyer_bargains_rather_than_paying_the_cap() -> None:
    positions = []
    at_cap = 0
    for cap, floor, ask, rounds, culture in SCENARIOS:
        price = (await play(cap, floor, ask, rounds, culture))[-1].final_price
        positions.append((price - floor) / (cap - floor))
        at_cap += price == cap
    assert at_cap <= len(SCENARIOS) // 3
    assert sum(positions) / len(positions) <= 0.6
