import json
import random
from dataclasses import asdict

import pytest

from app.engine.lucky import MALAYSIAN_CHINESE
from app.engine.policy import Action, Decision
from app.negotiation.agents import AgentView, Proposal, RuleAgent, Side
from app.negotiation.bidding import (
    STYLES,
    Bidder,
    BiddingConfig,
    BidTurn,
    rule_buyers,
    run_bidding_war,
)
from app.negotiation.referee import Status


class Scripted(RuleAgent):
    """Always proposes the same move."""

    def __init__(self, proposal: Proposal) -> None:
        super().__init__()
        self.proposal = proposal

    async def propose(self, view: AgentView) -> Proposal:
        return self.proposal

    async def speak(self, view: AgentView, decision: Decision) -> str:
        return "ok"


class Broken(RuleAgent):
    async def propose(self, view: AgentView) -> Proposal:
        raise RuntimeError("llm down")

    async def speak(self, view: AgentView, decision: Decision) -> str:
        raise RuntimeError("llm down")


def config(caps: list[int], floor: int = 700, ask: int = 1288, rounds: int = 6) -> BiddingConfig:
    bidders = tuple(Bidder(f"b{i}", f"Buyer {i}", cap) for i, cap in enumerate(caps))
    return BiddingConfig("Guitar", floor, ask, bidders, max_rounds=rounds)


async def run(cfg: BiddingConfig, buyers, seller=None) -> list[BidTurn]:  # type: ignore[no-untyped-def]
    return [e async for e in run_bidding_war(cfg, buyers, seller or RuleAgent())]


def winner(events: list[BidTurn]) -> dict:  # type: ignore[type-arg]
    return next(b for b in events[-1].bidders if b["state"] == "won")


async def test_a_war_ends_in_a_deal_inside_every_limit() -> None:
    rng = random.Random(3)
    for _ in range(60):
        n = rng.choice([2, 3, 4])
        floor = rng.randrange(400, 1500, 10)
        ask = int(floor * rng.uniform(1.15, 1.9))
        caps = [int(floor * rng.uniform(0.95, 1.45)) for _ in range(n)]
        cfg = config(caps, floor, ask)
        events = await run(cfg, rule_buyers(cfg))
        last = events[-1]
        assert last.status in (Status.DEAL, Status.SELLER_WALKED)
        if last.status is Status.DEAL:
            won = winner(events)
            cap = caps[int(won["id"][1:])]
            assert floor <= last.final_price <= cap  # type: ignore[operator]
            assert sum(b["state"] == "won" for b in last.bidders) == 1
            assert won["bid"] == last.final_price


async def test_budget_caps_never_enter_the_events() -> None:
    cfg = config([951, 962, 973])
    events = await run(cfg, rule_buyers(cfg))
    text = json.dumps([asdict(e) for e in events], default=str)
    assert "budget" not in text and "cap" not in text.replace("capital", "")


async def test_a_buyer_who_takes_the_ask_wins_at_once() -> None:
    cfg = config([1000, 1000], ask=900)
    agents = {"b0": Scripted(Proposal(action=Action.ACCEPT)), "b1": RuleAgent()}
    events = await run(cfg, agents)
    assert len(events) == 1
    assert events[0].status is Status.DEAL and events[0].final_price == 900
    assert events[0].winner == "b0"


async def test_a_lowballer_is_thrown_out_and_the_others_carry_on() -> None:
    cfg = config([950, 900, 1000, 990])
    events = await run(cfg, rule_buyers(cfg))  # the fourth seat is the lowballer
    thrown = [e for e in events if e.note and e.note.startswith("Thrown out")]
    assert [e.bidder for e in thrown] == ["b3"]
    assert events[-1].status is Status.DEAL
    assert winner(events)["id"] != "b3"
    # Once out, a buyer never moves again.
    after = [
        e for e in events if e.turn > thrown[0].turn and e.bidder == "b3" and e.side is Side.BUYER
    ]
    assert after == []


async def test_everyone_thrown_out_ends_the_war() -> None:
    cfg = config([950, 900])
    rude = Scripted(Proposal(action=Action.OFFER, price=1))
    events = await run(cfg, {"b0": rude, "b1": rude})
    assert events[-1].status is Status.SELLER_WALKED
    assert all(b["state"] == "thrown_out" for b in events[-1].bidders)


