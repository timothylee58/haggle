import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.engine.lucky import MALAYSIAN_CHINESE, NEUTRAL
from app.events.log import EventLog
from app.events.runner import NegotiationRunner
from app.events.stream import EventBus
from app.negotiation.agents import Agent, LLMAgent, RuleAgent
from app.negotiation.bidding import Bidder, BiddingConfig, rule_buyers
from app.negotiation.graph import NegotiationConfig
from app.shield.desk import SHIELD_EVENT, DealDesk, DeskError, public_view, shield_stream_done
from app.shield.gateway import FakeGateway, PaymentGateway, PayPalGateway

MAX_PRICE = 10_000_000
CULTURES = {"malaysian_chinese": MALAYSIAN_CHINESE, "neutral": NEUTRAL}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_async_engine(settings.database_url)
    redis = aioredis.from_url(settings.redis_url)
    app.state.log = EventLog(async_sessionmaker(engine, expire_on_commit=False))
    app.state.bus = EventBus(app.state.log, redis)
    app.state.runner = NegotiationRunner(app.state.bus)
    gateway: PaymentGateway
    if settings.paypal_client_id and settings.paypal_client_secret:
        gateway = PayPalGateway(settings.paypal_client_id, settings.paypal_client_secret)
        gateway_name = "paypal_sandbox"
    else:
        gateway = FakeGateway()
        gateway_name = "simulated"
    app.state.desk = DealDesk(app.state.bus, gateway, gateway_name)
    sweeper = asyncio.create_task(app.state.desk.sweep_forever())
    yield
    sweeper.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await sweeper
    await app.state.runner.shutdown()
    if isinstance(gateway, PayPalGateway):
        await gateway.aclose()
    await redis.aclose()
    await engine.dispose()


