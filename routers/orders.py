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
from connection_manager import manager  # 웹소켓 브로드캐스트

# 공통 함수 (utils.py)
from utils import verify_store_permission, send_discord_alert, create_audit_log
from services.notification import send_order_received, send_order_ready

# 포트원 API 키 설정 (.env 또는 환경 변수에서 로드)
PORTONE_API_KEY = os.getenv("PORTONE_API_KEY")
PORTONE_API_SECRET = os.getenv("PORTONE_API_SECRET")

# 라우터 생성
router = APIRouter(tags=["Orders & Payments"])


def _build_cash_receipt_body(items, total_amount: int, cr_merchant_uid: str, cr: schemas.CashReceiptRequest) -> dict:
    """포트원 외부 현금영수증 발급 요청 바디를 생성합니다."""
    type_map = {"PERSONAL": "person", "BUSINESS": "company"}
    id_type_map = {"phone": "phone", "card": "card", "business": "business_reg"}
    taxable = sum(i.price * i.quantity for i in items if not getattr(i, "is_tax_exempt", False))
    tax_free = total_amount - taxable
    vat = round(taxable / 11)
    return {
        "type": type_map.get(cr.trade_type, "person"),
        "identifier_type": id_type_map.get(cr.identifier_type, "phone"),
        "identifier": cr.identifier,
        "amount": total_amount,
        "vat": vat,
        "tax_free": tax_free,
        "product_name": "식음료",
    }


def _get_portone_token() -> str:
    """포트원 액세스 토큰을 발급합니다. 실패 시 예외를 발생시킵니다."""
    res = requests.post(
        "https://api.iamport.kr/users/getToken",
        json={"imp_key": PORTONE_API_KEY, "imp_secret": PORTONE_API_SECRET},
        timeout=10
    )
    if res.status_code != 200:
        raise Exception("포트원 토큰 발급 실패")
    return res.json()["response"]["access_token"]


# =========================================================
# 🛒 [그룹 1] 주문 생성 및 결제 (손님 & 직원 공통)
# =========================================================

@router.post("/orders/", response_model=schemas.OrderResponse)
async def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    now = datetime.now()
    current_time_str = now.strftime("%H:%M") 
    current_weekday = now.weekday()          

    # 1. 영업 시간 및 브레이크 타임 검증
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

    # 2. 요청된 메뉴 유효성 확인
    for item in order.items:
        menu = db.query(models.Menu).filter(
            models.Menu.id == item.menu_id, 
            models.Menu.store_id == order.store_id
        ).first()
        if not menu: 
            raise HTTPException(status_code=400, detail=f"잘못된 메뉴 요청입니다 (ID: {item.menu_id})")
        
    # 3. 테이블 방문 세션 유효성 검증 (홀 주문의 경우)
    if order.table_id and order.session_token:
        active_session = crud.get_active_table_session(db, session_token=order.session_token)
        if not active_session or active_session.table_id != order.table_id:
            raise HTTPException(status_code=403, detail="SESSION_EXPIRED")

    # 4. DB에 주문 생성
    created_order = crud.create_order(db=db, order=order)

    # 4. 테이블 상태 업데이트 (빈 자리 -> 접수 대기)
    if created_order.table_id:
        table = db.query(models.Table).filter(models.Table.id == created_order.table_id).first()
        if table:
            # 이미 식사 중인 테이블의 추가 주문일 경우 덮어쓰지 않음
            if table.current_status == "EMPTY":
                table.current_status = "PENDING"
                table.occupied_at = datetime.now()
            db.commit()
    
    # 5. 후불 결제(직원 주문 등) 즉시 주방 전송 로직
    is_post = getattr(order, 'is_post_pay', False) or getattr(order, 'payment_method', '') == "POST_PAY"
    
    if is_post:
        created_order.payment_status = "DEFERRED"
        db.commit()
        db.refresh(created_order)

        try:
            items_list = [{"menu_name": item.menu_name, "quantity": item.quantity, "options": item.options_desc or ""} for item in created_order.items]
            created_at_val = created_order.created_at
            created_at_str = created_at_val.strftime("%Y-%m-%d %H:%M:%S") if hasattr(created_at_val, 'strftime') else str(created_at_val)

            message = json.dumps({
                "type": "NEW_ORDER",
                "order_id": created_order.id,
                "daily_number": created_order.daily_number,
                "table_name": created_order.table.name if created_order.table else "Unknown",
                "created_at": created_at_str,
                "items": items_list,
                "order_type": order.order_type,
                "is_post_pay": True
            }, ensure_ascii=False)

            await manager.broadcast(message, store_id=int(created_order.store_id))
        except Exception as e:
            print(f"웹소켓 브로드캐스트 에러: {e}")

        # 후불 포장 주문 → 주문 접수 즉시 알림
        try:
            store = db.query(models.Store).filter(models.Store.id == created_order.store_id).first()
            if store:
                send_order_received(created_order, store)
        except Exception as e:
            print(f"[알림] 주문 접수 알림 오류: {e}")
    else:
        db.commit()

    return created_order


