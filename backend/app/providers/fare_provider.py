"""FareProvider interface (spec §4-E / §6).

Real providers (Amadeus Self-Service, Kiwi Tequila, SerpAPI Google Flights)
cost money and need keys, so the default is a deterministic offline mock that
exercises the full pipeline. Select with CARDPILOT_FARE_PROVIDER=mock|amadeus.
"""

from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class Fare:
    origin: str
    dest: str
    depart_date: date
    return_date: date | None
    cabin: str
    price_inr: float
    carrier: str
    source: str


class FareProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def search(self, origin: str, dest: str, depart_date: date,
               return_date: date | None = None, cabin: str = "economy") -> list[Fare]:
        """Return available fares, cheapest first."""


class MockFareProvider(FareProvider):
    """Deterministic pseudo-fares: same inputs → same prices. Offline & free."""

    name = "mock"
    CARRIERS = ["IndiGo", "Air India", "Akasa Air"]

    @staticmethod
    def _h(*parts) -> int:
        digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
        return int(digest[:8], 16)

    def search(self, origin, dest, depart_date, return_date=None, cabin="economy"):
        base = 2500 + self._h(origin.upper(), dest.upper()) % 9000
        if return_date:
            base = base * 2 * 0.92
        if cabin == "business":
            base *= 3.2
        fares = []
        for carrier in self.CARRIERS:
            wobble = 0.85 + (self._h(carrier, depart_date.isoformat()) % 3000) / 10000
            fares.append(Fare(origin.upper(), dest.upper(), depart_date, return_date,
                              cabin, round(base * wobble, 0), carrier, self.name))
        return sorted(fares, key=lambda f: f.price_inr)


class AmadeusFareProvider(FareProvider):
    """Amadeus Self-Service flight offers. Requires AMADEUS_CLIENT_ID/_SECRET."""

    name = "amadeus"

    def search(self, origin, dest, depart_date, return_date=None, cabin="economy"):
        raise NotImplementedError(
            "Amadeus integration stub: set AMADEUS_CLIENT_ID/AMADEUS_CLIENT_SECRET and "
            "implement the OAuth2 + /v2/shopping/flight-offers call here. The rest of "
            "the pipeline (quotes, alerts, trend advice) is provider-agnostic.")


def get_fare_provider() -> FareProvider:
    kind = os.environ.get("CARDPILOT_FARE_PROVIDER", "mock").lower()
    if kind == "amadeus":
        return AmadeusFareProvider()
    return MockFareProvider()
