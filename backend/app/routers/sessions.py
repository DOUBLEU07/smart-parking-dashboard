import csv
import io
import logging
from datetime import date
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import Select, exists, func, select
from sqlalchemy.exc import IntegrityError

from .. import trace
from ..config import get_settings
from ..deps import DB, CurrentUser, ManagerUser
from ..models import ParkingSession, ParkingSlot, Payment, SlotStatus, utcnow
from ..pricing import calculate_fee
from ..realtime import manager, parking_event
from ..schemas import (
    CheckInIn,
    CheckOutIn,
    PlateUpdate,
    QuoteOut,
    ReceiptOut,
    SessionOut,
    SessionPage,
    SlotOut,
    normalize_plate,
)
from ..services import get_lot_settings, local_day_bounds, pricing_rule, session_out, user_names

router = APIRouter(prefix="/sessions", tags=["sessions"])
log = logging.getLogger(__name__)


def _get_session(db: DB, session_id: int, lock: bool = False) -> ParkingSession:
    stmt = select(ParkingSession).where(ParkingSession.id == session_id)
    if lock:
        stmt = stmt.with_for_update(of=ParkingSession)
    s = db.scalar(stmt)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบรายการจอด")
    return s


def _trace_broadcast(reason: str) -> None:
    trace.step(
        "realtime",
        f"WebSocket broadcast “{reason}”",
        f"หลัง commit จะแจ้ง {manager.count} หน้าจอที่เปิดอยู่ให้ดึงข้อมูลใหม่ทันที",
        feature="Real-time (WebSocket)",
    )


def _trace_fee(q, rule, minutes_label: str = "") -> None:
    cap = f", เพดาน {rule.daily_cap:.0f} บาท/วัน" if rule.daily_cap is not None else ""
    if q.billable_hours == 0:
        calc = f"จอด {q.duration_minutes} นาที ≤ ฟรี {rule.free_minutes} นาที → 0 บาท"
    else:
        calc = f"จอด {q.duration_minutes} นาที → ปัดขึ้นเป็น {q.billable_hours} ชม. × {rule.hourly_rate:.0f} บาท{cap} → {q.amount:.0f} บาท"
    trace.step("logic", "คำนวณค่าจอดที่ server" + minutes_label, calc, feature="แสดงรายได้ปัจจุบัน")


def _plate_is_parked(db: DB, plate: str) -> bool:
    return bool(
        db.scalar(
            select(
                exists().where(ParkingSession.plate_number == plate, ParkingSession.exit_time.is_(None))
            )
        )
    )


@router.get("/suggest-slot", response_model=SlotOut | None)
def suggest_slot(_: CurrentUser, db: DB):
    slot = db.scalar(
        select(ParkingSlot)
        .where(ParkingSlot.status == SlotStatus.available)
        .order_by(func.length(ParkingSlot.slot_number), ParkingSlot.slot_number)
        .limit(1)
    )
    return SlotOut.model_validate(slot) if slot else None


@router.post("/check-in", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def check_in(body: CheckInIn, user: CurrentUser, db: DB, tasks: BackgroundTasks):
    trace.step("logic", "Validation ทะเบียนรถ", f"จัดรูปแบบเป็น “{body.plate_number}” (ตัดช่องว่าง ตัวพิมพ์ใหญ่ ตรวจอักขระ)",
               feature="Transaction + Validation")
    if _plate_is_parked(db, body.plate_number):
        raise HTTPException(status.HTTP_409_CONFLICT, f"รถทะเบียน {body.plate_number} อยู่ในลานแล้ว")
    trace.step("logic", "กฎธุรกิจ: 1 ทะเบียนจอดได้ครั้งละ 1 คัน", "ไม่พบทะเบียนนี้ในลาน → ผ่าน")

    if body.slot_id is not None:
        slot = db.get(ParkingSlot, body.slot_id, with_for_update=True)
        if slot is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบช่องจอด")
        if slot.status != SlotStatus.available:
            raise HTTPException(status.HTTP_409_CONFLICT, f"ช่อง {slot.slot_number} ไม่ว่าง")
    else:
        slot = db.scalar(
            select(ParkingSlot)
            .where(ParkingSlot.status == SlotStatus.available)
            .order_by(func.length(ParkingSlot.slot_number), ParkingSlot.slot_number)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if slot is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "ลานจอดเต็ม ไม่มีช่องว่าง")
    trace.step(
        "logic",
        f"จองช่อง {slot.slot_number}",
        ("พนักงานเลือกเอง" if body.slot_id is not None else "ระบบเลือกช่องว่างแรก")
        + " · lock แถวด้วย SELECT … FOR UPDATE กันสองเครื่องจองช่องเดียวกัน",
        feature="แสดงจำนวนช่องว่าง / ช่องที่ถูกใช้งาน",
    )

    slot.status = SlotStatus.occupied
    session = ParkingSession(
        slot_id=slot.id, plate_number=body.plate_number, entry_time=utcnow(), entered_by=user.id
    )
    db.add(session)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "ช่องจอดหรือทะเบียนนี้ถูกใช้งานพร้อมกัน กรุณาลองใหม่") from None

    db.refresh(session)
    trace.step("logic", f"บันทึกรถเข้า {session.plate_number} → ช่อง {slot.slot_number}",
               "สร้าง parking_session (entry_time = ตอนนี้) และเปลี่ยนสถานะช่องเป็น occupied", feature="แสดงรถเข้า–ออก")
    log.info("check-in plate=%s slot=%s by=%s", session.plate_number, slot.slot_number, user.username)
    _trace_broadcast("check_in")
    tasks.add_task(
        manager.broadcast,
        parking_event("check_in", plate_number=session.plate_number, slot_number=slot.slot_number),
    )
    rule = pricing_rule(get_lot_settings(db))
    return session_out(session, {user.id: user.full_name or user.username}, rule)


