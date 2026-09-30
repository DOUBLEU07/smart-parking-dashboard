from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from .. import trace
from ..config import get_settings
from ..deps import DB, ManagerUser
from ..models import ParkingSession, Payment, as_utc
from ..schemas import DailyPoint, ReportOut
from ..services import local_day_bounds, today_local

router = APIRouter(prefix="/reports", tags=["reports"])

MAX_RANGE_DAYS = 366


@router.get("/summary", response_model=ReportOut)
def report(_: ManagerUser, db: DB, date_from: date | None = None, date_to: date | None = None):
    date_to = date_to or today_local()
    date_from = date_from or date_to - timedelta(days=6)
    if date_from > date_to:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "วันที่เริ่มต้องไม่เกินวันที่สิ้นสุด")
    if (date_to - date_from).days >= MAX_RANGE_DAYS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "เลือกช่วงวันที่ได้ไม่เกิน 1 ปี")

    tz = get_settings().tz
    start, end = local_day_bounds(date_from, date_to)

    # Aggregated in Python: keeps day/hour bucketing in local time and portable
    # across Postgres and SQLite. Fine for a single lot's volume.
    payments = db.scalars(select(Payment).where(Payment.paid_at >= start, Payment.paid_at < end)).all()
    entered = db.scalars(
        select(ParkingSession.entry_time).where(ParkingSession.entry_time >= start, ParkingSession.entry_time < end)
    ).all()
    exited = db.scalars(
        select(ParkingSession).where(ParkingSession.exit_time >= start, ParkingSession.exit_time < end)
    ).all()

    days = [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]
    revenue = defaultdict(float)
    entries = defaultdict(int)
    exits = defaultdict(int)
    by_method = {"cash": 0.0, "qr": 0.0}
    hourly = [0] * 24

    for p in payments:
        revenue[as_utc(p.paid_at).astimezone(tz).date()] += float(p.amount)
        by_method[p.method.value] += float(p.amount)
    for t in entered:
        local = as_utc(t).astimezone(tz)
        entries[local.date()] += 1
        hourly[local.hour] += 1
    durations = []
    fees = []
    for s in exited:
        exits[as_utc(s.exit_time).astimezone(tz).date()] += 1
        durations.append((as_utc(s.exit_time) - as_utc(s.entry_time)).total_seconds() / 60)
        fees.append(float(s.fee or 0))

    total_revenue = sum(by_method.values())
    trace.step("logic", "รวมรายได้และสถิติตามช่วงวันที่", f"{date_from} ถึง {date_to}: รายได้ {total_revenue:.0f} บาท, รถออก {len(exited)} คัน",
               feature="ดูประวัติการจอดและรายได้")
    return ReportOut(
        date_from=date_from,
        date_to=date_to,
        total_revenue=total_revenue,
        total_entries=len(entered),
        total_exits=len(exited),
        avg_duration_minutes=round(sum(durations) / len(durations), 1) if durations else 0,
        avg_fee=round(sum(fees) / len(fees), 2) if fees else 0,
        revenue_by_method=by_method,
        daily=[DailyPoint(date=d, revenue=revenue[d], entries=entries[d], exits=exits[d]) for d in days],
        hourly_entries=hourly,
        peak_hour=max(range(24), key=hourly.__getitem__) if any(hourly) else None,
    )
