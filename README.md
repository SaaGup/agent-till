# Agent Till

**The merchant till that AI agents can use — and never overspend.**

Built for the Razorpay AI Buildathon, Track 01 (AI Growth & Agentic Commerce).

A merchant backend that is transactable by an AI buyer end to end, plus a growth co-pilot that
proposes bounded upsells during checkout. Every money-affecting action is **explainable**
(carries a plain-English reason), **bounded** (capped by a server-side policy engine the model
cannot argue with), **gated** (held for human approval past a threshold), and **audited**
(written to an append-only trail with the policy snapshot in force at the time).

---

## The idea

Agent-to-agent commerce has an obvious hole in it: the moment you let a model spend money, you
need something other than the model deciding how much it may spend. Prompts are not a control
surface — they are a suggestion. So the interesting part of making a merchant "sellable to AI
buyers" isn't the chat window, it's the layer underneath that stays trustworthy when the model
is confused, jailbroken, or simply wrong.

Agent Till is that layer, wrapped around a working storefront:

- The merchant exposes its catalog and checkout over **MCP**, so any agent can transact with it.
- An **AI buyer** browses, chooses and checks out on a shopper's behalf.
- A **growth co-pilot** proposes an add-on and a discount — and the policy engine clamps it.
- A **policy engine** enforces limits server-side, independent of anything the model says.
- An **audit trail** records why each decision went the way it did.

## Architecture

```
                    ┌──────────────────────────────────────────┐
   Browser ────────▶│  React + Tailwind  (Vercel)              │
                    │  chat · tool trace · dashboard · audit   │
                    └────────────────┬─────────────────────────┘
                                     │  REST + SSE
                    ┌────────────────▼─────────────────────────┐
                    │  FastAPI  (Render)                       │
                    │                                          │
                    │  ┌────────────┐      ┌────────────────┐  │
                    │  │ AI Buyer   │      │ Growth         │  │
                    │  │ agent      │      │ co-pilot       │  │
                    │  └─────┬──────┘      └───────┬────────┘  │
                    │        │  MCP (loopback)     │           │
                    │  ┌─────▼─────────────────────▼────────┐  │
                    │  │  MCP tool server (FastMCP)         │  │
                    │  │  search · product · intent · status│  │
                    │  └─────┬──────────────────────────────┘  │
                    │        │                                 │
                    │  ┌─────▼──────┐  ┌──────────┐  ┌──────┐  │
                    │  │  Policy    │  │  Audit   │  │Razor-│  │
                    │  │  engine    │  │  log     │  │pay   │  │
                    │  └────────────┘  └──────────┘  └───┬──┘  │
                    └──────────────────────────────────┬─┼─────┘
                                     │                 │ │
                            ┌────────▼──────┐    ┌─────▼─┴──────┐
                            │ Postgres (Neon)│   │  Razorpay    │
                            └────────────────┘   │  test mode   │
                                                 └──────┬───────┘
                                     webhook ◀──────────┘
```

The MCP server runs inside the FastAPI process bound to loopback: the agents that call it live
in the same process, so it never needs a public port — but it still speaks the real protocol,
which is what makes the merchant genuinely agent-callable rather than merely well-factored.

## What the guardrails actually do

All of this is plain Python in [`app/policy/engine.py`](backend/app/policy/engine.py), running
server-side inside the payment path. The model can request anything; these numbers decide.

| Guardrail | Default | Behaviour |
|---|---|---|
| Discount cap | 20% | Clamped. A 35% request becomes 20%, and the shopper is told. |
| Per-transaction cap | ₹5,000 | **Blocked** outright. |
| Session spend cap | ₹8,000 | **Blocked** — bounds one session's total blast radius, not just one order. |
| Approval threshold | ₹3,000 | **Gated** — held for a human merchant to approve or deny. |
| First-time buyer | — | **Gated**, regardless of amount. |
| Tool calls per turn | 8 | Circuit breaker trips; the agent stops and says so. |
| Consecutive tool errors | 3 | Circuit breaker trips. |

Two distinct failure modes on purpose: *bounded* (blocked outright) and *gated* (held for a
human) are different behaviours, and a reviewer can see both in the audit trail.

## Engineering decisions

**Payment confirmation is not something the agent can do.** `confirm_payment` reads status; it
never charges. Card details go from the shopper's browser to Razorpay Checkout directly and
never touch the agent or this backend — which keeps the whole system out of PCI scope, and is
the structural reason a human completes the payment step. This is a design property, not a
missing feature.

**Idempotency is enforced application-side.** Razorpay's Orders API has no idempotency header
(that exists only for Payouts). So a hash of `(session, cart, discount)` is stored as a unique
key on the local order, and a repeat call returns the existing order rather than creating a
second one at the gateway.

**The webhook is the source of truth, not the browser callback.** Both paths converge on one
idempotent `mark_paid`, so whichever arrives first wins and the second is a no-op. The client
callback exists only so the UI can update immediately; a dropped or forged callback can't move
an order to paid, because the webhook signature is verified over the raw request body before
any state changes.

**The agent loop is hand-rolled rather than a turnkey SDK runner.** Every tool call has to pass
through the circuit breaker and stream to the UI as it happens. The visible tool trace is the
product, not an implementation detail.

**The model provider is a config line.** Tool-calling is normalised behind a small interface
([`app/agents/llm.py`](backend/app/agents/llm.py)), so Gemini, Groq, Cerebras, OpenRouter or
Claude are swappable without touching the agent, the policy engine or the audit trail. The
default runs on a free tier.

**The audit log is written synchronously, never batched.** A crash must not be able to lose the
record of a money-affecting decision.

## Hardening

This runs on a public URL, so it is treated as internet-facing rather than demo-safe:

- CORS locked to the deployed frontend origin — never `*`.
- Per-IP rate limits on the chat and payment endpoints, so a public link can't be used to burn
  API budget or spam test orders.
- Chat message length capped server-side, bounding token spend per request regardless of what
  the client sends.
- Stack traces never returned to clients; full detail logged server-side as structured JSON.
- The demo failure-injection endpoint sits behind a shared-secret header — it deliberately
  breaks catalog state and must not be publicly triggerable.
- Secrets only ever from the environment; `.env` is gitignored and has never been committed.
- Dependencies pinned, with a `pip-audit` step in CI.

## Running it locally

```bash
git clone https://github.com/SaaGup/agent-till && cd agent-till
```

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
```

Copy `backend/.env.example` to `backend/.env` and fill in a Razorpay **test-mode** key pair and
a model API key (the default is Gemini's free tier — [get one here](https://aistudio.google.com/apikey)).
Without a model key everything still runs; only the agent chat is inert. Without Razorpay keys,
a built-in fake client stands in so the full policy/audit flow stays runnable.

```bash
cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

Tests:

```bash
cd backend && .venv/Scripts/python -m pytest -q
```

## Deploying

Backend on **Render** (free tier) via the committed `render.yaml`, database on **Neon** (free,
and unlike Render's free Postgres it doesn't expire after 30 days), frontend on **Vercel**
(free). Set the secrets listed in `render.yaml` in the Render dashboard, point the frontend's
`VITE_API_BASE` at the Render URL, and register the Razorpay webhook against
`https://<your-render-url>/webhooks/razorpay`.

> Render's free tier sleeps after 15 minutes idle and takes about a minute to wake. Warm the URL
> before a demo.

## Stack

FastAPI · SQLAlchemy · Alembic · Postgres (Neon) · FastMCP · Razorpay · React · TypeScript ·
Tailwind · pytest · GitHub Actions · Render · Vercel
