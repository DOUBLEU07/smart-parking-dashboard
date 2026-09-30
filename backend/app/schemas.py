import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import PaymentMethod, Role, SlotStatus


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def normalize_plate(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip().upper()
    if not 2 <= len(value) <= 20:
        raise ValueError("ทะเบียนรถต้องมี 2–20 ตัวอักษร")
    if not re.fullmatch(r"[0-9A-Z฀-๿ \-]+", value):
        raise ValueError("ทะเบียนรถมีอักขระที่ไม่รองรับ")
    return value


# ---------- auth / users ----------

Password = Field(min_length=8, max_length=72)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=72)


class UserOut(ORM):
    id: int
    username: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ChangePasswordIn(BaseModel):
    current_password: str = Field(max_length=72)
    new_password: str = Password


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: str = Field(default="", max_length=100)
    role: Role = Role.staff
    password: str = Password


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=100)
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)


# ---------- slots ----------


class SlotCreate(BaseModel):
    slot_number: str = Field(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9-]+$")

    @field_validator("slot_number")
    @classmethod
    def upper(cls, v: str) -> str:
        return v.upper()


class SlotBulkCreate(BaseModel):
    prefix: str = Field(default="P", max_length=4, pattern=r"^[A-Za-z]*$")
    count: int = Field(ge=1, le=200)


class SlotUpdate(BaseModel):
    slot_number: str | None = Field(default=None, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9-]+$")
    status: SlotStatus | None = None


class ActiveSessionBrief(BaseModel):
    id: int
    plate_number: str
    entry_time: datetime


class SlotOut(ORM):
    id: int
    slot_number: str
    status: SlotStatus
    session: ActiveSessionBrief | None = None


# ---------- sessions ----------


class CheckInIn(BaseModel):
    plate_number: str
    slot_id: int | None = None

    @field_validator("plate_number")
    @classmethod
    def check_plate(cls, v: str) -> str:
        return normalize_plate(v)


class PlateUpdate(BaseModel):
    plate_number: str

    @field_validator("plate_number")
    @classmethod
    def check_plate(cls, v: str) -> str:
        return normalize_plate(v)


class CheckOutIn(BaseModel):
    method: PaymentMethod
    expected_amount: float | None = Field(
        default=None, ge=0, description="ยอดที่พนักงานเห็นบนหน้าจอ ใช้ตรวจว่ายอดไม่เปลี่ยนก่อนยืนยัน"
    )


class QuoteOut(BaseModel):
    session_id: int
    plate_number: str
    slot_number: str
    entry_time: datetime
    quoted_at: datetime
    duration_minutes: int
    billable_hours: int
    amount: float


class PaymentOut(ORM):
    id: int
    amount: float
    method: PaymentMethod
    paid_at: datetime


class SessionOut(BaseModel):
    id: int
    slot_id: int
    slot_number: str
    plate_number: str
    entry_time: datetime
    exit_time: datetime | None
    duration_minutes: int
    fee: float | None
    current_fee: float | None = None
    payment: PaymentOut | None = None
    entered_by: str | None = None
    exited_by: str | None = None


class SessionPage(BaseModel):
    items: list[SessionOut]
    total: int
    page: int
    page_size: int


class ReceiptOut(BaseModel):
    session: SessionOut
    lot_name: str
    billable_hours: int


# ---------- dashboard / reports ----------


class ActivityItem(BaseModel):
    kind: str  # "entry" | "exit"
    at: datetime
    plate_number: str
    slot_number: str
    amount: float | None = None


class SummaryOut(BaseModel):
    lot_name: str
    total_slots: int
    capacity: int
    occupied: int
    available: int
    maintenance: int
    occupancy_rate: float
    alert_threshold: int
    near_full: bool
    is_full: bool
    today_revenue: float
    today_entries: int
    today_exits: int
    recent_activity: list[ActivityItem]
    generated_at: datetime


class DailyPoint(BaseModel):
    date: date
    revenue: float
    entries: int
    exits: int


class ReportOut(BaseModel):
    date_from: date
    date_to: date
    total_revenue: float
    total_entries: int
    total_exits: int
    avg_duration_minutes: float
    avg_fee: float
    revenue_by_method: dict[str, float]
    daily: list[DailyPoint]
    hourly_entries: list[int]
    peak_hour: int | None


# ---------- settings ----------


class LotSettingsBase(BaseModel):
    lot_name: str = Field(min_length=1, max_length=100)
    free_minutes: int = Field(ge=0, le=24 * 60)
    hourly_rate: float = Field(ge=0, le=100000)
    daily_cap: float | None = Field(default=None, ge=0, le=1000000)
    alert_threshold: int = Field(ge=50, le=100)


class LotSettingsOut(LotSettingsBase, ORM):
    updated_at: datetime


class FeePreviewIn(BaseModel):
    rule: LotSettingsBase
    durations: list[int] = Field(max_length=50, description="นาที")


class FeePreviewItem(BaseModel):
    minutes: int
    billable_hours: int
    amount: float
