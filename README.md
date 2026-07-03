# CardPilot

A **local-first personal credit-card rewards & travel-savings optimizer** for Indian credit cards. Seeded with ICICI Bank Coral as the reference card, architected for any card.

CardPilot answers five recurring questions:

| # | Question | Feature |
|---|----------|---------|
| 1 | Am I getting the most from my spends? | **Swipe Advisor** — which card to use for each spend |
| 2 | How do I redeem the points I've earned? | **Redemption Advisor** — catalog value, fees, mechanics |
| 3 | Is there a better card for how I spend? | **Card Recommendation Engine** — annual net-value simulation on your real spend |
| 4 | When/what should I redeem for max value? | **Redemption timing** — fee batching, expiry guard |
| 5 | How do I spend less on flights/travel? | **Travel Savings** — fare tracking, best card per booking, cash vs points |

## Design principles

- **Rules-as-data.** Card benefits change constantly. Every reward rate, fee and perk lives in versioned YAML under [`/data/cards/`](data/cards/) — never in code. Each file carries `last_verified` + `source_url`.
- **Value is always net.** Every recommendation subtracts fees, surcharges, annual fees and redemption charges before ranking. A "5X rewards" card with a ₹99+GST-per-redemption fee can lose to a lifetime-free card.
- **Explainable.** Every recommendation shows its math ("2 RP/₹100 × 50 slabs × ₹0.25/pt = ₹25").
- **Local-first.** SQLite on your machine; no cloud sync; only the last 4 digits of a card are ever stored.

## Quick start

### Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

On first start the DB is created and seeded from `/data` (12-card catalog, categories, ICICI redemption options). API docs at http://localhost:8000/docs.

Optional: `pip install pdfplumber` to enable ICICI PDF statement parsing.

### Frontend (React + Vite + Tailwind)

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173, proxies /api to :8000
```

### Tests

```bash
cd backend
python -m pytest tests/ -v
```

The suite includes the seven acceptance tests from the build spec (§9) pinned against the real ICICI Coral seed rules — grocery earn, utilities half-rate, fuel exclusion + surcharge waiver, milestone crossing, split-redemption fee warning, 90-day expiry alert, and cross-card swipe ranking.

## What's implemented (all phases, 0–5)

- **Phase 0 — Data foundation**: YAML card-rules schema, ICICI Coral seed + 11 more popular Indian cards, pure unit-tested rules engine.
- **Phase 1 — Track + Earn Optimizer**: manual entry, CSV upload with a column-mapping wizard, ICICI PDF parser (parser registry), MCC/keyword categorization with learned merchant→category corrections, points ledger with milestone & perk-gate tracking, Swipe Advisor.
- **Phase 2 — Redemption Advisor**: redemption catalog, per-request fee amortization & batching warnings, break-even math, points-expiry guard, redeem-vs-hold decision helper, realized-value logging.
- **Phase 3 — Card Recommendation**: spend profile derived from your real transactions, every catalog card simulated for projected annual net value (earn + milestones + quantified perks − fees), ranked vs your current card with honest caveats and a lifetime-free filter.
- **Phase 4 — Travel Savings**: `FareProvider` interface (offline mock by default, Amadeus stub), fare-quote history with book-now/wait trend guidance, fare alerts polled daily by APScheduler, best-card-per-booking, cash-vs-points comparison.
- **Phase 5 — Chat + Notifications**: grounded advisory chat (deterministic intent routing + engine tool calls; optional Ollama/Anthropic rephrasing that can never invent numbers) and nudges for expiry, milestones, fee waivers, perk gates and fare drops.

See [docs/ROADMAP.md](docs/ROADMAP.md) for per-phase details and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the system design.

### Configuration (all optional)

| Env var | Default | Purpose |
|---------|---------|---------|
| `CARDPILOT_DB_URL` | `sqlite:///./cardpilot.db` | Swap SQLite for Postgres |
| `CARDPILOT_ENABLE_SCHEDULER` | off | `1` starts daily fare polls + nudge scans |
| `CARDPILOT_FARE_PROVIDER` | `mock` | `amadeus` once keys are configured |
| `CARDPILOT_LLM` | `none` | `ollama` (local) or `anthropic` (opt-in cloud) for chat rephrasing |
| `CARDPILOT_LLM_MODEL` | provider default | Model name for the chat layer |

## Repository layout

```
backend/
  app/
    services/rules_engine.py   # pure function library: spend + rules → value
    services/redemption.py     # fee amortization, expiry, redeem-vs-hold
    services/categorize.py     # MCC / keyword / learned categorization
    services/ledger.py         # DB aggregation over transactions
    parsers/                   # statement parser registry (CSV, ICICI PDF)
    routers/                   # REST API
    models.py                  # SQLAlchemy models (spec §3)
    seed.py                    # idempotent seeding from /data
  tests/                       # acceptance (§9) + unit + API tests
frontend/                      # React + Vite + Tailwind SPA
data/
  cards/*.yaml                 # versioned card rules — the core dataset
  redemptions/*.yaml           # redemption option catalogs
  categories.yaml              # category taxonomy (MCC ranges + keywords)
docs/                          # architecture, schema, roadmap
```

## ⚠️ Data disclaimer

Reward rates, fees and perks in `/data/cards/` are **seed values** verified around July 2026 and **will drift**. Refresh from each issuer's official Most Important Terms & Conditions (MITC) before trusting any number — see the quarterly checklist in [docs/CARD_RULES_SCHEMA.md](docs/CARD_RULES_SCHEMA.md).

## License

Apache-2.0 — see [LICENSE](LICENSE).
