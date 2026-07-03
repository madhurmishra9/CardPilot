"""API tests for the enhancement round: portfolio, mappings, export, history,
staleness flag, realized value, statement-day reminders."""

import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ["CARDPILOT_DB_URL"] = f"sqlite:///{_tmp}/test_enh.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.scheduler import statement_day_reminders  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def seeded(client):
    from datetime import date
    card = client.post("/api/cards/mine", json={
        "card_id": "icici_coral", "statement_day": date.today().day}).json()
    client.post("/api/transactions", json={
        "user_card_id": card["id"], "date": "2026-06-01", "amount": 50000,
        "merchant": "AMAZON", "category_key": "online_shopping"})
    client.post("/api/transactions", json={
        "user_card_id": card["id"], "date": "2026-06-02", "amount": 20000,
        "merchant": "BSES", "category_key": "utilities"})
    return card["id"]


def test_catalog_carries_staleness_flag(client):
    cards = client.get("/api/cards/catalog").json()
    assert all("stale" in c for c in cards)


def test_card_history_endpoint(client):
    history = client.get("/api/cards/catalog/icici_coral/history").json()
    assert isinstance(history, list)
    assert client.get("/api/cards/catalog/nope/history").status_code == 404


def test_portfolio_endpoint(client, seeded):
    body = client.get("/api/recommend/portfolio?size=2").json()
    assert body["portfolios"]
    top = body["portfolios"][0]
    assert len(top["cards"]) == 2
    assert top["per_card"][0]["assigned_categories"] is not None


def test_merchant_share_param_changes_ranking_inputs(client, seeded):
    optimistic = client.get("/api/recommend/cards?merchant_share=1.0").json()
    conservative = client.get("/api/recommend/cards?merchant_share=0.3").json()
    opt_amz = next(r for r in optimistic["ranked"] if r["card_id"] == "amazon_pay_icici")
    con_amz = next(r for r in conservative["ranked"] if r["card_id"] == "amazon_pay_icici")
    assert con_amz["annual_net_value"] < opt_amz["annual_net_value"]


def test_csv_mapping_saved_and_listed(client):
    resp = client.post("/api/transactions/csv-mappings", json={
        "name": "ICICI netbanking",
        "mapping": {"date": "Txn Date", "amount": "Amount", "merchant": "Details"}})
    assert resp.status_code == 201
    mappings = client.get("/api/transactions/csv-mappings").json()
    assert any(m["name"] == "ICICI netbanking" for m in mappings)
    # upsert by name
    client.post("/api/transactions/csv-mappings", json={
        "name": "ICICI netbanking", "mapping": {"date": "D", "amount": "A"}})
    mappings = client.get("/api/transactions/csv-mappings").json()
    assert len([m for m in mappings if m["name"] == "ICICI netbanking"]) == 1


def test_export_json_and_csv(client, seeded):
    dump = client.get("/api/export/json").json()
    assert dump["transactions"]
    assert dump["cards"][0]["card_id"] == "icici_coral"
    csv_resp = client.get("/api/export/transactions.csv")
    assert csv_resp.status_code == 200
    assert "date,card,amount_inr" in csv_resp.text.splitlines()[0]


def test_realized_value_flows_into_advice(client, seeded):
    for d in ("2026-06-10", "2026-06-20"):
        client.post("/api/redemption/events", json={
            "user_card_id": seeded, "points_used": 1000,
            "inr_value_realized": 300, "fee_paid": 0, "date": d})
    advice = client.get(f"/api/redemption/advise/{seeded}").json()
    assert advice["realized_value_per_point"] == 0.3  # observed, beats 0.25 baseline


def test_statement_day_reminder_fires(client, seeded):
    assert statement_day_reminders() >= 1
    stored = client.get("/api/notifications").json()["stored"]
    assert any(n["type"] == "statement_day" for n in stored)
