"""Statement parser registry (Module A).

Each parser turns an uploaded statement into normalized rows:
    {"date": date, "amount": float, "merchant_raw": str}
Register per-issuer parsers here; the upload endpoint looks them up by key.
"""

from __future__ import annotations

from typing import Callable

from . import generic_csv, icici_pdf

PARSERS: dict[str, Callable] = {
    "generic_csv": generic_csv.parse,
    "icici_pdf": icici_pdf.parse,
}


def get_parser(key: str):
    if key not in PARSERS:
        raise KeyError(f"unknown parser '{key}'; available: {sorted(PARSERS)}")
    return PARSERS[key]
