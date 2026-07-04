"""ICICI Bank credit-card PDF statement parser.

Uses pdfplumber (optional dependency: `pip install pdfplumber`) to extract the
transaction table. ICICI statements list one row per transaction:
    Date | Ref. Number | Transaction Details | Currency | Intl amount | Amount(in Rs)
    10-MAY-25 | 743327451315130... | MC DONALDS PUNE IN | | 0.00 | 251.46
Refunds/reversals appear as a negative amount and are skipped. Merchant names
that wrap onto a second line within the same cell are collapsed into one.
"""

from __future__ import annotations

import io
from datetime import datetime

DATE_FORMAT = "%d-%b-%y"


def parse(content: bytes, mapping: dict | None = None) -> list[dict]:
    try:
        import pdfplumber  # noqa: PLC0415 — heavy optional dependency
    except ImportError as exc:
        raise RuntimeError(
            "PDF parsing requires pdfplumber: pip install pdfplumber") from exc

    rows = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    rows.extend(parse_row(row))
    return rows


def parse_row(row: list[str | None]) -> list[dict]:
    """Parse one extracted table row; exposed separately so it's testable
    without a PDF. Row layout: [Date, Ref. Number, Transaction Details,
    Currency, International amount, Amount(in Rs)]. Header rows and rows
    that don't start with a date are skipped."""
    if not row or len(row) < 6 or not row[0]:
        return []
    try:
        txn_date = datetime.strptime(row[0].strip(), DATE_FORMAT).date()
    except ValueError:
        return []
    amount_raw = (row[-1] or "").replace(",", "").strip()
    try:
        amount = float(amount_raw)
    except ValueError:
        return []
    if amount <= 0:  # refund/reversal — only spends earn
        return []
    merchant = " ".join((row[2] or "").split())
    return [{"date": txn_date, "amount": amount, "merchant_raw": merchant}]
