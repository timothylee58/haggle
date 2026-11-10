"""Probes real PayPal sandbox behaviour. Sandbox only.

uv run python -m scripts.sandbox_spike [--capture] [--currency MYR]
"""

import argparse
import asyncio
import uuid

from app.config import settings
from app.engine.policy import SpendGuard
from app.shield.gateway import GatewayError, PayPalGateway

AMOUNT_MINOR = 88800


async def main(capture: bool, currency: str) -> None:
    if not settings.paypal_client_id or not settings.paypal_client_secret:
        raise SystemExit("Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env")
    run = uuid.uuid4().hex[:10]
    guard = SpendGuard(cap_minor=AMOUNT_MINOR, approved=True)
    gateway = PayPalGateway(settings.paypal_client_id, settings.paypal_client_secret)
    try:
        order = await gateway.create_order(AMOUNT_MINOR, currency, guard, f"{run}-order")
        print(f"[ok] order {order.order_id} in {currency}\nApprove as the sandbox buyer:")
        print(f"  {order.approve_url}")
        await asyncio.to_thread(input, "Press Enter after approving... ")

        auth_id = await gateway.authorize_order(order.order_id, f"{run}-auth")
        print(f"[ok] authorization {auth_id}")

        async def probe(label: str, target_id: str) -> None:
            try:
                await gateway.create_shipment_tracking(
                    order.order_id, target_id, f"SPIKE{run}", "OTHER", f"{run}-{label}"
                )
                print(f"[ok] tracking accepted {label}")
            except GatewayError as error:
                print(f"[rejected] tracking {label}: {error}")

        await probe("on-authorization", auth_id)
        if capture:
            capture_id = await gateway.capture(
                auth_id, AMOUNT_MINOR, currency, guard, f"{run}-capture"
            )
            print(f"[ok] capture {capture_id}")
            await probe("on-capture", capture_id)
            print(f"[ok] refund {await gateway.refund(capture_id, f'{run}-refund')}")
        else:
            await gateway.void(auth_id, f"{run}-void")
            print("[ok] void")
    finally:
        await gateway.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--currency", default="MYR")
    args = parser.parse_args()
    asyncio.run(main(args.capture, args.currency))
