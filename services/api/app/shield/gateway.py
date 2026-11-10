"""One gateway interface, with fake and PayPal sandbox implementations."""

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.config import PAYPAL_SANDBOX_URL, settings
from app.engine.policy import SpendGuard


class GatewayError(Exception):
    pass


@dataclass(frozen=True)
class CreatedOrder:
    order_id: str
    approve_url: str | None


def to_decimal_string(amount_minor: int) -> str:
    return f"{amount_minor // 100}.{amount_minor % 100:02d}"


class PaymentGateway(Protocol):
    async def create_order(
        self,
        amount_minor: int,
        currency: str,
        guard: SpendGuard,
        key: str,
        return_url: str | None = None,
    ) -> CreatedOrder: ...
    async def authorize_order(self, order_id: str, key: str) -> str: ...
    async def capture(
        self, authorization_id: str, amount_minor: int, currency: str, guard: SpendGuard, key: str
    ) -> str: ...
    async def void(self, authorization_id: str, key: str) -> None: ...
    async def refund(self, capture_id: str, key: str) -> str: ...
    async def create_shipment_tracking(
        self, order_id: str, capture_id: str, tracking_number: str, carrier: str, key: str
    ) -> None: ...
    async def get_shipment_tracking(self, order_id: str) -> list[str]: ...


class FakeGateway:
    """Offline fallback. Same key returns the same result, like PayPal-Request-Id."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_tracking = False
        self.return_urls: list[str | None] = []
        self._results: dict[str, Any] = {}
        self._tracking: dict[str, list[str]] = {}

    def _once(self, op: str, key: str, value: Any) -> Any:
        scoped = f"{op}:{key}"
        if scoped not in self._results:
            self.calls.append(op)
            self._results[scoped] = value
        return self._results[scoped]

    async def create_order(
        self,
        amount_minor: int,
        currency: str,
        guard: SpendGuard,
        key: str,
        return_url: str | None = None,
    ) -> CreatedOrder:
        guard.check(amount_minor)
        self.return_urls.append(return_url)
        order = CreatedOrder(f"ORDER-{key}", None)
        result: CreatedOrder = self._once("create_order", key, order)
        return result

    async def authorize_order(self, order_id: str, key: str) -> str:
        return str(self._once("authorize", key, f"AUTH-{key}"))

    async def capture(
        self, authorization_id: str, amount_minor: int, currency: str, guard: SpendGuard, key: str
    ) -> str:
        guard.check(amount_minor)
        return str(self._once("capture", key, f"CAP-{key}"))

    async def void(self, authorization_id: str, key: str) -> None:
        self._once("void", key, None)

    async def refund(self, capture_id: str, key: str) -> str:
        return str(self._once("refund", key, f"REF-{key}"))

    async def create_shipment_tracking(
        self, order_id: str, capture_id: str, tracking_number: str, carrier: str, key: str
    ) -> None:
        if self.fail_tracking:
            raise GatewayError("tracking rejected")
        if f"tracking:{key}" not in self._results:
            self._tracking.setdefault(order_id, []).append(tracking_number)
        self._once("tracking", key, None)

    async def get_shipment_tracking(self, order_id: str) -> list[str]:
        return list(self._tracking.get(order_id, []))


class PayPalGateway:
    """PayPal Orders v2 and Payments v2. The base URL is fixed to the sandbox."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        transport: httpx.AsyncBaseTransport | None = None,
        return_url: str | None = None,
    ) -> None:
        self._auth = (client_id, client_secret)
        self._return_url = return_url or f"{settings.frontend_url}/"
        self._client = httpx.AsyncClient(
            base_url=PAYPAL_SANDBOX_URL, transport=transport, timeout=30
        )
        self._token: str | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _access_token(self) -> str:
        if self._token is None:
            response = await self._client.post(
                "/v1/oauth2/token",
                auth=self._auth,
                data={"grant_type": "client_credentials"},
            )
            if response.is_error:
                raise GatewayError(f"oauth failed: {response.status_code}")
            self._token = str(response.json()["access_token"])
        return self._token

    async def _post(self, path: str, key: str, body: dict[str, Any] | None = None) -> Any:
        headers = {
            "Authorization": f"Bearer {await self._access_token()}",
            "PayPal-Request-Id": key,
            "Prefer": "return=representation",
        }
        response = await self._client.post(path, json=body or {}, headers=headers)
        if response.status_code == 401:
            self._token = None
            headers["Authorization"] = f"Bearer {await self._access_token()}"
            response = await self._client.post(path, json=body or {}, headers=headers)
        if response.is_error:
            raise GatewayError(f"POST {path} -> {response.status_code}: {response.text}")
        return response.json() if response.content else {}

    async def create_order(
        self,
        amount_minor: int,
        currency: str,
        guard: SpendGuard,
        key: str,
        return_url: str | None = None,
    ) -> CreatedOrder:
        guard.check(amount_minor)
        back = return_url or self._return_url
        data = await self._post(
            "/v2/checkout/orders",
            key,
            {
                "intent": "AUTHORIZE",
                "purchase_units": [
                    {
                        "amount": {
                            "currency_code": currency,
                            "value": to_decimal_string(amount_minor),
                        }
                    }
                ],
                "payment_source": {
                    "paypal": {
                        "experience_context": {
                            "return_url": back,
                            "cancel_url": back,
                            "user_action": "PAY_NOW",
                        }
                    }
                },
            },
        )
        links = {link["rel"]: link["href"] for link in data.get("links", [])}
        return CreatedOrder(data["id"], links.get("approve") or links.get("payer-action"))

    async def authorize_order(self, order_id: str, key: str) -> str:
        data = await self._post(f"/v2/checkout/orders/{order_id}/authorize", key)
        payments = data["purchase_units"][0]["payments"]
        return str(payments["authorizations"][0]["id"])

    async def capture(
        self, authorization_id: str, amount_minor: int, currency: str, guard: SpendGuard, key: str
    ) -> str:
        guard.check(amount_minor)
        data = await self._post(
            f"/v2/payments/authorizations/{authorization_id}/capture",
            key,
            {
                "amount": {"currency_code": currency, "value": to_decimal_string(amount_minor)},
                "final_capture": True,
            },
        )
        return str(data["id"])

    async def void(self, authorization_id: str, key: str) -> None:
        await self._post(f"/v2/payments/authorizations/{authorization_id}/void", key)

    async def refund(self, capture_id: str, key: str) -> str:
        data = await self._post(f"/v2/payments/captures/{capture_id}/refund", key)
        return str(data["id"])

    async def create_shipment_tracking(
        self, order_id: str, capture_id: str, tracking_number: str, carrier: str, key: str
    ) -> None:
        await self._post(
            f"/v2/checkout/orders/{order_id}/track",
            key,
            {"capture_id": capture_id, "tracking_number": tracking_number, "carrier": carrier},
        )

    async def get_shipment_tracking(self, order_id: str) -> list[str]:
        response = await self._client.get(
            f"/v2/checkout/orders/{order_id}",
            headers={"Authorization": f"Bearer {await self._access_token()}"},
        )
        if response.is_error:
            raise GatewayError(f"GET order -> {response.status_code}: {response.text}")
        return [
            str(tracker["id"])
            for unit in response.json().get("purchase_units", [])
            for tracker in unit.get("shipping", {}).get("trackers", [])
        ]