app = FastAPI(title="Haggle API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartNegotiation(BaseModel):
    item: str = Field(min_length=1, max_length=200)
    budget_cap: int = Field(gt=0, le=MAX_PRICE)
    seller_floor: int = Field(gt=0, le=MAX_PRICE)
    opening_ask: int = Field(gt=0, le=MAX_PRICE)
    currency: str = Field(default="MYR", pattern="^[A-Z]{3}$")
    culture: Literal["malaysian_chinese", "neutral"] = "malaysian_chinese"
    max_rounds: int = Field(default=6, ge=1, le=20)
    use_llm: bool = False

    @model_validator(mode="after")
    def ask_meets_floor(self) -> "StartNegotiation":
        if self.opening_ask < self.seller_floor:
            raise ValueError("opening_ask cannot be below seller_floor")
        return self


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/negotiations", status_code=201)
async def start_negotiation(body: StartNegotiation, request: Request) -> dict[str, str]:
    agent: Agent = RuleAgent()
    if body.use_llm:
        if not settings.anthropic_api_key:
            raise HTTPException(503, "ANTHROPIC_API_KEY is not configured")
        agent = LLMAgent(settings.anthropic_api_key, settings.llm_model)
    config = NegotiationConfig(
        item=body.item,
        budget_cap=body.budget_cap,
        seller_floor=body.seller_floor,
        opening_ask=body.opening_ask,
        currency=body.currency,
        culture=CULTURES[body.culture],
        max_rounds=body.max_rounds,
    )
    deal_id = await request.app.state.runner.start(config, agent, agent)
    return {"deal_id": str(deal_id)}


class BidderBody(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    budget_cap: int = Field(gt=0, le=MAX_PRICE)
    style: Literal["balanced", "aggressive", "patient", "lowballer"] | None = None


class StartBiddingWar(BaseModel):
    item: str = Field(min_length=1, max_length=200)
    seller_floor: int = Field(gt=0, le=MAX_PRICE)
    opening_ask: int = Field(gt=0, le=MAX_PRICE)
    bidders: list[BidderBody] = Field(min_length=2, max_length=4)
    currency: str = Field(default="MYR", pattern="^[A-Z]{3}$")
    culture: Literal["malaysian_chinese", "neutral"] = "malaysian_chinese"
    max_rounds: int = Field(default=6, ge=1, le=20)
    use_llm: bool = False

    @model_validator(mode="after")
    def consistent(self) -> "StartBiddingWar":
        if self.opening_ask < self.seller_floor:
            raise ValueError("opening_ask cannot be below seller_floor")
        names = [b.name.strip().lower() for b in self.bidders]
        if len(set(names)) != len(names):
            raise ValueError("bidder names must be different")
        return self


@app.post("/bidding-wars", status_code=201)
async def start_bidding_war(body: StartBiddingWar, request: Request) -> dict[str, str]:
    seller: Agent = RuleAgent()
    bidders = tuple(
        Bidder(f"b{i + 1}", b.name.strip(), b.budget_cap) for i, b in enumerate(body.bidders)
    )
    config = BiddingConfig(
        item=body.item,
        seller_floor=body.seller_floor,
        opening_ask=body.opening_ask,
        bidders=bidders,
        currency=body.currency,
        culture=CULTURES[body.culture],
        max_rounds=body.max_rounds,
    )
    if body.use_llm:
        if not settings.anthropic_api_key:
            raise HTTPException(503, "ANTHROPIC_API_KEY is not configured")
        llm = LLMAgent(settings.anthropic_api_key, settings.llm_model)
        buyers: dict[str, Agent] = {b.id: llm for b in bidders}
        seller = llm
    else:
        styles = {f"b{i + 1}": b.style for i, b in enumerate(body.bidders) if b.style}
        buyers = rule_buyers(config, styles)
    deal_id = await request.app.state.runner.start_bidding(config, buyers, seller)
    return {"deal_id": str(deal_id)}


@app.get("/negotiations/{deal_id}/events")
async def negotiation_events(
    deal_id: UUID,
    request: Request,
    after: Annotated[int, Query(ge=0)] = 0,
    last_event_id: Annotated[int | None, Header(ge=0)] = None,
) -> EventSourceResponse:
    """Replays then follows. Browsers resume automatically through Last-Event-ID."""
    log: EventLog = request.app.state.log
    if not await log.read_after(deal_id):
        raise HTTPException(404, "unknown negotiation")
    bus: EventBus = request.app.state.bus
    start = last_event_id if last_event_id is not None else after

    async def frames() -> AsyncIterator[dict[str, str]]:
        async for event in bus.stream(deal_id, start):
            yield {"id": str(event.seq), "event": event.type, "data": json.dumps(event.payload)}

    return EventSourceResponse(frames())


class ShipBody(BaseModel):
    tracking_number: str = Field(min_length=1, max_length=64)
    carrier: str = Field(default="OTHER", min_length=1, max_length=64)


async def _shield(request: Request, deal_id: UUID, op: str, **kwargs: str) -> dict[str, object]:
    desk: DealDesk = request.app.state.desk
    try:
        return await desk.run(deal_id, op, **kwargs)
    except DeskError as error:
        raise HTTPException(error.status, error.message) from error


@app.get("/deals/{deal_id}/shield")
async def shield_state(deal_id: UUID, request: Request) -> dict[str, object]:
    desk: DealDesk = request.app.state.desk
    try:
        return await desk.view(deal_id)
    except DeskError as error:
        raise HTTPException(error.status, error.message) from error


@app.post("/deals/{deal_id}/shield/approve")
async def shield_approve(deal_id: UUID, request: Request) -> dict[str, object]:
    return await _shield(request, deal_id, "approve")


@app.post("/deals/{deal_id}/shield/authorize")
async def shield_authorize(deal_id: UUID, request: Request) -> dict[str, object]:
    return await _shield(request, deal_id, "authorize")


@app.post("/deals/{deal_id}/shield/ship")
async def shield_ship(deal_id: UUID, body: ShipBody, request: Request) -> dict[str, object]:
    return await _shield(
        request, deal_id, "ship", tracking_number=body.tracking_number, carrier=body.carrier
    )


@app.post("/deals/{deal_id}/shield/deliver")
async def shield_deliver(deal_id: UUID, request: Request) -> dict[str, object]:
    """Confirms delivery and captures. If capture fails, retry with /capture."""
    return await _shield(request, deal_id, "deliver")


@app.post("/deals/{deal_id}/shield/capture")
async def shield_capture(deal_id: UUID, request: Request) -> dict[str, object]:
    return await _shield(request, deal_id, "capture")


@app.post("/deals/{deal_id}/shield/cancel")
async def shield_cancel(deal_id: UUID, request: Request) -> dict[str, object]:
    return await _shield(request, deal_id, "cancel")


@app.post("/deals/{deal_id}/shield/refund")
async def shield_refund(deal_id: UUID, request: Request) -> dict[str, object]:
    return await _shield(request, deal_id, "refund")


@app.get("/deals/{deal_id}/shield/events")
async def shield_events(
    deal_id: UUID,
    request: Request,
    last_event_id: Annotated[int | None, Header(ge=0)] = None,
) -> EventSourceResponse:
    """Spectator feed: a public projection only, with no payment IDs or approval links."""
    bus: EventBus = request.app.state.bus
    if not await bus.log.read_after(deal_id):
        raise HTTPException(404, "unknown negotiation")

    async def frames() -> AsyncIterator[dict[str, str]]:
        async for event in bus.stream(deal_id, last_event_id or 0, stop=shield_stream_done):
            if event.type == SHIELD_EVENT:
                yield {
                    "id": str(event.seq),
                    "event": "shield",
                    "data": json.dumps(public_view(event.payload)),
                }

    return EventSourceResponse(frames())
