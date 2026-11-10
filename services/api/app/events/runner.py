"""Runs negotiations in the background and records every turn."""

import asyncio
import logging
from dataclasses import asdict
from uuid import UUID, uuid4

from app.events.stream import ENDED, EventBus
from app.negotiation.agents import Agent
from app.negotiation.graph import NegotiationConfig, run_negotiation

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

    async def shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
