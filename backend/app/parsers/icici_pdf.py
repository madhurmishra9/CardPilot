"""ICICI Bank credit-card PDF statement parser.

Uses pdfplumber (optional dependency: `pip install pdfplumber`) to extract the
transaction table. ICICI statement rows look like:
    03/06/2026  SWIGGY BANGALORE IN  1,234.56
Credits are marked with a trailing "CR" and are skipped.
"""

from __future__ import annotations

import io
import re
from datetime import datetime

ROW_RE = re.compile(
    r"(?P<date>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<merchant>.+?)\s+"
    r"(?P<amount>[\d,]+\.\d{2})\s*(?P<cr>CR)?\s*$"
)


def parse(content: bytes, mapping: dict | None = None) -> list[dict]:
    try:
        import pdfplumber  # noqa: PLC0415 — heavy optional dependency
    except ImportError as exc:
        raise RuntimeError(
            "PDF parsing requires pdfplumber: pip install pdfplumber") from exc

    rows = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                rows.extend(parse_line(line))
    return rows


def parse_line(line: str) -> list[dict]:
    """Parse one text line; exposed separately so it's testable without a PDF."""
    m = ROW_RE.match(line.strip())
    if not m or m.group("cr"):
        return []
    return [{
        "date": datetime.strptime(m.group("date"), "%d/%m/%Y").date(),
        "amount": float(m.group("amount").replace(",", "")),
        "merchant_raw": m.group("merchant").strip(),
    }]
