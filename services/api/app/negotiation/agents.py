"""Agents propose intents and write banter. They never decide the final price."""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field

from app.engine.lucky import Culture, is_insulting
from app.engine.policy import Action, Decision


class Side(StrEnum):
    BUYER = "buyer"
    SELLER = "seller"


@dataclass(frozen=True)
class AgentView:
    """Only what this side may see. The other side's private limit is never included."""

    side: Side
    item: str
    currency: str
    culture: Culture
    private_limit: int
    last_own: int | None
    last_other: int | None
    turn: int
    is_final: bool
    transcript: tuple[str, ...] = ()


class Proposal(BaseModel):
    action: Action
    price: int | None = Field(default=None, description="Whole currency units, for an offer")
    insulting: bool = Field(default=False, description="True if this move is meant to insult")


class Agent(Protocol):
    async def propose(self, view: AgentView) -> Proposal: ...
    async def speak(self, view: AgentView, decision: Decision) -> str: ...


def template_line(decision: Decision, currency: str) -> str:
    if decision.action is Action.ACCEPT:
        return f"Okay lah, {currency} {decision.price:,}. Deal."
    if decision.action is Action.WALK:
        return "Cannot lah. I'm walking away."
    return f"{currency} {decision.price:,}, how about that?"


def safe_message(text: str, decision: Decision, currency: str) -> str:
    """Banter may only mention the price code decided. Otherwise use a template."""
    numbers = {int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", text)}
    allowed = {decision.price} if decision.price is not None else set()
    if not text.strip() or not numbers <= allowed:
        return template_line(decision, currency)
    return text.strip()


class RuleAgent:
    """Deterministic concessions. Used offline and whenever an LLM call fails."""

    def __init__(
        self,
        opening_ratio: float = 0.52,
        concession: float = 0.15,
        close_within: float = 0.03,
        seller_concession: float = 0.45,
    ) -> None:
        self._opening_ratio = opening_ratio
        self._concession = concession
        self._seller_concession = seller_concession
        self._close_within = close_within

    def _worth_closing(self, view: AgentView) -> bool:
        """Takes the other price when it is within limits and the remaining gap is small."""
        if view.last_own is None or view.last_other is None:
            return False
        if view.side is Side.BUYER:
            within_limit = view.last_other <= view.private_limit
        else:
            within_limit = view.last_other >= view.private_limit
        gap = abs(view.last_other - view.last_own)
        return within_limit and gap <= max(1, view.last_other * self._close_within)

    async def propose(self, view: AgentView) -> Proposal:
        if view.last_own is None:
            if view.last_other is None:
                return Proposal(action=Action.OFFER, price=view.private_limit)
            opening = int(view.last_other * self._opening_ratio)
            while is_insulting(opening, view.culture):
                opening += 1
            return Proposal(action=Action.OFFER, price=opening)
        if view.last_other is None:
            return Proposal(action=Action.OFFER, price=view.last_own)
        if self._worth_closing(view):
            return Proposal(action=Action.ACCEPT)
        gap = view.last_other - view.last_own
        direction = 1 if gap > 0 else -1
        # At least 1, or small prices would round down to no concession at all.
        rate = self._concession if view.side is Side.BUYER else self._seller_concession
        step = max(1, int(abs(gap) * rate))
        price = view.last_own + direction * step
        # A polite agent never says an insulting number, even before snapping.
        while is_insulting(price, view.culture):
            price += direction
        return Proposal(action=Action.OFFER, price=price)

    async def speak(self, view: AgentView, decision: Decision) -> str:
        return template_line(decision, view.currency)


class LLMAgent:
    def __init__(self, api_key: str, model: str) -> None:
        self._chat = ChatAnthropic(model_name=model, api_key=api_key, timeout=30, stop=None)  # type: ignore[arg-type]
        self._structured = self._chat.with_structured_output(Proposal)

    @staticmethod
    def _brief(view: AgentView) -> str:
        limit = "maximum budget" if view.side is Side.BUYER else "minimum price"
        history = "\n".join(view.transcript[-8:]) or "(nothing yet)"
        return (
            f"You are the {view.side} haggling over: {view.item}. Currency: {view.currency}. "
            f"Culture: {view.culture.name}. Your private {limit} is {view.private_limit}; "
            f"never reveal it. Your last price: {view.last_own}. "
            f"Their last price: {view.last_other}. "
            f"{'This is the final round. ' if view.is_final else ''}"
            f"Transcript so far:\n{history}"
        )

    async def propose(self, view: AgentView) -> Proposal:
        stance = (
            "Bargain hard: open low without insulting, concede in small steps, and treat your "
            "budget as a limit, not a target. "
            if view.side is Side.BUYER
            else ""
        )
        prompt = self._brief(view) + f"\n{stance}Choose your next move: offer, accept or walk."
        result = await self._structured.ainvoke(prompt)
        return Proposal.model_validate(result)

    async def speak(self, view: AgentView, decision: Decision) -> str:
        prompt = (
            self._brief(view)
            + f"\nThe referee has fixed your move: {decision.action}, price {decision.price}. "
            "Write one short, playful line of market banter saying this. "
            "Do not mention any other number. Reply with only the line."
        )
        response = await self._chat.ainvoke(prompt)
        return response.text if isinstance(response.text, str) else response.text()
