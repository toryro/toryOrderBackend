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
import schemas

import models, schemas, crud, auth
from database import get_db, engine
from connection_manager import manager
import dependencies

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

os.makedirs("uploads", exist_ok=True)
app.mount("/images", StaticFiles(directory="uploads"), name="images")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    # [주의] 본인 IP로 수정!
    return {"url": f"http://192.168.0.172:8000/images/{filename}"}

# --- 🏢 그룹 API (슈퍼 관리자 전용) [신규 추가] ---
@app.post("/groups/", response_model=schemas.GroupResponse)
def create_group(
    group: schemas.GroupCreate, 
    db: Session = Depends(get_db),
    # 슈퍼 관리자만 그룹(프랜차이즈 본사)을 만들 수 있음
    current_user: models.User = Depends(dependencies.require_super_admin)
):
    return crud.create_group(db=db, group=group)

@app.get("/groups/", response_model=List[schemas.GroupResponse])
def read_groups(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.require_super_admin)
):
    return crud.get_groups(db=db)

# --- 🏪 가게/메뉴 API ---
@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")
    return crud.create_user(db=db, user=user)

# ★ [핵심 수정] 가게 생성: 슈퍼 관리자 -> '누구나' 가능 + '자동 내 가게 등록'
@app.post("/stores/", response_model=schemas.StoreResponse)
def create_store(
    store: schemas.StoreCreate, 
    db: Session = Depends(get_db),
    # 슈퍼 관리자뿐만 아니라, 로그인한 누구나(사장님) 접근 가능
    current_user: models.User = Depends(dependencies.get_current_active_user) 
):
    # 1. 이미 가게가 있는 사장님인지 체크 (사장님은 가게 1개만 운영 정책 시)
    if current_user.role == models.UserRole.STORE_OWNER and current_user.store_id is not None:
        raise HTTPException(status_code=400, detail="이미 등록된 가게가 있습니다.")

    # 2. 그룹 관리자가 가게를 만든다면? -> 자동으로 본인 그룹에 소속시킴
    if current_user.role == models.UserRole.GROUP_ADMIN:
        store.group_id = current_user.group_id

    # 3. 가게 생성
    new_store = crud.create_store(db=db, store=store)
    
    # 4. [시나리오 B의 핵심] 사장님이 직접 만들었으면, 이 가게를 '내 가게'로 등록
    if current_user.role == models.UserRole.STORE_OWNER:
        current_user.store_id = new_store.id
        db.add(current_user)
        db.commit() # 유저 정보 업데이트 (store_id 추가)
        
    return new_store

@app.get("/stores/{store_id}", response_model=schemas.StoreResponse)
def read_store(store_id: int, db: Session = Depends(get_db)):
    db_store = crud.get_store(db, store_id=store_id)
    if db_store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return db_store

# ★ [수정] 메뉴/카테고리 등록 -> 해당 가게 사장님(또는 관리자)만 가능
# (정교하게 하려면 "내 가게인지" 체크하는 로직이 필요하지만, 일단 로그인 필수 조건만 걸어봅니다)
@app.post("/stores/{store_id}/categories/", response_model=schemas.CategoryResponse)
def create_category_for_store(
    store_id: int, 
    category: schemas.CategoryCreate, 
    db: Session = Depends(get_db),
    # 👇 로그인한 사용자만 메뉴를 만들 수 있게 보호
    current_user: models.User = Depends(dependencies.get_current_active_user)
):
    return crud.create_category(db=db, category=category, store_id=store_id)

@app.post("/categories/{category_id}/menus/", response_model=schemas.MenuResponse)
def create_menu_for_category(category_id: int, menu: schemas.MenuCreate, db: Session = Depends(get_db)):
    return crud.create_menu(db=db, menu=menu, category_id=category_id)

# [신규] 메뉴에 옵션 그룹 추가
@app.post("/menus/{menu_id}/option-groups/", response_model=schemas.OptionGroupResponse)
def create_option_group(menu_id: int, group: schemas.OptionGroupCreate, db: Session = Depends(get_db)):
    return crud.create_option_group(db=db, group=group, menu_id=menu_id)

# [신규] 옵션 그룹에 세부 옵션 추가
@app.post("/option-groups/{group_id}/options/", response_model=schemas.OptionResponse)
def create_option(group_id: int, option: schemas.OptionCreate, db: Session = Depends(get_db)):
    return crud.create_option(db=db, option=option, group_id=group_id)

@app.post("/stores/{store_id}/tables/", response_model=schemas.TableResponse)
def create_table_for_store(store_id: int, table: schemas.TableCreate, db: Session = Depends(get_db)):
    return crud.create_table(db=db, table=table, store_id=store_id)

@app.get("/tables/{table_id}/qrcode")
def get_qr_code(table_id: int, db: Session = Depends(get_db)):
    table = crud.get_table(db, table_id=table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    qr_url = f"http://192.168.0.172:5173/order/{table.qr_token}" # IP 확인
    return {"qr_code_url": qr_url, "qr_token": table.qr_token}

@app.get("/tables/by-token/{qr_token}")
def get_table_by_token(qr_token: str, db: Session = Depends(get_db)):
    table = db.query(models.Table).filter(models.Table.qr_token == qr_token).first()
    if not table:
        raise HTTPException(status_code=404, detail="유효하지 않은 QR 코드입니다.")
    return {
        "store_id": table.store_id,
        "table_id": table.id,
        "label": table.name
    }

# --- 🔔 주문 및 알림 ---

@app.post("/orders/", response_model=schemas.OrderResponse)
async def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    # 1. DB 저장 (여기서 옵션 가격까지 다 계산됨)
    new_order = crud.create_order(db=db, order=order)
    
    # 2. 주방으로 알림 전송
    try:
        items_list = []
        for item in new_order.items:
            items_list.append({
                "menu_name": item.menu_name,
                "quantity": item.quantity,
                "price": item.price, 
                "options": item.options_desc, # [추가] 옵션 내용도 전송!
                "subtotal": item.price * item.quantity
            })

        message = json.dumps({
            "type": "NEW_ORDER",
            "order_id": new_order.id,
            "table_id": new_order.table_id,
            "total_price": new_order.total_price,
            "created_at": str(new_order.created_at),
            "items": items_list
        }, ensure_ascii=False)
        
        await manager.broadcast(message, store_id=order.store_id)

    except Exception as e:
        print(f"알림 전송 중 에러 발생: {e}")

    return new_order

@app.websocket("/ws/{store_id}")
async def websocket_endpoint(websocket: WebSocket, store_id: int):
    await manager.connect(websocket, store_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, store_id)

# 1. [주방용] 특정 가게의 '미완료' 주문 목록 조회
@app.get("/stores/{store_id}/orders", response_model=List[schemas.OrderResponse]) 
def read_store_orders(store_id: int, is_completed: bool = False, db: Session = Depends(get_db)):
    orders = db.query(models.Order).filter(
        models.Order.store_id == store_id, 
        models.Order.is_completed == is_completed
    ).order_by(models.Order.id.desc()).all()
    return orders

# 2. [주방용] 주문 완료 처리 (상태 변경)
@app.patch("/orders/{order_id}/complete")
def complete_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order.is_completed = True # 완료 상태로 변경
    db.commit()
    return {"message": "Order completed"}