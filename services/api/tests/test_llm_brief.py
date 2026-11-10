from app.engine.lucky import MALAYSIAN_CHINESE, NEUTRAL
from app.negotiation.agents import AgentView, LLMAgent, Side


def view(side: Side, culture=MALAYSIAN_CHINESE, last_other: int | None = 880) -> AgentView:
    return AgentView(side, "Bike", "MYR", culture, 600, None, last_other, 1, False)


def test_buyer_brief_teaches_the_face_rules() -> None:
    brief = LLMAgent._brief(view(Side.BUYER))
    assert "ends in 4" in brief and "44" in brief
    assert "Never offer less than 440" in brief


def test_seller_brief_has_no_lowball_rule() -> None:
    brief = LLMAgent._brief(view(Side.SELLER, last_other=500))
    assert "Never offer less than" not in brief
    assert "ends in 4" in brief


def test_neutral_culture_adds_no_number_rules() -> None:
    brief = LLMAgent._brief(view(Side.SELLER, NEUTRAL))
    assert "ends in" not in brief
