import enum
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; every stored timestamp is UTC, so re-attach it."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Role(str, enum.Enum):
    owner = "owner"
    manager = "manager"
    staff = "staff"


ROLE_RANK = {Role.staff: 1, Role.manager: 2, Role.owner: 3}


class SlotStatus(str, enum.Enum):
    available = "available"
    occupied = "occupied"
    maintenance = "maintenance"


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    qr = "qr"


def _enum(cls: type[enum.Enum]) -> Enum:
    return Enum(cls, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e])


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(_enum(Role), default=Role.staff)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ParkingSlot(Base):
    __tablename__ = "parking_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_number: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    status: Mapped[SlotStatus] = mapped_column(_enum(SlotStatus), default=SlotStatus.available)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ParkingSession(Base):
    __tablename__ = "parking_sessions"
    __table_args__ = (
        # One active (not yet exited) session per slot and per plate.
        Index(
            "uq_active_session_slot",
            "slot_id",
            unique=True,
            postgresql_where=text("exit_time IS NULL"),
            sqlite_where=text("exit_time IS NULL"),
        ),
        Index(
            "uq_active_session_plate",
            "plate_number",
            unique=True,
            postgresql_where=text("exit_time IS NULL"),
            sqlite_where=text("exit_time IS NULL"),
        ),
        CheckConstraint("exit_time IS NULL OR exit_time >= entry_time", name="ck_exit_after_entry"),
        CheckConstraint("fee IS NULL OR fee >= 0", name="ck_fee_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("parking_slots.id", ondelete="RESTRICT"), index=True)
    plate_number: Mapped[str] = mapped_column(String(20), index=True)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    entered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    exited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    slot: Mapped[ParkingSlot] = relationship(lazy="joined", innerjoin=True)
    payment: Mapped["Payment | None"] = relationship(back_populates="session", uselist=False)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_amount_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("parking_sessions.id", ondelete="RESTRICT"), unique=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    method: Mapped[PaymentMethod] = mapped_column(_enum(PaymentMethod))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    received_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    session: Mapped[ParkingSession] = relationship(back_populates="payment")


class LotSettings(Base):
    """Single-row table (id = 1) holding pricing and alert configuration."""

    __tablename__ = "lot_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    lot_name: Mapped[str] = mapped_column(String(100), default="Smart Parking")
    free_minutes: Mapped[int] = mapped_column(Integer, default=15)
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("20"))
    daily_cap: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=Decimal("200"))
    alert_threshold: Mapped[int] = mapped_column(Integer, default=90)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
