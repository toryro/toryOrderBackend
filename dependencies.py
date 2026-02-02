# dependencies.py

from fastapi import Depends, HTTPException, status
from auth import get_current_user
from models import User, UserRole

def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# 슈퍼 관리자만 통과
def require_super_admin(current_user: User = Depends(get_current_active_user)):
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="권한이 없습니다 (Super Admin Only)")
    return current_user

# 그룹 관리자 이상 (슈퍼 + 그룹)
def require_group_admin(current_user: User = Depends(get_current_active_user)):
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.GROUP_ADMIN]:
        raise HTTPException(status_code=403, detail="권한이 없습니다 (Group Admin Only)")
    return current_user