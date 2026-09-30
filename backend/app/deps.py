from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import trace
from .database import get_db
from .models import ROLE_RANK, Role, User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)

DB = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "กรุณาเข้าสู่ระบบ",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    user_id = decode_token(credentials.credentials)
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        trace.step("auth", "JWT ไม่ถูกต้องหรือหมดอายุ", feature="Authentication", ok=False)
        raise unauthorized
    trace.step("auth", "ตรวจ JWT ผ่าน (Authentication)", f"user={user.username} role={user.role.value}", feature="Authentication")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(minimum: Role) -> Callable[[User], User]:
    def checker(user: CurrentUser) -> User:
        passed = ROLE_RANK[user.role] >= ROLE_RANK[minimum]
        trace.step("auth", f"ตรวจสิทธิ์ RBAC: ต้องเป็น {minimum.value} ขึ้นไป", f"role={user.role.value} → {'ผ่าน' if passed else 'ไม่ผ่าน'}",
                   feature="Authorization", ok=passed)
        if not passed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "ไม่มีสิทธิ์ใช้งานส่วนนี้")
        return user

    return checker


ManagerUser = Annotated[User, Depends(require_role(Role.manager))]
OwnerUser = Annotated[User, Depends(require_role(Role.owner))]
