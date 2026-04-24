import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

import uuid

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
    # 테이블 정보만 반환 — 세션 생성 없음
    table = db.query(models.Table).filter(models.Table.qr_token == qr_token).first()
    if table:
        return {
            "store_id": table.store_id,
            "table_id": table.id,
            "label": table.name,
            "order_type_setting": table.order_type_setting,
            "is_virtual": False,
            "session_token": None,
        }

    # 가상 세션 토큰으로 조회 (포장 전용 1회용 링크)
    vs = crud.get_active_virtual_session(db, token=qr_token)
    if vs:
        return {
            "store_id": vs.store_id,
            "table_id": None,
            "label": "포장",
            "order_type_setting": "TAKEOUT_ONLY",
            "is_virtual": True,
            "session_token": None,
        }

    raise HTTPException(status_code=404, detail="유효하지 않은 QR 코드입니다.")

@router.post("/tables/by-token/{qr_token}/session")
def create_session_for_table(qr_token: str, db: Session = Depends(get_db)):
    # 처음 QR 스캔 시 한 번만 호출 — 방문 세션 발급
    table = db.query(models.Table).filter(models.Table.qr_token == qr_token).first()
    if not table:
        raise HTTPException(status_code=404, detail="유효하지 않은 QR 코드입니다.")
    session = crud.create_table_session(db, table_id=table.id)
    return {"session_token": session.session_token}

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
    calls = db.query(models.StaffCall).filter(
        models.StaffCall.store_id == store_id, 
        models.StaffCall.is_completed == False
    ).all()
    
    # 💡 models.py에 정의하신 @property table_name 덕분에 
    # 별도의 루프 없이 바로 리턴해도 schemas.StaffCallResponse가 알아서 인식합니다.
    return calls

@router.patch("/calls/{call_id}/complete")
async def complete_staff_call(call_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    # 호출 확인 처리
    call = db.query(models.StaffCall).filter(models.StaffCall.id == call_id).first()
    if not call: 
        raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, call.store_id)
    call.is_completed = True
    db.commit()
    
    # ✨ [추가된 부분] 다른 화면에서도 직원 호출 카드 지우기
    try:
        message = json.dumps({"type": "CALL_COMPLETED", "call_id": call_id}, ensure_ascii=False)
        await manager.broadcast(message, store_id=int(call.store_id))
    except: 
        pass

    return {"message": "호출 처리가 완료되었습니다."}

# =========================================================
# ✨ [신규 추가] 테이블 상태 수동 변경 API
# =========================================================
@router.patch("/tables/{table_id}/status")
async def update_table_status(
    table_id: int, 
    req: schemas.TableStatusUpdate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user) # ✨ 토큰 인증 추가
):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="테이블을 찾을 수 없습니다.")
    
    # ✨ 보안 추가: 내 매장의 테이블인지 확인
    verify_store_permission(db, current_user, table.store_id)
    
    table.current_status = req.status
    
    if req.status == "EMPTY":
        table.occupied_at = None
    elif req.status == "OCCUPIED" and not table.occupied_at:
        table.occupied_at = datetime.now()
        
    db.commit()
    return {"message": "테이블 상태가 변경되었습니다.", "status": table.current_status}

# =========================================================
# ✨ [신규 추가] 현황판 퇴석 처리 및 QR 토큰 갱신 API
# =========================================================
@router.post("/tables/{table_id}/clear")
async def clear_table(table_id: int, db: Session = Depends(get_db)):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="테이블을 찾을 수 없습니다.")

    # 🛡️ [방어 로직] 조리 중이거나 대기 중인 주문이 있는지 확인
    pending_orders = db.query(models.Order).filter(
        models.Order.table_id == table_id,
        models.Order.is_completed == False,
        models.Order.payment_status != "CANCELLED"
    ).all()

    # 만약 강제로 비우는 것이라면 주문들을 모두 취소 처리하거나 완료 처리해야 함
    for order in pending_orders:
        order.payment_status = "CANCELLED"  # 또는 운영 방침에 따라 처리
        order.is_completed = True 

    # 기존 손님의 방문 세션 만료 (재주문 차단)
    crud.invalidate_table_sessions(db, table_id)

    # 테이블 상태 초기화
    table.current_status = "EMPTY"
    table.occupied_at = None
    db.commit()

    # 📡 [웹소켓] 주방과 현황판에 '테이블 비워짐 + 주문 취소됨' 알림 전송
    await manager.broadcast(json.dumps({
        "type": "TABLE_STATUS_CHANGED",
        "table_id": table_id,
        "status": "EMPTY",
        "message": "CANCEL_PENDING_ORDERS" # 주방에서 이 메시지를 받으면 해당 테이블 주문 제거
    }), table.store_id)

    return {"message": "테이블이 성공적으로 비워졌습니다."}

@router.get("/stores/{store_id}/tables", response_model=List[schemas.TableResponse])
def get_tables_for_store(store_id: int, db: Session = Depends(get_db)):
    # 해당 매장의 모든 테이블을 조회해서 현황판으로 보내줍니다.
    tables = db.query(models.Table).filter(models.Table.store_id == store_id).all()
    return tables


# =========================================================
# 📦 가상 세션 (포장 전용 1회용 주문 링크)
# =========================================================

@router.post("/stores/{store_id}/virtual-sessions", response_model=schemas.VirtualSessionResponse)
def create_virtual_session(
    store_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    verify_store_permission(db, current_user, store_id)
    session = crud.create_virtual_session(db, store_id=store_id)
    return session


@router.delete("/virtual-sessions/{vs_token}")
def invalidate_virtual_session(
    vs_token: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    vs = crud.get_active_virtual_session(db, token=vs_token)
    if not vs:
        raise HTTPException(status_code=404, detail="유효하지 않은 세션입니다.")
    verify_store_permission(db, current_user, vs.store_id)
    crud.invalidate_virtual_session(db, token=vs_token)
    return {"message": "세션이 파기되었습니다."}