@router.post("/payments/complete")
async def verify_payment(payload: schemas.PaymentVerifyRequest, db: Session = Depends(get_db)):
    # 아임포트 선불 결제 사후 검증 로직
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

    # 긴급 모드 중 선불 결제 차단
    store = db.query(models.Store).filter(models.Store.id == order.store_id).first()
    if store and store.is_emergency_mode:
        raise HTTPException(status_code=503, detail="EMERGENCY_MODE")

    try:
        token_res = requests.post(
            "https://api.iamport.kr/users/getToken", 
            json={"imp_key": PORTONE_API_KEY, "imp_secret": PORTONE_API_SECRET}
        )
        if token_res.status_code != 200: 
            raise HTTPException(status_code=500, detail="PG사 토큰 발급 실패") 
        access_token = token_res.json()["response"]["access_token"]

        payment_data = None
        
        res1 = requests.get(
            f"https://api.iamport.kr/payments/{clean_imp_uid}", 
            headers={"Authorization": access_token}
        )
        if res1.status_code == 200: 
            payment_data = res1.json().get("response")
        
        if not payment_data:
            res2 = requests.get(
                f"https://api.iamport.kr/payments/find/{clean_merchant_uid}", 
                headers={"Authorization": access_token}
            )
            if res2.status_code == 200: 
                payment_data = res2.json().get("response")

        if not payment_data: 
            raise HTTPException(status_code=404, detail="결제 정보를 찾을 수 없습니다.")
            
        if int(payment_data['amount']) != order.total_price: 
            raise HTTPException(status_code=400, detail="결제 금액 불일치 (위변조 의심)")

        # DB에 결제 완료 기록
        order.payment_status = "PAID"
        order.imp_uid = clean_imp_uid
        order.merchant_uid = clean_merchant_uid
        order.paid_amount = payment_data['amount']
        
        # 선불 주문 시 테이블 상태 PENDING으로 변경 (포장 카운터는 제외)
        if order.table_id:
            table = db.query(models.Table).filter(models.Table.id == order.table_id).first()
            if table and table.table_type != "TAKEOUT_COUNTER":
                if table.current_status == "EMPTY":
                    table.current_status = "PENDING"
                    table.occupied_at = datetime.now()
        db.commit()

        # 주방으로 웹소켓 전송
        try:
            items_list = [{"menu_name": item.menu_name, "quantity": item.quantity, "options": item.options_desc or ""} for item in order.items]
            created_at_val = order.created_at
            created_at_str = created_at_val.strftime("%Y-%m-%d %H:%M:%S") if hasattr(created_at_val, 'strftime') else str(created_at_val)

            message = json.dumps({
                "type": "NEW_ORDER",
                "order_id": order.id,
                "daily_number": order.daily_number,
                "table_name": order.table.name if order.table else "Unknown",
                "created_at": created_at_str,
                "order_type": order.order_type,
                "items": items_list
            }, ensure_ascii=False)

            await manager.broadcast(message, store_id=int(order.store_id))
        except:
            pass

        # 포장 가상 세션 결제 완료 → 1회용 토큰 즉시 파기
        if payload.virtual_session_token:
            crud.invalidate_virtual_session(db, token=payload.virtual_session_token)

        # 포장 카운터 세션 결제 완료 → 해당 세션만 파기
        if payload.session_token:
            crud.invalidate_table_session_by_token(db, session_token=payload.session_token)

        # 영수증 자동 출력 (has_pos=False + 프린터 설정된 경우)
        store = db.query(models.Store).filter(models.Store.id == order.store_id).first()
        if store:
            from routers.printer import try_auto_print_receipt
            try_auto_print_receipt(order, store)

        # 선불 포장 주문 결제 완료 → 주문 접수 알림
        try:
            if store:
                send_order_received(order, store)
        except Exception as e:
            print(f"[알림] 주문 접수 알림 오류: {e}")

        return {"status": "success", "message": "완료", "daily_number": order.daily_number}

    except Exception as e:
        send_discord_alert(f"결제 검증 중 에러 발생!\n주문번호: {order_id}\n내용: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================
# 💴 후불 수납 처리
# =========================================================

@router.patch("/orders/{order_id}/collect-payment")
async def collect_payment(
    order_id: int,
    req: schemas.CollectPaymentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """후불 주문 수납 처리 (DEFERRED → PAID). 이미 PAID면 멱등 처리."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")

    verify_store_permission(db, current_user, order.store_id)

    if order.payment_status == "PAID":
        return {"message": "이미 수납된 주문입니다.", "payment_method": order.payment_method}

    if order.payment_status not in ("DEFERRED",):
        raise HTTPException(status_code=400, detail="후불(미수납) 주문만 수납 처리할 수 있습니다.")

    # 현금영수증 발급 시도 (현금 결제 + 요청 있을 때만 / 실패해도 수납은 계속)
    cash_receipt_result = None
    if req.payment_method == "cash" and req.cash_receipt and PORTONE_API_KEY and PORTONE_API_SECRET:
        cr = req.cash_receipt
        cr_merchant_uid = f"cr_{order_id}_{int(datetime.now().timestamp())}"
        try:
            access_token = _get_portone_token()
            body = _build_cash_receipt_body(order.items, order.total_price, cr_merchant_uid, cr)
            receipt_res = requests.post(
                f"https://api.iamport.kr/receipts/external/{cr_merchant_uid}",
                headers={"Authorization": access_token},
                json=body,
                timeout=10
            )
            rd = receipt_res.json()
            if receipt_res.status_code == 200 and rd.get("code") == 0:
                resp = rd.get("response", {})
                order.cash_receipt_status = "ISSUED"
                order.cash_receipt_number = resp.get("receipt_tid") or resp.get("pg_tid")
                order.cash_receipt_type = cr.trade_type
                order.cash_receipt_merchant_uid = cr_merchant_uid
                cash_receipt_result = "ISSUED"
            else:
                order.cash_receipt_status = "FAILED"
                cash_receipt_result = "FAILED"
                send_discord_alert(f"현금영수증 발급 실패!\n주문번호: {order_id}\n응답: {rd.get('message')}")
        except Exception as e:
            order.cash_receipt_status = "FAILED"
            cash_receipt_result = "FAILED"
            send_discord_alert(f"현금영수증 발급 오류!\n주문번호: {order_id}\n내용: {str(e)}")

    order.payment_status = "PAID"
    order.payment_method = req.payment_method
    order.paid_amount = order.total_price
    order.is_completed = True  # 수납 완료 시점에 주문을 완전히 종료
    db.commit()
    cr_detail = f" | 현금영수증: {cash_receipt_result}" if cash_receipt_result else ""
    create_audit_log(db=db, user_id=current_user.id, action="COLLECT_PAYMENT", target_type="ORDER", target_id=order_id, details=f"후불 수납 완료: 주문#{order.daily_number} {order.total_price:,}원 ({req.payment_method}){cr_detail}")

    try:
        await manager.broadcast(json.dumps({
            "type": "PAYMENT_COLLECTED",
            "order_id": order_id,
            "table_id": order.table_id,
        }), store_id=int(order.store_id))
    except:
        pass

    # 영수증 자동 출력 (has_pos=False + 프린터 설정된 경우)
    store = db.query(models.Store).filter(models.Store.id == order.store_id).first()
    if store:
        from routers.printer import try_auto_print_receipt
        try_auto_print_receipt(order, store)

    return {"message": "수납이 완료되었습니다.", "payment_method": req.payment_method}


# =========================================================
# 🧑‍🍳 [그룹 2] 주방 제어 및 상태 관리 (KDS & 현황판 연동)
# =========================================================

@router.get("/stores/{store_id}/orders", response_model=List[schemas.OrderResponse]) 
def read_store_orders(store_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    # 주방에서 아직 조리 완료되지 않은 주문들을 불러옴
    verify_store_permission(db, current_user, store_id)
    
    orders = db.query(models.Order).filter(
        models.Order.store_id == store_id,
        models.Order.payment_status.in_(["PAID", "DEFERRED", "PARTIAL_CANCELLED", "CANCELLED"]),
        models.Order.is_completed == False 
    ).order_by(models.Order.id.asc()).all()

    result = []
    for o in orders:
        order_data = schemas.OrderResponse.model_validate(o).model_dump()
        order_data["table_name"] = o.table.name if o.table else "포장/알수없음"
        result.append(order_data)
        
    return result

@router.patch("/orders/{order_id}/cooking")
async def start_cooking_order(order_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    # 중복 제거됨: 주방에서 '조리 시작' 버튼 클릭 시
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        
    verify_store_permission(db, current_user, order.store_id)
    
    order.cooking_status = "COOKING"
    
    # 테이블 현황판 상태 동기화
    if order.table_id:
        table = db.query(models.Table).filter(models.Table.id == order.table_id).first()
        if table and table.current_status == "PENDING":
            table.current_status = "COOKING"
            
    db.commit()
    
    # 홀 현황판 즉시 갱신을 위한 웹소켓 발송
    try:
        await manager.broadcast(json.dumps({
            "type": "TABLE_STATUS_CHANGED",
            "table_id": order.table_id
        }), store_id=int(order.store_id))
    except Exception as e:
        print(f"WS Error: {e}")
        
    return {"message": "조리가 시작되었습니다."}

@router.patch("/orders/{order_id}/complete")
async def complete_order(order_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order: 
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        
    verify_store_permission(db, current_user, order.store_id)
    
    # ✨ [핵심 1] commit()을 하면 데이터가 날아갈 수 있으므로 변수에 미리 안전하게 피신시킵니다.
    table_id = order.table_id
    store_id = order.store_id
    
    # 1. 조리 완료 처리
    # DEFERRED(후불) 주문은 수납 완료 시점에 is_completed=True가 되므로 여기서는 변경 안 함
    order.cooking_status = "COMPLETED"
    if order.payment_status != "DEFERRED":
        order.is_completed = True
    db.commit()
    
    # 2. 미완료 주문 확인 및 테이블 상태 변경
    if table_id:
        # ✨ [핵심 2] == False 대신 != True를 사용하여 NULL 값으로 인한 오류까지 완벽 방어합니다.
        pending_orders = db.query(models.Order).filter(
            models.Order.table_id == table_id,
            models.Order.payment_status != "CANCELLED",
            models.Order.is_completed != True ,
            models.Order.id != order_id  # 👈 이 한 줄을 추가해 주세요!
        ).count()
        
        print(f"==================================================")
        print(f"✅ [디버그] 주문번호 {order_id}번 조리 완료 처리됨!")
        print(f"✅ [디버그] 테이블 {table_id}번에 남은 미완료 주문 개수: {pending_orders}개")
        
        if pending_orders == 0:
            table = db.query(models.Table).filter(models.Table.id == table_id).first()
            if table:
                table.current_status = "OCCUPIED"
                db.commit()
                print(f"✅ [디버그] 남은 주문이 0개이므로 테이블 상태를 '식사 중(OCCUPIED)'으로 변경했습니다!")
        else:
            print(f"⚠️ [디버그] 아직 {pending_orders}개의 다른 주문이 남아있어 테이블 상태를 유지합니다.")
        print(f"==================================================")

    # 3. 실시간 신호 전송
    try:
        await manager.broadcast(json.dumps({
            "type": "ORDER_COMPLETED",
            "order_id": order_id,
            "table_id": table_id
        }, ensure_ascii=False), store_id=int(store_id))

        if table_id:
            await manager.broadcast(json.dumps({
                "type": "TABLE_STATUS_CHANGED",
                "table_id": table_id
            }), store_id=int(store_id))
    except:
        pass

    # 4. 포장 완료 알림
    try:
        store = db.query(models.Store).filter(models.Store.id == store_id).first()
        if store:
            send_order_ready(order, store)
    except Exception as e:
        print(f"[알림] 포장 완료 알림 오류: {e}")

    return {"message": "조리 완료 처리되었습니다."}

@router.patch("/orders/{order_id}/target-time")
async def update_order_target_time(order_id: int, time_change: int, db: Session = Depends(get_db)):
    # 주방 지연 시간 조정
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    new_time = order.target_time + time_change
    if new_time < 5: new_time = 5 
        
    order.target_time = new_time
    db.commit()
    return {"message": "시간이 업데이트 되었습니다.", "target_time": new_time}


# =========================================================
# 🕰️ [그룹 3] 과거 주문 내역 및 정산 (히스토리)
# =========================================================

@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    cancel_req: schemas.OrderCancelRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")

    verify_store_permission(db, current_user, order.store_id)

    if order.payment_status == "CANCELLED":
        raise HTTPException(status_code=400, detail="이미 취소된 주문입니다.")

    is_partial = len(cancel_req.cancelled_item_ids) > 0

    # 부분 취소: 대상 항목 확인 및 환불액 산정
    if is_partial:
        items_to_cancel = db.query(models.OrderItem).filter(
            models.OrderItem.id.in_(cancel_req.cancelled_item_ids),
            models.OrderItem.order_id == order_id,
            models.OrderItem.is_cancelled == False
        ).all()

        if not items_to_cancel:
            raise HTTPException(status_code=400, detail="취소할 항목이 없습니다. 이미 취소된 항목이거나 잘못된 ID입니다.")

        if cancel_req.amount is not None:
            refund_amount = cancel_req.amount
        else:
            refund_amount = sum(item.price * item.quantity for item in items_to_cancel)
    else:
        # 전체 취소: 잔여 결제 금액 전액 환불
        if cancel_req.amount is not None:
            refund_amount = cancel_req.amount
        elif order.paid_amount is not None and order.paid_amount > 0:
            refund_amount = order.paid_amount
        else:
            refund_amount = order.total_price

    # PortOne 선불 결제 건인 경우 실제 환불 API 호출
    # (후불 주문은 imp_uid가 None이므로 자동으로 스킵됨)
    portone_refunded = False
    if order.imp_uid and order.payment_status in ["PAID", "PARTIAL_CANCELLED"]:
        if not PORTONE_API_KEY or not PORTONE_API_SECRET:
            raise HTTPException(status_code=500, detail="포트원 API 키가 서버에 설정되지 않았습니다. 관리자에게 문의하세요.")

        try:
            token_res = requests.post(
                "https://api.iamport.kr/users/getToken",
                json={"imp_key": PORTONE_API_KEY, "imp_secret": PORTONE_API_SECRET},
                timeout=10
            )
            if token_res.status_code != 200:
                raise HTTPException(status_code=500, detail="PG사 토큰 발급 실패")
            access_token = token_res.json()["response"]["access_token"]

            cancel_payload = {
                "imp_uid": order.imp_uid,
                "reason": cancel_req.reason,
                "amount": refund_amount,
                "checksum": order.paid_amount,  # 현재 환불 가능 잔액 (PortOne에서 잔액 불일치 시 거부)
            }

            cancel_res = requests.post(
                "https://api.iamport.kr/payments/cancel",
                headers={"Authorization": access_token},
                json=cancel_payload,
                timeout=10
            )
            cancel_data = cancel_res.json()

            if cancel_res.status_code != 200 or cancel_data.get("code") != 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"환불 처리 실패: {cancel_data.get('message', '알 수 없는 오류')}"
                )

            portone_refunded = True

        except HTTPException:
            raise
        except Exception as e:
            send_discord_alert(f"환불 처리 중 오류!\n주문번호: {order_id}\n내용: {str(e)}")
            raise HTTPException(status_code=500, detail=f"환불 처리 중 오류: {str(e)}")

    # DB 상태 업데이트
    # ※ PortOne 환불이 성공했는데 DB commit이 실패하면 돈은 환불됐지만 DB는 여전히 PAID 상태가 됨
    #   이를 감지하기 위해 commit 실패 시 긴급 알림을 발송함
    if is_partial:
        for item in items_to_cancel:
            item.is_cancelled = True
        order.paid_amount = max(0, (order.paid_amount or 0) - refund_amount)
        order.payment_status = "PARTIAL_CANCELLED"
    else:
        for item in order.items:
            item.is_cancelled = True
        order.payment_status = "CANCELLED"
        order.paid_amount = 0
        order.is_completed = True

    try:
        db.commit()
    except Exception as db_err:
        db.rollback()
        if portone_refunded:
            # 치명적: PortOne 환불은 완료됐지만 DB 업데이트 실패 → 수동 처리 필요
            send_discord_alert(
                f"🚨 치명적 오류: PortOne 환불 성공 후 DB 업데이트 실패!\n"
                f"주문번호: {order_id} | 환불금액: {refund_amount}원 | imp_uid: {order.imp_uid}\n"
                f"즉시 수동으로 DB를 확인하고 상태를 업데이트하세요.\n오류: {str(db_err)}"
            )
            raise HTTPException(
                status_code=500,
                detail="환불은 처리됐으나 DB 업데이트에 실패했습니다. 관리자에게 즉시 문의하세요."
            )
        raise HTTPException(status_code=500, detail=f"DB 업데이트 실패: {str(db_err)}")

    create_audit_log(
        db, current_user.id,
        "PARTIAL_CANCEL" if is_partial else "CANCEL",
        "Order", order_id,
        f"사유: {cancel_req.reason}, 환불금액: {refund_amount}원"
    )

    # WebSocket 브로드캐스트
    try:
        await manager.broadcast(json.dumps({
            "type": "ORDER_CANCELLED",
            "order_id": order_id,
            "is_partial": is_partial,
            "table_id": order.table_id
        }, ensure_ascii=False), store_id=int(order.store_id))
    except Exception as e:
        print(f"WS Error: {e}")

    # 현금영수증 처리 (ISSUED 상태일 때만)
    if order.cash_receipt_status == "ISSUED" and order.cash_receipt_merchant_uid and PORTONE_API_KEY and PORTONE_API_SECRET:
        old_cr_uid = order.cash_receipt_merchant_uid
        remaining_amount = (order.paid_amount or 0)  # DB commit 이후이므로 이미 갱신된 값 사용

        try:
            access_token = _get_portone_token()

            # 1. 기존 현금영수증 조회 (재발급에 필요한 식별번호 확보)
            get_res = requests.get(
                f"https://api.iamport.kr/receipts/external/{old_cr_uid}",
                headers={"Authorization": access_token},
                timeout=10
            )
            orig = get_res.json().get("response", {}) if get_res.status_code == 200 else {}

            # 2. 기존 현금영수증 취소
            del_res = requests.delete(
                f"https://api.iamport.kr/receipts/external/{old_cr_uid}",
                headers={"Authorization": access_token},
                timeout=10
            )
            del_data = del_res.json()
            if del_res.status_code != 200 or del_data.get("code") != 0:
                raise Exception(f"현금영수증 취소 실패: {del_data.get('message')}")

            if is_partial and remaining_amount > 0 and orig.get("identifier"):
                # 3. 부분 취소: 남은 금액으로 새 현금영수증 재발급
                new_cr_uid = f"cr_{order_id}_{int(datetime.now().timestamp())}"
                active_items = [i for i in order.items if not i.is_cancelled]
                taxable = sum(i.price * i.quantity for i in active_items if not getattr(i, "is_tax_exempt", False))
                tax_free = remaining_amount - taxable
                new_res = requests.post(
                    f"https://api.iamport.kr/receipts/external/{new_cr_uid}",
                    headers={"Authorization": access_token},
                    json={
                        "type": orig.get("type", "person"),
                        "identifier_type": orig.get("identifier_type", "phone"),
                        "identifier": orig.get("identifier"),
                        "amount": remaining_amount,
                        "vat": round(taxable / 11),
                        "tax_free": tax_free,
                        "product_name": "식음료",
                    },
                    timeout=10
                )
                new_data = new_res.json()
                if new_res.status_code == 200 and new_data.get("code") == 0:
                    resp = new_data.get("response", {})
                    order.cash_receipt_status = "ISSUED"
                    order.cash_receipt_number = resp.get("receipt_tid") or resp.get("pg_tid")
                    order.cash_receipt_merchant_uid = new_cr_uid
                else:
                    order.cash_receipt_status = "FAILED"
                    send_discord_alert(
                        f"현금영수증 재발급 실패! 수동 처리 필요\n"
                        f"주문번호: {order_id} | 남은금액: {remaining_amount}원\n"
                        f"응답: {new_data.get('message')}"
                    )
            else:
                # 전체 취소 또는 재발급 식별번호 없음: CANCELLED 처리
                order.cash_receipt_status = "CANCELLED"
                order.cash_receipt_merchant_uid = None

            db.commit()

        except Exception as e:
            send_discord_alert(
                f"현금영수증 {'부분취소 후 재발급' if is_partial else '취소'} 오류! 수동 처리 필요\n"
                f"주문번호: {order_id} | merchant_uid: {old_cr_uid}\n"
                f"오류: {str(e)}"
            )

    return {
        "message": "부분 취소 완료" if is_partial else "주문 취소 완료",
        "refund_amount": refund_amount,
        "payment_status": order.payment_status
    }


@router.post("/orders/{order_id}/cash-receipt/reissue")
async def reissue_cash_receipt(
    order_id: int,
    req: schemas.CashReceiptRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    """FAILED 또는 CANCELLED 상태의 현금영수증을 재발급합니다."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")

    verify_store_permission(db, current_user, order.store_id)

    if order.payment_method != "cash":
        raise HTTPException(status_code=400, detail="현금 결제 주문만 현금영수증을 발급할 수 있습니다.")
    if order.cash_receipt_status not in ("FAILED", "CANCELLED", "NONE"):
        raise HTTPException(status_code=400, detail=f"재발급 불가 상태입니다: {order.cash_receipt_status}")
    if not PORTONE_API_KEY or not PORTONE_API_SECRET:
        raise HTTPException(status_code=500, detail="포트원 API 키가 설정되지 않았습니다.")

    active_items = [i for i in order.items if not i.is_cancelled]
    total_amount = sum(i.price * i.quantity for i in active_items)
    if total_amount <= 0:
        raise HTTPException(status_code=400, detail="유효한 주문 금액이 없습니다.")

    cr_merchant_uid = f"cr_{order_id}_{int(datetime.now().timestamp())}"
    try:
        access_token = _get_portone_token()
        body = _build_cash_receipt_body(active_items, total_amount, cr_merchant_uid, req)
        receipt_res = requests.post(
            f"https://api.iamport.kr/receipts/external/{cr_merchant_uid}",
            headers={"Authorization": access_token},
            json=body,
            timeout=10
        )
        rd = receipt_res.json()
        if receipt_res.status_code != 200 or rd.get("code") != 0:
            raise HTTPException(status_code=400, detail=f"현금영수증 발급 실패: {rd.get('message', '알 수 없는 오류')}")

        resp = rd.get("response", {})
        order.cash_receipt_status = "ISSUED"
        order.cash_receipt_number = resp.get("receipt_tid") or resp.get("pg_tid")
        order.cash_receipt_type = req.trade_type
        order.cash_receipt_merchant_uid = cr_merchant_uid
        db.commit()

        create_audit_log(db=db, user_id=current_user.id, action="CASH_RECEIPT_REISSUE",
                         target_type="ORDER", target_id=order_id,
                         details=f"현금영수증 재발급: {req.trade_type} / {req.identifier_type}")
        return {"status": "ISSUED", "cash_receipt_number": order.cash_receipt_number}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"재발급 중 오류: {str(e)}")


