from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, ForeignKey
from typing import List
import json
import shutil
import uuid
import os
import requests 
from datetime import datetime, timedelta

import models, schemas, crud, auth
from database import get_db, engine
from connection_manager import manager
import dependencies
from schemas import PaymentVerifyRequest

from pydantic import BaseModel

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인에서의 접근을 허용 (상용화 시에는 프론트엔드 도메인만 넣어야 함)
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, OPTIONS 등 모든 통신 방법 허용
    allow_headers=["*"],  # 모든 헤더(토큰 포함) 허용
)

# =========================================================
# 🚨 [가벼운 실무 대안] 디스코드 긴급 알림 (웹훅) 설정
# =========================================================
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def send_discord_alert(message: str):
    """치명적인 에러 발생 시 디스코드로 실시간 메시지를 쏩니다."""
    try:
        # 주소를 넣었을 때만 작동하도록 방어 로직
        if DISCORD_WEBHOOK_URL and "discord.com" in DISCORD_WEBHOOK_URL:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚨 **[토리오더 긴급알림]**\n{message}"})
    except:
        pass # 알림을 보내다가 에러가 나더라도 메인 서버는 멈추지 않도록 무시합니다.

# =========================================================

os.makedirs("uploads", exist_ok=True)
app.mount("/images", StaticFiles(directory="uploads"), name="images")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# ✅ 포트원 API 설정
PORTONE_API_KEY = os.getenv("PORTONE_API_KEY")
PORTONE_API_SECRET = os.getenv("PORTONE_API_SECRET")

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
    my_ip = "127.0.0.1" # GCP 외부 IP 반영
    return {"url": f"http://{my_ip}:8000/images/{filename}"}

# =========================================================
# 🔥 [엔터프라이즈] 브랜드 및 재고 관리 API
# =========================================================

@app.post("/brands/", response_model=schemas.BrandResponse)
def create_brand(brand: schemas.BrandCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    if current_user.role != models.UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="오직 슈퍼 관리자만 브랜드를 생성할 수 있습니다.")
    
    db_brand = models.Brand(
        name=brand.name,
        logo_url=brand.logo_url,
        homepage=brand.homepage,
        support_email=brand.support_email,
        business_number=brand.business_number
    )
    db.add(db_brand)
    db.commit()
    db.refresh(db_brand)
    return db_brand

@app.get("/brands/", response_model=List[schemas.BrandResponse])
def read_brands(db: Session = Depends(get_db)):
    return db.query(models.Brand).all()

@app.get("/brands/{brand_id}", response_model=schemas.BrandResponse)
def read_brand(brand_id: int, db: Session = Depends(get_db)):
    brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
    if not brand: raise HTTPException(status_code=404, detail="Brand not found")
    return brand

@app.post("/groups/", response_model=schemas.GroupResponse)
def create_group(group: schemas.GroupCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN]:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
    
    target_brand_id = group.brand_id
    if current_user.role == models.UserRole.BRAND_ADMIN:
        target_brand_id = current_user.brand_id

    db_group = models.Group(name=group.name, brand_id=target_brand_id)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

@app.post("/brands/distribute-menu", response_model=dict)
def distribute_menu(req: schemas.MenuDistributeRequest, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN]:
        raise HTTPException(status_code=403, detail="메뉴 배포 권한이 없습니다.")

    source_cat = db.query(models.Category).filter(models.Category.id == req.source_category_id).first()
    if not source_cat: raise HTTPException(status_code=404, detail="원본 카테고리를 찾을 수 없습니다.")

    target_stores = []
    if req.target_store_ids:
        target_stores = db.query(models.Store).filter(models.Store.id.in_(req.target_store_ids)).all()
    else:
        if current_user.brand_id:
            target_stores = db.query(models.Store).filter(models.Store.brand_id == current_user.brand_id).all()
        else:
            raise HTTPException(status_code=400, detail="배포할 대상 매장을 지정해주세요.")

    success_count = 0
    for store in target_stores:
        target_cat = db.query(models.Category).filter(models.Category.store_id == store.id, models.Category.name == source_cat.name).first()
        if not target_cat:
            target_cat = models.Category(name=source_cat.name, description=source_cat.description, order_index=source_cat.order_index, store_id=store.id)
            db.add(target_cat)
            db.commit()
            db.refresh(target_cat)

        for src_menu in source_cat.menus:
            existing_menu = db.query(models.Menu).filter(models.Menu.category_id == target_cat.id, models.Menu.name == src_menu.name, models.Menu.store_id == store.id).first()
            if existing_menu:
                existing_menu.price = src_menu.price
                existing_menu.description = src_menu.description
                existing_menu.image_url = src_menu.image_url
            else:
                new_menu = models.Menu(name=src_menu.name, price=src_menu.price, description=src_menu.description, image_url=src_menu.image_url, order_index=src_menu.order_index, category_id=target_cat.id, store_id=store.id)
                db.add(new_menu)
        success_count += 1

    db.commit()
    return {"message": f"총 {success_count}개 매장에 메뉴 배포 완료"}


