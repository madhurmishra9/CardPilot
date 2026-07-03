# Card rules schema (`/data/cards/*.yaml`)

Card benefit rules are a **maintained dataset, not a scrape**. Every file is
the single source of truth for one card; the engine never hardcodes a rate.
A non-coder should be able to edit these files.

## Schema

```yaml
card_id: icici_coral              # unique key, snake_case
display_name: "ICICI Bank Coral Credit Card"
issuer: "ICICI Bank"
network_variants: [visa, mastercard, amex, rupay]
lifetime_free: false
joining_fee: 500
annual_fee: 500
annual_fee_gst_extra: true        # GST added on top of the fee
annual_fee_waiver_spend: 150000   # waived if prev-year spend >= this; 0 = not waivable
last_verified: "2026-07-03"       # REQUIRED — date the rules were checked vs MITC
source_url: "https://…"           # REQUIRED — official issuer page / MITC

reward_program: "ICICI Rewards"
point_value_inr: 0.25             # baseline ₹/point; options may differ
redemption_fee_inr: 99            # PER redemption request; 0 = free
redemption_fee_gst_rate: 0.18
points_expiry_months: 36          # 0 = points never expire

earn_rules:
  rates:                          # first match wins; retail_default is the fallback
    - category: online_shopping   # must be a key from /data/categories.yaml
      rate_points_per_100: 5      # points per full ₹100 slab (floats allowed)
      merchants: [amazon]         # optional: only these merchants (substring match)
      monthly_cap_points: 5000    # optional
    - category: retail_default
      rate_points_per_100: 2
  excluded_categories: [fuel, cash_advance, wallet_load, emi_conversion]

milestones:                       # {} if none
  period: anniversary_year        # or calendar_quarter
  tiers:
    - spend: 200000
      bonus_points: 2000
  step_after:                     # optional: repeating bonus beyond the last tier
    every_spend: 100000
    bonus_points: 1000
  max_bonus_points: 10000         # cap per period

perks:                            # every value quantified so net-value math works
  fuel_surcharge_waiver:
    rate: 0.01
    min_txn: 400
    max_txn: 4000
    merchants: [HPCL]             # empty/omitted = any fuel merchant
  lounge_domestic_airport:
    count_per_quarter: 1          # or count_per_year
    unlock_spend_prev_quarter: 75000   # optional spend gate
    value_per_visit_inr: 1000
  upi_linkable: true
```

## Engine semantics

- **Earn**: points = `floor(floor(amount / 100) × rate)`, i.e. per full ₹100
  slab. Excluded categories earn 0 and are flagged ineligible.
- **Rate matching**: the first `rates` entry whose category matches (and whose
  `merchants` list, if present, matches the transaction merchant) wins;
  otherwise `retail_default` applies.
- **Milestones**: cumulative spend in the period; `step_after` adds a repeating
  bonus beyond the last tier; `max_bonus_points` caps the total.
- **Net value** always deducts redemption fees (+GST) and unwaived annual fees.

## Quarterly verification checklist

Rules drift silently — banks change terms without notice. Every quarter:

1. Open each card's `source_url` (issuer MITC / product page).
2. Check: earn rates, exclusions, caps, point value, redemption fee,
   expiry window, milestones, lounge/perk gates, annual fee + waiver.
3. Update the YAML and bump `last_verified` — even if nothing changed.
4. Run `python -m pytest backend/tests/` — the acceptance suite pins the
   reference (Coral) behaviour and will catch schema mistakes.
5. Commit with a message like `data: verify icici_coral rules (2026-Q4)`.

Cards whose `last_verified` is older than ~2 quarters should be treated as
suspect and surfaced as such in the UI (planned nudge).
