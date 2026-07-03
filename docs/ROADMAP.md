# Roadmap

| Phase | Deliverable | Definition of done | Status |
|-------|-------------|--------------------|--------|
| 0 | Data foundation | Card-rules schema + Coral seed + 11 popular cards; rules engine unit-tested | ✅ done |
| 1 | Track + Earn Optimizer | Manual/CSV/PDF ingest, categorization, points ledger, Swipe Advisor | ✅ done |
| 2 | Redemption Advisor | Redemption catalog, fee/expiry/timing logic, redeem-vs-hold helper | ✅ done |
| 3 | Card Recommendation | Spend profile → simulated annual net value ranking, lifetime-free filter | ⬜ next |
| 4 | Travel Savings | Fare provider + alerts, best-card-for-booking, points-vs-cash-vs-miles | ⬜ |
| 5 | Chat + Notifications | Grounded LLM front door, nudges/alerts | ⬜ |

**MVP = Phases 0–2** (this repository's current state) — solves user needs
#1 (max value per swipe), #2 (how to redeem) and #4 (when to redeem).

## Phase 3 — Card Recommendation Engine

- Derive `SpendProfile` from real transactions (model already exists).
- Simulate each catalog card against the user's actual category breakdown:
  `annual_net_value = Σ spend_cat × effective_rate + milestones + quantified
  perks − annual fee (unless waiver met) − amortized joining fee`.
- Rank vs. the current card with an honest delta and caveats; filterable by
  lifetime-free / no-annual-fee.

## Phase 4 — Travel / Flight Savings

- `FareProvider` interface (Amadeus Self-Service / Kiwi Tequila / SerpAPI
  Google Flights — pick one to start, cache aggressively).
- `FareQuote` history per route + `FareAlert` targets (models already exist);
  APScheduler daily poll; book-now-vs-wait guidance from price trend.
- Best card + channel per booking; cash vs points vs miles-transfer comparison;
  perk-timing nudges (lounge unlock before a trip).

## Phase 5 — Advisory chat + notifications

- LLM front door (Ollama local, Anthropic/OpenAI fallback behind an
  `llm_provider` interface). **Grounding contract:** the model may only state
  numbers returned by engine tool calls — no free-form reward math.
- Nudges: expiry ≤90 days, milestone almost reached, fee-waiver progress,
  lounge/BMS gate progress, fare drops. In-app first; email/Telegram later.

## Deliberately deferred

- **Account Aggregator (Sahamati)** ingestion — requires FIU/TSP onboarding and
  consent flows; statement upload is the MVP baseline.
- **DB encryption at rest** (SQLCipher / field-level) — before any packaged
  distribution.
- **Browser extension / share-target** for the Swipe Advisor.
