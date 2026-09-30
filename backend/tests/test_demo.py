from app.database import SessionLocal
from app.models import ParkingSlot


def traced(client, method, path, headers, **kw):
    r = client.request(method, path, headers={**headers, "X-Debug-Trace": "1"}, **kw)
    trace_id = r.headers.get("X-Trace-Id")
    assert trace_id, "traced request must return X-Trace-Id"
    t = client.get(f"/api/demo/traces/{trace_id}", headers=headers).json()
    return r, t


def test_check_in_trace_records_auth_logic_sql_and_broadcast(client, staff):
    r, t = traced(client, "POST", "/api/sessions/check-in", staff, json={"plate_number": "tr 1"})
    assert r.status_code == 201
    tiers = [s["tier"] for s in t["steps"]]
    titles = " | ".join(s["title"] for s in t["steps"])
    assert {"edge", "api", "auth", "logic", "db", "realtime"} <= set(tiers)
    assert "SQL INSERT" in titles and "COMMIT" in titles
    assert t["status"] == 201 and t["duration_ms"] >= 0


def test_rejected_request_trace_shows_failure(client, staff):
    _, t = traced(client, "GET", "/api/reports/summary", staff)
    assert t["status"] == 403
    assert any(s["tier"] == "auth" and not s["ok"] for s in t["steps"])


def test_untraced_requests_have_no_trace_header(client, staff):
    assert "X-Trace-Id" not in client.get("/api/slots", headers=staff).headers


def test_advance_time_makes_fee_payable(client, staff):
    s = client.post("/api/sessions/check-in", json={"plate_number": "ADV 1"}, headers=staff).json()
    assert client.get(f"/api/sessions/{s['id']}/quote", headers=staff).json()["amount"] == 0
    client.post(f"/api/demo/sessions/{s['id']}/advance", json={"minutes": 90}, headers=staff)
    assert client.get(f"/api/sessions/{s['id']}/quote", headers=staff).json()["amount"] == 40


def test_reset_restores_demo_lot(client, manager, staff):
    assert client.post("/api/demo/reset", headers=staff).status_code == 403
    assert client.post("/api/demo/reset", headers=manager).status_code == 204
    with SessionLocal() as db:
        assert db.query(ParkingSlot).count() == 30
    summary = client.get("/api/dashboard/summary", headers=staff).json()
    assert summary["occupied"] == 24 and summary["occupancy_rate"] == 80.0


def test_status_reports_network(client, staff):
    body = client.get("/api/demo/status", headers=staff).json()
    assert body["demo_mode"] is True and body["backend_host"]
