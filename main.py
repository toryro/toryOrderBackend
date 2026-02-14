from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, UploadFile, File
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

os.makedirs("uploads", exist_ok=True)
app.mount("/images", StaticFiles(directory="uploads"), name="images")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://34.41.197.82:8000",
    "http://34.41.197.82:5173"
    "http://192.168.0.151:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 포트원 API 설정
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
    # my_ip = "192.168.0.151" 
    my_ip = "43.41.197.82" 
    return {"url": f"http://{my_ip}:8000/images/{filename}"}

# =========================================================
# 🔥 [엔터프라이즈] 브랜드 및 재고 관리 API
# =========================================================

# 1. 브랜드(본사) 생성
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

# 2. 그룹 생성
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

# 3. 메뉴 배포
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
            existing_menu = db.query(models.Menu).filter(models.Menu.category_id == target_cat.id, models.Menu.name == src_menu.name).first()
            if existing_menu:
                existing_menu.price = src_menu.price
                existing_menu.description = src_menu.description
                existing_menu.image_url = src_menu.image_url
            else:
                new_menu = models.Menu(name=src_menu.name, price=src_menu.price, description=src_menu.description, image_url=src_menu.image_url, order_index=src_menu.order_index, category_id=target_cat.id)
                db.add(new_menu)
        success_count += 1

    db.commit()
    return {"message": f"총 {success_count}개 매장에 메뉴 배포 완료"}

# =========================================================
# 🔥 [신규 추가] 재고(Inventory) 관리 API
# =========================================================

# 1. 재고 등록 (입고)
@app.post("/stores/{store_id}/inventories", response_model=schemas.InventoryResponse)
def create_inventory(store_id: int, item: schemas.InventoryCreate, db: Session = Depends(get_db)):
    db_item = models.Inventory(store_id=store_id, name=item.name, quantity=item.quantity, unit=item.unit, safe_quantity=item.safe_quantity)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

# 2. 재고 목록 조회
@app.get("/stores/{store_id}/inventories", response_model=List[schemas.InventoryResponse])
def read_inventories(store_id: int, db: Session = Depends(get_db)):
    return db.query(models.Inventory).filter(models.Inventory.store_id == store_id).all()

# 3. 재고 수정 (수량 변경 등)
@app.patch("/inventories/{id}", response_model=schemas.InventoryResponse)
def update_inventory(id: int, update: schemas.InventoryUpdate, db: Session = Depends(get_db)):
    item = db.query(models.Inventory).filter(models.Inventory.id == id).first()
    if not item: raise HTTPException(status_code=404, detail="Item not found")
    
    if update.quantity is not None: item.quantity = update.quantity
    if update.safe_quantity is not None: item.safe_quantity = update.safe_quantity
    
    db.commit()
    db.refresh(item)
    return item

# 4. 레시피 연결 (메뉴 - 재료)
@app.post("/menus/{menu_id}/recipes", response_model=schemas.RecipeResponse)
def create_recipe(menu_id: int, recipe: schemas.RecipeCreate, db: Session = Depends(get_db)):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    inventory = db.query(models.Inventory).filter(models.Inventory.id == recipe.inventory_id).first()
    
    if not menu or not inventory: raise HTTPException(status_code=404, detail="Menu or Inventory not found")
    
    db_recipe = models.Recipe(menu_id=menu_id, inventory_id=recipe.inventory_id, amount_needed=recipe.amount_needed)
    db.add(db_recipe)
    db.commit()
    db.refresh(db_recipe)
    
    return {
        "id": db_recipe.id,
        "inventory_name": inventory.name,
        "amount_needed": db_recipe.amount_needed,
        "unit": inventory.unit
    }

# =========================================================

