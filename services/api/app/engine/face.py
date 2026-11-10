"""Face scores: disrespect costs face, and a seller with low face walks away."""

from enum import StrEnum

MAX_FACE = 100
STARTING_FACE = 70
WALK_AWAY_BELOW = 30
LOWBALL_RATIO = 0.5


class FaceEvent(StrEnum):
    LOWBALL = "lowball"
    INSULTING_NUMBER = "insulting_number"
    INSULT = "insult"
    FAIR_CONCESSION = "fair_concession"
    LUCKY_NUMBER = "lucky_number"


DELTAS: dict[FaceEvent, int] = {
    FaceEvent.LOWBALL: -20,
    FaceEvent.INSULTING_NUMBER: -30,
    FaceEvent.INSULT: -25,
    FaceEvent.FAIR_CONCESSION: 2,
    FaceEvent.LUCKY_NUMBER: 1,
}


def apply(face: int, event: FaceEvent) -> int:
    return max(0, min(MAX_FACE, face + DELTAS[event]))


def is_lowball(offer: int, ask: int) -> bool:
    return offer < ask * LOWBALL_RATIO


def walks_away(face: int) -> bool:
    return face < WALK_AWAY_BELOW