async def test_everyone_walking_ends_the_war() -> None:
    cfg = config([950, 900])
    quitter = Scripted(Proposal(action=Action.WALK))
    events = await run(cfg, {"b0": quitter, "b1": quitter})
    assert events[-1].status is Status.BUYER_WALKED


async def test_the_sealed_final_goes_to_the_highest_bid() -> None:
    cfg = config([800, 900], rounds=2)
    events = await run(cfg, rule_buyers(cfg, {"b0": "balanced", "b1": "balanced"}))
    last = events[-1]
    assert last.status is Status.DEAL and last.side is Side.SELLER
    assert last.winner == "b1"
    finals = {e.bidder: e.price for e in events if e.round == 2 and e.side is Side.BUYER}
    assert finals["b1"] > finals["b0"] and last.final_price == finals["b1"]


async def test_a_tie_goes_to_whoever_reached_the_price_first() -> None:
    cfg = config([900, 900], rounds=2)
    same = RuleAgent()
    events = await run(cfg, {"b0": same, "b1": RuleAgent()})
    assert events[-1].status is Status.DEAL
    assert events[-1].winner == "b0"


async def test_no_bid_reaching_the_floor_means_no_deal() -> None:
    cfg = config([600, 650], floor=700)
    events = await run(cfg, rule_buyers(cfg))
    assert events[-1].status is Status.SELLER_WALKED
    assert events[-1].final_price is None


async def test_a_failed_llm_falls_back_and_the_war_still_finishes() -> None:
    cfg = config([950, 900, 1000])
    events = await run(cfg, {b.id: Broken() for b in cfg.bidders}, Broken())
    assert events[-1].status is not Status.ONGOING


async def test_buyers_see_only_the_best_rival_bid() -> None:
    seen: list[AgentView] = []

    class Spy(RuleAgent):
        async def propose(self, view: AgentView) -> Proposal:
            seen.append(view)
            return await super().propose(view)

    cfg = config([951, 962, 973])
    await run(cfg, {b.id: Spy() for b in cfg.bidders})
    buyers = [v for v in seen if v.side is Side.BUYER]
    assert buyers and all(v.private_limit in (951, 962, 973) for v in buyers)
    assert {v.rival_count for v in buyers} <= {0, 1, 2}
    # Another buyer's limit is never in a view: only the best rival bid is.
    assert not any(v.rival_best in (951, 962, 973) for v in buyers if v.rival_best)


@pytest.mark.parametrize("last_bid", [700, 760])
async def test_rivals_make_the_seller_concede_more_slowly(last_bid: int) -> None:
    def view(rivals: int) -> AgentView:
        return AgentView(
            Side.SELLER,
            "Guitar",
            "MYR",
            MALAYSIAN_CHINESE,
            600,
            1288,
            last_bid,
            3,
            False,
            rival_count=rivals,
        )

    alone = await RuleAgent().propose(view(0))
    contested = await RuleAgent().propose(view(2))
    assert contested.price is not None and alone.price is not None
    assert contested.price > alone.price  # strictly: with rivals the seller gives up less


async def test_a_trailing_buyer_pushes_harder() -> None:
    def view(rival_best: int | None) -> AgentView:
        return AgentView(
            Side.BUYER,
            "Guitar",
            "MYR",
            MALAYSIAN_CHINESE,
            950,
            700,
            1100,
            3,
            False,
            rival_best=rival_best,
        )

    leading = await RuleAgent().propose(view(None))
    trailing = await RuleAgent().propose(view(800))
    assert trailing.price is not None and leading.price is not None
    assert trailing.price > leading.price


def test_config_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        config([900])  # a war needs rivals
    with pytest.raises(ValueError):
        config([900] * 5)
    with pytest.raises(ValueError):
        BiddingConfig(
            "x", 700, 1288, (Bidder("a", "Sam", 900), Bidder("b", "sam", 900))
        )  # same name
    with pytest.raises(ValueError):
        config([900, 900], floor=1500, ask=1000)
    with pytest.raises(ValueError):
        config([900, 0])
    assert set(STYLES) >= {"balanced", "aggressive", "patient", "lowballer"}
