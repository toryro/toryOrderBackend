from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List

# 프로젝트 내부 모듈
import models
import schemas
import crud
import auth
import dependencies
from database import get_db

# 공통 함수 (utils.py)
from utils import create_audit_log

# ✨ 라우터 생성
router = APIRouter(tags=["Auth & Users"])

# =========================================================
# 🔐 로그인 및 인증 API
# =========================================================

@router.post("/token", response_model=dict)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 일치하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(dependencies.get_current_user)):
    return current_user


# =========================================================
# 👤 계정 관리 API (관리자용)
# =========================================================

@router.get("/users/", response_model=List[schemas.UserResponse])
def read_all_users(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    # 1. 슈퍼 관리자: 전체 계정 조회
    if current_user.role == models.UserRole.SUPER_ADMIN: 
        return db.query(models.User).all()
    
    # 2. 브랜드 관리자: 본인 브랜드 소속의 점주 및 직원 조회
    if current_user.role == models.UserRole.BRAND_ADMIN:
        if current_user.brand_id:
            return db.query(models.User).filter(
                models.User.brand_id == current_user.brand_id, 
                models.User.role.in_([models.UserRole.STORE_OWNER, models.UserRole.STAFF])
            ).all()
        return []
        
    # 3. 점주: 본인 매장 소속의 직원 조회
    if current_user.role == models.UserRole.STORE_OWNER:
        if current_user.store_id:
            return db.query(models.User).filter(models.User.store_id == current_user.store_id).all()
        return []
        
    raise HTTPException(status_code=403, detail="조회 권한이 없습니다.")

@router.post("/admin/users/", response_model=schemas.UserResponse)
def create_user_by_admin(user: schemas.UserCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN, models.UserRole.STORE_OWNER]:
        raise HTTPException(status_code=403, detail="계정 생성 권한이 없습니다.")
        
    if crud.get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")
        
    new_user = crud.create_user(db=db, user=user)
    
    # 신규 계정 발급 감사 로그
    create_audit_log(
        db=db, user_id=current_user.id, action="CREATE_USER", 
        target_type="USER", target_id=new_user.id, 
        details=f"새 계정 발급: {new_user.email}"
    )
    return new_user

@router.delete("/admin/users/{user_id}")
def delete_user_by_admin(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    user_to_delete = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_to_delete: 
        raise HTTPException(status_code=404, detail="User not found")
        
    # 권한 검증 로직
    if current_user.role == models.UserRole.SUPER_ADMIN: 
        pass
    elif current_user.role == models.UserRole.BRAND_ADMIN and user_to_delete.brand_id == current_user.brand_id: 
        pass
    elif current_user.role == models.UserRole.STORE_OWNER and user_to_delete.store_id == current_user.store_id and user_to_delete.role == models.UserRole.STAFF: 
        pass
    else: 
        raise HTTPException(status_code=403, detail="삭제 권한이 없거나 다른 매장의 계정입니다.")
        
    # 계정 삭제 감사 로그
    create_audit_log(
        db=db, user_id=current_user.id, action="DELETE_USER", 
        target_type="USER", target_id=user_id, 
        details=f"계정 삭제됨: {user_to_delete.email}"
    )
    
    db.delete(user_to_delete)
    db.commit()
    return {"message": "User deleted"}