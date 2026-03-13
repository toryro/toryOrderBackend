from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List

# 프로젝트 내부 모듈
import models
import schemas
import dependencies
from database import get_db

# ✨ 라우터 생성
router = APIRouter(tags=["System & Notices"])

# =========================================================
# 📢 공지사항 (Notice) 관리 API
# =========================================================

@router.post("/admin/notices")
def create_notice(notice: schemas.NoticeCreate, db: Session = Depends(get_db)):
    # 시스템 관리자 또는 본사에서 공지사항을 발송
    new_notice = models.Notice(
        title=notice.title, 
        content=notice.content, 
        target_type=notice.target_type, 
        target_brand_id=notice.target_brand_id, 
        target_store_id=notice.target_store_id
    )
    db.add(new_notice)
    db.commit()
    return {"message": "발송 완료"}

@router.get("/notices/unread")
def get_unread_notices(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    # 1. 사용자가 이미 읽은 공지사항 ID 목록 추출
    read_notice_ids = [r.notice_id for r in db.query(models.NoticeRead).filter(models.NoticeRead.user_id == current_user.id).all()]
    
    filters = [models.Notice.is_active == True]
    if read_notice_ids: 
        filters.append(models.Notice.id.notin_(read_notice_ids))
        
    # 2. 사용자 권한/소속에 맞는 공지사항 타겟 필터링
    target_filters = [models.Notice.target_type == "ALL"]
    
    if current_user.brand_id: 
        target_filters.append(and_(models.Notice.target_type == "BRAND", models.Notice.target_brand_id == current_user.brand_id))
        
    if current_user.store_id: 
        target_filters.append(and_(models.Notice.target_type == "STORE", models.Notice.target_store_id == current_user.store_id))
        
        # 소속 매장의 상위 브랜드 공지도 볼 수 있도록 처리
        user_store = db.query(models.Store).filter(models.Store.id == current_user.store_id).first()
        if user_store and user_store.brand_id: 
            target_filters.append(and_(models.Notice.target_type == "BRAND", models.Notice.target_brand_id == user_store.brand_id))
            
    return db.query(models.Notice).filter(and_(*filters), or_(*target_filters)).order_by(models.Notice.created_at.asc()).all()

@router.post("/notices/{notice_id}/read")
def mark_notice_read(notice_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    # 특정 공지사항을 읽음 처리
    db.add(models.NoticeRead(user_id=current_user.id, notice_id=notice_id))
    db.commit()
    return {"message": "읽음 처리 완료"}

@router.get("/admin/notices/history")
def get_notice_history(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    # 관리자용: 본인이 발송한(또는 권한 내의) 전체 공지 내역 조회
    if current_user.role == "SUPER_ADMIN": 
        return db.query(models.Notice).order_by(models.Notice.created_at.desc()).all()
    elif current_user.role == "BRAND_ADMIN": 
        return db.query(models.Notice).filter(
            or_(models.Notice.target_brand_id == current_user.brand_id, models.Notice.target_type == "BRAND")
        ).order_by(models.Notice.created_at.desc()).all()
    return []

@router.get("/notices/my")
def get_my_notices(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    # 일반 사용자용: 내게 도착한 모든 공지사항 (읽음/안읽음 모두 포함)
    target_filters = [models.Notice.target_type == "ALL"]
    
    if current_user.brand_id: 
        target_filters.append(and_(models.Notice.target_type == "BRAND", models.Notice.target_brand_id == current_user.brand_id))
        
    if current_user.store_id:
        target_filters.append(and_(models.Notice.target_type == "STORE", models.Notice.target_store_id == current_user.store_id))
        
        user_store = db.query(models.Store).filter(models.Store.id == current_user.store_id).first()
        if user_store and user_store.brand_id: 
            target_filters.append(and_(models.Notice.target_type == "BRAND", models.Notice.target_brand_id == user_store.brand_id))
    
    notices = db.query(models.Notice).filter(or_(*target_filters)).order_by(models.Notice.created_at.desc()).all()
    read_notice_ids = {r.notice_id for r in db.query(models.NoticeRead).filter(models.NoticeRead.user_id == current_user.id).all()}
    
    return [
        {
            "id": n.id, 
            "title": n.title, 
            "content": n.content, 
            "created_at": n.created_at, 
            "is_read": n.id in read_notice_ids
        } for n in notices
    ]


# =========================================================
# 🕵️‍♂️ 시스템 보안 (Audit Logs) 조회 API
# =========================================================

@router.get("/admin/audit-logs")
def get_audit_logs(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    query = db.query(models.AuditLog).join(models.User)
    
    # 본사 관리자는 자기 브랜드의 로그만 조회 가능
    if current_user.role == "BRAND_ADMIN": 
        query = query.filter(models.User.brand_id == current_user.brand_id)
    # 슈퍼 관리자가 아니면 빈 배열 리턴 (접근 차단)
    elif current_user.role != "SUPER_ADMIN": 
        return []
        
    # 최근 100개의 로그만 반환 (과부하 방지)
    logs = query.order_by(models.AuditLog.created_at.desc()).limit(100).all()
    
    return [
        {
            "id": log.id, 
            "user_name": log.user.name if log.user else "-", 
            "user_email": log.user.email if log.user else "-", 
            "action": log.action, 
            "target_type": log.target_type, 
            "details": log.details, 
            "created_at": log.created_at
        } for log in logs
    ]