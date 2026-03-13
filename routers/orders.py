from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import json
import os
import requests
from datetime import datetime

# 프로젝트 내부 모듈
import models
import schemas
import crud
import dependencies
from database import get_db
from connection_manager import manager  # 웹소켓 브로드캐스트를 위해 임포트

# 공통 함수 (utils.py)
from utils import verify_store_permission, send_discord_alert

# 포트원 API 키 설정 (.env 또는 환경 변수에서 로드)
PORTONE_API_KEY = os.getenv("PORTONE_API_KEY")
PORTONE_API_SECRET = os.getenv("PORTONE_API_SECRET")

# ✨ 라우터 생성
router = APIRouter(tags=["Orders & Payments"])

# =========================================================
# 🛒 주문 생성 (프론트엔드/손님용)
# =========================================================

@router.post("/orders/", response_model=schemas.OrderResponse)
async def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    now = datetime.now()
    current_time_str = now.strftime("%H:%M") 
    current_weekday = now.weekday()          

    # 영업 시간 및 브레이크 타임 검증
    today_hours = db.query(models.OperatingHour).filter(
        models.OperatingHour.store_id == order.store_id, 
        models.OperatingHour.day_of_week == current_weekday
    ).first()
    
    if today_hours:
        if today_hours.is_closed:
            raise HTTPException(status_code=400, detail="오늘은 매장 휴무일입니다.")
        if today_hours.break_time_list and today_hours.break_time_list != "[]":
            try:
                break_times = json.loads(today_hours.break_time_list)
                for bt in break_times:
                    if bt.get("start") and bt.get("end"):
                        if bt["start"] <= current_time_str <= bt["end"]:
                            raise HTTPException(
                                status_code=400, 
                                detail=f"현재 브레이크 타임({bt['start']} ~ {bt['end']}) 중이므로 주문할 수 없습니다. ☕"
                            )
            except: 
                pass 

    # 요청된 메뉴가 실제 존재하는지 확인
    for item in order.items:
        menu = db.query(models.Menu).filter(
            models.Menu.id == item.menu_id, 
            models.Menu.store_id == order.store_id
        ).first()
        if not menu: 
            raise HTTPException(status_code=400, detail=f"잘못된 메뉴 요청입니다 (ID: {item.menu_id})")
        
    created_order = crud.create_order(db=db, order=order)
    db.commit()
    return created_order


# =========================================================
# 📋 주문 내역 조회 및 상태 변경 (점주/관리자용)
# =========================================================

