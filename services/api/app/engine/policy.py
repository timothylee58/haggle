"""Validates and clamps LLM intents. The LLM proposes; this module decides."""

from dataclasses import dataclass
from enum import StrEnum

from app.engine.lucky import Culture, NoAcceptablePrice, snap


class Action(StrEnum):
    OFFER = "offer"
    ACCEPT = "accept"
    WALK = "walk"


@dataclass(frozen=True)
class Intent:
    action: Action
    price: int | None = None


@dataclass(frozen=True)
class Decision:
    action: Action
    price: int | None
    overridden: bool = False


class GuardrailViolation(Exception):
    pass


@dataclass(frozen=True)
class SpendGuard:
    """Budget cap and approval gate, in minor units. Re-checked by every gateway."""

    cap_minor: int
    requires_approval: bool = True
    approved: bool = False

    def check(self, amount_minor: int) -> None:
        if amount_minor <= 0:
            raise GuardrailViolation("amount must be positive")
        if amount_minor > self.cap_minor:
            raise GuardrailViolation(f"{amount_minor} exceeds cap {self.cap_minor}")
        if self.requires_approval and not self.approved:
            raise GuardrailViolation("human approval required")


def _snap_or_bound(price: int, culture: Culture, low: int, high: int) -> int:
    try:
        return snap(price, culture, floor=low, ceiling=high)
    except NoAcceptablePrice:
        return min(max(price, low), high)


def decide_buyer(
    intent: Intent, cap: int, culture: Culture, last_own: int | None, last_ask: int | None
) -> Decision:
    """Never exceeds the cap and never bids below the buyer's own last offer."""
    if intent.action is Action.WALK:
        return Decision(Action.WALK, None)
    if intent.action is Action.ACCEPT:
        if last_ask is not None and last_ask <= cap:
            return Decision(Action.ACCEPT, last_ask)
        return Decision(Action.OFFER, _snap_or_bound(cap, culture, last_own or 1, cap), True)

    requested = intent.price if intent.price is not None else (last_own or 1)
    low = min(last_own or 1, cap)
    if last_own is not None and requested > last_own:
        # A real concession must survive snapping, or lucky numbers stall the haggle.
        low = min(last_own + 1, cap)
    price = _snap_or_bound(requested, culture, low, cap)
    if last_ask is not None and price >= last_ask and last_ask <= cap:
        return Decision(Action.ACCEPT, last_ask, True)
    return Decision(Action.OFFER, price, price != requested)


def decide_seller(
    intent: Intent, floor: int, culture: Culture, last_own: int | None, last_bid: int | None
) -> Decision:
    """Never sells below the floor and never raises the seller's own last ask."""
    if intent.action is Action.WALK:
        return Decision(Action.WALK, None)
    high = max(last_own, floor) if last_own is not None else None
    if intent.action is Action.ACCEPT:
        if last_bid is not None and last_bid >= floor:
            return Decision(Action.ACCEPT, last_bid)
        top = high if high is not None else floor * 2
        return Decision(Action.OFFER, _snap_or_bound(floor, culture, floor, top), True)

    requested = intent.price if intent.price is not None else (high or floor)
    top = high if high is not None else max(requested, floor) * 2
    if last_own is not None and requested < last_own:
        top = max(last_own - 1, floor)
    price = _snap_or_bound(requested, culture, floor, top)
    if last_bid is not None and last_bid >= price:
        return Decision(Action.ACCEPT, last_bid, True)
    return Decision(Action.OFFER, price, price != requested)
