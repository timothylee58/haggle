# Open risks

The Week 1 gate **passed against the PayPal sandbox** on 2026-11-09. All three Shield endings ran for real:

- Capture: MYR 768 authorized, shipped, delivered, captured, tracking read back.
- Void: a MYR 768 hold placed and then voided, nothing captured.
- Refund: MYR 888 captured and refunded in full. The MYR 768 capture was also refunded by hand afterwards.

Things the sandbox taught us:

- Orders need a `return_url`, or the buyer's approval is never recorded.
- The buyer must be the sandbox Personal account, not the account that owns the API keys.
- Tracking is refused on an authorization and accepted after capture.

| Risk | State | Next step or fallback |
|---|---|---|
| Authorize then capture fails in the sandbox | Closed: passed | None |
| Sandbox blocks us altogether | Closed: it did not | None |
| Sandbox merchant refuses MYR | Closed: MYR works | None |
| Tracking refused on an authorization | Closed: confirmed, already handled | Tracking is sent after capture |
| Tracking read-back returns nothing | Closed: read back after capture | None |
| MCP or toolkit lacks authorize-only | Decided: stay on REST (see ADR 1, based on docs, no live MCP trial) | Revisit if MCP gains authorize, void and capture-later tools |
| Return URL points at localhost | Fixed in code: per-deal page. `FRONTEND_URL` must be set for any public demo | Set `FRONTEND_URL` |
| Real Claude agents behave differently from rule agents | Tested on 2026-11-10 with `claude-sonnet-5-5` on 3 deals (guitar, bike, tight-overlap laptop): all closed inside both caps. Early runs lowballed and named insulting numbers because the prompt never listed the face rules; fixed. Claude can still pay near the cap (bike: 588 on a 450 to 600 range), and only 3 runs were checked. | Run more deals with `scripts.run_negotiation --llm` before trusting the average. Code still enforces caps and prices. |
| Deadlines are placeholders | Open | Tune `Deadlines` to the real authorization window. |
| Shield routes have no login | Mitigated: Shield actions need the owner token returned at match start (only its hash is stored). Spectators can watch only. Tested; checked in the browser. | The token lives in the starting browser's storage, so losing it loses control of that match. There are still no accounts. |
| Public demo abuse or surprise Claude bill | Mitigated: per-IP match and price-check limits, a daily Claude cap (`LLM_MATCHES_PER_DAY`, 0 turns Claude off). Limits fail open if Redis is down. | Set the cap to what you will pay for. Not load tested. |
| Channel3 response shape | Open: built from the documented shape and tested only against a local stand-in. Never called live. | First real search with a key. Field mapping is in `parse_products` (`services/api/app/market.py`). |
| Render deploy | Open: `render.yaml` validates against Render's schema but has never been deployed. | Follow docs/deploy.md. `FRONTEND_URL` and `NEXT_PUBLIC_API_URL` need the real addresses, and the web app must be rebuilt after changing the latter. |
