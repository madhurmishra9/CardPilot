"""End-to-end API tests for Phases 3–5 endpoints."""

import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ["CARDPILOT_DB_URL"] = f"sqlite:///{_tmp}/test35.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.scheduler import poll_fare_alerts, scan_nudges  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def seeded(client):
    card = client.post("/api/cards/mine", json={"card_id": "icici_coral",
                                                "anniversary_month": 1}).json()
    txns = [
        {"date": "2026-06-01", "amount": 40000, "merchant": "AMAZON",
         "category_key": "online_shopping"},
        {"date": "2026-06-05", "amount": 12000, "merchant": "BSES DELHI",
         "category_key": "utilities"},
        {"date": "2026-06-10", "amount": 9000, "merchant": "BIGBASKET",
         "category_key": "groceries"},
    ]
    for t in txns:
        client.post("/api/transactions", json={"user_card_id": card["id"], **t})
    return card["id"]


def test_recommend_ranks_catalog(client, seeded):
    body = client.get("/api/recommend/cards").json()
    assert body["current_card_id"] == "icici_coral"
    assert body["spend_profile"]["online_shopping"] > 0
    assert len(body["ranked"]) >= 10
    top = body["ranked"][0]
    assert "annual_net_value" in top and "charges_flag" in top
    current = next(r for r in body["ranked"] if r["is_current"])
    assert current["delta_vs_current_inr"] == 0.0


def test_recommend_ltf_filter(client, seeded):
    body = client.get("/api/recommend/cards?ltf_only=true").json()
    assert body["ranked"]
    assert all(r["lifetime_free"] for r in body["ranked"])


def test_travel_search_full_advisory(client, seeded):
    resp = client.post("/api/travel/search", json={
        "origin": "BOM", "dest": "BKK", "depart_date": "2026-09-01"}).json()
    assert resp["fares"]
    assert resp["trend"]["action"] in ("book_now", "book_soon", "wait",
                                       "insufficient_history")
    assert resp["best_card"][0]["effective_cost_inr"] < resp["fares"][0]["price_inr"]
    paths = list(resp["points_vs_cash"].values())[0]
    assert {p["path"] for p in paths} == {"cash", "points"}


def test_fare_alert_lifecycle_and_scheduler(client, seeded):
    created = client.post("/api/travel/alerts",
                          json={"route": "BOM-BKK", "target_price": 99999})
    assert created.status_code == 201
    fired = poll_fare_alerts()  # mock fares are always under ₹99,999
    assert fired >= 1
    stored = client.get("/api/notifications").json()["stored"]
    assert any(n["type"] == "fare_drop" for n in stored)
    alert_id = created.json()["id"]
    assert client.delete(f"/api/travel/alerts/{alert_id}").status_code == 204


def test_nudge_scan_persists(client, seeded):
    scan_nudges()
    body = client.get("/api/notifications").json()
    assert isinstance(body["live"], list)


def test_chat_swipe_is_grounded(client, seeded):
    resp = client.post("/api/chat",
                       json={"message": "Which card for ₹5k groceries?"}).json()
    assert resp["intent"] == "swipe"
    assert resp["llm"] == "none"          # default: deterministic, offline
    assert "ICICI Bank Coral" in resp["reply"]
    assert "₹" in resp["reply"]           # numbers come from the engine


def test_chat_recommend(client, seeded):
    resp = client.post("/api/chat",
                       json={"message": "Is there a better card for me?"}).json()
    assert resp["intent"] == "recommend"
    assert "annual net value" in resp["facts"]


def test_notification_mark_read(client, seeded):
    stored = client.get("/api/notifications").json()["stored"]
    if stored:
        n = stored[0]
        assert client.post(f"/api/notifications/{n['id']}/read").json()["read"] is True
