from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..deps import DB, OwnerUser
from ..models import Role, User
from ..schemas import UserCreate, UserOut, UserUpdate
from ..security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(_: OwnerUser, db: DB):
    return db.scalars(select(User).order_by(User.id)).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, _: OwnerUser, db: DB):
    user = User(
        username=body.username,
        full_name=body.full_name,
        role=body.role,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"มีชื่อผู้ใช้ {body.username} อยู่แล้ว") from None
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, owner: OwnerUser, db: DB):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบผู้ใช้")

    losing_owner = user.role == Role.owner and (
        (body.role is not None and body.role != Role.owner) or body.is_active is False
    )
    if losing_owner:
        if user.id == owner.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "ไม่สามารถลดสิทธิ์หรือปิดบัญชีของตัวเองได้")
        active_owners = db.scalar(
            select(func.count()).where(User.role == Role.owner, User.is_active.is_(True))
        )
        if active_owners <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "ต้องมีเจ้าของ (owner) ที่ใช้งานได้อย่างน้อย 1 คน")

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password:
        user.password_hash = hash_password(body.password)
    db.commit()
    return user
