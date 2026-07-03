"""Generic CSV statement parser with a column-mapping wizard.

The caller supplies a mapping once per bank export format (remembered client-side
or in user prefs), e.g. {"date": "Txn Date", "amount": "Amount (INR)",
"merchant": "Description", "date_format": "%d/%m/%Y"}.
Debits are positive spend; credit/negative rows are skipped.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime

DEFAULT_DATE_FORMATS = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d-%b-%Y", "%m/%d/%Y"]


def _parse_date(raw: str, fmt: str | None) -> date:
    raw = raw.strip()
    formats = [fmt] if fmt else DEFAULT_DATE_FORMATS
    for f in formats:
        try:
            return datetime.strptime(raw, f).date()
        except ValueError:
            continue
    raise ValueError(f"unparseable date: {raw!r}")


def _parse_amount(raw: str) -> float:
    cleaned = raw.replace("₹", "").replace(",", "").replace("INR", "").strip()
    negative = cleaned.endswith("CR") or cleaned.startswith("-")
    cleaned = cleaned.removesuffix("CR").removesuffix("DR").strip().lstrip("-")
    value = float(cleaned)
    return -value if negative else value


def parse(content: bytes, mapping: dict) -> list[dict]:
    """Parse CSV bytes into normalized transaction rows using the column mapping."""
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    date_col = mapping["date"]
    amount_col = mapping["amount"]
    merchant_col = mapping.get("merchant")
    fmt = mapping.get("date_format")

    rows = []
    for raw in reader:
        if raw.get(date_col) is None or raw.get(amount_col) in (None, ""):
            continue
        try:
            amount = _parse_amount(raw[amount_col])
        except ValueError:
            continue
        if amount <= 0:  # skip credits/refunds — only spends earn
            continue
        rows.append({
            "date": _parse_date(raw[date_col], fmt),
            "amount": amount,
            "merchant_raw": (raw.get(merchant_col) or "").strip() if merchant_col else "",
        })
    return rows
