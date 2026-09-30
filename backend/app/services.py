from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    LotSettings,
    ParkingSession,
    ParkingSlot,
    Payment,
    SlotStatus,
    User,
    as_utc,
    utcnow,
)
from .pricing import FeeQuote, PricingRule, calculate_fee
from .schemas import ActivityItem, PaymentOut, SessionOut, SummaryOut


def get_lot_settings(db: Session) -> LotSettings:
    row = db.get(LotSettings, 1)
    if row is None:
        row = LotSettings(id=1)
        db.add(row)
        db.commit()
    return row


def pricing_rule(s: LotSettings) -> PricingRule:
    return PricingRule(s.free_minutes, s.hourly_rate, s.daily_cap)


def quote(session: ParkingSession, rule: PricingRule, at: datetime | None = None) -> FeeQuote:
    return calculate_fee(as_utc(session.entry_time), at or utcnow(), rule)


def local_day_bounds(day_from: date, day_to: date) -> tuple[datetime, datetime]:
    """UTC range covering local days [day_from, day_to] inclusive."""
    tz = get_settings().tz
    start = datetime.combine(day_from, time.min, tz).astimezone(UTC)
    end = datetime.combine(day_to + timedelta(days=1), time.min, tz).astimezone(UTC)
    return start, end


def today_local() -> date:
    return datetime.now(get_settings().tz).date()


def session_out(
    s: ParkingSession,
    users: dict[int, str] | None = None,
    rule: PricingRule | None = None,
) -> SessionOut:
    entry = as_utc(s.entry_time)
    exit_ = as_utc(s.exit_time)
    end = exit_ or utcnow()
    current_fee = None
    if exit_ is None and rule is not None:
        current_fee = float(calculate_fee(entry, end, rule).amount)
    users = users or {}
    return SessionOut(
        id=s.id,
        slot_id=s.slot_id,
        slot_number=s.slot.slot_number,
        plate_number=s.plate_number,
        entry_time=entry,
        exit_time=exit_,
        duration_minutes=max(0, int((end - entry).total_seconds() // 60)),
        fee=float(s.fee) if s.fee is not None else None,
        current_fee=current_fee,
        payment=PaymentOut.model_validate(s.payment) if s.payment else None,
        entered_by=users.get(s.entered_by) if s.entered_by else None,
        exited_by=users.get(s.exited_by) if s.exited_by else None,
    )


def user_names(db: Session) -> dict[int, str]:
    return {u.id: (u.full_name or u.username) for u in db.scalars(select(User))}


def build_summary(db: Session) -> SummaryOut:
    lot = get_lot_settings(db)
    counts = dict(
        db.execute(select(ParkingSlot.status, func.count()).group_by(ParkingSlot.status)).all()
    )
    occupied = counts.get(SlotStatus.occupied, 0)
    available = counts.get(SlotStatus.available, 0)
    maintenance = counts.get(SlotStatus.maintenance, 0)
    capacity = occupied + available
    rate = round(occupied / capacity * 100, 1) if capacity else 0.0

    start, end = local_day_bounds(today_local(), today_local())
    revenue = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.paid_at >= start, Payment.paid_at < end
        )
    )
    entries = db.scalar(
        select(func.count()).where(ParkingSession.entry_time >= start, ParkingSession.entry_time < end)
    )
    exits = db.scalar(
        select(func.count()).where(ParkingSession.exit_time >= start, ParkingSession.exit_time < end)
    )

    recent_in = db.scalars(
        select(ParkingSession).order_by(ParkingSession.entry_time.desc()).limit(10)
    ).all()
    recent_out = db.scalars(
        select(ParkingSession)
        .where(ParkingSession.exit_time.is_not(None))
        .order_by(ParkingSession.exit_time.desc())
        .limit(10)
    ).all()
    activity = [
        ActivityItem(kind="entry", at=as_utc(s.entry_time), plate_number=s.plate_number, slot_number=s.slot.slot_number)
        for s in recent_in
    ] + [
        ActivityItem(
            kind="exit",
            at=as_utc(s.exit_time),
            plate_number=s.plate_number,
            slot_number=s.slot.slot_number,
            amount=float(s.fee or 0),
        )
        for s in recent_out
    ]
    activity.sort(key=lambda a: a.at, reverse=True)

    return SummaryOut(
        lot_name=lot.lot_name,
        total_slots=occupied + available + maintenance,
        capacity=capacity,
        occupied=occupied,
        available=available,
        maintenance=maintenance,
        occupancy_rate=rate,
        alert_threshold=lot.alert_threshold,
        near_full=capacity > 0 and rate >= lot.alert_threshold,
        is_full=capacity > 0 and available == 0,
        today_revenue=float(revenue or 0),
        today_entries=entries or 0,
        today_exits=exits or 0,
        recent_activity=activity[:10],
        generated_at=utcnow(),
    )
