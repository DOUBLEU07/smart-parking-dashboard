from datetime import timedelta

from app.database import SessionLocal
from app.models import ParkingSession
from tests.conftest import login


def backdate(session_id: int, minutes: int) -> None:
    with SessionLocal() as db:
        s = db.get(ParkingSession, session_id)
        s.entry_time = s.entry_time - timedelta(minutes=minutes)
        db.commit()


def summary(client, headers):
    return client.get("/api/dashboard/summary", headers=headers).json()


def test_requires_login(client):
    assert client.get("/api/dashboard/summary").status_code == 401
    r = client.post("/api/auth/login", json={"username": "owner", "password": "wrong"})
    assert r.status_code == 401


def test_demo_flow_entry_exit_revenue(client, staff):
    before = summary(client, staff)
    assert before["available"] == 10 and before["occupied"] == 0

    r = client.post("/api/sessions/check-in", json={"plate_number": " กข  1234 "}, headers=staff)
    assert r.status_code == 201, r.text
    session = r.json()
    assert session["plate_number"] == "กข 1234"
    assert session["slot_number"] == "P01"  # first free slot is suggested

    mid = summary(client, staff)
    assert mid["available"] == 9 and mid["occupied"] == 1 and mid["today_entries"] == 1

    backdate(session["id"], 75)  # 75 min -> 2 billable hours -> 40 baht
    quote = client.get(f"/api/sessions/{session['id']}/quote", headers=staff).json()
    assert quote["amount"] == 40

    r = client.post(
        f"/api/sessions/{session['id']}/check-out",
        json={"method": "cash", "expected_amount": 40},
        headers=staff,
    )
    assert r.status_code == 200, r.text
    receipt = r.json()
    assert receipt["session"]["fee"] == 40
    assert receipt["session"]["payment"]["method"] == "cash"

    after = summary(client, staff)
    assert after["available"] == 10
    assert after["today_revenue"] == 40
    assert after["today_exits"] == 1
    assert after["recent_activity"][0]["kind"] == "exit"


def test_checkout_rejects_stale_quote(client, staff):
    s = client.post("/api/sessions/check-in", json={"plate_number": "AB 1"}, headers=staff).json()
    backdate(s["id"], 61)
    r = client.post(f"/api/sessions/{s['id']}/check-out", json={"method": "qr", "expected_amount": 20}, headers=staff)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "fee_changed"
    assert r.json()["detail"]["amount"] == 40
    # Double check-out is refused.
    assert client.post(f"/api/sessions/{s['id']}/check-out", json={"method": "qr"}, headers=staff).status_code == 200
    assert client.post(f"/api/sessions/{s['id']}/check-out", json={"method": "qr"}, headers=staff).status_code == 409


def test_free_parking_creates_no_payment(client, staff):
    s = client.post("/api/sessions/check-in", json={"plate_number": "FREE 1"}, headers=staff).json()
    r = client.post(f"/api/sessions/{s['id']}/check-out", json={"method": "cash"}, headers=staff).json()
    assert r["session"]["fee"] == 0 and r["session"]["payment"] is None


def test_duplicate_plate_and_busy_slot(client, staff):
    s = client.post("/api/sessions/check-in", json={"plate_number": "กข 1"}, headers=staff).json()
    assert client.post("/api/sessions/check-in", json={"plate_number": "กข 1"}, headers=staff).status_code == 409
    r = client.post("/api/sessions/check-in", json={"plate_number": "กข 2", "slot_id": s["slot_id"]}, headers=staff)
    assert r.status_code == 409
    bad = client.post("/api/sessions/check-in", json={"plate_number": "<script>"}, headers=staff)
    assert bad.status_code == 422


def test_full_lot_and_near_full_alert(client, staff):
    for i in range(8):
        client.post("/api/sessions/check-in", json={"plate_number": f"X {i}"}, headers=staff)
    assert summary(client, staff)["near_full"] is False  # 80%
    client.post("/api/sessions/check-in", json={"plate_number": "X 8"}, headers=staff)
    s = summary(client, staff)
    assert s["near_full"] is True and s["is_full"] is False  # 90%
    client.post("/api/sessions/check-in", json={"plate_number": "X 9"}, headers=staff)
    assert summary(client, staff)["is_full"] is True
    r = client.post("/api/sessions/check-in", json={"plate_number": "X 10"}, headers=staff)
    assert r.status_code == 409