@router.get("/stores/{store_id}/orders", response_model=List[schemas.OrderResponse]) 
def read_store_orders(store_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    verify_store_permission(db, current_user, store_id)
    
    # 결제 완료 혹은 취소된 상태이면서, 아직 '처리 완료(조리 완료)'되지 않은 주문만 가져옴
    orders = db.query(models.Order).filter(
        models.Order.store_id == store_id,
        models.Order.payment_status.in_(["PAID", "PARTIAL_CANCELLED", "CANCELLED"]),
        models.Order.is_completed == False 
    ).order_by(models.Order.id.asc()).all()

    result = []
    for o in orders:
        order_data = schemas.OrderResponse.model_validate(o).model_dump()
        order_data["table_name"] = o.table.name if o.table else "알수없음"
        result.append(order_data)
        
    return result

@router.patch("/orders/{order_id}/complete")
def complete_order(order_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order: 
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        
    verify_store_permission(db, current_user, order.store_id)
    order.is_completed = True 
    db.commit()
    
    return {"message": "Order completed"}


# =========================================================
# 💳 포트원(아임포트) 결제 사후 검증
# =========================================================

@router.post("/payments/complete")
async def verify_payment(payload: schemas.PaymentVerifyRequest, db: Session = Depends(get_db)):
    clean_imp_uid = payload.imp_uid.strip()
    clean_merchant_uid = payload.merchant_uid.strip()
    
    try: 
        order_id = int(clean_merchant_uid.split("_")[1])
    except: 
        raise HTTPException(status_code=400, detail="잘못된 주문 번호 형식")

    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order: 
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        
    if order.payment_status == "PAID": 
        return {"status": "already_paid", "message": "이미 처리된 주문입니다."}

    try:
        # 1. 포트원 인증 토큰 발급
        token_res = requests.post(
            "https://api.iamport.kr/users/getToken", 
            json={"imp_key": PORTONE_API_KEY, "imp_secret": PORTONE_API_SECRET}
        )
        if token_res.status_code != 200: 
            raise HTTPException(status_code=500, detail="PG사 토큰 발급 실패") 
        access_token = token_res.json()["response"]["access_token"]

        payment_data = None
        
        # 2. imp_uid로 결제 정보 조회
        res1 = requests.get(
            f"https://api.iamport.kr/payments/{clean_imp_uid}", 
            headers={"Authorization": access_token}
        )
        if res1.status_code == 200: 
            payment_data = res1.json().get("response")
        
        # 3. (혹시 실패시) merchant_uid로 결제 정보 재조회
        if not payment_data:
            res2 = requests.get(
                f"https://api.iamport.kr/payments/find/{clean_merchant_uid}", 
                headers={"Authorization": access_token}
            )
            if res2.status_code == 200: 
                payment_data = res2.json().get("response")

        if not payment_data: 
            raise HTTPException(status_code=404, detail="결제 정보를 찾을 수 없습니다.")
            
        # 4. 결제 금액 변조 확인 (매우 중요)
        if int(payment_data['amount']) != order.total_price: 
            raise HTTPException(status_code=400, detail="결제 금액 불일치 (위변조 의심)")

        # 5. DB 업데이트
        order.payment_status = "PAID"
        order.imp_uid = clean_imp_uid
        order.merchant_uid = clean_merchant_uid
        order.paid_amount = payment_data['amount']
        db.commit()

        # 6. 매장 POS(주문 모니터)로 웹소켓 실시간 알림 전송
        try:
            items_list = [
                {
                    "menu_name": item.menu_name, 
                    "quantity": item.quantity, 
                    "options": item.options_desc or ""
                } for item in order.items
            ]
            
            created_at_val = order.created_at
            created_at_str = created_at_val.strftime("%Y-%m-%d %H:%M:%S") if hasattr(created_at_val, 'strftime') else str(created_at_val)

            message = json.dumps({
                "type": "NEW_ORDER", 
                "order_id": order.id, 
                "daily_number": order.daily_number,
                "table_name": order.table.name if order.table else "Unknown", 
                "created_at": created_at_str, 
                "items": items_list
            }, ensure_ascii=False)
            
            await manager.broadcast(message, store_id=int(order.store_id))
            
        except: 
            pass # 웹소켓 전송에 실패해도 결제는 정상 완료 처리되어야 함

        return {"status": "success", "message": "완료", "daily_number": order.daily_number}
        
    except Exception as e:
        # 치명적 오류 발생 시 디스코드로 알림
        send_discord_alert(f"결제 검증 중 치명적 에러 발생!\n주문번호: {order_id}\n내용: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    
    # =========================================================
# 🕰️ 과거 주문 내역 조회 (결제 내역)
# =========================================================

@router.get("/stores/{store_id}/orders/history", response_model=List[schemas.OrderResponse])
def read_store_order_history(store_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    # 1. 권한 검사 (내 매장이 맞는지)
    verify_store_permission(db, current_user, store_id)
    
    # 2. 해당 매장의 전체 주문 내역을 최신순(id.desc)으로 최대 100개까지 불러옵니다.
    orders = db.query(models.Order).filter(
        models.Order.store_id == store_id
    ).order_by(models.Order.id.desc()).limit(100).all()

    result = []
    for o in orders:
        order_data = schemas.OrderResponse.model_validate(o).model_dump()
        # 테이블 이름 매핑 (테이블이 삭제되었거나 포장 주문일 경우 예외 처리)
        order_data["table_name"] = o.table.name if o.table else "포장/미지정"
        result.append(order_data)
        
    return result