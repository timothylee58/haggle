import httpx
import pytest

from app.market import (
    Channel3Client,
    MarketError,
    MarketResult,
    cached_search,
    normalise,
    parse_products,
    summarise,
)

PAYLOAD = {
    "products": [
        {
            "id": "p1",
            "title": "Yamaha FG800 Acoustic Guitar",
            "brands": [{"id": "b1", "name": "Yamaha"}],
            "images": ["https://img.example/1.jpg"],
            "offers": [
                {
                    "url": "https://a.example/p",
                    "domain": "a.example",
                    "price": {"price": 249.99, "currency": "USD"},
                    "availability": "InStock",
                    "condition": "new",
                },
                {
                    "url": "https://b.example/p",
                    "domain": "b.example",
                    "price": {"price": 199.0, "currency": "USD"},
                    "availability": "OutOfStock",
                    "condition": "new",
                },
            ],
        },
        {
            "id": "p2",
            "title": "Yamaha FG830",
            "images": [{"url": "https://img.example/2.jpg"}],
            "offers": [
                {
                    "url": "https://c.example",
                    "domain": "c.example",
                    "price": {"price": 349, "currency": "USD"},
                    "availability": "InStock",
                    "condition": "new",
                }
            ],
        },
        {"id": "p3", "title": "Nothing to buy", "offers": []},
        {
            "id": "p4",
            "title": "Priced in euros",
            "offers": [
                {
                    "domain": "d.example",
                    "price": {"price": 900, "currency": "eur"},
                    "availability": "InStock",
                }
            ],
        },
        {"id": "p5", "offers": [{"price": {"price": 5, "currency": "USD"}}]},
    ],
    "next_page_token": None,
}


def test_each_product_gets_its_best_offer_and_unusable_ones_are_dropped() -> None:
    products = parse_products(PAYLOAD)
    assert [p.id for p in products] == ["p1", "p2", "p4"]  # no offers, and no title, are dropped
    first = products[0]
    # The cheaper offer is out of stock, so the in-stock one is the real price.
    assert (first.price, first.retailer, first.brand, first.image_url) == (
        249.99,
        "a.example",
        "Yamaha",
        "https://img.example/1.jpg",
    )
    assert products[1].image_url == "https://img.example/2.jpg"  # an image object works too
    assert products[2].currency == "EUR"


def test_the_summary_uses_the_main_currency_only() -> None:
    stats = summarise(parse_products(PAYLOAD))
    assert stats is not None
    assert (stats.currency, stats.low, stats.median, stats.high) == ("USD", 250, 299, 349)
    assert summarise([]) is None


def test_a_prefers_new_in_stock_then_any_in_stock_then_anything() -> None:
    def offer(price: float, availability: str, condition: str) -> dict:  # type: ignore[type-arg]
        return {
            "domain": "x",
            "price": {"price": price, "currency": "USD"},
            "availability": availability,
            "condition": condition,
        }

    def best(*offers: dict) -> float:  # type: ignore[type-arg]
        return parse_products({"products": [{"id": "1", "title": "t", "offers": list(offers)}]})[
            0
        ].price

    assert best(offer(50, "InStock", "used"), offer(80, "InStock", "new")) == 80
    assert best(offer(50, "OutOfStock", "new"), offer(80, "InStock", "used")) == 80
    assert best(offer(50, "OutOfStock", "new"), offer(40, "OutOfStock", "new")) == 40


def client_for(handler) -> Channel3Client:  # type: ignore[no-untyped-def]
    return Channel3Client("test-key", transport=httpx.MockTransport(handler))


async def test_the_search_sends_the_key_and_the_query_to_the_right_place() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=PAYLOAD)

    result = await client_for(handler).search("yamaha fg800")
    request = seen[0]
    assert (request.method, request.url.path, request.headers["x-api-key"]) == (
        "POST",
        "/v1/search",
        "test-key",
    )
    assert b"yamaha fg800" in request.content
    assert result.stats is not None and result.stats.median == 299


@pytest.mark.parametrize(
    ("status", "words"),
    [(429, "busy"), (401, "not set up"), (403, "not set up"), (500, "could not answer")],
)
async def test_failures_become_safe_messages(status: int, words: str) -> None:
    with pytest.raises(MarketError, match=words):
        await client_for(
            lambda request: httpx.Response(status, json={"detail": "secret detail"})
        ).search("x")


async def test_an_unreachable_service_is_reported_not_raised_raw() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    with pytest.raises(MarketError, match="could not be reached"):
        await client_for(handler).search("x")


class DictCache:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.expiry: dict[str, int | None] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key], self.expiry[key] = value, ex


class BrokenCache:
    async def get(self, key: str) -> str | None:
        raise ConnectionError("down")

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        raise ConnectionError("down")


async def test_a_repeated_search_costs_one_credit_and_expires() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=PAYLOAD)

    cache, client = DictCache(), client_for(handler)
    first = await cached_search(client, cache, "t", "Yamaha  FG800")
    again = await cached_search(
        client, cache, "t", "yamaha fg800"
    )  # same search, different spacing and case
    assert calls == 1 and again == first and isinstance(again, MarketResult)
    assert list(cache.expiry.values()) == [3600]
    assert normalise("  A   b ") == "a b"


async def test_a_broken_cache_never_breaks_the_search() -> None:
    result = await cached_search(
        client_for(lambda r: httpx.Response(200, json=PAYLOAD)), BrokenCache(), "t", "guitar"
    )
    assert len(result.products) == 3
