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
| Shield routes have no login | Open | Anyone with a deal link can act on it. Fix before any public demo. |
