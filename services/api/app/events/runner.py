"""Runs negotiations in the background and records every turn."""

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import asdict
from uuid import UUID, uuid4

from app.events.stream import ENDED, EventBus
from app.negotiation.agents import Agent
from app.negotiation.bidding import BiddingConfig, run_bidding_war
from app.negotiation.graph import NegotiationConfig, run_negotiation
from app.negotiation.referee import Status

logger = logging.getLogger(__name__)


class NegotiationRunner:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(self, config: NegotiationConfig, buyer: Agent, seller: Agent) -> UUID:
        deal_id = uuid4()
        await self._bus.log.save_terms(deal_id, config.budget_cap * 100)
        # Spectators read this log, so the budget cap and floor must never enter it.
        await self._bus.publish(
            deal_id,
            "negotiation_started",
            {
                "item": config.item,
                "currency": config.currency,
                "opening_ask": config.opening_ask,
                "max_rounds": config.max_rounds,
                "culture": config.culture.name,
            },
        )
        task = asyncio.create_task(self._run(deal_id, config, buyer, seller))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return deal_id

    async def _run(
        self, deal_id: UUID, config: NegotiationConfig, buyer: Agent, seller: Agent
    ) -> None:
        status, final_price = "failed", None
        try:
            async for event in run_negotiation(config, buyer, seller):
                await self._bus.publish(deal_id, "turn", asdict(event))
                status, final_price = event.status.value, event.final_price
        except Exception:
            status, final_price = "failed", None
            logger.exception("negotiation %s failed", deal_id)
        await self._bus.publish(deal_id, ENDED, {"status": status, "final_price": final_price})

    async def start_bidding(
        self, config: BiddingConfig, buyers: Mapping[str, Agent], seller: Agent
    ) -> UUID:
        deal_id = uuid4()
        # No budget cap is saved yet: only the winner's cap matters, and it is saved when they win.
        await self._bus.publish(
            deal_id,
            "negotiation_started",
            {
                "mode": "bidding_war",
                "item": config.item,
                "currency": config.currency,
                "opening_ask": config.opening_ask,
                "max_rounds": config.max_rounds,
                "culture": config.culture.name,
                "bidders": [{"id": b.id, "name": b.name} for b in config.bidders],
            },
        )
        task = asyncio.create_task(self._run_bidding(deal_id, config, buyers, seller))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return deal_id

    async def _run_bidding(
        self, deal_id: UUID, config: BiddingConfig, buyers: Mapping[str, Agent], seller: Agent
    ) -> None:
        status, final_price, winner = "failed", None, None
        caps = {b.id: b.budget_cap for b in config.bidders}
        try:
            async for event in run_bidding_war(config, buyers, seller):
                if event.status is Status.DEAL and event.winner is not None:
                    # Saved before the winning event goes out, so the Shield can always find the cap.
                    await self._bus.log.save_terms(deal_id, caps[event.winner] * 100)
                    # On a winning move the mover (or the leader being answered) is the winner.
                    winner = {"id": event.winner, "name": event.bidder_name}
                await self._bus.publish(deal_id, "turn", asdict(event))
                status, final_price = event.status.value, event.final_price
        except Exception:
            status, final_price, winner = "failed", None, None
            logger.exception("bidding war %s failed", deal_id)
        await self._bus.publish(
            deal_id, ENDED, {"status": status, "final_price": final_price, "winner": winner}
        )

    async def shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
