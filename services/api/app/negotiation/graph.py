"""LangGraph loop: buyer -> referee -> seller -> referee, ending in bounded rounds."""

import logging
import operator
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from app.engine.face import STARTING_FACE
from app.engine.lucky import MALAYSIAN_CHINESE, Culture
from app.engine.policy import Action, Decision, Intent, decide_buyer, decide_seller
from app.negotiation.agents import (
    Agent,
    AgentView,
    Proposal,
    RuleAgent,
    Side,
    safe_message,
    template_line,
)
from app.negotiation.referee import Status, apply_face, face_events, judge

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NegotiationConfig:
    item: str
    budget_cap: int
    seller_floor: int
    opening_ask: int
    currency: str = "MYR"
    culture: Culture = MALAYSIAN_CHINESE
    max_rounds: int = 6

    def __post_init__(self) -> None:
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")
        if min(self.budget_cap, self.seller_floor, self.opening_ask) <= 0:
            raise ValueError("prices must be positive")
        if self.opening_ask < self.seller_floor:
            raise ValueError("opening_ask cannot be below seller_floor")


@dataclass(frozen=True)
class TurnEvent:
    turn: int
    side: Side
    action: Action
    price: int | None
    requested_price: int | None
    overridden: bool
    message: str
    last_bid: int | None
    last_ask: int | None
    gap: int | None
    buyer_face: int
    seller_face: int
    status: Status
    final_price: int | None


@dataclass(frozen=True)
class PendingMove:
    side: Side
    decision: Decision
    requested: int | None
    insulting: bool
    message: str


class State(TypedDict):
    turn: int
    round: int
    last_bid: int | None
    last_ask: int | None
    buyer_face: int
    seller_face: int
    status: Status
    final_price: int | None
    pending: PendingMove | None
    transcript: Annotated[list[str], operator.add]
    event: TurnEvent | None


def initial_state(config: NegotiationConfig) -> State:
    return {
        "turn": 0,
        "round": 1,
        "last_bid": None,
        "last_ask": config.opening_ask,
        "buyer_face": STARTING_FACE,
        "seller_face": STARTING_FACE,
        "status": Status.ONGOING,
        "final_price": None,
        "pending": None,
        "transcript": [],
        "event": None,
    }