# --- 🏪 가게/메뉴/주문 API ---
@app.get("/groups/my/stores", response_model=List[schemas.StoreResponse])
def read_my_stores(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    if current_user.role == models.UserRole.SUPER_ADMIN: return db.query(models.Store).all()
    if current_user.role == models.UserRole.BRAND_ADMIN: return db.query(models.Store).filter(models.Store.brand_id == current_user.brand_id).all() if current_user.brand_id else []
    if current_user.role == models.UserRole.GROUP_ADMIN: return db.query(models.Store).filter(models.Store.group_id == current_user.group_id).all() if current_user.group_id else []
    if current_user.role == models.UserRole.STORE_OWNER: return db.query(models.Store).filter(models.Store.id == current_user.store_id).all() if current_user.store_id else []
    return []

# =========================================================
# 👤 계정 관리 API (관리자용)
# =========================================================
@app.get("/users/", response_model=List[schemas.UserResponse])
def read_all_users(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    if current_user.role == models.UserRole.SUPER_ADMIN:
        return db.query(models.User).all()
    if current_user.role == models.UserRole.BRAND_ADMIN:
        if not current_user.brand_id:
            return []
        return db.query(models.User).filter(
            models.User.brand_id == current_user.brand_id,
            models.User.role.in_([models.UserRole.STORE_OWNER, models.UserRole.STAFF])
        ).all()
    raise HTTPException(status_code=403, detail="조회 권한이 없습니다.")

@app.post("/admin/users/", response_model=schemas.UserResponse)
def create_user_by_admin(user: schemas.UserCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN, models.UserRole.STORE_OWNER]:
        raise HTTPException(status_code=403, detail="계정 생성 권한이 없습니다.")
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")
    return crud.create_user(db=db, user=user)

@app.delete("/admin/users/{user_id}")
def delete_user_by_admin(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    if current_user.role != models.UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="슈퍼 관리자만 삭제할 수 있습니다.")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}

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

# 🔥 카테고리/메뉴 생성 시 매장 권한 확인 적용
@app.post("/stores/{store_id}/categories/", response_model=schemas.CategoryResponse)
def create_category_for_store(store_id: int, category: schemas.CategoryCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_store_user)):
    if current_user.store_id != store_id: raise HTTPException(status_code=403, detail="권한 불일치")
    return crud.create_category(db=db, category=category, store_id=store_id)

@app.post("/categories/{category_id}/menus/", response_model=schemas.MenuResponse)
def create_menu_for_category(category_id: int, menu: schemas.MenuCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_store_user)):
    category = db.query(models.Category).filter(models.Category.id == category_id, models.Category.store_id == current_user.store_id).first()
    if not category: raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    return crud.create_menu(db=db, menu=menu, category_id=category_id, store_id=current_user.store_id)

@app.post("/menus/{menu_id}/option-groups/", response_model=schemas.OptionGroupResponse)
def create_option_group(menu_id: int, group: schemas.OptionGroupCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_store_user)):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id, models.Menu.store_id == current_user.store_id).first()
    if not menu: raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    return crud.create_option_group(db=db, group=group, menu_id=menu_id, store_id=current_user.store_id)

@app.post("/stores/{store_id}/tables/", response_model=schemas.TableResponse)
def create_table_for_store(store_id: int, table: schemas.TableCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_store_user)):
    if store_id != current_user.store_id: raise HTTPException(status_code=403, detail="권한 불일치")
    return crud.create_table(db=db, table=table, store_id=store_id)

@app.get("/tables/by-token/{qr_token}")
def get_table_by_token(qr_token: str, db: Session = Depends(get_db)):
    table = db.query(models.Table).filter(models.Table.qr_token == qr_token).first()
    if not table: raise HTTPException(status_code=404, detail="유효하지 않은 QR 코드입니다.")
    return {"store_id": table.store_id, "table_id": table.id, "label": table.name}

