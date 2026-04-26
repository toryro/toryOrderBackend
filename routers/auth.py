from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
import secrets
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta

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


def _send_reset_email(to_email: str, reset_url: str) -> None:
    """비밀번호 재설정 이메일 발송. SMTP 미설정 시 콘솔에 출력(개발 모드)."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM") or smtp_user or "noreply@toryorder.com"

    if not smtp_host or not smtp_user:
        print(f"[DEV] 비밀번호 재설정 링크 (SMTP 미설정): {reset_url}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[Tory Order] 비밀번호 재설정 안내"
    msg["From"] = smtp_from
    msg["To"] = to_email

    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 24px; background: #f8fafc;">
        <div style="background: white; border-radius: 16px; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
            <h2 style="color: #4f46e5; margin: 0 0 8px;">🔐 비밀번호 재설정</h2>
            <p style="color: #374151; margin: 0 0 24px;">비밀번호 재설정을 요청하셨습니다.<br>아래 버튼을 클릭하여 새 비밀번호를 설정하세요.</p>
            <a href="{reset_url}"
               style="display: inline-block; background: #4f46e5; color: white; padding: 14px 28px;
                      border-radius: 10px; font-weight: bold; text-decoration: none; font-size: 16px;">
               새 비밀번호 설정하기
            </a>
            <p style="color: #6b7280; font-size: 13px; margin: 24px 0 0;">
                이 링크는 <strong>30분</strong> 후 만료됩니다.<br>
                본인이 요청하지 않았다면 이 이메일을 무시하세요.
            </p>
        </div>
    </div>
    """
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [to_email], msg.as_string())
    except Exception as e:
        print(f"[EMAIL ERROR] 발송 실패 ({to_email}): {e}")

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
    refresh_token = auth.create_refresh_token(data={"sub": user.email})
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/token/refresh", response_model=dict)
async def refresh_access_token(body: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    email = auth.verify_refresh_token(body.refresh_token)
    if not email:
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다.")
    user = crud.get_user_by_email(db, email=email)
    if not user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다.")
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


# =========================================================
# 🔑 비밀번호 재설정 API (인증 불필요)
# =========================================================

@router.post("/auth/forgot-password")
def forgot_password(req: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    """이메일로 비밀번호 재설정 링크 발송. 이메일 존재 여부를 노출하지 않음."""
    user = crud.get_user_by_email(db, req.email)
    if user:
        # 기존 미사용 토큰 모두 무효화
        db.query(models.PasswordResetToken).filter(
            models.PasswordResetToken.user_id == user.id,
            models.PasswordResetToken.is_used == False,
        ).update({"is_used": True})

        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=30)
        db.add(models.PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at))
        db.commit()

        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        reset_url = f"{frontend_url}/reset-password?token={token}"
        _send_reset_email(user.email, reset_url)

    # 이메일 존재 여부 무관하게 동일한 응답 반환 (보안)
    return {"message": "입력하신 이메일로 재설정 링크를 발송했습니다."}


@router.post("/auth/reset-password")
def reset_password(req: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    """토큰 검증 후 비밀번호 변경."""
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="비밀번호는 최소 6자 이상이어야 합니다.")

    reset_token = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token == req.token,
        models.PasswordResetToken.is_used == False,
    ).first()

    if not reset_token:
        raise HTTPException(status_code=400, detail="유효하지 않은 링크입니다.")

    if reset_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="만료된 링크입니다. 비밀번호 찾기를 다시 요청해주세요.")

    reset_token.user.hashed_password = auth.get_password_hash(req.new_password)
    reset_token.is_used = True
    db.commit()

    return {"message": "비밀번호가 변경되었습니다."}