# --- 🏪 가게/메뉴/주문 API ---
@app.get("/groups/my/stores", response_model=List[schemas.StoreResponse])
def read_my_stores(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    if current_user.role == models.UserRole.SUPER_ADMIN: return db.query(models.Store).all()
    if current_user.role == models.UserRole.BRAND_ADMIN: return db.query(models.Store).filter(models.Store.brand_id == current_user.brand_id).all() if current_user.brand_id else []
    if current_user.role == models.UserRole.GROUP_ADMIN: return db.query(models.Store).filter(models.Store.group_id == current_user.group_id).all() if current_user.group_id else []
    if current_user.role == models.UserRole.STORE_OWNER: return db.query(models.Store).filter(models.Store.id == current_user.store_id).all() if current_user.store_id else []
    return []

# =========================================================
# 👤 [신규 추가] 계정 관리 API (관리자용)
# =========================================================

# 1. 전체 사용자 목록 조회
@app.get("/users/", response_model=List[schemas.UserResponse])
def read_all_users(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    # 1. 슈퍼 관리자: 모든 계정 조회
    if current_user.role == models.UserRole.SUPER_ADMIN:
        return db.query(models.User).all()
    
    # 2. 브랜드 관리자: 내 브랜드 소속 계정만 조회 (점주, 직원)
    if current_user.role == models.UserRole.BRAND_ADMIN:
        if not current_user.brand_id:
            return []
        return db.query(models.User).filter(
            models.User.brand_id == current_user.brand_id,
            models.User.role.in_([models.UserRole.STORE_OWNER, models.UserRole.STAFF])
        ).all()
        
    raise HTTPException(status_code=403, detail="조회 권한이 없습니다.")

# 2. 관리자 권한으로 계정 생성 (회원가입 없이 즉시 생성)
@app.post("/admin/users/", response_model=schemas.UserResponse)
def create_user_by_admin(user: schemas.UserCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    # 권한 체크
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN]:
        raise HTTPException(status_code=403, detail="계정 생성 권한이 없습니다.")

    # 이메일 중복 체크
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")
    
    # 계정 생성 위임 (crud.py 활용)
    return crud.create_user(db=db, user=user)

# 3. 계정 삭제
@app.delete("/admin/users/{user_id}")
def delete_user_by_admin(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    if current_user.role != models.UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="슈퍼 관리자만 삭제할 수 있습니다.")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
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

# ... (중간 생략: 카테고리, 메뉴 생성 등 기존 API 그대로 유지) ...
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

# --- 🔥 [대폭 수정] 주문 생성 (재고 차감 로직 적용) ---
@app.post("/orders/", response_model=schemas.OrderResponse)
async def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    # 1. 재고 확인 (Stock Check)
    deduct_list = {} # {inventory_id: deduct_amount}
    
    for item in order.items:
        menu = db.query(models.Menu).filter(models.Menu.id == item.menu_id).first()
        if not menu: continue
        
        # 메뉴에 연결된 레시피 확인
        for recipe in menu.recipes:
            needed = recipe.amount_needed * item.quantity
            current_deduct = deduct_list.get(recipe.inventory_id, 0)
            deduct_list[recipe.inventory_id] = current_deduct + needed

    # 2. 재고 부족 여부 검사
    for inv_id, amount in deduct_list.items():
        inventory = db.query(models.Inventory).filter(models.Inventory.id == inv_id).first()
        if not inventory: continue
        
        if inventory.quantity < amount:
            raise HTTPException(status_code=400, detail=f"재고 부족: {inventory.name} (남은 양: {inventory.quantity}, 필요 양: {amount})")

    # 3. 주문 생성 (기존 로직)
    created_order = crud.create_order(db=db, order=order)

    # 4. 재고 실제 차감 (Deduct)
    for inv_id, amount in deduct_list.items():
        inventory = db.query(models.Inventory).filter(models.Inventory.id == inv_id).first()
        inventory.quantity -= amount
    
    db.commit()
    
    return created_order

@app.websocket("/ws/{store_id}")
async def websocket_endpoint(websocket: WebSocket, store_id: int):
    store_id_int = int(store_id)
    print(f"🔌 [WebSocket] 연결 요청: Store {store_id_int}", flush=True)
    await manager.connect(websocket, store_id_int)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        print(f"🔌 [WebSocket] 연결 종료: Store {store_id_int}", flush=True)
        manager.disconnect(websocket, store_id_int)

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

# --- 💳 결제 검증 (중복 방지 & 알림 수정) ---
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

    print(f"🔍 [검증 시작] UID: {clean_imp_uid} -> Order: {order.id}", flush=True)

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
        print(f"❌ [에러] {e}", flush=True)
        raise HTTPException(status_code=400, detail=str(e))

# --- 직원 호출 옵션 관리 ---
@app.get("/stores/{store_id}/call-options", response_model=List[schemas.CallOptionResponse])
def get_call_options(store_id: int, db: Session = Depends(get_db)):
    return db.query(models.CallOption).filter(models.CallOption.store_id == store_id).all()

@app.post("/stores/{store_id}/call-options", response_model=schemas.CallOptionResponse)
def create_call_option(store_id: int, option: schemas.CallOptionCreate, db: Session = Depends(get_db)):
    new_option = models.CallOption(store_id=store_id, name=option.name)
    db.add(new_option)
    db.commit()
    db.refresh(new_option)
    return new_option

@app.delete("/call-options/{option_id}")
def delete_call_option(option_id: int, db: Session = Depends(get_db)):
    option = db.query(models.CallOption).filter(models.CallOption.id == option_id).first()
    if not option: raise HTTPException(status_code=404, detail="Option not found")
    db.delete(option)
    db.commit()
    return {"message": "deleted"}

# (직원 호출 알림)
@app.post("/stores/{store_id}/calls", response_model=schemas.StaffCallResponse)
async def create_staff_call(store_id: int, call: schemas.StaffCallCreate, db: Session = Depends(get_db)):
    table = db.query(models.Table).filter(models.Table.id == call.table_id).first()
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
def read_active_calls(store_id: int, db: Session = Depends(get_db)):
    calls = db.query(models.StaffCall).filter(models.StaffCall.store_id == store_id, models.StaffCall.is_completed == False).all()
    return [schemas.StaffCallResponse(id=c.id, table_id=c.table_id, message=c.message, created_at=c.created_at, is_completed=c.is_completed, table_name=c.table.name if c.table else "Unknown") for c in calls]

@app.patch("/calls/{call_id}/complete")
def complete_staff_call(call_id: int, db: Session = Depends(get_db)):
    call = db.query(models.StaffCall).filter(models.StaffCall.id == call_id).first()
    call.is_completed = True
    db.commit()
    return {"message": "completed"}