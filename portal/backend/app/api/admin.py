"""管理后台 API — 用户/角色/权限/SSO/通知配置"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import require_permission
from app.core.security import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/sso/public")
def list_sso_public(db: Session = Depends(get_db)):
    """公开接口：返回已启用的 SSO 提供商列表（供登录页展示按钮）"""
    from app.models.oauth_config import SysOAuthConfig
    configs = db.query(SysOAuthConfig).filter(SysOAuthConfig.enabled == True).all()
    return [{"provider": c.provider} for c in configs]


# ─── Schemas ────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    password: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    dept_id: Optional[int] = None
    role_codes: List[str] = []

class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    dept_id: Optional[int] = None
    status: Optional[int] = None
    password: Optional[str] = None
    role_codes: Optional[List[str]] = None

class RoleCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    permission_codes: List[str] = []

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_codes: Optional[List[str]] = None

class OAuthConfigUpdate(BaseModel):
    app_id: Optional[str] = None
    app_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    enabled: Optional[bool] = None
    extra_config: Optional[dict] = None

class SysConfigUpdate(BaseModel):
    value: dict
    description: Optional[str] = None


# ─── Users ──────────────────────────────────────────────────────────────────

@router.get("/users")
def list_users(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("user:manage")),
):
    from app.models.user import SysUser
    from app.models.role import SysUserRole, SysRole
    q = db.query(SysUser)
    if keyword:
        q = q.filter(
            SysUser.username.contains(keyword) | SysUser.real_name.contains(keyword)
        )
    total = q.count()
    users = q.offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for u in users:
        roles = (
            db.query(SysRole)
            .join(SysUserRole, SysUserRole.role_id == SysRole.id)
            .filter(SysUserRole.user_id == u.id)
            .all()
        )
        result.append({
            "id": u.id,
            "username": u.username,
            "real_name": u.real_name,
            "email": u.email,
            "phone": u.phone,
            "dept_id": u.dept_id,
            "status": u.status,
            "avatar": u.avatar,
            "last_login_at": u.last_login_at,
            "oauth_provider": u.oauth_provider,
            "created_at": u.created_at,
            "roles": [{"id": r.id, "code": r.code, "name": r.name} for r in roles],
        })
    return {"total": total, "items": result}


@router.post("/users", status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("user:manage")),
):
    from app.models.user import SysUser
    from app.models.role import SysUserRole, SysRole
    if db.query(SysUser).filter(SysUser.username == body.username).first():
        raise HTTPException(400, "用户名已存在")
    user = SysUser(
        username=body.username,
        password=hash_password(body.password),
        real_name=body.real_name,
        email=body.email,
        phone=body.phone,
        dept_id=body.dept_id,
        status=1,
    )
    db.add(user)
    db.flush()
    for code in body.role_codes:
        role = db.query(SysRole).filter(SysRole.code == code).first()
        if role:
            db.add(SysUserRole(user_id=user.id, role_id=role.id, granted_by=current_user.id))
    db.commit()
    return {"id": user.id, "username": user.username}


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("user:manage")),
):
    from app.models.user import SysUser
    from app.models.role import SysUserRole, SysRole
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    if body.real_name is not None:
        user.real_name = body.real_name
    if body.email is not None:
        user.email = body.email
    if body.phone is not None:
        user.phone = body.phone
    if body.dept_id is not None:
        user.dept_id = body.dept_id
    if body.status is not None:
        user.status = body.status
    if body.password:
        user.password = hash_password(body.password)
    if body.role_codes is not None:
        db.query(SysUserRole).filter(SysUserRole.user_id == user_id).delete()
        for code in body.role_codes:
            role = db.query(SysRole).filter(SysRole.code == code).first()
            if role:
                db.add(SysUserRole(user_id=user_id, role_id=role.id, granted_by=current_user.id))
    db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("user:manage")),
):
    from app.models.user import SysUser
    from app.models.role import SysUserRole
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.username == "admin":
        raise HTTPException(400, "不能删除内置管理员")
    if user.id == current_user.id:
        raise HTTPException(400, "不能删除自己的账号")
    db.query(SysUserRole).filter(SysUserRole.user_id == user_id).delete()
    db.delete(user)
    db.commit()
    return {"ok": True}


# ─── Roles ──────────────────────────────────────────────────────────────────

@router.get("/roles")
def list_roles(
    db: Session = Depends(get_db),
    _=Depends(require_permission("role:manage")),
):
    from app.models.role import SysRole, SysRolePermission, SysPermission
    roles = db.query(SysRole).all()
    result = []
    for r in roles:
        perms = (
            db.query(SysPermission)
            .join(SysRolePermission, SysRolePermission.permission_id == SysPermission.id)
            .filter(SysRolePermission.role_id == r.id)
            .all()
        )
        result.append({
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "description": r.description,
            "is_system": r.is_system,
            "permissions": [{"id": p.id, "code": p.code, "name": p.name} for p in perms],
        })
    return result


@router.post("/roles", status_code=201)
def create_role(
    body: RoleCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("role:manage")),
):
    from app.models.role import SysRole, SysRolePermission, SysPermission
    if db.query(SysRole).filter(SysRole.code == body.code).first():
        raise HTTPException(400, "角色代码已存在")
    role = SysRole(code=body.code, name=body.name, description=body.description)
    db.add(role)
    db.flush()
    for code in body.permission_codes:
        perm = db.query(SysPermission).filter(SysPermission.code == code).first()
        if perm:
            db.add(SysRolePermission(role_id=role.id, permission_id=perm.id))
    db.commit()
    return {"id": role.id, "code": role.code}


@router.put("/roles/{role_id}")
def update_role(
    role_id: int,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("role:manage")),
):
    from app.models.role import SysRole, SysRolePermission, SysPermission
    role = db.query(SysRole).filter(SysRole.id == role_id).first()
    if not role:
        raise HTTPException(404, "角色不存在")
    if role.is_system:
        raise HTTPException(400, "系统内置角色不可修改")
    if body.name is not None:
        role.name = body.name
    if body.description is not None:
        role.description = body.description
    if body.permission_codes is not None:
        db.query(SysRolePermission).filter(SysRolePermission.role_id == role_id).delete()
        for code in body.permission_codes:
            perm = db.query(SysPermission).filter(SysPermission.code == code).first()
            if perm:
                db.add(SysRolePermission(role_id=role_id, permission_id=perm.id))
    db.commit()
    return {"ok": True}


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("role:manage")),
):
    from app.models.role import SysRole, SysRolePermission, SysUserRole
    role = db.query(SysRole).filter(SysRole.id == role_id).first()
    if not role:
        raise HTTPException(404, "角色不存在")
    if role.is_system:
        raise HTTPException(400, "系统内置角色不可删除")
    db.query(SysRolePermission).filter(SysRolePermission.role_id == role_id).delete()
    db.query(SysUserRole).filter(SysUserRole.role_id == role_id).delete()
    db.delete(role)
    db.commit()
    return {"ok": True}


# ─── Permissions ────────────────────────────────────────────────────────────

@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    _=Depends(require_permission("role:manage")),
):
    from app.models.role import SysPermission
    perms = db.query(SysPermission).all()
    return [{"id": p.id, "code": p.code, "name": p.name, "resource_type": p.resource_type, "action": p.action} for p in perms]


# ─── OAuth / SSO Config ─────────────────────────────────────────────────────

@router.get("/sso")
def list_sso(
    db: Session = Depends(get_db),
    _=Depends(require_permission("system:config")),
):
    from app.models.oauth_config import SysOAuthConfig
    configs = db.query(SysOAuthConfig).all()
    return [
        {
            "id": c.id,
            "provider": c.provider,
            "app_id": c.app_id,
            "redirect_uri": c.redirect_uri,
            "enabled": c.enabled,
            "extra_config": _redact(c.extra_config) if c.extra_config else None,
        }
        for c in configs
    ]


@router.put("/sso/{provider}")
def update_sso(
    provider: str,
    body: OAuthConfigUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("system:config")),
):
    from app.models.oauth_config import SysOAuthConfig
    cfg = db.query(SysOAuthConfig).filter(SysOAuthConfig.provider == provider).first()
    if not cfg:
        cfg = SysOAuthConfig(provider=provider)
        db.add(cfg)
    if body.app_id is not None:
        cfg.app_id = body.app_id
    if body.app_secret is not None:
        cfg.app_secret = body.app_secret
    if body.redirect_uri is not None:
        cfg.redirect_uri = body.redirect_uri
    if body.enabled is not None:
        cfg.enabled = body.enabled
    if body.extra_config is not None:
        cfg.extra_config = body.extra_config
    db.commit()
    return {"ok": True}


# ─── System Config (SMTP / Notify) ──────────────────────────────────────────

_SENSITIVE_FIELDS = {"password", "secret", "access_key", "secret_key", "token", "api_key", "credential"}


def _redact(value: dict) -> dict:
    """脱敏：将敏感字段替换为占位符（递归处理嵌套 dict）"""
    if not isinstance(value, dict):
        return value
    return {
        k: "***" if k in _SENSITIVE_FIELDS and v else (_redact(v) if isinstance(v, dict) else v)
        for k, v in value.items()
    }


@router.get("/config/{key}")
def get_config(
    key: str,
    db: Session = Depends(get_db),
    _=Depends(require_permission("system:config")),
):
    from app.models.sys_config import SysConfig
    row = db.query(SysConfig).filter(SysConfig.key == key).first()
    if not row:
        return {"key": key, "value": None}
    return {"key": row.key, "value": _redact(row.value), "description": row.description}


@router.put("/config/{key}")
def set_config(
    key: str,
    body: SysConfigUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("system:config")),
):
    from app.models.sys_config import SysConfig
    row = db.query(SysConfig).filter(SysConfig.key == key).first()
    if not row:
        row = SysConfig(key=key)
        db.add(row)
    row.value = body.value
    if body.description is not None:
        row.description = body.description
    db.commit()
    return {"ok": True}


@router.post("/config/smtp/test")
def test_smtp(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("system:config")),
):
    """发送测试邮件到当前用户邮箱"""
    from app.core.notifier import send_email
    email = getattr(current_user, "email", None)
    if not email:
        raise HTTPException(400, "当前用户未设置邮箱")
    ok = send_email(email, "SMTP 测试邮件", "<p>SMTP 配置测试成功！</p>")
    if not ok:
        raise HTTPException(500, "邮件发送失败，请检查 SMTP 配置")
    return {"ok": True, "sent_to": email}


# ─── Resource ACL ────────────────────────────────────────────────────────────

class ResourceAccessGrant(BaseModel):
    resource_type: str   # workflow / datasource
    resource_id: int
    subject_type: str    # user / role
    subject_id: int
    permission: str      # read / write / admin

class ResourceAccessRevoke(BaseModel):
    resource_type: str
    resource_id: int
    subject_type: str
    subject_id: int


@router.get("/resource-access")
def list_resource_access(
    resource_type: str,
    resource_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("user:manage")),
):
    """查询指定资源的授权列表"""
    from app.models.resource_access import SysResourceAccess
    rows = db.query(SysResourceAccess).filter(
        SysResourceAccess.resource_type == resource_type,
        SysResourceAccess.resource_id == resource_id,
    ).all()
    return [
        {
            "id": r.id,
            "subject_type": r.subject_type,
            "subject_id": r.subject_id,
            "permission": r.permission,
            "granted_by": r.granted_by,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.post("/resource-access", status_code=201)
def grant_resource_access(
    body: ResourceAccessGrant,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("user:manage")),
):
    """授予用户/角色对指定资源的权限（幂等：已存在则更新）"""
    from app.models.resource_access import SysResourceAccess
    _VALID_TYPES = {"workflow", "datasource", "component"}
    _VALID_PERMS = {"read", "write", "admin"}
    _VALID_SUBJECTS = {"user", "role"}
    if body.resource_type not in _VALID_TYPES:
        raise HTTPException(400, f"无效的 resource_type: {body.resource_type}")
    if body.permission not in _VALID_PERMS:
        raise HTTPException(400, f"无效的 permission: {body.permission}")
    if body.subject_type not in _VALID_SUBJECTS:
        raise HTTPException(400, f"无效的 subject_type: {body.subject_type}")

    existing = db.query(SysResourceAccess).filter(
        SysResourceAccess.resource_type == body.resource_type,
        SysResourceAccess.resource_id == body.resource_id,
        SysResourceAccess.subject_type == body.subject_type,
        SysResourceAccess.subject_id == body.subject_id,
    ).first()

    if existing:
        existing.permission = body.permission
        existing.granted_by = current_user.id
    else:
        db.add(SysResourceAccess(
            resource_type=body.resource_type,
            resource_id=body.resource_id,
            subject_type=body.subject_type,
            subject_id=body.subject_id,
            permission=body.permission,
            granted_by=current_user.id,
        ))
    db.commit()
    return {"ok": True}


@router.delete("/resource-access")
def revoke_resource_access(
    body: ResourceAccessRevoke,
    db: Session = Depends(get_db),
    _=Depends(require_permission("user:manage")),
):
    """撤销用户/角色对指定资源的权限"""
    from app.models.resource_access import SysResourceAccess
    deleted = db.query(SysResourceAccess).filter(
        SysResourceAccess.resource_type == body.resource_type,
        SysResourceAccess.resource_id == body.resource_id,
        SysResourceAccess.subject_type == body.subject_type,
        SysResourceAccess.subject_id == body.subject_id,
    ).delete()
    db.commit()
    return {"ok": True, "deleted": deleted}


# ─── Notify Channels ────────────────────────────────────────────────────────

class NotifyChannelCreate(BaseModel):
    name: str
    type: str  # email / feishu_webhook / dingtalk_webhook / wecom_webhook
    config: dict
    enabled: bool = True

class NotifyChannelUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    config: Optional[dict] = None
    enabled: Optional[bool] = None

_VALID_CHANNEL_TYPES = {"email", "feishu_webhook", "dingtalk_webhook", "wecom_webhook"}


@router.get("/notify-channels")
def list_notify_channels(
    db: Session = Depends(get_db),
    _=Depends(require_permission("system:config")),
):
    """列出所有通知渠道"""
    from app.models.sys_notify_channel import SysNotifyChannel
    channels = db.query(SysNotifyChannel).order_by(SysNotifyChannel.id.desc()).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "type": c.type,
            "config": _redact(c.config) if c.config else None,
            "enabled": c.enabled,
            "created_at": str(c.created_at) if c.created_at else None,
            "updated_at": str(c.updated_at) if c.updated_at else None,
        }
        for c in channels
    ]


@router.post("/notify-channels", status_code=201)
def create_notify_channel(
    body: NotifyChannelCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("system:config")),
):
    """创建通知渠道"""
    from app.models.sys_notify_channel import SysNotifyChannel
    if body.type not in _VALID_CHANNEL_TYPES:
        raise HTTPException(400, f"无效的渠道类型: {body.type}")
    ch = SysNotifyChannel(
        name=body.name,
        type=body.type,
        config=body.config,
        enabled=body.enabled,
        created_by=current_user.id,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return {"id": ch.id, "name": ch.name, "type": ch.type}


@router.put("/notify-channels/{channel_id}")
def update_notify_channel(
    channel_id: int,
    body: NotifyChannelUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("system:config")),
):
    """更新通知渠道"""
    from app.models.sys_notify_channel import SysNotifyChannel
    ch = db.query(SysNotifyChannel).filter(SysNotifyChannel.id == channel_id).first()
    if not ch:
        raise HTTPException(404, "渠道不存在")
    if body.name is not None:
        ch.name = body.name
    if body.type is not None:
        if body.type not in _VALID_CHANNEL_TYPES:
            raise HTTPException(400, f"无效的渠道类型: {body.type}")
        ch.type = body.type
    if body.config is not None:
        ch.config = body.config
    if body.enabled is not None:
        ch.enabled = body.enabled
    db.commit()
    return {"ok": True}


@router.delete("/notify-channels/{channel_id}")
def delete_notify_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("system:config")),
):
    """删除通知渠道"""
    from app.models.sys_notify_channel import SysNotifyChannel
    ch = db.query(SysNotifyChannel).filter(SysNotifyChannel.id == channel_id).first()
    if not ch:
        raise HTTPException(404, "渠道不存在")
    db.delete(ch)
    db.commit()
    return {"ok": True}


@router.post("/notify-channels/{channel_id}/test")
async def test_notify_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("system:config")),
):
    """测试通知渠道是否可达"""
    from app.models.sys_notify_channel import SysNotifyChannel
    from app.core.notifier import test_channel
    ch = db.query(SysNotifyChannel).filter(SysNotifyChannel.id == channel_id).first()
    if not ch:
        raise HTTPException(404, "渠道不存在")
    ok = await test_channel(channel_id)
    if not ok:
        raise HTTPException(502, "通知发送失败，请检查渠道配置")
    return {"ok": True, "channel_name": ch.name}
