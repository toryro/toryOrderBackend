from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

import models
import schemas
import dependencies
from database import get_db
from utils import verify_store_permission

router = APIRouter(tags=["Payment Config"])


@router.get("/stores/{store_id}/payment-config/public")
def get_public_payment_config(store_id: int, db: Session = Depends(get_db)):
    """공개 결제 설정 조회 (인증 불필요). 프론트엔드 SDK 초기화에 사용."""
    config = db.query(models.StorePaymentConfig).filter_by(store_id=store_id, is_active=True).first()
    if not config:
        return None
    return {
        "portone_store_id": config.portone_store_id,
        "channel_key": config.channel_key,
        "pg_provider": config.pg_provider,
    }


@router.get("/stores/{store_id}/payment-config", response_model=schemas.PaymentConfigResponse)
def get_payment_config(
    store_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    verify_store_permission(db, current_user, store_id)
    config = db.query(models.StorePaymentConfig).filter_by(store_id=store_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="결제 설정이 없습니다. 먼저 PortOne 연동 정보를 등록하세요.")
    return config


@router.put("/stores/{store_id}/payment-config", response_model=schemas.PaymentConfigResponse)
def upsert_payment_config(
    store_id: int,
    req: schemas.PaymentConfigUpsert,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """결제 설정 등록/수정 (없으면 생성, 있으면 덮어쓰기)"""
    verify_store_permission(db, current_user, store_id)
    config = db.query(models.StorePaymentConfig).filter_by(store_id=store_id).first()
    if config:
        config.portone_store_id = req.portone_store_id
        # "__keep__" 센티넬이면 기존 secret 유지, 아니면 업데이트
        if req.portone_api_secret != "__keep__":
            config.portone_api_secret = req.portone_api_secret
        config.channel_key = req.channel_key
        config.pg_provider = req.pg_provider
        config.is_active = req.is_active
        config.updated_at = datetime.utcnow()
    else:
        config = models.StorePaymentConfig(store_id=store_id, **req.model_dump())
        db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.delete("/stores/{store_id}/payment-config", status_code=204)
def delete_payment_config(
    store_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    verify_store_permission(db, current_user, store_id)
    config = db.query(models.StorePaymentConfig).filter_by(store_id=store_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="결제 설정이 없습니다.")
    db.delete(config)
    db.commit()
