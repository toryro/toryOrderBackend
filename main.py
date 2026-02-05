from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
import json
import shutil
import uuid
import os
import requests # ✅ requests만 사용
from datetime import datetime, timedelta

import models, schemas, crud, auth
from database import get_db, engine
from connection_manager import manager
import dependencies
from schemas import PaymentVerifyRequest

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

os.makedirs("uploads", exist_ok=True)
app.mount("/images", StaticFiles(directory="uploads"), name="images")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://192.168.0.151:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ [최종 확정] 포트원 V1 API 인증 정보 (여기에만 입력하면 됩니다)
PORTONE_API_KEY = "1408482452335854"
PORTONE_API_SECRET = "3FqFpFpadaj4lWalLiZoZ9pGCSu5jLA1Vzfplm4a6AcNedFxaD6X5QyVwV0Sc2uJN4wtW6Vxakwj6j5d"

# --- 🔐 로그인 API ---
@app.post("/token", response_model=dict)
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

@app.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(dependencies.get_current_active_user)):
    return current_user

# --- 📸 이미지 업로드 API ---
@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = f"uploads/{filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    my_ip = "192.168.0.151" 
    return {"url": f"http://{my_ip}:8000/images/{filename}"}

# --- 🏪 가게/메뉴/주문 API (핵심 로직 외 생략 없이 유지) ---
@app.post("/stores/", response_model=schemas.StoreResponse)
def create_store(store: schemas.StoreCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    if current_user.role == models.UserRole.STORE_OWNER and current_user.store_id is not None:
        raise HTTPException(status_code=400, detail="이미 등록된 가게가 있습니다.")
    new_store = crud.create_store(db=db, store=store)
    if current_user.role == models.UserRole.STORE_OWNER:
        current_user.store_id = new_store.id
        db.add(current_user)
        db.commit()
    return new_store

@app.get("/stores/{store_id}", response_model=schemas.StoreResponse)
def read_store(store_id: int, db: Session = Depends(get_db)):
    db_store = crud.get_store(db, store_id=store_id)
    if not db_store: raise HTTPException(status_code=404, detail="Store not found")
    return db_store

@app.post("/stores/{store_id}/categories/", response_model=schemas.CategoryResponse)
def create_category_for_store(store_id: int, category: schemas.CategoryCreate, db: Session = Depends(get_db)):
    return crud.create_category(db=db, category=category, store_id=store_id)

@app.post("/categories/{category_id}/menus/", response_model=schemas.MenuResponse)
def create_menu_for_category(category_id: int, menu: schemas.MenuCreate, db: Session = Depends(get_db)):
    return crud.create_menu(db=db, menu=menu, category_id=category_id)

@app.post("/menus/{menu_id}/option-groups/", response_model=schemas.OptionGroupResponse)
def create_option_group(menu_id: int, group: schemas.OptionGroupCreate, db: Session = Depends(get_db)):
    return crud.create_option_group(db=db, group=group, menu_id=menu_id)

@app.post("/stores/{store_id}/tables/", response_model=schemas.TableResponse)
def create_table_for_store(store_id: int, table: schemas.TableCreate, db: Session = Depends(get_db)):
    return crud.create_table(db=db, table=table, store_id=store_id)

@app.get("/tables/by-token/{qr_token}")
def get_table_by_token(qr_token: str, db: Session = Depends(get_db)):
    table = db.query(models.Table).filter(models.Table.qr_token == qr_token).first()
    if not table: raise HTTPException(status_code=404, detail="유효하지 않은 QR 코드입니다.")
    return {"store_id": table.store_id, "table_id": table.id, "label": table.name}

# --- 🔔 웹소켓 및 주문 ---
@app.post("/orders/", response_model=schemas.OrderResponse)
async def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    return crud.create_order(db=db, order=order)

@app.websocket("/ws/{store_id}")
async def websocket_endpoint(websocket: WebSocket, store_id: int):
    print(f"🔌 [WebSocket] 연결: Store {store_id}", flush=True)
    await manager.connect(websocket, store_id)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, store_id)

@app.get("/stores/{store_id}/orders", response_model=List[schemas.OrderResponse]) 
def read_store_orders(store_id: int, db: Session = Depends(get_db)):
    return db.query(models.Order).filter(
        models.Order.store_id == store_id,
        models.Order.payment_status == "PAID"
    ).order_by(models.Order.id.desc()).all()

@app.patch("/orders/{order_id}/complete")
def complete_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order: raise HTTPException(status_code=404, detail="Order not found")
    order.is_completed = True 
    db.commit()
    return {"message": "Order completed"}

