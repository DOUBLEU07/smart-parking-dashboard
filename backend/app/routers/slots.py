import re

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError

from ..deps import DB, CurrentUser, ManagerUser
from ..models import ParkingSession, ParkingSlot, SlotStatus, as_utc
from ..realtime import manager, parking_event
from ..schemas import ActiveSessionBrief, SlotBulkCreate, SlotCreate, SlotOut, SlotUpdate

router = APIRouter(prefix="/slots", tags=["slots"])


def _natural_key(slot: ParkingSlot):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", slot.slot_number)]


@router.get("", response_model=list[SlotOut])
def list_slots(_: CurrentUser, db: DB):
    slots = sorted(db.scalars(select(ParkingSlot)), key=_natural_key)
    active = {
        s.slot_id: s for s in db.scalars(select(ParkingSession).where(ParkingSession.exit_time.is_(None)))
    }
    out = []
    for slot in slots:
        s = active.get(slot.id)
        out.append(
            SlotOut(
                id=slot.id,
                slot_number=slot.slot_number,
                status=slot.status,
                session=ActiveSessionBrief(id=s.id, plate_number=s.plate_number, entry_time=as_utc(s.entry_time))
                if s
                else None,
            )
        )
    return out


def _commit_or_conflict(db: DB, message: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, message) from None


@router.post("", response_model=SlotOut, status_code=status.HTTP_201_CREATED)
def create_slot(body: SlotCreate, _: ManagerUser, db: DB, tasks: BackgroundTasks):
    slot = ParkingSlot(slot_number=body.slot_number)
    db.add(slot)
    _commit_or_conflict(db, f"มีช่องจอด {body.slot_number} อยู่แล้ว")
    tasks.add_task(manager.broadcast, parking_event("slots_changed"))
    return SlotOut(id=slot.id, slot_number=slot.slot_number, status=slot.status)


@router.post("/bulk", response_model=list[SlotOut], status_code=status.HTTP_201_CREATED)
def bulk_create(body: SlotBulkCreate, _: ManagerUser, db: DB, tasks: BackgroundTasks):
    prefix = body.prefix.upper()
    existing = set(db.scalars(select(ParkingSlot.slot_number)))
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    numbers = [int(m.group(1)) for n in existing if (m := pattern.match(n))]
    start = max(numbers, default=0) + 1
    width = max(2, len(str(start + body.count - 1)))
    created = []
    for i in range(start, start + body.count):
        slot = ParkingSlot(slot_number=f"{prefix}{i:0{width}d}")
        db.add(slot)
        created.append(slot)
    _commit_or_conflict(db, "เลขช่องจอดซ้ำกับที่มีอยู่")
    tasks.add_task(manager.broadcast, parking_event("slots_changed"))
    return [SlotOut(id=s.id, slot_number=s.slot_number, status=s.status) for s in created]


@router.patch("/{slot_id}", response_model=SlotOut)
def update_slot(slot_id: int, body: SlotUpdate, _: ManagerUser, db: DB, tasks: BackgroundTasks):
    slot = db.get(ParkingSlot, slot_id, with_for_update=True)
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบช่องจอด")
    if body.status is not None and body.status != slot.status:
        if body.status == SlotStatus.occupied:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "สถานะ 'มีรถจอด' ต้องเกิดจากการบันทึกรถเข้าเท่านั้น")
        if slot.status == SlotStatus.occupied:
            raise HTTPException(status.HTTP_409_CONFLICT, "มีรถจอดอยู่ในช่องนี้ ต้องบันทึกรถออกก่อน")
        slot.status = body.status
    if body.slot_number is not None:
        slot.slot_number = body.slot_number.upper()
    _commit_or_conflict(db, "เลขช่องจอดซ้ำกับที่มีอยู่")
    tasks.add_task(manager.broadcast, parking_event("slots_changed", slot_number=slot.slot_number))
    return SlotOut(id=slot.id, slot_number=slot.slot_number, status=slot.status)


@router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_slot(slot_id: int, _: ManagerUser, db: DB, tasks: BackgroundTasks):
    slot = db.get(ParkingSlot, slot_id)
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบช่องจอด")
    if db.scalar(select(exists().where(ParkingSession.slot_id == slot_id))):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "ช่องนี้มีประวัติการจอดแล้ว ลบไม่ได้ ให้ตั้งสถานะเป็น 'ปิดปรับปรุง' แทน",
        )
    db.delete(slot)
    db.commit()
    tasks.add_task(manager.broadcast, parking_event("slots_changed"))
