import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

# 프로젝트 내부 모듈
import models
import schemas
import crud
import dependencies
from database import get_db
from connection_manager import manager  # 호출 알림을 위해 웹소켓 매니저 임포트

# 공통 함수 (utils.py)
from utils import verify_store_permission

# ✨ 라우터 생성
router = APIRouter(tags=["Tables & Staff Calls"])

# =========================================================
# 🪑 테이블(Table) 관리 API
# =========================================================

@router.post("/stores/{store_id}/tables/", response_model=schemas.TableResponse)
def create_table_for_store(store_id: int, table: schemas.TableCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    # 매장 관리 권한 확인
    verify_store_permission(db, current_user, store_id)
    return crud.create_table(db=db, table=table, store_id=store_id)

@router.get("/tables/by-token/{qr_token}")
def get_table_by_token(qr_token: str, db: Session = Depends(get_db)):
    # 손님이 QR 스캔 시 테이블 정보를 가져오는 API (비로그인 허용)
    table = db.query(models.Table).filter(models.Table.qr_token == qr_token).first()
    if not table: 
        raise HTTPException(status_code=404, detail="유효하지 않은 QR 코드입니다.")
    return {"store_id": table.store_id, "table_id": table.id, "label": table.name}

@router.patch("/tables/{table_id}", response_model=schemas.TableResponse)
def update_table(table_id: int, table_update: schemas.TableUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table: 
        raise HTTPException(status_code=404, detail="테이블을 찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, table.store_id)
    table.name = table_update.name
    
    db.commit()
    db.refresh(table)
    return table

@router.delete("/tables/{table_id}")
def delete_table(table_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table: 
        raise HTTPException(status_code=404, detail="테이블을 찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, table.store_id)
    db.delete(table)
    db.commit()
    return {"message": "테이블이 삭제되었습니다."}


# =========================================================
# 🔔 직원 호출(Staff Call) 관리 API
# =========================================================

@router.get("/stores/{store_id}/call-options", response_model=List[schemas.CallOptionResponse])
def get_call_options(store_id: int, db: Session = Depends(get_db)):
    # 손님 화면에서 호출 버튼 리스트를 보여주기 위해 권한 검사 제외
    return db.query(models.CallOption).filter(models.CallOption.store_id == store_id).all()

@router.post("/stores/{store_id}/call-options", response_model=schemas.CallOptionResponse)
def create_call_option(store_id: int, option: schemas.CallOptionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    verify_store_permission(db, current_user, store_id)
    new_option = models.CallOption(store_id=store_id, name=option.name)
    db.add(new_option)
    db.commit()
    db.refresh(new_option)
    return new_option

@router.delete("/call-options/{option_id}")
def delete_call_option(option_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    option = db.query(models.CallOption).filter(models.CallOption.id == option_id).first()
    if not option: 
        raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, option.store_id)
    db.delete(option)
    db.commit()
    return {"message": "호출 옵션이 삭제되었습니다."}

@router.post("/stores/{store_id}/calls", response_model=schemas.StaffCallResponse)
async def create_staff_call(store_id: int, call: schemas.StaffCallCreate, db: Session = Depends(get_db)):
    # 실시간 호출 생성 (손님용)
    new_call = models.StaffCall(store_id=store_id, table_id=call.table_id, message=call.message)
    db.add(new_call)
    db.commit()
    db.refresh(new_call)

    # 매장 관리자 페이지(WebSocket)로 실시간 알림 전송
    try:
        message = json.dumps({
            "type": "NEW_CALL", 
            "message": f"🔔 새로운 직원 호출: {call.message}"
        }, ensure_ascii=False)
        await manager.broadcast(message, store_id=store_id)
    except: 
        pass
        
    return new_call

@router.get("/stores/{store_id}/calls", response_model=List[schemas.StaffCallResponse])
def read_active_calls(store_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    verify_store_permission(db, current_user, store_id)
    # 아직 완료되지 않은(is_completed=False) 호출 목록만 조회
    calls = db.query(models.StaffCall).filter(
        models.StaffCall.store_id == store_id, 
        models.StaffCall.is_completed == False
    ).all()
    
    return [
        schemas.StaffCallResponse(
            id=c.id, 
            table_id=c.table_id, 
            message=c.message, 
            created_at=c.created_at, 
            is_completed=c.is_completed, 
            table_name=c.table.name if c.table else "Unknown"
        ) for c in calls
    ]

@router.patch("/calls/{call_id}/complete")
def complete_staff_call(call_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    # 호출 확인 처리
    call = db.query(models.StaffCall).filter(models.StaffCall.id == call_id).first()
    if not call: 
        raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, call.store_id)
    call.is_completed = True
    db.commit()
    
    return {"message": "호출 처리가 완료되었습니다."}