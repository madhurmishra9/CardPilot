"""End-to-end API tests against a temp SQLite DB with the real seed catalog."""

import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ["CARDPILOT_DB_URL"] = f"sqlite:///{_tmp}/test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def coral_card_id(client):
    resp = client.post("/api/cards/mine", json={"card_id": "icici_coral",
                                                "last4": "1234", "anniversary_month": 4})
    assert resp.status_code == 201
    return resp.json()["id"]


def test_catalog_seeded(client):
    cards = client.get("/api/cards/catalog").json()
    assert len(cards) >= 10
    assert any(c["card_id"] == "icici_coral" for c in cards)


def test_manual_txn_auto_categorized(client, coral_card_id):
    resp = client.post("/api/transactions", json={
        "user_card_id": coral_card_id, "date": "2026-06-15",
        "amount": 5000, "merchant": "BIGBASKET MUMBAI"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["category_key"] == "groceries"
    assert body["points_earned"] == 100  # 2/₹100 × 50 slabs


def test_excluded_category_earns_nothing(client, coral_card_id):
    resp = client.post("/api/transactions", json={
        "user_card_id": coral_card_id, "date": "2026-06-16",
        "amount": 2000, "merchant": "HPCL PETROL PUMP"})
    body = resp.json()
    assert body["category_key"] == "fuel"
    assert body["points_earned"] == 0
    assert body["is_reward_eligible"] is False


def test_csv_upload(client, coral_card_id):
    csv_bytes = (b"Txn Date,Details,Amount\n"
                 b"10/06/2026,SWIGGY BANGALORE,800.00\n"
                 b"11/06/2026,PAYMENT THANK YOU,-5000.00\n")
    resp = client.post("/api/transactions/upload",
                       data={"user_card_id": str(coral_card_id), "parser": "generic_csv",
                             "mapping": '{"date": "Txn Date", "amount": "Amount", '
                                        '"merchant": "Details"}'},
                       files={"file": ("stmt.csv", csv_bytes, "text/csv")})
    assert resp.status_code == 201
    assert resp.json()["imported"] == 1


def test_category_correction_learns(client, coral_card_id):
    txn = client.post("/api/transactions", json={
        "user_card_id": coral_card_id, "date": "2026-06-17",
        "amount": 1000, "merchant": "SWIGGY INSTAMART"}).json()
    resp = client.patch(f"/api/transactions/{txn['id']}/category",
                        json={"category_key": "groceries", "remember": True})
    assert resp.json()["category_key"] == "groceries"
    # future imports of the same merchant use the learned mapping
    txn2 = client.post("/api/transactions", json={
        "user_card_id": coral_card_id, "date": "2026-06-18",
        "amount": 500, "merchant": "SWIGGY INSTAMART"}).json()
    assert txn2["category_key"] == "groceries"


def test_swipe_advisor_shows_math(client, coral_card_id):
    resp = client.post("/api/advisor/swipe",
                       json={"category": "utilities", "amount": 3000})
    ranked = resp.json()
    assert ranked[0]["card_id"] == "icici_coral"
    assert ranked[0]["explanation"]


def test_dashboard_summary(client, coral_card_id):
    cards = client.get("/api/advisor/dashboard").json()
    coral = next(c for c in cards if c["card_id"] == "icici_coral")
    assert coral["points_balance"] > 0
    assert any(g["perk"] == "annual_fee_waiver" for g in coral["perk_gates"])


def test_redemption_advise(client, coral_card_id):
    resp = client.get(f"/api/redemption/advise/{coral_card_id}").json()
    assert resp["fee_per_request_inr"] == 116.82
    assert resp["break_even_points"] == 468
    assert resp["decision"]["action"] in ("redeem", "hold")


def test_log_redemption_event(client, coral_card_id):
    resp = client.post("/api/redemption/events", json={
        "user_card_id": coral_card_id, "points_used": 2000,
        "inr_value_realized": 500, "fee_paid": 116.82, "date": "2026-07-01"})
    assert resp.status_code == 201
    assert resp.json()["realized_value_per_point"] == 0.25
