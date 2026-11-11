"""Real-world prices from Channel3, so a haggle starts from what the thing actually costs.

Channel3 searches product data across thousands of retailers (https://channel3.ai/docs). We use it for
one job: turn a typed item name into a handful of real products with real prices, so the seller's ask
and the buyer's budget can start from a market price and a deal can be judged against it.

The API key stays on the server. Results are cached, because every search costs a credit.
"""

import json
import logging
from dataclasses import asdict, dataclass
from statistics import median
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

CACHE_SECONDS = 3600
MAX_PRODUCTS = 6


class MarketError(Exception):
    """Channel3 could not answer. The message is safe to show to the person searching."""


@dataclass(frozen=True)
class MarketProduct:
    id: str
    title: str
    brand: str | None
    image_url: str | None
    price: float
    currency: str
    retailer: str | None
    url: str | None
    condition: str | None


@dataclass(frozen=True)
class MarketStats:
    currency: str
    low: int
    median: int
    high: int


@dataclass(frozen=True)
class MarketResult:
    query: str
    products: list[MarketProduct]
    stats: MarketStats | None

    def to_json(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "products": [asdict(p) for p in self.products],
            "stats": asdict(self.stats) if self.stats else None,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "MarketResult":
        stats = data.get("stats")
        return cls(
            query=data["query"],
            products=[MarketProduct(**p) for p in data["products"]],
            stats=MarketStats(**stats) if stats else None,
        )


def _image(images: Any) -> str | None:
    """Image entries may be plain URLs or objects that carry one."""
    if not isinstance(images, list) or not images:
        return None
    first = images[0]
    if isinstance(first, str):
        return first
    if isinstance(first, dict):
        url = first.get("url")
        return url if isinstance(url, str) else None
    return None


def _best_offer(offers: Any) -> dict[str, Any] | None:
    """The cheapest offer that is in stock and new, else the cheapest in stock, else the cheapest."""
    usable = [o for o in offers or [] if isinstance(o, dict) and isinstance(o.get("price"), dict)]
    usable = [
        o
        for o in usable
        if isinstance(o["price"].get("price"), int | float) and o["price"]["price"] > 0
    ]
    if not usable:
        return None

    def rank(offer: dict[str, Any]) -> tuple[int, float]:
        in_stock = str(offer.get("availability", "")).lower() == "instock"
        new = str(offer.get("condition", "new")).lower() == "new"
        return (0 if in_stock and new else 1 if in_stock else 2, float(offer["price"]["price"]))

    return min(usable, key=rank)


def parse_products(payload: dict[str, Any]) -> list[MarketProduct]:
    products: list[MarketProduct] = []
    for item in payload.get("products", []):
        if not isinstance(item, dict) or not item.get("title"):
            continue
        offer = _best_offer(item.get("offers"))
        if offer is None:
            continue
        price = offer["price"]
        brands = item.get("brands") or []
        products.append(
            MarketProduct(
                id=str(item.get("id", "")),
                title=str(item["title"])[:160],
                brand=str(brands[0]["name"])
                if brands and isinstance(brands[0], dict) and brands[0].get("name")
                else None,
                image_url=_image(item.get("images")),
                price=float(price["price"]),
                currency=str(price.get("currency") or "USD").upper()[:3],
                retailer=offer.get("domain") if isinstance(offer.get("domain"), str) else None,
                url=offer.get("url") if isinstance(offer.get("url"), str) else None,
                condition=offer.get("condition")
                if isinstance(offer.get("condition"), str)
                else None,
            )
        )
    return products[:MAX_PRODUCTS]


def summarise(products: list[MarketProduct]) -> MarketStats | None:
    """Low, median and high in the currency most results use. Prices in other currencies are left out."""
    if not products:
        return None
    currencies = [p.currency for p in products]
    main = max(set(currencies), key=currencies.count)
    prices = [p.price for p in products if p.currency == main]
    return MarketStats(main, round(min(prices)), round(median(prices)), round(max(prices)))


class Channel3Client:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.trychannel3.com",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, transport=transport, timeout=15)
        self._headers = {"x-api-key": api_key, "content-type": "application/json"}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def search(self, query: str, limit: int = 10) -> MarketResult:
        try:
            response = await self._client.post(
                "/v1/search", headers=self._headers, json={"query": query, "limit": limit}
            )
        except httpx.HTTPError as error:
            logger.warning("channel3 request failed: %s", error)
            raise MarketError("The price service could not be reached. Try again.") from error
        if response.status_code == 429:
            raise MarketError("The price service is busy. Try again in a few seconds.")
        if response.status_code in (401, 403):
            logger.error("channel3 rejected the API key (%s)", response.status_code)
            raise MarketError("The price service is not set up correctly on this server.")
        if response.is_error:
            logger.warning("channel3 returned %s", response.status_code)
            raise MarketError("The price service could not answer that search.")
        products = parse_products(response.json())
        return MarketResult(query, products, summarise(products))


class Cache(Protocol):
    async def get(self, key: str) -> bytes | str | None: ...
    async def set(self, key: str, value: str, ex: int | None = None) -> object: ...


def normalise(query: str) -> str:
    return " ".join(query.lower().split())


async def cached_search(
    client: Channel3Client, cache: Cache, prefix: str, query: str
) -> MarketResult:
    """One credit per distinct search per hour. A broken cache never breaks the search."""
    key = f"{prefix}:market:{normalise(query)}"
    try:
        hit = await cache.get(key)
        if hit:
            return MarketResult.from_json(json.loads(hit))
    except Exception:
        logger.warning("market cache read failed", exc_info=True)
    result = await client.search(query)
    try:
        await cache.set(key, json.dumps(result.to_json()), ex=CACHE_SECONDS)
    except Exception:
        logger.warning("market cache write failed", exc_info=True)
    return result
