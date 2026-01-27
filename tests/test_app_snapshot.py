import json

from app.web.app import app


def test_snapshot_reads_file(tmp_path, monkeypatch):
    snapshot = {
        "timestamp": "2026-01-27T12:00:00",
        "weather": {"source": "nws_api", "current_temp": 70, "high_today": 75},
        "portfolio": {"balance": 1000, "portfolio_value": 2500},
    }
    snapshot_path = tmp_path / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot))

    monkeypatch.setenv("BOT_SNAPSHOT_FILE", str(snapshot_path))

    client = app.test_client()
    resp = client.get("/api/snapshot")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["weather"]["source"] == "nws_api"
