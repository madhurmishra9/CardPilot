# Roadmap

| Phase | Deliverable | Definition of done | Status |
|-------|-------------|--------------------|--------|
| 0 | Data foundation | Card-rules schema + Coral seed + 11 popular cards; rules engine unit-tested | ✅ done |
| 1 | Track + Earn Optimizer | Manual/CSV/PDF ingest, categorization, points ledger, Swipe Advisor | ✅ done |
| 2 | Redemption Advisor | Redemption catalog, fee/expiry/timing logic, redeem-vs-hold helper | ✅ done |
| 3 | Card Recommendation | Spend profile → simulated annual net value ranking, lifetime-free filter | ✅ done |
| 4 | Travel Savings | Fare provider + alerts, best-card-for-booking, points-vs-cash | ✅ done |
| 5 | Chat + Notifications | Grounded LLM front door, nudges/alerts | ✅ done |

All five phases are implemented. Notes on the later phases:

## Phase 3 — Card Recommendation Engine (`services/recommend.py`)

- `SpendProfile` derived from real transactions, annualized
  (`services/spend_profile.py`), persisted on each run.
- Every catalog card simulated on the user's actual category breakdown:
  `annual_net_value = Σ spend_cat × effective_rate (caps respected) +
  milestones + quantified perks − annual fee (unless waiver met) − amortized
  joining fee`.
- Ranked vs. the current card with an honest delta, a charges flag
  (lifetime-free / waivable / not waivable) and caveats (merchant-restricted
  rates, spend-gated lounges, monthly caps). `ltf_only` filter supported.

## Phase 4 — Travel / Flight Savings (`services/travel.py`, `providers/fare_provider.py`)

- `FareProvider` interface with a deterministic offline **mock provider**
  (default) and an Amadeus stub — set `CARDPILOT_FARE_PROVIDER` and keys to go
  live; the rest of the pipeline is provider-agnostic.
- `FareQuote` history per route + `FareAlert` targets; APScheduler daily poll
  (enable with `CARDPILOT_ENABLE_SCHEDULER=1`); book-now / book-soon / wait
  guidance from the tracked price trend.
- Best card per booking (effective cost = fare − net reward value) and
  cash-vs-points comparison per card, fee and opportunity cost included.
  Miles-transfer paths activate when a card carries `miles_transfer`
  redemption options.

## Phase 5 — Advisory chat + notifications (`services/chat.py`, `services/notifications.py`)

- Deterministic intent router → engine tool calls produce FACTS; the LLM
  provider only rephrases. **Grounding contract enforced by construction:**
  the model never sees raw card rules, only engine output. Providers: `none`
  (default, fully offline), `ollama` (local), `anthropic` (opt-in cloud) via
  `CARDPILOT_LLM`.
- Nudges: expiry ≤90 days, milestone almost reached, fee-waiver progress,
  lounge/BMS gate progress (live API) + fare drops (scheduler-persisted).
  In-app delivery; email/Telegram are future channels.

## Deliberately deferred

- **Account Aggregator (Sahamati)** ingestion — requires FIU/TSP onboarding and
  consent flows; statement upload is the MVP baseline.
- **Real fare provider integration** — the Amadeus stub documents where the
  OAuth2 + flight-offers call goes; needs paid API keys.
- **DB encryption at rest** (SQLCipher / field-level) — before any packaged
  distribution.
- **Browser extension / share-target** for the Swipe Advisor.
- **Email / Telegram notification delivery** — nudges are in-app today.
