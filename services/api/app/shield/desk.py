"""Connects a finished negotiation to the Shield and saves every step to the event log."""

import asyncio
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any
from uuid import UUID

from app.config import settings
from app.engine.policy import GuardrailViolation, SpendGuard
from app.events.log import StoredEvent
from app.events.stream import ENDED, EventBus
from app.shield.gateway import GatewayError, PaymentGateway
from app.shield.service import ShieldService
from app.shield.state_machine import Deal, DealState, InvalidTransition, is_overdue

logger = logging.getLogger(__name__)

SHIELD_EVENT = "shield"
SWEEP_SECONDS = 60
FINISHED = {DealState.REFUNDED.value, DealState.VOIDED.value}


class DeskError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _to_payload(deal: Deal) -> dict[str, Any]:
    data = asdict(deal)
    data["state"] = deal.state.value
    for key in ("authorized_at", "shipped_at"):
        data[key] = data[key].isoformat() if data[key] else None
    return data


def _from_payload(data: dict[str, Any]) -> Deal:
    values = dict(data)
    values["state"] = DealState(values["state"])
    for key in ("authorized_at", "shipped_at"):
        values[key] = datetime.fromisoformat(values[key]) if values[key] else None
    return Deal(**values)


def public_view(payload: dict[str, Any]) -> dict[str, Any]:
    """Only what spectators may see. New private fields stay private by default."""
    deal = payload["deal"]
    return {
        "state": deal["state"],
        "step": payload["step"],
        "amount_minor": deal["amount_minor"],
        "currency": deal["currency"],
        "tracking_number": deal["tracking_number"],
        "carrier": deal["carrier"],
        "gateway": payload["gateway"],
    }


def shield_stream_done(event: StoredEvent) -> bool:
    if event.type == ENDED:
        return bool(event.payload.get("status") != "deal")
    return event.type == SHIELD_EVENT and event.payload["deal"]["state"] in FINISHED


class DealDesk:
    def __init__(
        self,
        bus: EventBus,
        gateway: PaymentGateway,
        gateway_name: str,
        service: ShieldService | None = None,
    ) -> None:
        self._bus = bus
        self._service = service or ShieldService(gateway)
        self.gateway_name = gateway_name

    async def _load(self, deal_id: UUID) -> tuple[Deal, bool]:
        latest = await self._bus.log.latest(deal_id, SHIELD_EVENT)
        if latest is not None:
            return _from_payload(latest.payload["deal"]), bool(latest.payload["approved"])
        # The amount always comes from the logged result, never from a client request.
        ended = await self._bus.log.latest(deal_id, ENDED)
        started = await self._bus.log.latest(deal_id, "negotiation_started")
        if started is None:
            raise DeskError(404, "unknown deal")
        if ended is None or ended.payload["status"] != "deal":
            raise DeskError(409, "this negotiation did not end in a deal")
        amount = int(ended.payload["final_price"]) * 100
        return Deal(str(deal_id), amount, started.payload["currency"]), False

    async def _guard(self, deal_id: UUID, approved: bool) -> SpendGuard:
        cap = await self._bus.log.budget_cap(deal_id)
        if cap is None:
            raise DeskError(409, "this deal has no recorded budget cap")
        return SpendGuard(cap_minor=cap, approved=approved)

    async def _save(self, deal_id: UUID, deal: Deal, approved: bool, step: str) -> None:
        payload = {
            "deal": _to_payload(deal),
            "approved": approved,
            "step": step,
            "gateway": self.gateway_name,
        }
        await self._bus.publish(deal_id, SHIELD_EVENT, payload)

    async def view(self, deal_id: UUID) -> dict[str, Any]:
        deal, approved = await self._load(deal_id)
        latest = await self._bus.log.latest(deal_id, SHIELD_EVENT)
        payload = {
            "deal": _to_payload(deal),
            "approved": approved,
            # The last step actually taken, not a fixed value.
            "step": latest.payload["step"] if latest is not None else "negotiated",
            "gateway": self.gateway_name,
        }
        return public_view(payload)

    async def run(self, deal_id: UUID, op: str, **kwargs: str) -> dict[str, Any]:
        try:
            async with self._bus.log.locked(deal_id):
                return await self._run_locked(deal_id, op, **kwargs)
        except InvalidTransition as error:
            raise DeskError(409, str(error)) from error
        except GuardrailViolation as error:
            raise DeskError(403, str(error)) from error
        except GatewayError as error:
            logger.warning("gateway failed on %s for %s: %s", op, deal_id, error)
            raise DeskError(502, "The payment provider rejected this step. Try again.") from error

    async def _run_locked(self, deal_id: UUID, op: str, **kwargs: str) -> dict[str, Any]:
        deal, approved = await self._load(deal_id)
        before = (deal, approved)
        service = self._service
        approve_url: str | None = None
        repeated = False

        if op == "approve":
            guard = await self._guard(deal_id, True)
            # PayPal sends the buyer back to this deal's own page after approving.
            back = f"{settings.frontend_url}/deals/{deal_id}"
            deal, approve_url = await service.create_order(deal, guard, back)
            approved = True
            # The order key is fixed, so asking again returns the same order and link.
            # Nothing changed, so there is nothing new to log.
            repeated = (deal, approved) == before
        elif op == "authorize":
            deal = await service.authorize(deal)
        elif op == "ship":
            deal = await service.ship(deal, kwargs["tracking_number"], kwargs["carrier"])
        elif op == "deliver":
            deal = await service.confirm_delivery(deal)
            # Saved first: if capture then fails, delivery stays recorded and capture can retry.
            await self._save(deal_id, deal, approved, "deliver")
            deal = await service.capture(deal, await self._guard(deal_id, approved))
            op = "capture"
        elif op == "capture":
            deal = await service.capture(deal, await self._guard(deal_id, approved))
        elif op == "cancel":
            deal = await service.cancel(deal)
        elif op == "refund":
            deal = await service.refund(deal)
        elif op == "expire":
            deal = await service.expire_if_overdue(deal)
        else:
            raise DeskError(404, "unknown step")

        if not repeated:
            await self._save(deal_id, deal, approved, op)
        result = public_view(
            {
                "deal": _to_payload(deal),
                "step": op,
                "gateway": self.gateway_name,
            }
        )
        # Only the caller who approved receives the PayPal link. It is never streamed.
        return {**result, "approve_url": approve_url}

    async def sweep(self) -> int:
        """Voids holds past their deadline. Returns how many were voided."""
        voided = 0
        for deal_id in await self._bus.log.deals_with(SHIELD_EVENT):
            latest = await self._bus.log.latest(deal_id, SHIELD_EVENT)
            if latest is None or latest.payload["deal"]["state"] not in ("authorized", "shipped"):
                continue
            deal = _from_payload(latest.payload["deal"])
            if not is_overdue(deal, self._service.now(), self._service.deadlines):
                continue
            await self.run(deal_id, "expire")
            voided += 1
        return voided

    async def sweep_forever(self) -> None:
        while True:
            try:
                await self.sweep()
            except Exception:
                logger.exception("deadline sweep failed")
            await asyncio.sleep(SWEEP_SECONDS)
