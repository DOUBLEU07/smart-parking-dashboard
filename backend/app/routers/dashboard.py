from fastapi import APIRouter

from .. import trace
from ..deps import DB, CurrentUser
from ..schemas import SummaryOut
from ..services import build_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=SummaryOut)
def summary(_: CurrentUser, db: DB):
    s = build_summary(db)
    trace.step(
        "logic",
        "สรุป KPI ของลาน",
        f"ว่าง {s.available}/{s.capacity} · ใช้งาน {s.occupancy_rate}% · รายได้วันนี้ {s.today_revenue:.0f} บาท",
        feature="Dashboard สรุปข้อมูลสำคัญ",
    )
    trace.step(
        "logic",
        "ตรวจเกณฑ์แจ้งเตือนใกล้เต็ม",
        f"{s.occupancy_rate}% {'≥' if s.near_full else '<'} {s.alert_threshold}% → "
        + ("แจ้งเตือน!" if s.near_full else "ยังไม่แจ้งเตือน"),
        feature="แจ้งเตือนเมื่อพื้นที่จอดใกล้เต็ม",
    )
    return s
