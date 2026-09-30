"""Initial data: settings row, first owner account, and optional demo data.

Demo data leaves the lot at 80% occupancy so that checking in three more cars
crosses the 90% alert threshold during the demo.
"""

import logging
import random
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    LotSettings,
    ParkingSession,
    ParkingSlot,
    Payment,
    PaymentMethod,
    Role,
    SlotStatus,
    User,
    utcnow,
)
from .pricing import calculate_fee
from .security import hash_password
from .services import pricing_rule

log = logging.getLogger(__name__)

DEMO_SLOTS = 30
DEMO_OCCUPIED = 24
HISTORY_DAYS = 14

THAI_PREFIXES = ["กข", "กท", "ขค", "ฆง", "จฉ", "ชซ", "ฌญ", "ฐฑ", "ถท", "นบ", "ปผ", "พฟ", "มย", "รล", "วศ", "สห"]


def _plate(rng: random.Random) -> str:
    lead = str(rng.randint(1, 9)) if rng.random() < 0.4 else ""
    return f"{lead}{rng.choice(THAI_PREFIXES)} {rng.randint(1, 9999)}"


def seed(db: Session) -> None:
    settings = get_settings()

    if db.get(LotSettings, 1) is None:
        db.add(LotSettings(id=1))
        db.commit()

    if db.scalar(select(func.count()).select_from(User)) == 0:
        db.add(
            User(
                username=settings.initial_owner_username,
                full_name="เจ้าของลาน",
                role=Role.owner,
                password_hash=hash_password(settings.initial_owner_password),
            )
        )
        if settings.seed_demo_data:
            db.add_all(
                [
                    User(username="manager", full_name="ผู้ดูแลลาน", role=Role.manager,
                         password_hash=hash_password(settings.demo_password)),
                    User(username="staff", full_name="พนักงานประจำลาน", role=Role.staff,
                         password_hash=hash_password(settings.demo_password)),
                ]
            )
        db.commit()
        log.info("created initial users")

    if settings.seed_demo_data and db.scalar(select(func.count()).select_from(ParkingSlot)) == 0:
        _seed_demo(db)


def _seed_demo(db: Session) -> None:
    rng = random.Random(42)
    staff = db.scalar(select(User).where(User.username == "staff"))
    staff_id = staff.id if staff else None
    rule = pricing_rule(db.get(LotSettings, 1))

    slots = [ParkingSlot(slot_number=f"P{i:02d}") for i in range(1, DEMO_SLOTS + 1)]
    db.add_all(slots)
    db.flush()

    now = utcnow()
    used_plates: set[str] = set()

    # Completed history for the past two weeks (busier on weekday office hours).
    for day in range(HISTORY_DAYS, -1, -1):
        base = (now - timedelta(days=day)).replace(hour=0, minute=0, second=0, microsecond=0)
        visits = rng.randint(35, 60)
        for _ in range(visits):
            # 00:00 UTC is 07:00 in Bangkok; keep arrivals between ~07:00 and ~20:00 local.
            entry = base + timedelta(minutes=rng.randint(0, 13 * 60))
            exit_ = entry + timedelta(minutes=rng.choice([10, 25, 45, 70, 95, 130, 180, 240, 320, 480]))
            if exit_ >= now - timedelta(minutes=5):
                continue
            slot = rng.choice(slots)
            fee = calculate_fee(entry, exit_, rule).amount
            s = ParkingSession(
                slot_id=slot.id, plate_number=_plate(rng), entry_time=entry, exit_time=exit_,
                fee=fee, entered_by=staff_id, exited_by=staff_id,
            )
            db.add(s)
            db.flush()
            if fee > 0:
                method = PaymentMethod.qr if rng.random() < 0.45 else PaymentMethod.cash
                db.add(Payment(session_id=s.id, amount=fee, method=method, paid_at=exit_, received_by=staff_id))

    # Cars currently parked.
    for slot in rng.sample(slots, DEMO_OCCUPIED):
        plate = _plate(rng)
        while plate in used_plates:
            plate = _plate(rng)
        used_plates.add(plate)
        slot.status = SlotStatus.occupied
        db.add(
            ParkingSession(
                slot_id=slot.id, plate_number=plate,
                entry_time=now - timedelta(minutes=rng.randint(5, 300)), entered_by=staff_id,
            )
        )
    db.commit()
    log.info("seeded demo data: %d slots, %d occupied", DEMO_SLOTS, DEMO_OCCUPIED)
