import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def no_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests start many matches from one address. The limits themselves are tested explicitly."""
    monkeypatch.setattr(settings, "rate_limits_enabled", False)
