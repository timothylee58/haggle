"""Validates each transition before touching the gateway, so a bad state moves no money."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from app.engine.policy import SpendGuard
from app.shield.gateway import GatewayError, PaymentGateway
from app.shield.state_machine import (
    DEFAULT_DEADLINES,
    Deadlines,
    Deal,
    DealEvent,
    DealState,
    InvalidTransition,
    is_overdue,
    transition,
)


class ShieldService:
    def __init__(
        self,
        gateway: PaymentGateway,
        deadlines: Deadlines = DEFAULT_DEADLINES,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._gateway = gateway
        self._deadlines = deadlines
        self._clock = clock

    def now(self) -> datetime:
        return self._clock()

    @property
    def deadlines(self) -> Deadlines:
        return self._deadlines

    def _next(self, deal: Deal, event: DealEvent, **kwargs: str | None) -> Deal:
        return transition(deal, event, self._clock(), self._deadlines, **kwargs)  # type: ignore[arg-type]

    async def create_order(
        self, deal: Deal, guard: SpendGuard, return_url: str | None = None
    ) -> tuple[Deal, str | None]:
        """Returns the deal and the URL where the buyer approves the hold."""
        if deal.state is not DealState.NEGOTIATED:
            raise InvalidTransition(f"cannot create an order from {deal.state}")
        order = await self._gateway.create_order(
            deal.amount_minor, deal.currency, guard, f"{deal.deal_id}-order", return_url
        )
        return replace(deal, order_id=order.order_id), order.approve_url

    async def authorize(self, deal: Deal) -> Deal:
        updated = self._next(deal, DealEvent.AUTHORIZE)
        if deal.order_id is None:
            raise InvalidTransition("no order to authorize")
        authorization_id = await self._gateway.authorize_order(
            deal.order_id, f"{deal.deal_id}-authorize"
        )
        return replace(updated, authorization_id=authorization_id)

    async def ship(self, deal: Deal, tracking_number: str, carrier: str) -> Deal:
        # Tracking stays in our records until capture, pending the sandbox spike.
        return self._next(deal, DealEvent.SHIP, tracking_number=tracking_number, carrier=carrier)

    async def confirm_delivery(self, deal: Deal) -> Deal:
        return self._next(deal, DealEvent.CONFIRM_DELIVERY)

    async def capture(self, deal: Deal, guard: SpendGuard) -> Deal:
        updated = self._next(deal, DealEvent.CAPTURE)
        if deal.authorization_id is None:
            raise InvalidTransition("no authorization to capture")
        capture_id = await self._gateway.capture(
            deal.authorization_id,
            deal.amount_minor,
            deal.currency,
            guard,
            f"{deal.deal_id}-capture",
        )
        updated = replace(updated, capture_id=capture_id)
        if deal.order_id and deal.tracking_number and deal.carrier:
            try:
                await self._gateway.create_shipment_tracking(
                    deal.order_id,
                    capture_id,
                    deal.tracking_number,
                    deal.carrier,
                    f"{deal.deal_id}-tracking",
                )
            except GatewayError:
                pass  # The money has moved; a failed tracking push must not hide that.
        return updated

    async def refund(self, deal: Deal) -> Deal:
        updated = self._next(deal, DealEvent.REFUND)
        if deal.capture_id is None:
            raise InvalidTransition("no capture to refund")
        await self._gateway.refund(deal.capture_id, f"{deal.deal_id}-refund")
        return updated

    async def _void(self, deal: Deal, event: DealEvent) -> Deal:
        updated = self._next(deal, event)
        if deal.authorization_id is None:
            raise InvalidTransition("no authorization to void")
        await self._gateway.void(deal.authorization_id, f"{deal.deal_id}-void")
        return updated

    async def cancel(self, deal: Deal) -> Deal:
        return await self._void(deal, DealEvent.CANCEL)

    async def expire_if_overdue(self, deal: Deal) -> Deal:
        if is_overdue(deal, self._clock(), self._deadlines):
            return await self._void(deal, DealEvent.TIMEOUT)
        return deal