@router.get("/stores/{store_id}/orders/history", response_model=List[schemas.OrderResponse])
def read_store_order_history(
    store_id: int,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    from datetime import datetime as dt, timedelta
    verify_store_permission(db, current_user, store_id)

    store = db.query(models.Store).filter(models.Store.id == store_id).first()
    closing_hour = int(store.closing_hour or 0) if store else 0

    q = db.query(models.Order).filter(models.Order.store_id == store_id)

    if start_date and end_date:
        start_dt = dt.strptime(start_date, "%Y-%m-%d").replace(hour=closing_hour, minute=0, second=0)
        end_dt   = dt.strptime(end_date,   "%Y-%m-%d").replace(hour=closing_hour, minute=0, second=0) + timedelta(days=1)
        q = q.filter(models.Order.created_at >= start_dt, models.Order.created_at < end_dt)
        q = q.order_by(models.Order.id.desc()).limit(500)
    else:
        # 날짜 미지정 시 오늘 영업일만 반환
        today = dt.now().replace(hour=closing_hour, minute=0, second=0)
        if dt.now().hour < closing_hour:
            today -= timedelta(days=1)
        q = q.filter(models.Order.created_at >= today).order_by(models.Order.id.desc())

    orders = q.all()
    result = []
    for o in orders:
        order_data = schemas.OrderResponse.model_validate(o).model_dump()
        order_data["table_name"] = o.table.name if o.table else "포장/미지정"
        result.append(order_data)
    return result