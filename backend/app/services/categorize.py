"""Merchant/MCC -> category mapping (Module A).

Priority: user-learned merchant mapping > MCC ranges > merchant keyword match
> retail_default. Learned mappings are passed in by the caller (the service
layer owns the DB); this module stays pure.
"""

from __future__ import annotations

DEFAULT_CATEGORY = "retail_default"


def normalize_merchant(raw: str) -> str:
    return " ".join(raw.lower().split())


def categorize(merchant_raw: str | None, categories: list[dict],
               mcc: int | None = None,
               learned: dict[str, str] | None = None) -> str:
    """Return the category key for a transaction."""
    merchant = normalize_merchant(merchant_raw or "")

    if learned and merchant in learned:
        return learned[merchant]

    if mcc is not None:
        for cat in categories:
            for low, high in cat.get("mcc_ranges") or []:
                if low <= mcc <= high:
                    return cat["key"]

    if merchant:
        for cat in categories:
            for kw in cat.get("keywords") or []:
                if kw.lower() in merchant:
                    return cat["key"]

    return DEFAULT_CATEGORY
