from app.security import hash_token, new_token, token_matches, window, within_limit


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.expiries: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expiries[key] = seconds


class DownRedis:
    async def incr(self, key: str) -> int:
        raise ConnectionError("redis is down")

    async def expire(self, key: str, seconds: int) -> None:
        raise ConnectionError("redis is down")


def test_tokens_are_random_and_only_the_right_one_matches() -> None:
    a, b = new_token(), new_token()
    assert a != b and len(a) >= 30
    stored = hash_token(a)
    assert token_matches(a, stored)
    assert not token_matches(b, stored)
    assert not token_matches(a + "x", stored)


def test_a_missing_token_or_hash_never_matches() -> None:
    assert not token_matches(None, hash_token("x"))
    assert not token_matches("x", None)
    assert not token_matches("", hash_token(""))


async def test_the_window_counts_then_refuses_and_expires_its_key() -> None:
    redis = FakeRedis()
    results = [await within_limit(redis, "k", 3, 3600) for _ in range(5)]
    assert results == [True, True, True, False, False]
    assert redis.expiries == {"k": 3600}  # set once, on the first hit


async def test_a_dead_counter_store_lets_requests_through() -> None:
    assert await within_limit(DownRedis(), "k", 1, 60) is True


def test_the_window_changes_when_the_period_rolls_over() -> None:
    assert window(3600) == window(3600)
    assert window(86400) <= window(3600)
