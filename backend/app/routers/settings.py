from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks

from ..deps import DB, CurrentUser, OwnerUser
from ..models import utcnow
from ..pricing import PricingRule, fee_for_minutes
from ..realtime import manager, parking_event
from ..schemas import FeePreviewIn, FeePreviewItem, LotSettingsBase, LotSettingsOut
from ..services import get_lot_settings

router = APIRouter(prefix="/settings", tags=["settings"])


def _dec(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value))


@router.get("", response_model=LotSettingsOut)
def read_settings(_: CurrentUser, db: DB):
    return get_lot_settings(db)


@router.put("", response_model=LotSettingsOut)
def update_settings(body: LotSettingsBase, owner: OwnerUser, db: DB, tasks: BackgroundTasks):
    row = get_lot_settings(db)
    row.lot_name = body.lot_name
    row.free_minutes = body.free_minutes
    row.hourly_rate = _dec(body.hourly_rate)
    row.daily_cap = _dec(body.daily_cap)
    row.alert_threshold = body.alert_threshold
    row.updated_at = utcnow()
    row.updated_by = owner.id
    db.commit()
    tasks.add_task(manager.broadcast, parking_event("settings_changed"))
    return row


@router.post("/preview", response_model=list[FeePreviewItem])
def preview(body: FeePreviewIn, _: OwnerUser):
    rule = PricingRule(body.rule.free_minutes, _dec(body.rule.hourly_rate), _dec(body.rule.daily_cap))
    out = []
    for minutes in body.durations:
        q = fee_for_minutes(minutes, rule)
        out.append(FeePreviewItem(minutes=minutes, billable_hours=q.billable_hours, amount=float(q.amount)))
    return out
