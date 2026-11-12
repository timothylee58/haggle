"""Bidding war: one seller haggles with several buyers at once.

The rules, all enforced in code:

- One public ask. Each buyer has their own bid, face, patience and private budget cap.
- A round: every active buyer moves in turn (bid, walk, or take the ask and win on the spot),
  then the seller answers the leading bid once.
- Rivals matter. A trailing buyer pushes harder and a seller with rivals concedes more slowly
  (see RuleAgent). Buyers see only the best rival bid, never a rival's budget.
- Face is per pair. A buyer who insults or lowballs the seller loses the seller's patience and is
  thrown out, while the others carry on.
- The last round is sealed: each buyer makes a forced final bid, and the highest bid at or above the
  floor wins. Ties go to the buyer who held the higher bid going into that round, then to whoever
  reached the price first.
"""

import logging
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.engine import face
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
from app.negotiation.referee import Status, apply_face, face_events

logger = logging.getLogger(__name__)

MIN_BIDDERS, MAX_BIDDERS = 2, 4


@dataclass(frozen=True)
class Bidder:
    id: str
    name: str
    budget_cap: int


@dataclass(frozen=True)
class BiddingConfig:
    item: str
    seller_floor: int
    opening_ask: int
    bidders: tuple[Bidder, ...]
    currency: str = "MYR"
    culture: Culture = MALAYSIAN_CHINESE
    max_rounds: int = 6

    def __post_init__(self) -> None:
        if not MIN_BIDDERS <= len(self.bidders) <= MAX_BIDDERS:
            raise ValueError(f"a bidding war needs {MIN_BIDDERS} to {MAX_BIDDERS} buyers")
        if len({b.id for b in self.bidders}) != len(self.bidders):
            raise ValueError("bidder ids must be unique")
        if len({b.name.strip().lower() for b in self.bidders}) != len(self.bidders):
            raise ValueError("bidder names must be unique")
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")
        if min(self.seller_floor, self.opening_ask, *(b.budget_cap for b in self.bidders)) <= 0:
            raise ValueError("prices must be positive")
        if self.opening_ask < self.seller_floor:
            raise ValueError("opening_ask cannot be below seller_floor")


@dataclass(frozen=True)
class BidTurn:
    """One move in the war. The first fields match the two-party TurnEvent, so older views still read it."""

    turn: int
    round: int
    side: Side
    action: Action
    price: int | None
    requested_price: int | None
    overridden: bool
    message: str
    last_bid: int | None  # the leading bid
    last_ask: int
    gap: int | None
    buyer_face: int  # the moving buyer's face (the leader's, on a seller turn)
    seller_face: int  # the seller's patience with that buyer
    status: Status
    final_price: int | None
    bidder: str  # who moved, or on a seller turn, the leader being answered
    bidder_name: str
    bidders: list[dict[str, Any]]  # the whole board after this move; never includes budget caps
    note: str | None = None
    winner: str | None = None


@dataclass
class _Seat:
    bidder: Bidder
    bid: int | None = None
    bid_turn: int = 0  # the turn the current bid was placed, for tie-breaks
    carried: int = 0  # the bid held going into the sealed final round; breaks final-round ties
    face: int = STARTING_FACE
    patience: int = STARTING_FACE
    state: str = "bidding"  # bidding | walked | thrown_out | won
    final_bid: bool = False


@dataclass
class _War:
    ask: int
    seats: dict[str, _Seat]
    turn: int = 0
    round: int = 1
    transcript: list[str] = field(default_factory=list)

    def active(self) -> list[_Seat]:
        return [s for s in self.seats.values() if s.state == "bidding"]

    def leader(self) -> _Seat | None:
        bidding = [s for s in self.active() if s.bid is not None]
        # Highest bid wins. A tie goes to the buyer who held the higher bid going into the sealed
        # final round (before then everyone's is 0), then to whoever reached the price first.
        return max(bidding, key=lambda s: (s.bid or 0, s.carried, -s.bid_turn), default=None)

    def top_bid(self) -> int | None:
        """The best live bid for display. Unlike leader(), it still counts a buyer who just won."""
        live = [
            s.bid
            for s in self.seats.values()
            if s.state in ("bidding", "won") and s.bid is not None
        ]
        return max(live, default=None)

    def board(self) -> list[dict[str, Any]]:
        return [
            {
                "id": s.bidder.id,
                "name": s.bidder.name,
                "bid": s.bid,
                "face": s.face,
                "patience": s.patience,
                "state": s.state,
            }
            for s in self.seats.values()
        ]