@router.get("/active", response_model=list[SessionOut])
def active_sessions(_: CurrentUser, db: DB, q: str = ""):
    stmt = select(ParkingSession).where(ParkingSession.exit_time.is_(None))
    if q.strip():
        stmt = stmt.where(ParkingSession.plate_number.contains(q.strip().upper()))
    stmt = stmt.order_by(ParkingSession.entry_time)
    rule = pricing_rule(get_lot_settings(db))
    names = user_names(db)
    return [session_out(s, names, rule) for s in db.scalars(stmt)]


def _history_query(
    date_from: date | None, date_to: date | None, q: str, state: str | None
) -> Select:
    stmt = select(ParkingSession)
    if date_from or date_to:
        start, end = local_day_bounds(date_from or date(2000, 1, 1), date_to or date(2100, 1, 1))
        stmt = stmt.where(ParkingSession.entry_time >= start, ParkingSession.entry_time < end)
    if q.strip():
        stmt = stmt.where(ParkingSession.plate_number.contains(q.strip().upper()))
    if state == "active":
        stmt = stmt.where(ParkingSession.exit_time.is_(None))
    elif state == "completed":
        stmt = stmt.where(ParkingSession.exit_time.is_not(None))
    return stmt


@router.get("", response_model=SessionPage)
def history(
    _: CurrentUser,
    db: DB,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str = "",
    state: Literal["active", "completed"] | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    stmt = _history_query(date_from, date_to, q, state)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    trace.step("logic", "ค้นประวัติการจอด", f"พบ {total} รายการ (หน้า {page})", feature="ดูประวัติการจอดและรายได้")
    rows = db.scalars(
        stmt.order_by(ParkingSession.entry_time.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    rule = pricing_rule(get_lot_settings(db))
    names = user_names(db)
    return SessionPage(
        items=[session_out(s, names, rule) for s in rows], total=total or 0, page=page, page_size=page_size
    )


@router.get("/export")
def export_csv(
    _: ManagerUser,
    db: DB,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str = "",
    state: Literal["active", "completed"] | None = None,
):
    tz = get_settings().tz
    names = user_names(db)
    rows = db.scalars(_history_query(date_from, date_to, q, state).order_by(ParkingSession.entry_time)).all()

    buf = io.StringIO()
    buf.write("﻿")  # BOM so Excel reads Thai correctly
    writer = csv.writer(buf)
    writer.writerow(
        ["รหัส", "ทะเบียน", "ช่องจอด", "เวลาเข้า", "เวลาออก", "ระยะเวลา (นาที)", "ค่าจอด", "วิธีชำระ", "ผู้บันทึกเข้า", "ผู้บันทึกออก"]
    )
    for s in rows:
        o = session_out(s, names)
        writer.writerow(
            [
                o.id,
                o.plate_number,
                o.slot_number,
                o.entry_time.astimezone(tz).strftime("%Y-%m-%d %H:%M"),
                o.exit_time.astimezone(tz).strftime("%Y-%m-%d %H:%M") if o.exit_time else "",
                o.duration_minutes,
                f"{o.fee:.2f}" if o.fee is not None else "",
                o.payment.method.value if o.payment else "",
                o.entered_by or "",
                o.exited_by or "",
            ]
        )
    filename = f"parking-sessions-{date_from or 'all'}-{date_to or 'all'}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{session_id}/quote", response_model=QuoteOut)
def get_quote(session_id: int, _: CurrentUser, db: DB):
    s = _get_session(db, session_id)
    if s.exit_time is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "รายการนี้บันทึกรถออกแล้ว")
    now = utcnow()
    session = session_out(s)
    rule = pricing_rule(get_lot_settings(db))
    q = calculate_fee(session.entry_time, now, rule)
    _trace_fee(q, rule, " (ใบเสนอราคา)")
    return QuoteOut(
        session_id=s.id,
        plate_number=s.plate_number,
        slot_number=s.slot.slot_number,
        entry_time=session.entry_time,
        quoted_at=now,
        duration_minutes=q.duration_minutes,
        billable_hours=q.billable_hours,
        amount=float(q.amount),
    )


@router.post("/{session_id}/check-out", response_model=ReceiptOut)
def check_out(session_id: int, body: CheckOutIn, user: CurrentUser, db: DB, tasks: BackgroundTasks):
    s = _get_session(db, session_id, lock=True)
    if s.exit_time is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "รายการนี้บันทึกรถออกแล้ว")

    lot = get_lot_settings(db)
    now = utcnow()
    trace.step("logic", "Lock รายการจอด (SELECT … FOR UPDATE)", "กันกดปล่อยรถซ้ำพร้อมกันจากสองเครื่อง", feature="Transaction + Validation")
    rule = pricing_rule(lot)
    q = calculate_fee(session_out(s).entry_time, now, rule)
    _trace_fee(q, rule)
    if body.expected_amount is not None and abs(float(q.amount) - body.expected_amount) > 0.005:
        # Fee moved into the next hour between the quote and the confirmation.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "message": f"ค่าจอดเปลี่ยนเป็น {q.amount:.0f} บาท กรุณายืนยันยอดใหม่",
                "code": "fee_changed",
                "amount": float(q.amount),
            },
        )
    if body.expected_amount is not None:
        trace.step("logic", "ตรวจยอดตรงกับที่พนักงานเห็นบนจอ", f"คาดไว้ {body.expected_amount:.0f} = คำนวณได้ {q.amount:.0f} บาท → ผ่าน",
                   feature="Transaction + Validation")

    s.exit_time = now
    s.fee = q.amount
    s.exited_by = user.id
    slot = s.slot
    if slot.status == SlotStatus.occupied:
        slot.status = SlotStatus.available
    trace.step("logic", f"ปล่อยช่อง {slot.slot_number} กลับเป็นว่าง + บันทึกเวลาออก",
               f"ชำระ {q.amount:.0f} บาท ด้วย {body.method.value}" if q.amount > 0 else "อยู่ในช่วงจอดฟรี ไม่สร้างรายการชำระเงิน",
               feature="แสดงรถเข้า–ออก")
    if q.amount > 0:
        db.add(Payment(session_id=s.id, amount=q.amount, method=body.method, paid_at=now, received_by=user.id))
    db.commit()
    db.refresh(s)

    _trace_broadcast("check_out")
    log.info("check-out plate=%s slot=%s fee=%s by=%s", s.plate_number, slot.slot_number, q.amount, user.username)
    tasks.add_task(
        manager.broadcast,
        parking_event(
            "check_out", plate_number=s.plate_number, slot_number=slot.slot_number, amount=float(q.amount)
        ),
    )
    return ReceiptOut(session=session_out(s, user_names(db)), lot_name=lot.lot_name, billable_hours=q.billable_hours)


@router.patch("/{session_id}", response_model=SessionOut)
def fix_plate(session_id: int, body: PlateUpdate, _: CurrentUser, db: DB, tasks: BackgroundTasks):
    s = _get_session(db, session_id, lock=True)
    if s.exit_time is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "แก้ไขได้เฉพาะรถที่ยังอยู่ในลาน")
    plate = normalize_plate(body.plate_number)
    if plate != s.plate_number and _plate_is_parked(db, plate):
        raise HTTPException(status.HTTP_409_CONFLICT, f"รถทะเบียน {plate} อยู่ในลานแล้ว")
    s.plate_number = plate
    db.commit()
    tasks.add_task(manager.broadcast, parking_event("plate_fixed", plate_number=plate, slot_number=s.slot.slot_number))
    return session_out(s, user_names(db), pricing_rule(get_lot_settings(db)))
