from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import hashlib
import hmac
import json
import logging
import secrets
import time
from collections import defaultdict
from threading import Lock

from app.core.database import get_db
from app.core.security import verify_password, create_access_token, hash_password, get_current_user
from app.models.user import SysUser

router = APIRouter(prefix="/auth", tags=["认证"])

# 登录暴力破解防护：按 IP 计数，5 次失败后锁定 5 分钟
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_LOCKOUT_SECONDS = 300
_login_attempts: dict[str, list[float]] = defaultdict(list)
_login_lock = Lock()


def _check_login_rate(ip: str) -> None:
    now = time.time()
    with _login_lock:
        attempts = [t for t in _login_attempts[ip] if now - t < _LOGIN_LOCKOUT_SECONDS]
        _login_attempts[ip] = attempts
        if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
            retry_after = int(_LOGIN_LOCKOUT_SECONDS - (now - attempts[0]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"登录尝试过于频繁，请 {retry_after} 秒后再试",
            )


def _record_failed_login(ip: str) -> None:
    with _login_lock:
        _login_attempts[ip].append(time.time())


def _clear_login_attempts(ip: str) -> None:
    with _login_lock:
        _login_attempts.pop(ip, None)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    _check_login_rate(client_ip)
    user = db.query(SysUser).filter(SysUser.username == req.username).first()
    if not user or not verify_password(req.password, user.password):
        _record_failed_login(client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if user.status != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")

    _clear_login_attempts(client_ip)

    token = create_access_token(data={"sub": user.username})
    return LoginResponse(
        access_token=token,
        user={
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "role": user.role,
            "email": user.email,
        },
    )


@router.get("/me")
def get_me(current_user: SysUser = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "real_name": current_user.real_name,
        "role": current_user.role,
        "email": current_user.email,
        "phone": current_user.phone,
    }


@router.put("/password")
def change_password(
    req: ChangePasswordRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(req.old_password, current_user.password):
        raise HTTPException(status_code=400, detail="旧密码错误")
    current_user.password = hash_password(req.new_password)
    db.commit()
    return {"message": "密码修改成功"}
