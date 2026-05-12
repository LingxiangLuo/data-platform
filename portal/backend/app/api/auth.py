from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password, create_access_token, hash_password, get_current_user
from app.models.user import SysUser

router = APIRouter(prefix="/auth", tags=["认证"])


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
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(SysUser).filter(SysUser.username == req.username).first()
    if not user or not verify_password(req.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if user.status != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")

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
