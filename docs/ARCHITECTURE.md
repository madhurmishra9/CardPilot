# CardPilot architecture

```
┌────────────── React + Vite + Tailwind (SPA) ──────────────┐
│  Dashboard · Swipe Advisor · Redemption · Card Compare ·  │
│  Travel · Chat · Transactions · My Cards                  │
└───────────────────────────┬───────────────────────────────┘
                            │ REST (JSON), /api proxied by Vite in dev
┌───────────────────────────▼───────────────────────────────┐
│  FastAPI (backend/app)                                     │
│  routers/   cards · transactions · advisor · redemption ·  │
│             recommend · travel · chat · notifications      │
│  services/  rules_engine · redemption · categorize ·       │
│             ledger · recommend · travel · spend_profile ·  │
│             chat · notifications                            │
│  providers/ fare_provider (mock|amadeus) · llm_provider     │
│             (none|ollama|anthropic)                         │
│  parsers/   generic_csv · icici_pdf (registry)             │
│  scheduler/ APScheduler: daily fare polls + nudge scans    │
│  seed.py    idempotent seeding from /data on startup       │
└───────────────────────────┬───────────────────────────────┘
                            │ SQLAlchemy 2.0
                    ┌────────▼────────┐
                    │ SQLite (default)│  ← local-first
                    │ / Postgres via   │    CARDPILOT_DB_URL
                    └──────────────────┘
   card rules & redemption catalog: /data/**/*.yaml (versioned in git)
```

## The rules engine is the core asset

`backend/app/services/rules_engine.py` and `redemption.py` are **pure function
libraries** — zero I/O, zero DB access, fully unit-tested. Everything else is
plumbing around them:

- `points_earned(rules, category, amount, merchant)` — slab-based earn with
  exclusions, merchant-scoped rates and monthly caps.
- `transaction_net_value(...)` — net ₹ value of one swipe: points value +
  surcharge waiver + milestone-crossing bonus − transaction fees, with a
  human-readable explanation list.
- `rank_cards_for_spend(...)` — the Swipe Advisor.
- `milestone_bonus_total / next_milestone` — anniversary-year cumulative tiers
  with step bonuses and caps.
- `perk_gate_progress / effective_annual_fee` — spend-gated perks (lounge, BMS)
  and fee-waiver tracking.
- `redemption.batching_advice / break_even_points` — per-request fee
  amortization (the ₹99+GST fee is the single biggest destroyer of value).
- `redemption.expiry_alerts / redeem_vs_hold` — timing.

**Rules are data.** The engine receives a card's rules as a plain dict parsed
from `/data/cards/<card_id>.yaml`. No reward rate exists in Python code; the
test suite loads the same YAML files the app ships with.

## Data flow

1. **Ingest** (Module A): manual form, CSV upload (column-mapping wizard,
   mapping supplied per bank format), or ICICI PDF via the parser registry.
   Each row is categorized (learned merchant map > MCC > keywords >
   `retail_default`) and its points computed at insert time via the engine.
2. **Ledger** (Module B1): aggregates per user-card — points balance
   (earned + milestone bonuses − redeemed), anniversary-year and
   calendar-quarter spend, perk-gate progress.
3. **Swipe Advisor** (Module B2): `POST /api/advisor/swipe` ranks the user's
   cards by net value for a `(category, amount, merchant)` and surfaces
   milestone-aware nudges.
4. **Redemption Advisor** (Module C): `GET /api/redemption/advise/{card}`
   returns balance, fee break-even, batching warning, expiry alerts, ranked
   options net of fee, and a redeem-vs-hold decision with rationale.
   `POST /api/redemption/events` logs actual redemptions to learn true ₹/point.

## Privacy & security

- Local-first by default; the DB never leaves the machine.
- Only the last 4 digits of a card are stored — never the full PAN.
- No bank credentials anywhere (statement upload avoids this).
- Planned: SQLCipher / field-level encryption at rest; per-call redaction and
  explicit opt-in if a cloud LLM is ever used (Phase 5); DPDP Act review before
  any multi-user hosting.

## Phases 3–5 modules

- **Recommendation** (`services/recommend.py`, pure): simulates every catalog
  card on the user's annualized spend profile — earn (caps respected, honest
  caveats for merchant-restricted rates), milestones, quantified perks
  (spend-gated lounges only count when the gate is met), minus effective
  annual fee and amortized joining fee. `services/spend_profile.py` derives
  and persists the profile from real transactions.
- **Travel** (`services/travel.py`, pure + `providers/fare_provider.py`):
  `FareProvider` ABC with a deterministic offline mock (default) and an
  Amadeus stub. Quote history feeds `fare_trend_advice` (book_now / book_soon /
  wait); `best_card_for_booking` reuses the swipe ranker; `points_vs_cash`
  compares paths including redemption fee and opportunity cost.
- **Chat** (`services/chat.py` + `providers/llm_provider.py`): deterministic
  intent router (swipe / redeem / progress / recommend) calls the engines to
  build FACTS; the LLM provider only rephrases them. Grounding is enforced by
  construction — the model never sees card rules, only computed output, and
  every provider falls back to the raw facts on failure.
- **Notifications** (`services/notifications.py` + `scheduler.py`): live
  nudges (expiry, milestone, fee waiver, perk gates) computed on request;
  APScheduler (opt-in via `CARDPILOT_ENABLE_SCHEDULER=1`) persists fare-drop
  alerts and high-priority nudges daily.

## Remaining extension points

- Parser registry (`parsers/__init__.py`) — add per-issuer statement parsers.
- `AmadeusFareProvider` — wire OAuth2 + flight-offers once keys exist.
- Account Aggregator ingestion behind an `aa_provider` interface (v2).
- Email/Telegram delivery for notifications.