async def run_bidding_war(
    config: BiddingConfig,
    buyers: Mapping[str, Agent] | Agent,
    seller: Agent,
) -> AsyncIterator[BidTurn]:
    """Yields one event per move, ready to stream to spectators."""
    fallback = RuleAgent()
    agents: dict[str, Agent] = (
        dict(buyers) if isinstance(buyers, Mapping) else {b.id: buyers for b in config.bidders}
    )
    war = _War(config.opening_ask, {b.id: _Seat(b) for b in config.bidders})

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

    def buyer_view(seat: _Seat, final: bool, rnd: int) -> AgentView:
        rivals = [s for s in war.active() if s is not seat and s.bid is not None]
        return AgentView(
            side=Side.BUYER,
            item=config.item,
            currency=config.currency,
            culture=config.culture,
            private_limit=seat.bidder.budget_cap,
            last_own=seat.bid,
            last_other=war.ask,
            turn=war.turn + 1,
            is_final=final,
            transcript=tuple(war.transcript),
            rival_count=len(rivals),
            rival_best=max((s.bid or 0 for s in rivals), default=None),
        )

    def seller_view(leader: _Seat, final: bool) -> AgentView:
        others = [s for s in war.active() if s is not leader and s.bid is not None]
        return AgentView(
            side=Side.SELLER,
            item=config.item,
            currency=config.currency,
            culture=config.culture,
            private_limit=config.seller_floor,
            last_own=war.ask,
            last_other=leader.bid,
            turn=war.turn + 1,
            is_final=final,
            transcript=tuple(war.transcript),
            rival_count=len(others),
            rival_best=max((s.bid or 0 for s in others), default=None),
        )

    def event(
        side: Side,
        seat: _Seat,
        decision: Decision,
        requested: int | None,
        message: str,
        status: Status,
        final_price: int | None,
        note: str | None = None,
        winner: Bidder | None = None,
    ) -> BidTurn:
        war.turn += 1
        war.transcript.append(f"{seat.bidder.name if side is Side.BUYER else 'seller'}: {message}")
        top = war.top_bid()
        return BidTurn(
            turn=war.turn,
            round=war.round,
            side=side,
            action=decision.action,
            price=decision.price,
            requested_price=requested,
            overridden=decision.overridden,
            message=message,
            last_bid=top,
            last_ask=war.ask,
            gap=war.ask - top if top is not None else None,
            buyer_face=seat.face,
            seller_face=seat.patience,
            status=status,
            final_price=final_price,
            bidder=seat.bidder.id,
            bidder_name=seat.bidder.name,
            bidders=war.board(),
            note=note,
            winner=winner.id if winner else None,
        )

    def end_without_deal() -> Status:
        thrown = any(s.state == "thrown_out" for s in war.seats.values())
        return Status.SELLER_WALKED if thrown else Status.BUYER_WALKED

    for rnd in range(1, config.max_rounds + 1):
        final = rnd == config.max_rounds
        war.round = rnd
        if final:
            for seat in war.active():
                seat.carried = seat.bid or 0

        for seat in list(war.active()):
            view = buyer_view(seat, final, rnd)
            agent = agents[seat.bidder.id]
            proposal = await propose(agent, view)
            cap = seat.bidder.budget_cap
            decision = decide_buyer(
                Intent(proposal.action, proposal.price), cap, config.culture, seat.bid, war.ask
            )
            if final and decision.action is not Action.WALK:
                # The sealed final bid: take an affordable ask (it counts as a bid at the ask), or offer the cap.
                if war.ask <= cap:
                    decision = Decision(Action.OFFER, war.ask, True)
                else:
                    forced = decide_buyer(
                        Intent(Action.OFFER, cap), cap, config.culture, seat.bid, war.ask
                    )
                    decision = Decision(forced.action, forced.price, True)
            message = await speak(agent, view, decision)

            events = face_events(
                proposal.price,
                proposal.insulting,
                decision,
                seat.bid,
                war.ask,
                config.culture,
                True,
            )
            seat.patience = apply_face(seat.patience, events)

            if decision.action is Action.ACCEPT and not final:
                seat.bid, seat.bid_turn, seat.state = decision.price, war.turn + 1, "won"
                yield event(
                    Side.BUYER,
                    seat,
                    decision,
                    proposal.price,
                    message,
                    Status.DEAL,
                    decision.price,
                    "Took the ask",
                    seat.bidder,
                )
                return
            if decision.action is Action.WALK:
                seat.state = "walked"
            elif decision.price is not None:
                if decision.price != seat.bid:
                    seat.bid_turn = war.turn + 1
                seat.bid = decision.price
                seat.final_bid = final
            note = None
            if seat.state == "bidding" and face.walks_away(seat.patience):
                seat.state, note = "thrown_out", "Thrown out: the seller's patience ran out"
            elif seat.state == "walked":
                note = "Walked away"
            status = Status.ONGOING if war.active() else end_without_deal()
            yield event(Side.BUYER, seat, decision, proposal.price, message, status, None, note)
            if status is not Status.ONGOING:
                return

        leader = war.leader()
        if leader is None:
            return

        if final:
            # Sealed: the highest bid at or above the floor wins.
            if leader.bid is not None and leader.bid >= config.seller_floor:
                decision = Decision(Action.ACCEPT, leader.bid, True)
                leader.state = "won"
                message = await speak(seller, seller_view(leader, True), decision)
                yield event(
                    Side.SELLER,
                    leader,
                    decision,
                    None,
                    message,
                    Status.DEAL,
                    leader.bid,
                    "Highest sealed bid wins",
                    leader.bidder,
                )
            else:
                decision = Decision(Action.WALK, None, True)
                message = await speak(seller, seller_view(leader, True), decision)
                yield event(
                    Side.SELLER,
                    leader,
                    decision,
                    None,
                    message,
                    Status.SELLER_WALKED,
                    None,
                    "No bid reached the floor",
                )
            return

        view = seller_view(leader, False)
        proposal = await propose(seller, view)
        decision = decide_seller(
            Intent(proposal.action, proposal.price),
            config.seller_floor,
            config.culture,
            war.ask,
            leader.bid,
        )
        message = await speak(seller, view, decision)
        events = face_events(
            proposal.price, proposal.insulting, decision, war.ask, leader.bid, config.culture, False
        )
        for seat in war.active():
            seat.face = apply_face(seat.face, events)

        if decision.action is Action.ACCEPT:
            leader.state = "won"
            yield event(
                Side.SELLER,
                leader,
                decision,
                proposal.price,
                message,
                Status.DEAL,
                decision.price,
                "Accepted the best bid",
                leader.bidder,
            )
            return
        if decision.action is Action.WALK:
            yield event(
                Side.SELLER,
                leader,
                decision,
                proposal.price,
                message,
                Status.SELLER_WALKED,
                None,
                "Walked away from the table",
            )
            return
        if decision.price is not None:
            war.ask = decision.price
        yield event(Side.SELLER, leader, decision, proposal.price, message, Status.ONGOING, None)


# Distinct buyers make a war rather than one buyer cloned. A "lowballer" opens far too low,
# so the seller's patience runs out and they are thrown out while the others carry on.
STYLES: dict[str, dict[str, float]] = {
    "balanced": {"opening_ratio": 0.52, "concession": 0.15},
    "aggressive": {"opening_ratio": 0.50, "concession": 0.22},
    "patient": {"opening_ratio": 0.58, "concession": 0.10},
    "lowballer": {"opening_ratio": 0.25, "concession": 0.04},
}
DEFAULT_STYLE_ORDER = ("balanced", "aggressive", "patient", "lowballer")


def rule_buyers(config: BiddingConfig, styles: Mapping[str, str] | None = None) -> dict[str, Agent]:
    """One deterministic rule agent per bidder, styled by name or by seat."""
    chosen = styles or {}
    return {
        b.id: RuleAgent(
            **STYLES[chosen.get(b.id, DEFAULT_STYLE_ORDER[i % len(DEFAULT_STYLE_ORDER)])]
        )
        for i, b in enumerate(config.bidders)
    }