def build_graph(config: NegotiationConfig, buyer: Agent, seller: Agent):  # type: ignore[no-untyped-def]
    fallback = RuleAgent()

    async def propose(agent: Agent, view: AgentView) -> Proposal:
        try:
            return await agent.propose(view)
        except Exception:
            logger.exception("%s proposal failed; using rule agent", view.side)
            return await fallback.propose(view)

    async def speak(agent: Agent, view: AgentView, decision: Decision) -> str:
        try:
            return safe_message(await agent.speak(view, decision), decision, view.currency)
        except Exception:
            logger.exception("%s banter failed; using template", view.side)
            return template_line(decision, view.currency)

    def view_for(state: State, side: Side) -> AgentView:
        is_buyer = side is Side.BUYER
        return AgentView(
            side=side,
            item=config.item,
            currency=config.currency,
            culture=config.culture,
            private_limit=config.budget_cap if is_buyer else config.seller_floor,
            last_own=state["last_bid"] if is_buyer else state["last_ask"],
            last_other=state["last_ask"] if is_buyer else state["last_bid"],
            turn=state["turn"] + 1,
            is_final=state["round"] >= config.max_rounds,
            transcript=tuple(state["transcript"]),
        )

    async def buyer_node(state: State) -> dict[str, PendingMove]:
        view = view_for(state, Side.BUYER)
        proposal = await propose(buyer, view)
        intent = Intent(proposal.action, proposal.price)

        def decide(i: Intent) -> Decision:
            return decide_buyer(
                i, config.budget_cap, config.culture, view.last_own, view.last_other
            )

        decision = decide(intent)
        if view.is_final and decision.action is Action.OFFER and decision.price is not None:
            # The forced final move: take an affordable ask, otherwise offer the full cap.
            # So any overlap between cap and floor ends in a deal unless someone walks.
            ask = view.last_other
            if ask is not None and ask <= config.budget_cap:
                decision = Decision(Action.ACCEPT, ask, True)
            else:
                forced = decide(Intent(Action.OFFER, config.budget_cap))
                decision = Decision(forced.action, forced.price, True)
        message = await speak(buyer, view, decision)
        move = PendingMove(Side.BUYER, decision, proposal.price, proposal.insulting, message)
        return {"pending": move}

    async def seller_node(state: State) -> dict[str, PendingMove]:
        view = view_for(state, Side.SELLER)
        if view.is_final:
            # The final offer is take-it-or-leave-it, and the LLM does not get a choice.
            bid = view.last_other
            acceptable = bid is not None and bid >= config.seller_floor
            proposal = Proposal(action=Action.ACCEPT if acceptable else Action.WALK)
            decision = Decision(proposal.action, bid if acceptable else None, True)
        else:
            proposal = await propose(seller, view)
            decision = decide_seller(
                Intent(proposal.action, proposal.price),
                config.seller_floor,
                config.culture,
                view.last_own,
                view.last_other,
            )
        message = await speak(seller, view, decision)
        move = PendingMove(Side.SELLER, decision, proposal.price, proposal.insulting, message)
        return {"pending": move}

    def referee_node(state: State) -> dict[str, object]:
        move = state["pending"]
        assert move is not None
        is_buyer = move.side is Side.BUYER
        last_own = state["last_bid"] if is_buyer else state["last_ask"]
        last_other = state["last_ask"] if is_buyer else state["last_bid"]
        events = face_events(
            move.requested,
            move.insulting,
            move.decision,
            last_own,
            last_other,
            config.culture,
            is_buyer,
        )
        # A buyer's behaviour moves the seller's face, and the reverse.
        seller_face = apply_face(state["seller_face"], events) if is_buyer else state["seller_face"]
        buyer_face = state["buyer_face"] if is_buyer else apply_face(state["buyer_face"], events)

        last_bid, last_ask = state["last_bid"], state["last_ask"]
        if move.decision.action is Action.OFFER:
            if is_buyer:
                last_bid = move.decision.price
            else:
                last_ask = move.decision.price

        final_round = state["round"] >= config.max_rounds
        outcome = judge(move.decision, is_buyer, seller_face, final_round)
        turn = state["turn"] + 1
        gap = last_ask - last_bid if last_ask is not None and last_bid is not None else None
        event = TurnEvent(
            turn=turn,
            side=move.side,
            action=move.decision.action,
            price=move.decision.price,
            requested_price=move.requested,
            overridden=move.decision.overridden,
            message=move.message,
            last_bid=last_bid,
            last_ask=last_ask,
            gap=gap,
            buyer_face=buyer_face,
            seller_face=seller_face,
            status=outcome.status,
            final_price=outcome.final_price,
        )
        return {
            "turn": turn,
            "round": state["round"] + (0 if is_buyer else 1),
            "last_bid": last_bid,
            "last_ask": last_ask,
            "buyer_face": buyer_face,
            "seller_face": seller_face,
            "status": outcome.status,
            "final_price": outcome.final_price,
            "pending": None,
            "transcript": [f"{move.side}: {move.message}"],
            "event": event,
        }

    def route(state: State) -> str:
        if state["status"] is not Status.ONGOING:
            return END
        return "seller" if state["turn"] % 2 == 1 else "buyer"

    graph = StateGraph(State)
    graph.add_node("buyer", buyer_node)
    graph.add_node("seller", seller_node)
    graph.add_node("referee", referee_node)
    graph.add_edge(START, "buyer")
    graph.add_edge("buyer", "referee")
    graph.add_edge("seller", "referee")
    graph.add_conditional_edges("referee", route, ["buyer", "seller", END])
    return graph.compile()


async def run_negotiation(
    config: NegotiationConfig, buyer: Agent, seller: Agent
) -> AsyncIterator[TurnEvent]:
    """Yields one event per turn, ready to stream to spectators."""
    graph = build_graph(config, buyer, seller)
    limit = config.max_rounds * 8 + 10
    async for update in graph.astream(
        initial_state(config), {"recursion_limit": limit}, stream_mode="updates"
    ):
        referee = update.get("referee")
        if referee is not None:
            yield referee["event"]
