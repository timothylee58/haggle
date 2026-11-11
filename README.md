# Haggle

AI buyer and seller agents haggle over a price while you watch live, and the money is protected by design.
Built for the PayPal AI Hackathon.

**Principle: code decides, the LLM talks.** Prices, face, lucky numbers, budget caps and payment state are deterministic and unit-tested. The LLM only writes banter and proposes an intent that code validates.

## Architecture

```
frontend/ (Next.js) --SSE--> services/api/ (FastAPI)
                               |- app/negotiation/  LangGraph loop: buyer -> referee -> seller -> referee
                               |- app/engine/  face, lucky numbers, policy (pure Python, no I/O)
                               |- app/shield/  state machine + PayPal gateway + service
                               `- Postgres (deal events) + Redis (SSE fan-out)
```

### Kena Scam Shield

```
NEGOTIATED -> AUTHORIZED -> SHIPPED -> DELIVERED -> CAPTURED -> REFUNDED
                  |            |
                  `--(timeout / cancel)--> VOIDED
```

Funds are authorized, never captured, until delivery is confirmed. A missed ship or delivery deadline voids the hold. The service validates a transition before it touches the gateway.

### Guardrails

- `SpendGuard` in `engine/policy.py` holds the budget cap and human-approval toggle.
- Gateways re-check the guard, so a bug upstream cannot overspend.
- `PAYPAL_ENV` is a `Literal["sandbox"]` and the gateway URL is fixed to the sandbox.

## Status

| Piece | State |
|---|---|
| engine: lucky numbers, face, policy | done, tested |
| shield: state machine, service, gateways | done, tested against a fake gateway and a mocked PayPal |
| PayPal sandbox behaviour | **unverified, run the spike** |
| Event log and SSE API | done, tested against real Postgres and Redis |
| Finished deals connected to Shield, saved to the log, with a deadline sweep | done, tested against the fake gateway |
| LangGraph negotiation loop | done, tested with rule and scripted agents; real LLM **unverified** |
| Spectator UI | done, checked in the browser with rule agents |

## Run

Postgres and Redis run through Homebrew services on the dev Mac, or `docker compose up -d`.

```bash
cd services/api && cp .env.example .env && uv sync
createdb -h localhost -O haggle haggle_test  # once, for tests
uv run alembic upgrade head
uv run ruff check . && uv run mypy app && uv run pytest -q
uv run uvicorn app.main:app --reload
```

```bash
cd frontend && pnpm install && pnpm dev
```

The web app has three routes: `/` is the landing page, `/play` is the start form, and `/deals/{id}` is the live match and Shield panel. The landing page needs no API.

`tests/test_tuning.py` plays 30 rule-agent scenarios and checks that the deals, closing gap and face scores stay in range.

## API

- `POST /negotiations` with `item`, `budget_cap`, `seller_floor`, `opening_ask` starts a negotiation and returns `deal_id`. Add `"use_llm": true` for Claude.
- `GET /negotiations/{deal_id}/events` streams SSE events: `negotiation_started`, `turn`, `negotiation_ended`. Reconnects resume through `Last-Event-ID`.

- `/deals/{deal_id}/shield` reads the Shield state. POST to `/approve`, `/authorize`, `/ship`, `/deliver`, `/capture`, `/cancel` or `/refund` under it to act. **These routes have no login yet.**
- `GET /deals/{deal_id}/shield/events` streams a public view with no payment IDs.

## Watch a negotiation

```bash
cd services/api
uv run python -m scripts.run_negotiation        # offline rule agents
uv run python -m scripts.run_negotiation --llm  # needs ANTHROPIC_API_KEY
```

## Week 1 gate

```bash
cd services/api
uv run python -m scripts.gate                   # offline, fake gateway
uv run python -m scripts.gate --cancel          # offline, void path
uv run python -m scripts.gate --paypal          # real sandbox, the actual gate
```

Open risks are in [docs/risks.md](docs/risks.md), decisions in [docs/architecture.md](docs/architecture.md).

## Day 1 spike

```bash
cd services/api
uv run python -m scripts.sandbox_spike            # authorize, probe tracking, void
uv run python -m scripts.sandbox_spike --capture  # authorize, probe tracking, capture, refund
```

Questions it answers:

1. Does `create_shipment_tracking` accept an authorization-only transaction, or only a captured one? If not, keep tracking in our DB while the hold is open and push it to PayPal after capture (already how `ShieldService.capture` behaves).
2. Does the sandbox merchant accept MYR and SGD, or must the demo fall back to USD?
3. Is the buyer-approval redirect workable for a live demo? `FakeGateway` exists as an offline fallback.
4. What is the real authorization window? Tune `Deadlines` in `shield/state_machine.py` to it.