# --- 🔥 주문 생성 (손님 API - 교차 검증 적용) ---
@app.post("/orders/", response_model=schemas.OrderResponse)
async def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    deduct_list = {} 
    
    for item in order.items:
        # 🔥 교차 검증: 요청된 메뉴가 결제하려는 해당 매장의 메뉴인지 강제 확인
        menu = db.query(models.Menu).filter(
            models.Menu.id == item.menu_id,
            models.Menu.store_id == order.store_id # 👈 손님의 악의적 조작 방어
        ).first()
        if not menu: 
            raise HTTPException(status_code=400, detail=f"잘못된 메뉴 요청입니다 (ID: {item.menu_id})")
        
    created_order = crud.create_order(db=db, order=order)

    db.commit()
    return created_order

@app.websocket("/ws/{store_id}")
async def websocket_endpoint(websocket: WebSocket, store_id: int, token: str = Query(None)):
    # 1. 토큰이 아예 없는 경우 연결 거부
    if token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    # 2. 토큰 해독(Decode) 및 사용자 식별
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    # 3. 데이터베이스에서 사용자 권한 및 소속 매장 확인
    db = SessionLocal()
    try:
        user = crud.get_user_by_email(db, email=email)
        # 본사/슈퍼관리자가 아니면서, 접속하려는 store_id와 자신의 소속 매장이 다르면 차단!
        if not user or (user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.GROUP_ADMIN] and user.store_id != store_id):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    finally:
        db.close()

    # 4. 모든 검증을 통과한 경우에만 연결 수락 (Connection Manager에 등록)
    await manager.connect(websocket, store_id)
    try:
        while True:
            # 클라이언트(주방)가 연결을 끊지 않는 한 대기
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, store_id)

@app.get("/stores/{store_id}/orders", response_model=List[schemas.OrderResponse]) 
def read_store_orders(store_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_store_user)):
    if store_id != current_user.store_id: raise HTTPException(status_code=403, detail="권한 불일치")
    return db.query(models.Order).filter(
        models.Order.store_id == store_id,
        models.Order.payment_status == "PAID"
    ).order_by(models.Order.id.desc()).all()

@app.patch("/orders/{order_id}/complete")
def complete_order(order_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_store_user)):
    order = db.query(models.Order).filter(
        models.Order.id == order_id, 
        models.Order.store_id == current_user.store_id
    ).first()
    if not order: raise HTTPException(status_code=404, detail="권한이 없거나 주문을 찾을 수 없습니다.")
    order.is_completed = True 
    db.commit()
    return {"message": "Order completed"}

# --- 💳 결제 검증 (🔥 에러 발생 시 디스코드 알림 발송!) ---
@app.post("/payments/complete")
async def verify_payment(payload: PaymentVerifyRequest, db: Session = Depends(get_db)):
    clean_imp_uid = payload.imp_uid.strip()
    clean_merchant_uid = payload.merchant_uid.strip()
    
    try:
        order_id = int(clean_merchant_uid.split("_")[1])
    except:
        raise HTTPException(status_code=400, detail="잘못된 주문 번호 형식")

    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order: raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")

    if order.payment_status == "PAID":
        return {"status": "already_paid", "message": "이미 처리된 주문입니다."}

    try:
        token_res = requests.post("https://api.iamport.kr/users/getToken", json={
            "imp_key": PORTONE_API_KEY, "imp_secret": PORTONE_API_SECRET
        })
        if token_res.status_code != 200:
            raise HTTPException(status_code=500, detail="PG사 토큰 발급 실패") 
        access_token = token_res.json()["response"]["access_token"]

        payment_data = None
        res1 = requests.get(f"https://api.iamport.kr/payments/{clean_imp_uid}", headers={"Authorization": access_token})
        if res1.status_code == 200: payment_data = res1.json().get("response")
        
        if not payment_data:
            res2 = requests.get(f"https://api.iamport.kr/payments/find/{clean_merchant_uid}", headers={"Authorization": access_token})
            if res2.status_code == 200: payment_data = res2.json().get("response")

        if not payment_data:
            raise HTTPException(status_code=404, detail="결제 정보를 찾을 수 없습니다.")

        if int(payment_data['amount']) != order.total_price: 
            raise HTTPException(status_code=400, detail="금액 불일치")

        order.payment_status = "PAID"
        order.imp_uid = clean_imp_uid
        order.merchant_uid = clean_merchant_uid
        order.paid_amount = payment_data['amount']
        db.commit()

        try:
            items_list = [{
                "menu_name": item.menu_name,
                "quantity": item.quantity,
                "options": item.options_desc or ""
            } for item in order.items]

            created_at_val = order.created_at
            if hasattr(created_at_val, 'strftime'):
                created_at_str = created_at_val.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created_at_str = str(created_at_val)

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

        return {
            "status": "success", 
            "message": "완료",
            "daily_number": order.daily_number
            }

    except Exception as e:
        # 🔥 여기서 디스코드로 에러 메시지를 쏩니다!
        send_discord_alert(f"결제 검증 중 치명적 에러 발생!\n내용: {str(e)}")
        print(f"❌ [에러] {e}", flush=True)
        raise HTTPException(status_code=400, detail=str(e))

