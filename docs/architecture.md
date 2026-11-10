# Architecture decisions

## ADR 1: PayPal through direct REST, not MCP

Status: **decided** on 2026-11-10.

Decision: every money call goes through `PayPalGateway`, which calls PayPal Orders v2 and Payments v2 directly. The PayPal MCP server and Agent Toolkit are not used.

What the sandbox runs proved for REST (2026-11-09): authorize-only orders, capture after delivery, void, full refund, tracking after capture and reading it back. Each money call carries our own `PayPal-Request-Id`, so a retry cannot move money twice.

Why not MCP:

- **Authorize-only is not documented.** The official MCP tools describe creating an order and paying it, which captures at once. I found no official authorize, void or capture-later tool. Kena Shield depends on holding funds until delivery, so this is the deciding gap. Third-party MCP servers do expose authorize and capture, but those are not PayPal's.
- **Idempotency is unconfirmed.** PayPal advises sending `PayPal-Request-Id` on any call that creates or modifies data ([PayPal idempotency guide](https://developer.paypal.com/api/rest/reference/idempotency/)). I found nothing saying the MCP tools accept or set it, and a retried capture is the case where it matters.
- **An extra layer in the money path.** A tool-calling hop adds a place for failures and for an agent to choose arguments. Here only `ShieldService` reaches the gateway, and the buyer and seller agents have no payment tools at all.
- **Comparisons favour the API for deterministic payment flows.** See [Scalekit's PayPal MCP versus API write-up](https://www.scalekit.com/blog/paypal-mcp-vs-api).

Limits of this decision, stated plainly:

- It rests on documentation and on REST working, **not on a live MCP trial**. The PayPal MCP connector was not authorized in this session, so no MCP call was made, and the week-1 step of calling it from an orchestrator node was not done.
- Revisit it only if the official MCP server gains authorize, void and capture-later tools that accept an idempotency key. Until then REST stays.

## Delivery confirmation

The demo confirms delivery with a buyer button. There is no carrier check.

## Tracking

PayPal refuses tracking on an authorization alone (`CAPTURE_ID_NOT_FOUND`) and accepts it after capture. So tracking stays in our records while the hold is open and goes to PayPal right after capture, which is what `ShieldService.capture` does.

## Return URL

PayPal records a buyer's approval only when the order carries a `return_url`. `DealDesk` sets it to the deal's own page, `{FRONTEND_URL}/deals/{deal_id}`, so the buyer lands back on that deal's Shield panel. `FRONTEND_URL` defaults to `http://localhost:3000` and must be set to the real site before any public demo.

## Replay

Rule agents are deterministic, so running them is the seeded mode: the same config always gives the same negotiation (`tests/test_gate.py`). No separate replay file exists.
