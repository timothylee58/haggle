"""Publishes events and streams them. Redis only wakes readers; they read from Postgres."""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.events.log import EventLog, StoredEvent

logger = logging.getLogger(__name__)

ENDED = "negotiation_ended"
POLL_SECONDS = 5.0


def channel(deal_id: UUID) -> str:
    return f"deal:{deal_id}"


class EventBus:
    def __init__(self, log: EventLog, redis: aioredis.Redis) -> None:
        self.log = log
        self._redis = redis

    async def publish(self, deal_id: UUID, type_: str, payload: dict[str, Any]) -> StoredEvent:
        event = await self.log.append(deal_id, type_, payload)
        try:
            await self._redis.publish(channel(deal_id), str(event.seq))
        except RedisError:
            # The event is stored; readers will pick it up on their next poll.
            logger.warning("redis publish failed for deal %s", deal_id, exc_info=True)
        return event

    async def stream(
        self,
        deal_id: UUID,
        after: int = 0,
        stop: Callable[[StoredEvent], bool] = lambda event: event.type == ENDED,
    ) -> AsyncIterator[StoredEvent]:
        """Replays from `after`, follows live, and stops once `stop` says so."""
        pubsub = self._redis.pubsub()
        subscribed = False
        try:
            # Subscribing before the first read means no event can slip between them.
            try:
                await pubsub.subscribe(channel(deal_id))
                subscribed = True
            except RedisError:
                logger.warning("redis subscribe failed; polling only", exc_info=True)
            cursor = after
            while True:
                for event in await self.log.read_after(deal_id, cursor):
                    cursor = event.seq
                    yield event
                    if stop(event):
                        return
                if subscribed:
                    try:
                        await pubsub.get_message(
                            ignore_subscribe_messages=True, timeout=POLL_SECONDS
                        )
                        continue
                    except RedisError:
                        subscribed = False
                        logger.warning("redis read failed; polling only", exc_info=True)
                await asyncio.sleep(POLL_SECONDS)
        finally:
            await pubsub.aclose()