def test_maintenance_slot_excluded(client, manager, staff):
    slots = client.get("/api/slots", headers=staff).json()
    r = client.patch(f"/api/slots/{slots[0]['id']}", json={"status": "maintenance"}, headers=manager)
    assert r.status_code == 200
    s = summary(client, staff)
    assert s["capacity"] == 9 and s["maintenance"] == 1
    session = client.post("/api/sessions/check-in", json={"plate_number": "M 1"}, headers=staff).json()
    assert session["slot_number"] == "P02"


def test_role_permissions(client, owner, manager, staff):
    assert client.get("/api/reports/summary", headers=staff).status_code == 403
    assert client.get("/api/reports/summary", headers=manager).status_code == 200
    assert client.post("/api/slots/bulk", json={"count": 2}, headers=staff).status_code == 403
    assert client.get("/api/users", headers=manager).status_code == 403
    assert client.get("/api/users", headers=owner).status_code == 200
    body = {"lot_name": "Lot", "free_minutes": 0, "hourly_rate": 30, "daily_cap": None, "alert_threshold": 80}
    assert client.put("/api/settings", json=body, headers=manager).status_code == 403
    assert client.put("/api/settings", json=body, headers=owner).status_code == 200
    assert client.get("/api/settings", headers=staff).json()["hourly_rate"] == 30


def test_bulk_slots_continue_numbering(client, manager):
    r = client.post("/api/slots/bulk", json={"prefix": "P", "count": 2}, headers=manager)
    assert [s["slot_number"] for s in r.json()] == ["P11", "P12"]


def test_slot_with_history_cannot_be_deleted(client, manager, staff):
    s = client.post("/api/sessions/check-in", json={"plate_number": "D 1"}, headers=staff).json()
    client.post(f"/api/sessions/{s['id']}/check-out", json={"method": "cash"}, headers=staff)
    assert client.delete(f"/api/slots/{s['slot_id']}", headers=manager).status_code == 409


def test_owner_cannot_lock_themselves_out(client, owner):
    me = client.get("/api/auth/me", headers=owner).json()
    r = client.patch(f"/api/users/{me['id']}", json={"role": "staff"}, headers=owner)
    assert r.status_code == 400


def test_inactive_user_token_rejected(client, owner):
    staff_headers = login(client, "staff")
    users = client.get("/api/users", headers=owner).json()
    staff_id = next(u["id"] for u in users if u["username"] == "staff")
    client.patch(f"/api/users/{staff_id}", json={"is_active": False}, headers=owner)
    assert client.get("/api/auth/me", headers=staff_headers).status_code == 401


def test_history_report_and_export(client, manager, staff):
    s = client.post("/api/sessions/check-in", json={"plate_number": "R 1"}, headers=staff).json()
    backdate(s["id"], 30)
    client.post(f"/api/sessions/{s['id']}/check-out", json={"method": "qr"}, headers=staff)

    page = client.get("/api/sessions", params={"q": "r 1", "state": "completed"}, headers=staff).json()
    assert page["total"] == 1 and page["items"][0]["fee"] == 20

    report = client.get("/api/reports/summary", headers=manager).json()
    assert report["total_revenue"] == 20
    assert report["revenue_by_method"]["qr"] == 20
    assert len(report["daily"]) == 7

    csv = client.get("/api/sessions/export", headers=manager)
    assert csv.status_code == 200 and "R 1" in csv.text


def test_websocket_auth_and_broadcast(client, staff):
    token = staff["Authorization"].split()[1]
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["type"] == "ready"
        client.post("/api/sessions/check-in", json={"plate_number": "WS 1"}, headers=staff)
        event = ws.receive_json()
        assert event["type"] == "parking.updated" and event["reason"] == "check_in"


def test_websocket_rejects_bad_token(client):
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"type": "auth", "token": "nope"})
        try:
            ws.receive_json()
            raise AssertionError("socket should be closed")
        except Exception as exc:  # noqa: BLE001
            assert "1008" in str(exc) or exc.__class__.__name__ == "WebSocketDisconnect"
