import pytest

from app.engine import face
from app.engine.face import FaceEvent
from app.engine.lucky import MALAYSIAN_CHINESE, NEUTRAL, NoAcceptablePrice, is_insulting, snap
from app.engine.lucky import MALAYSIAN_CHINESE as MC
from app.engine.policy import (
    Action,
    GuardrailViolation,
    Intent,
    SpendGuard,
    decide_buyer,
    decide_seller,
)


def test_888_respected_and_444_insulting() -> None:
    assert not is_insulting(888, MC)
    assert is_insulting(444, MC)
    assert not is_insulting(444, NEUTRAL)


@pytest.mark.parametrize("price,expected", [(900, 888), (1000, 988), (444, 398), (880, 888)])
def test_snap_favours_8(price: int, expected: int) -> None:
    result = snap(price, MC)
    assert "4" not in str(result)
    assert result == expected


def test_snap_respects_ceiling_and_floor() -> None:
    assert snap(880, MC, ceiling=885) == 878
    assert snap(880, MC, floor=883, ceiling=885) in (883, 885)


def test_snap_impossible_range() -> None:
    with pytest.raises(NoAcceptablePrice):
        snap(444, MC, floor=444, ceiling=444)


def test_neutral_only_clamps() -> None:
    assert snap(901, NEUTRAL) == 901
    assert snap(901, NEUTRAL, ceiling=900) == 900


def test_face_costs_clamps_and_walks() -> None:
    assert face.apply(70, FaceEvent.LOWBALL) == 50
    assert face.apply(10, FaceEvent.INSULTING_NUMBER) == 0
    assert face.apply(99, FaceEvent.FAIR_CONCESSION) == 100
    assert face.is_lowball(40, 100) and not face.is_lowball(50, 100)
    assert face.walks_away(29) and not face.walks_away(30)


@pytest.mark.parametrize("price", [1, 700, 1000, 1001, 10**7])
def test_buyer_can_never_exceed_cap(price: int) -> None:
    decision = decide_buyer(Intent(Action.OFFER, price), 1000, MC, None, None)
    assert decision.price is not None and decision.price <= 1000


def test_buyer_accept_above_cap_becomes_offer() -> None:
    decision = decide_buyer(Intent(Action.ACCEPT), 1000, MC, 800, 1500)
    assert decision.action is Action.OFFER and decision.overridden
    assert decision.price is not None and decision.price <= 1000


def test_buyer_cannot_regress_and_crossing_accepts() -> None:
    d = decide_buyer(Intent(Action.OFFER, 500), 1000, NEUTRAL, 700, None)
    assert d.price == 700
    d = decide_buyer(Intent(Action.OFFER, 900), 1000, NEUTRAL, 700, 850)
    assert (d.action, d.price) == (Action.ACCEPT, 850)


def test_seller_floor_and_no_raising_ask() -> None:
    assert decide_seller(Intent(Action.OFFER, 100), 500, NEUTRAL, 900, None).price == 500
    assert decide_seller(Intent(Action.OFFER, 2000), 500, NEUTRAL, 900, None).price == 900
    d = decide_seller(Intent(Action.ACCEPT), 500, NEUTRAL, 900, 400)
    assert d.action is Action.OFFER and d.overridden


def test_spend_guard() -> None:
    SpendGuard(100, approved=True).check(100)
    SpendGuard(100, requires_approval=False).check(1)
    for guard, amount in [
        (SpendGuard(100, approved=True), 101),
        (SpendGuard(100), 50),
        (SpendGuard(100, approved=True), 0),
    ]:
        with pytest.raises(GuardrailViolation):
            guard.check(amount)


def test_concession_survives_snapping() -> None:
    buyer = decide_buyer(Intent(Action.OFFER, 941), 1000, MALAYSIAN_CHINESE, 938, 988)
    assert buyer.price is not None and buyer.price > 938
    seller = decide_seller(Intent(Action.OFFER, 985), 700, MALAYSIAN_CHINESE, 988, 938)
    assert seller.price is not None and seller.price < 988
