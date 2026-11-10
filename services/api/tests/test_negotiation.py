import pytest

from app.engine.lucky import NEUTRAL
from app.engine.policy import Action, Decision
from app.negotiation.agents import AgentView, Proposal, RuleAgent, Side, safe_message
from app.negotiation.graph import NegotiationConfig, TurnEvent, run_negotiation
from app.negotiation.referee import Status

CONFIG = NegotiationConfig("Guitar", budget_cap=950, seller_floor=700, opening_ask=1288)


class Scripted(RuleAgent):
    """Always proposes the same move and says the same line."""

    def __init__(self, proposal: Proposal, line: str = "hello") -> None:
        super().__init__()
        self.proposal = proposal
        self.line = line
        self.views: list[AgentView] = []

    async def propose(self, view: AgentView) -> Proposal:
        self.views.append(view)
        return self.proposal

    async def speak(self, view: AgentView, decision: Decision) -> str:
        return self.line


class Broken(RuleAgent):
    async def propose(self, view: AgentView) -> Proposal:
        raise RuntimeError("llm down")

    async def speak(self, view: AgentView, decision: Decision) -> str:
        raise RuntimeError("llm down")


async def run(config: NegotiationConfig, buyer: RuleAgent, seller: RuleAgent) -> list[TurnEvent]:
    return [e async for e in run_negotiation(config, buyer, seller)]


async def test_rule_agents_reach_a_deal_within_limits() -> None:
    events = await run(CONFIG, RuleAgent(), RuleAgent())
    last = events[-1]
    assert last.status is Status.DEAL
    assert last.final_price is not None and 700 <= last.final_price <= 950


async def test_greedy_llm_cannot_exceed_cap() -> None:
    buyer = Scripted(Proposal(action=Action.OFFER, price=1_000_000))
    seller = Scripted(Proposal(action=Action.OFFER, price=5_000_000))
    events = await run(CONFIG, buyer, seller)
    for e in events:
        if e.side is Side.BUYER and e.price is not None:
            assert e.price <= CONFIG.budget_cap


async def test_seller_cannot_sell_below_floor() -> None:
    config = NegotiationConfig(
        "Guitar", budget_cap=500, seller_floor=700, opening_ask=800, culture=NEUTRAL
    )
    buyer = Scripted(Proposal(action=Action.OFFER, price=500))
    seller = Scripted(Proposal(action=Action.ACCEPT))
    events = await run(config, buyer, seller)
    assert events[-1].final_price is None
    assert all(e.price is None or e.side is Side.BUYER or e.price >= 700 for e in events)


@pytest.mark.parametrize("rounds", [1, 2, 7])
async def test_stubborn_agents_always_end(rounds: int) -> None:
    config = NegotiationConfig(
        "Guitar", budget_cap=600, seller_floor=700, opening_ask=800, max_rounds=rounds
    )
    buyer = Scripted(Proposal(action=Action.OFFER, price=600))
    seller = Scripted(Proposal(action=Action.OFFER, price=800))
    events = await run(config, buyer, seller)
    assert len(events) <= rounds * 2
    assert events[-1].status is not Status.ONGOING


async def test_final_offer_is_the_cap_when_ask_is_beyond_it() -> None:
    config = NegotiationConfig(
        "Guitar", budget_cap=750, seller_floor=700, opening_ask=800, max_rounds=1, culture=NEUTRAL
    )
    seller = Scripted(Proposal(action=Action.WALK))
    events = await run(config, Scripted(Proposal(action=Action.OFFER, price=720)), seller)
    assert (events[-1].status, events[-1].final_price) == (Status.DEAL, 750)
    assert seller.views == []  # the LLM gets no choice on the final offer


async def test_insults_make_seller_walk() -> None:
    buyer = Scripted(Proposal(action=Action.OFFER, price=444, insulting=True))
    events = await run(CONFIG, buyer, RuleAgent())
    assert events[-1].status is Status.SELLER_WALKED
    assert events[-1].side is Side.BUYER
    assert events[-1].seller_face < 30


async def test_444_is_never_actually_offered() -> None:
    buyer = Scripted(Proposal(action=Action.OFFER, price=444))
    events = await run(CONFIG, buyer, RuleAgent())
    assert all(e.price != 444 for e in events)


async def test_private_limits_stay_private() -> None:
    buyer, seller = Scripted(Proposal(action=Action.WALK)), RuleAgent()
    await run(CONFIG, buyer, seller)
    view = buyer.views[0]
    assert view.private_limit == CONFIG.budget_cap
    assert CONFIG.seller_floor not in (view.last_other, view.last_own)


async def test_failed_llm_falls_back_and_still_finishes() -> None:
    events = await run(CONFIG, Broken(), Broken())
    assert events[-1].status is not Status.ONGOING
    assert all(e.message for e in events)


def test_banter_cannot_quote_another_price() -> None:
    decision = Decision(Action.OFFER, 888)
    assert safe_message("888 lah, boss!", decision, "MYR") == "888 lah, boss!"
    assert "888" in safe_message("Fine, 2,000!", decision, "MYR")
    assert "2,000" not in safe_message("Fine, 2,000!", decision, "MYR")


def test_config_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        NegotiationConfig("x", 100, 200, 150)
    with pytest.raises(ValueError):
        NegotiationConfig("x", 100, 50, 80, max_rounds=0)


async def test_final_move_takes_an_affordable_ask() -> None:
    config = NegotiationConfig(
        "Guitar", budget_cap=900, seller_floor=790, opening_ask=800, max_rounds=1, culture=NEUTRAL
    )
    buyer = Scripted(Proposal(action=Action.OFFER, price=780))
    events = await run(config, buyer, RuleAgent())
    assert (events[-1].status, events[-1].final_price) == (Status.DEAL, 800)
    assert events[-1].side is Side.BUYER
