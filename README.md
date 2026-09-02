# Agent-Ready Storefront with a Growth Co-Pilot

Built for the Razorpay AI Buildathon — Track 01 (AI Growth & Agentic Commerce).

> Status: in progress. This README is being filled in as the project is built — see the plan/architecture notes below, which will be replaced with final content (live URLs, setup steps, demo script, engineering decisions) as each piece lands.

## What this is

A merchant backend that is transactable by an AI buyer end-to-end, plus a growth co-pilot agent that proposes bounded upsells during checkout — with every money-affecting action explainable, bounded by server-side policy, gated behind human approval where required, and logged to an immutable audit trail.

## Architecture (summary)

- **Backend**: FastAPI + Postgres (Alembic-migrated), with an MCP tool server embedded internally for agent access to the catalog/checkout.
- **Agents**: a Claude-powered "AI Buyer" agent and a "Growth Co-Pilot" agent, both calling the same MCP tools.
- **Payments**: Razorpay Orders API + Checkout.js, test mode only.
- **Policy engine**: server-side discount caps, transaction/session spend caps, human-approval gating, and a circuit breaker bounding agent tool-call/error behavior.
- **Frontend**: React + Tailwind, Razorpay-inspired visual identity.
- **Deployed**: backend on Railway, frontend on Vercel.

Full details will be added here as the build progresses.
