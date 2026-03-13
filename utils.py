import os
import requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
import models

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def send_discord_alert(message: str):
    try:
        if DISCORD_WEBHOOK_URL and "discord.com" in DISCORD_WEBHOOK_URL:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚨 **[토리오더 긴급알림]**\n{message}"})
    except: pass 

def verify_store_permission(db: Session, current_user: models.User, store_id: int):
    if current_user.role == models.UserRole.SUPER_ADMIN: return True
    if current_user.role == models.UserRole.BRAND_ADMIN:
        store = db.query(models.Store).filter(models.Store.id == store_id).first()
        if not store or store.brand_id != current_user.brand_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="타 브랜드 매장에는 접근불가")
        return True
    if current_user.role in [models.UserRole.STORE_OWNER, models.UserRole.STAFF]:
        if current_user.store_id != store_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="소속 매장이 아님")
        return True
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="접근 권한이 없습니다.")

def create_audit_log(db: Session, user_id: int, action: str, target_type: str, target_id: int, details: str):
    db.add(models.AuditLog(user_id=user_id, action=action, target_type=target_type, target_id=target_id, details=details))
    db.commit()