"""Single-server mode: FastAPI serves the built SPA alongside /api."""

import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ["CARDPILOT_DB_URL"] = f"sqlite:///{_tmp}/test_spa.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import FRONTEND_DIST, app  # noqa: E402

needs_dist = pytest.mark.skipif(
    not FRONTEND_DIST.exists(),
    reason="frontend/dist not built (run `npm run build` in frontend/)")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@needs_dist
def test_root_serves_spa(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "CardPilot" in resp.text


@needs_dist
def test_pwa_assets_served(client):
    assert client.get("/manifest.webmanifest").status_code == 200
    assert client.get("/sw.js").status_code == 200
    assert client.get("/icon.svg").status_code == 200


@needs_dist
def test_spa_fallback_for_client_routes(client):
    resp = client.get("/some/client/route")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@needs_dist
def test_api_not_shadowed(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/definitely-not-a-route").status_code == 404


@needs_dist
def test_no_path_traversal(client):
    resp = client.get("/../backend/app/main.py")
    assert "text/html" in resp.headers["content-type"]  # falls back to index, no leak
