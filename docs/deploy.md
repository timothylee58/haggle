# Deploy on Render

`render.yaml` at the repo root is a Render Blueprint. It creates four things in one go:

| Resource | Type | What it does |
|---|---|---|
| `haggle-api` | Web service (Python) | FastAPI. Runs migrations before each deploy. Health check at `/health`. |
| `haggle-web` | Web service (Node) | The Next.js app. |
| `haggle-db` | Postgres 17 | The source of truth for every deal and payment event. |
| `haggle-redis` | Key Value (Redis) | Wakes the event stream up, holds rate-limit counters and the price-check cache. Losing it loses nothing important. |

The blueprint was checked against Render's published schema (`https://render.com/schema/render.yaml.json`, zero errors). It has **not** been deployed yet: that needs your Render account.

## Cost

- `haggle-api` and `haggle-web` use Render's smallest paid instance (no `plan` is set). Free web services sleep after 15 idle minutes and take about a minute to wake, which a judge would read as a broken demo. `preDeployCommand` (migrations) is also not available on free instances.
- `haggle-redis` is on the free plan.
- `haggle-db` uses Render's default Postgres plan. Free Postgres expires after 30 days, so check the plan on the dashboard before submitting.

Check current prices on Render's pricing page before you click Apply.

To run on free instances anyway for a quick look: set `plan: free` on both web services, delete `preDeployCommand`, and put `uv run alembic upgrade head &&` in front of the API's `startCommand`. Expect cold starts.

## Steps

1. Push this repo to GitHub (done: it is public).
2. In Render: **New > Blueprint**, pick the repo, and Render reads `render.yaml`.
3. Render asks for the values marked `sync: false`. Fill what you have, leave the rest blank:
   - `FRONTEND_URL`: the web app's address. You do not know it yet. Put a placeholder like `https://haggle-web.onrender.com` (Render's default is `https://<service-name>.onrender.com`, and a name clash gets a suffix) and fix it in step 5 if it differs.
   - `NEXT_PUBLIC_API_URL`: the API's address, for the same reason, e.g. `https://haggle-api.onrender.com`.
   - Optional keys: `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `ANTHROPIC_API_KEY`, `CHANNEL3_API_KEY`.
4. Click **Apply**. The database and Key Value start first, then the API (migrations run before it goes live), then the web app.
5. Open each service's page and copy its real `onrender.com` address. If either differs from what you typed, correct `FRONTEND_URL` on the API and `NEXT_PUBLIC_API_URL` on the web app, then **redeploy the web app**. `NEXT_PUBLIC_API_URL` is baked in when Next.js builds, so changing it without a rebuild does nothing.
6. Visit `<api>/health` (expect `{"status":"ok"}`) and `<api>/features`, then the web app, and start a match.

## Environment variables

API (`haggle-api`):

| Variable | Set by | Notes |
|---|---|---|
| `DATABASE_URL` | Blueprint, from `haggle-db` | Render gives `postgres://...`; the API rewrites it to the asyncpg driver itself. |
| `REDIS_URL` | Blueprint, from `haggle-redis` | |
| `FRONTEND_URL` | You | Used for CORS and as PayPal's return address. No trailing slash needed. |
| `LLM_MATCHES_PER_DAY` | Blueprint (25) | Daily cap on Claude matches for the whole server. `0` turns Claude off. |
| `MATCHES_PER_HOUR_PER_IP` | Optional (30) | Match starts per visitor per hour. |
| `MARKET_CHECKS_PER_HOUR_PER_IP` | Optional (60) | Price checks per visitor per hour. |
| `ANTHROPIC_API_KEY` | You, optional | Blank: the "Use Claude" switch is disabled and agents are rule-based. |
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | You, optional | Blank: simulated payments. Set: PayPal **sandbox** (the code refuses anything else). |
| `CHANNEL3_API_KEY` | You, optional | Blank: the price-check box is hidden. |

Web (`haggle-web`): `NEXT_PUBLIC_API_URL` and `NODE_VERSION`.

## Choose the payments mode for the public demo

- **Simulated** (leave the PayPal keys blank). Every judge can click through the whole Shield with no account. The panel is badged "Simulated payments" so nobody is misled. This is the safest default.
- **PayPal sandbox** (set both keys). The real approve, hold, ship, capture flow. A visitor needs a sandbox buyer login to approve the hold, so put those credentials in the Devpost testing instructions. Nothing real moves, but the owner-token rule below still applies.

## What protects a public demo

- **Shield actions are owner-only.** Starting a match returns a random token once. The browser keeps it and sends it as `x-deal-token`; the server stores only its SHA-256 hash. Anyone else who opens the link can watch but not approve, ship, capture, cancel or refund. Clearing browser storage or switching browsers loses control of that match, by design.
- **Rate limits.** Per-IP match starts and price checks per hour, backed by Key Value. If Key Value is down the limits fail open rather than taking the app down.
- **Claude spend cap.** `LLM_MATCHES_PER_DAY` caps Claude matches across everyone. Set it to what you are happy to pay for.
- **`GET /features`** tells the web app what is switched on (`claude`, `market_price`, `payments`) so it never offers something that would fail.

## Channel3 price check

Channel3 searches product data across many retailers. Haggle uses it for one job: a "Check real prices" box on the start form that turns an item name into real products and prices, then offers to prefill the opening ask, seller floor and buyer budgets from a market price. The pick is saved on the match as a reference line shown to spectators, for example "deal is 30% below retail". **It never decides a price.** Prices stay in code.

Setup:

1. Get a key at <https://trychannel3.com/developers>. The hackathon promo code is `PAYPAL-HACKATHON-2026`.
2. Set `CHANNEL3_API_KEY` on `haggle-api` (Render dashboard > haggle-api > Environment). Locally, put it in `services/api/.env`.
3. Open `<api>/features`: `"market_price": true` means it is on.
4. Search for something on `/play`.

Behaviour: the key stays on the server; each distinct search is cached for an hour (one credit per search per hour); the best in-stock, new offer per product is used; low, median and high are computed in the currency most results use. Errors show a plain message (busy, not set up, unreachable) and never block starting a match.

**Honest status:** the integration is tested against a local stand-in shaped like Channel3's documented response, not against the live service, because no key was available when it was built. The first real search is the real test. If the field names differ, the fix is in `parse_products` in `services/api/app/market.py`.

## After deploying

- Run a match with `use_llm` on and watch the `LLM_MATCHES_PER_DAY` counter work: the Claude switch should disable itself once the cap is hit.
- Open a match link in a private window and confirm the Shield shows "You're watching" with no action buttons.
- The first request after a long idle can be slow on any plan that sleeps.