# --- 직원 호출 옵션 관리 ---
@app.get("/stores/{store_id}/call-options", response_model=List[schemas.CallOptionResponse])
def get_call_options(store_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_store_user)):
    if store_id != current_user.store_id: raise HTTPException(status_code=403, detail="권한 불일치")
    return db.query(models.CallOption).filter(models.CallOption.store_id == store_id).all()

@app.post("/stores/{store_id}/call-options", response_model=schemas.CallOptionResponse)
def create_call_option(store_id: int, option: schemas.CallOptionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_store_user)):
    if store_id != current_user.store_id: raise HTTPException(status_code=403, detail="권한 불일치")
    new_option = models.CallOption(store_id=store_id, name=option.name)
    db.add(new_option)
    db.commit()
    db.refresh(new_option)
    return new_option

@app.delete("/call-options/{option_id}")
def delete_call_option(option_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_store_user)):
    option = db.query(models.CallOption).filter(
        models.CallOption.id == option_id,
        models.CallOption.store_id == current_user.store_id
    ).first()
    if not option: raise HTTPException(status_code=404, detail="권한이 없거나 찾을 수 없습니다.")
    db.delete(option)
    db.commit()
    return {"message": "deleted"}

# (직원 호출 알림 - 손님 API, 문지기 없음)
@app.post("/stores/{store_id}/calls", response_model=schemas.StaffCallResponse)
async def create_staff_call(store_id: int, call: schemas.StaffCallCreate, db: Session = Depends(get_db)):
    table = db.query(models.Table).filter(models.Table.id == call.table_id, models.Table.store_id == store_id).first() 
    if not table: raise HTTPException(status_code=404, detail="Table not found")

    db_call = models.StaffCall(store_id=store_id, table_id=call.table_id, message=call.message)
    db.add(db_call)
    db.commit()
    db.refresh(db_call)
    
    try:
        if hasattr(db_call.created_at, 'strftime'):
            created_at_str = db_call.created_at.strftime("%H:%M:%S")
        else:
            created_at_str = str(db_call.created_at).split(".")[0]

        message = json.dumps({
            "type": "STAFF_CALL",
            "id": db_call.id,
            "table_name": table.name,
            "message": db_call.message,
            "created_at": created_at_str
        }, ensure_ascii=False)
        
        await manager.broadcast(message, store_id=store_id)
        print(f"🔔 [직원호출 발송] {table.name}: {call.message}", flush=True)
        
    except Exception as e:
        print(f"⚠️ [알림 발송 실패] {e}", flush=True)

    return schemas.StaffCallResponse(
        id=db_call.id, table_id=db_call.table_id, table_name=table.name,
        message=db_call.message, created_at=db_call.created_at, is_completed=db_call.is_completed
    )

@app.get("/stores/{store_id}/calls", response_model=List[schemas.StaffCallResponse])
def read_active_calls(store_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_store_user)):
    if store_id != current_user.store_id: raise HTTPException(status_code=403, detail="권한 불일치")
    calls = db.query(models.StaffCall).filter(models.StaffCall.store_id == store_id, models.StaffCall.is_completed == False).all()
    return [schemas.StaffCallResponse(id=c.id, table_id=c.table_id, message=c.message, created_at=c.created_at, is_completed=c.is_completed, table_name=c.table.name if c.table else "Unknown") for c in calls]

@app.patch("/calls/{call_id}/complete")
def complete_staff_call(call_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_store_user)):
    call = db.query(models.StaffCall).filter(
        models.StaffCall.id == call_id,
        models.StaffCall.store_id == current_user.store_id
    ).first()
    if not call: raise HTTPException(status_code=404, detail="권한이 없거나 찾을 수 없습니다.")
    call.is_completed = True
    db.commit()
    return {"message": "completed"}