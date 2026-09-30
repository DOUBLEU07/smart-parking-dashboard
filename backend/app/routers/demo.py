"""Demo Mode helpers for the live pitch. Every endpoint 404s when DEMO_MODE is off."""

import socket
from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.engine import make_url

from .. import trace
from ..config import get_settings
from ..deps import DB, CurrentUser, ManagerUser
from ..models import LotSettings, ParkingSession, ParkingSlot, Payment
from ..realtime import manager, parking_event
from ..seed import _seed_demo


def _require_demo() -> None:
    if not get_settings().demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")


router = APIRouter(prefix="/demo", tags=["demo"], dependencies=[Depends(_require_demo)])


def _ips(host: str) -> list[str]:
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(host, None, socket.AF_INET)})
    except OSError:
        return []


@router.get("/status")
def demo_status(request: Request, _: CurrentUser):
    db_host = make_url(get_settings().database_url).host or "(sqlite)"
    hostname = socket.gethostname()
    forwarded = request.headers.get("x-forwarded-for")
    return {
        "demo_mode": True,
        "via_nginx": forwarded is not None,
        "client_ip": forwarded.split(",")[0].strip() if forwarded else request.client.host,
        "proxy_ip": request.client.host if forwarded else None,
        "backend_host": hostname,
        "backend_ips": _ips(hostname),
        "db_host": db_host,
        "db_ips": _ips(db_host) if db_host != "(sqlite)" else [],
        "ws_clients": manager.count,
    }


@router.get("/traces/{trace_id}")
def get_trace(trace_id: int, _: CurrentUser):
    t = trace.get(trace_id)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบ trace")
    return t


class AdvanceIn(BaseModel):
    minutes: int = Field(ge=1, le=24 * 60)


@router.post("/sessions/{session_id}/advance")
def advance_time(session_id: int, body: AdvanceIn, _: CurrentUser, db: DB, tasks: BackgroundTasks):
    """Pretend the car has been parked `minutes` longer, so the demo can show a real fee."""
    s = db.get(ParkingSession, session_id)
    if s is None or s.exit_time is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบรถคันนี้ในลาน")
    s.entry_time = s.entry_time - timedelta(minutes=body.minutes)
    trace.step("logic", "Demo: เลื่อนเวลาเข้าจอดย้อนหลัง", f"+{body.minutes} นาที (ใช้เฉพาะตอนสาธิต)")
    db.commit()
    tasks.add_task(manager.broadcast, parking_event("time_advanced", plate_number=s.plate_number))
    return {"id": s.id, "entry_time": s.entry_time}


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset(_: ManagerUser, db: DB, tasks: BackgroundTasks):
    """Restore the seeded demo lot (30 slots, 80% full, two weeks of history)."""
    db.execute(delete(Payment))
    db.execute(delete(ParkingSession))
    db.execute(delete(ParkingSlot))
    lot = db.get(LotSettings, 1) or LotSettings(id=1)
    lot.free_minutes, lot.hourly_rate, lot.daily_cap, lot.alert_threshold = 15, Decimal("20"), Decimal("200"), 90
    db.add(lot)
    db.commit()
    _seed_demo(db)
    trace.step("logic", "Demo: รีเซ็ตข้อมูลลานจอด", "ลบข้อมูลเดิมแล้ว seed ใหม่ (30 ช่อง ใช้งาน 80%)")
    tasks.add_task(manager.broadcast, parking_event("reset"))