# --- 💳 결제 검증 (최적화 버전) ---
@app.post("/payments/complete")
async def verify_payment(payload: PaymentVerifyRequest, db: Session = Depends(get_db)):
    clean_imp_uid = payload.imp_uid.strip()
    clean_merchant_uid = payload.merchant_uid.strip()
    
    print(f"🔍 [검증 시작] UID: {clean_imp_uid}", flush=True)

    try:
        # 1. 토큰 발급
        token_res = requests.post("https://api.iamport.kr/users/getToken", json={
            "imp_key": PORTONE_API_KEY, "imp_secret": PORTONE_API_SECRET
        })
        if token_res.status_code != 200:
            raise HTTPException(status_code=500, detail="PG사 토큰 발급 실패") 
        access_token = token_res.json()["response"]["access_token"]

        # 2. 결제 조회
        payment_data = None
        
        # [1차] imp_uid 조회
        res1 = requests.get(f"https://api.iamport.kr/payments/{clean_imp_uid}", headers={"Authorization": access_token})
        if res1.status_code == 200: payment_data = res1.json().get("response")
        
        # [2차] merchant_uid 조회
        if not payment_data:
            print("⚠️ [1차 실패] merchant_uid 조회 시도", flush=True)
            res2 = requests.get(f"https://api.iamport.kr/payments/find/{clean_merchant_uid}", headers={"Authorization": access_token})
            if res2.status_code == 200: payment_data = res2.json().get("response")

        # [3차] 리스트 수색
        if not payment_data:
            print("⚠️ [2차 실패] 리스트 수색", flush=True)
            res3 = requests.get("https://api.iamport.kr/payments/status/all?limit=10&sorting=-started", headers={"Authorization": access_token})
            if res3.status_code == 200:
                for item in res3.json()["response"]["list"]:
                    if item["imp_uid"] == clean_imp_uid or item["merchant_uid"] == clean_merchant_uid:
                        payment_data = item
                        break

        if not payment_data:
            raise HTTPException(status_code=404, detail="결제 정보를 찾을 수 없습니다.")

        # 3. DB 검증 및 업데이트
        order_id = int(clean_merchant_uid.split("_")[1])
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        
        if not order: raise HTTPException(status_code=404, detail="주문 없음")
        if int(payment_data['amount']) != order.total_price: raise HTTPException(status_code=400, detail="금액 불일치")

        order.payment_status = "PAID"
        order.imp_uid = clean_imp_uid
        order.merchant_uid = clean_merchant_uid
        order.paid_amount = payment_data['amount']
        db.commit()

        print(f"💾 [DB 저장] Order {order.id}", flush=True)

        # 4. 주방 알림 전송 (상세 정보 포함)
        try:
            items_list = [{
                "menu_name": item.menu_name,
                "quantity": item.quantity,
                "options": item.options_desc or ""
            } for item in order.items]

            # ✅ [수정됨] 날짜가 글자(str)여도 에러 안 나게 처리
            if hasattr(order.created_at, 'strftime'):
                created_at_str = order.created_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created_at_str = str(order.created_at) # 이미 글자라면 그대로 사용

            message = json.dumps({
                "type": "NEW_ORDER",
                "order_id": order.id,
                "daily_number": order.daily_number,
                "table_name": order.table.name if order.table else "Unknown",
                "created_at": created_at_str,
                "items": items_list
            }, ensure_ascii=False)
            
            await manager.broadcast(message, store_id=int(order.store_id))
            print("🚀 [알림] 주방 전송 완료", flush=True)

        except Exception as e:
            print(f"⚠️ [알림 실패] {e}", flush=True)

        return {"status": "success"}

    except Exception as e:
        print(f"❌ [에러] {e}", flush=True)
        raise HTTPException(status_code=400, detail=str(e))

# (나머지 CRUD API들도 그대로 둡니다. 필요시 추가해주세요)
@app.post("/stores/{store_id}/calls", response_model=schemas.StaffCallResponse)
def create_staff_call(store_id: int, call: schemas.StaffCallCreate, db: Session = Depends(get_db)):
    table = db.query(models.Table).filter(models.Table.id == call.table_id).first()
    db_call = models.StaffCall(store_id=store_id, table_id=call.table_id, message=call.message)
    db.add(db_call)
    db.commit()
    db.refresh(db_call)
    return schemas.StaffCallResponse(id=db_call.id, table_id=db_call.table_id, table_name=table.name, message=db_call.message, created_at=db_call.created_at, is_completed=db_call.is_completed)

@app.get("/stores/{store_id}/calls", response_model=List[schemas.StaffCallResponse])
def read_active_calls(store_id: int, db: Session = Depends(get_db)):
    calls = db.query(models.StaffCall).filter(models.StaffCall.store_id == store_id, models.StaffCall.is_completed == False).all()
    return [schemas.StaffCallResponse(id=c.id, table_id=c.table_id, message=c.message, created_at=c.created_at, is_completed=c.is_completed, table_name=c.table.name if c.table else "Unknown") for c in calls]

@app.patch("/calls/{call_id}/complete")
def complete_staff_call(call_id: int, db: Session = Depends(get_db)):
    call = db.query(models.StaffCall).filter(models.StaffCall.id == call_id).first()
    call.is_completed = True
    db.commit()
    return {"message": "completed"}