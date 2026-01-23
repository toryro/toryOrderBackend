from fastapi import Depends, HTTPException, status
from models import User, UserRole # models.py에서 User와 UserRole 가져오기
import auth # 기존 auth.py (로그인 검증 로직)

# 1. [기본] 활동 중인 유저인지 확인
# (로그인은 했지만 정지된 계정일 수도 있으니까요)
def get_current_active_user(current_user: User = Depends(auth.get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="비활성화된 계정입니다.")
    return current_user

# 2. [슈퍼 관리자] 전용 검문소
def require_super_admin(current_user: User = Depends(get_current_active_user)):
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="권한이 없습니다 (슈퍼 관리자만 가능)"
        )
    return current_user

# 3. [그룹 관리자] 이상 검문소 (슈퍼 관리자 + 그룹 관리자)
def require_group_admin(current_user: User = Depends(get_current_active_user)):
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.GROUP_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="권한이 없습니다 (그룹 관리자 권한 필요)"
        )
    return current_user

# 4. [사장님] 이상 검문소 (모두 통과 가능하지만, 로그인 필수)
def require_store_owner(current_user: User = Depends(get_current_active_user)):
    # 사실상 로그인한 모든 유저는 최소 사장님(STORE_OWNER) 이상이므로 
    # 별도 체크가 없어도 되지만, 명시적으로 함수를 만들어두면 좋습니다.
    return current_user