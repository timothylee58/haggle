"""Pure rules for scoring a move and deciding whether the negotiation ends."""

from dataclasses import dataclass
from enum import StrEnum

from app.engine import face
from app.engine.face import FaceEvent
from app.engine.lucky import Culture, is_insulting
from app.engine.policy import Action, Decision


class Status(StrEnum):
    ONGOING = "ongoing"
    DEAL = "deal"
    NO_DEAL = "no_deal"
    SELLER_WALKED = "seller_walked"
    BUYER_WALKED = "buyer_walked"


def face_events(
    requested: int | None,
    insulting: bool,
    decision: Decision,
    last_own: int | None,
    last_other: int | None,
    culture: Culture,
    is_buyer: bool,
) -> list[FaceEvent]:
    """Scores what the agent tried, even when policy corrected the actual price."""
    events: list[FaceEvent] = []
    if insulting:
        events.append(FaceEvent.INSULT)
    if requested is not None:
        if is_insulting(requested, culture):
            events.append(FaceEvent.INSULTING_NUMBER)
        if is_buyer and last_other is not None and face.is_lowball(requested, last_other):
            events.append(FaceEvent.LOWBALL)
    if decision.action is Action.OFFER and decision.price is not None and last_own is not None:
        conceded = decision.price > last_own if is_buyer else decision.price < last_own
        if conceded:
            events.append(FaceEvent.FAIR_CONCESSION)
    lucky = culture.lucky_digit
    if lucky and decision.price is not None and str(decision.price).endswith(lucky):
        events.append(FaceEvent.LUCKY_NUMBER)
    return events


def apply_face(score: int, events: list[FaceEvent]) -> int:
    for event in events:
        score = face.apply(score, event)
    return score


@dataclass(frozen=True)
class Outcome:
    status: Status
    final_price: int | None = None


def judge(decision: Decision, is_buyer: bool, seller_face: int, final_round: bool) -> Outcome:
    if decision.action is Action.ACCEPT:
        return Outcome(Status.DEAL, decision.price)
    if decision.action is Action.WALK:
        return Outcome(Status.BUYER_WALKED if is_buyer else Status.SELLER_WALKED)
    if face.walks_away(seller_face):
        return Outcome(Status.SELLER_WALKED)
    if final_round and not is_buyer:
        return Outcome(Status.NO_DEAL)
    return Outcome(Status.ONGOING)
