"""Kena Scam Shield state machine. Pure: no I/O, and the clock is passed in."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum


class DealState(StrEnum):
    NEGOTIATED = "negotiated"
    AUTHORIZED = "authorized"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CAPTURED = "captured"
    REFUNDED = "refunded"
    VOIDED = "voided"


class DealEvent(StrEnum):
    AUTHORIZE = "authorize"
    SHIP = "ship"
    CONFIRM_DELIVERY = "confirm_delivery"
    CAPTURE = "capture"
    REFUND = "refund"
    CANCEL = "cancel"
    TIMEOUT = "timeout"


class InvalidTransition(Exception):
    pass


@dataclass(frozen=True)
class Deadlines:
    """Provisional. Tune to the real authorization window found by the spike."""

    ship_within: timedelta = timedelta(days=3)
    deliver_within: timedelta = timedelta(days=14)


DEFAULT_DEADLINES = Deadlines()


@dataclass(frozen=True)
class Deal:
    deal_id: str
    amount_minor: int
    currency: str
    state: DealState = DealState.NEGOTIATED
    order_id: str | None = None
    authorization_id: str | None = None
    capture_id: str | None = None
    tracking_number: str | None = None
    carrier: str | None = None
    authorized_at: datetime | None = None
    shipped_at: datetime | None = None


_TABLE: dict[tuple[DealState, DealEvent], DealState] = {
    (DealState.NEGOTIATED, DealEvent.AUTHORIZE): DealState.AUTHORIZED,
    (DealState.AUTHORIZED, DealEvent.SHIP): DealState.SHIPPED,
    (DealState.SHIPPED, DealEvent.CONFIRM_DELIVERY): DealState.DELIVERED,
    (DealState.DELIVERED, DealEvent.CAPTURE): DealState.CAPTURED,
    (DealState.CAPTURED, DealEvent.REFUND): DealState.REFUNDED,
    (DealState.AUTHORIZED, DealEvent.CANCEL): DealState.VOIDED,
    (DealState.SHIPPED, DealEvent.CANCEL): DealState.VOIDED,
    (DealState.AUTHORIZED, DealEvent.TIMEOUT): DealState.VOIDED,
    (DealState.SHIPPED, DealEvent.TIMEOUT): DealState.VOIDED,
}


def is_overdue(deal: Deal, now: datetime, deadlines: Deadlines) -> bool:
    if deal.state is DealState.AUTHORIZED and deal.authorized_at is not None:
        return now > deal.authorized_at + deadlines.ship_within
    if deal.state is DealState.SHIPPED and deal.shipped_at is not None:
        return now > deal.shipped_at + deadlines.deliver_within
    return False


def transition(
    deal: Deal,
    event: DealEvent,
    now: datetime,
    deadlines: Deadlines = DEFAULT_DEADLINES,
    tracking_number: str | None = None,
    carrier: str | None = None,
) -> Deal:
    target = _TABLE.get((deal.state, event))
    if target is None:
        raise InvalidTransition(f"{event} not allowed from {deal.state}")
    overdue = is_overdue(deal, now, deadlines)

    if event is DealEvent.TIMEOUT:
        if not overdue:
            raise InvalidTransition("deadline has not passed")
        return replace(deal, state=target)
    if event in (DealEvent.SHIP, DealEvent.CONFIRM_DELIVERY) and overdue:
        raise InvalidTransition("deadline has passed; the hold must be voided")
    if event is DealEvent.SHIP:
        if not tracking_number or not tracking_number.strip():
            raise InvalidTransition("shipping requires a tracking number")
        return replace(
            deal,
            state=target,
            tracking_number=tracking_number.strip(),
            carrier=carrier,
            shipped_at=now,
        )
    if event is DealEvent.AUTHORIZE:
        return replace(deal, state=target, authorized_at=now)
    return replace(deal, state=target)
