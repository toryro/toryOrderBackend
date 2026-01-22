from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import json  # <--- [중요] 이게 없어서 에러가 났을 확률이 높습니다!

import models, schemas, crud
from database import get_db, engine
from connection_manager import manager # <--- 이것도 꼭 있어야 합니다.

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 기존 API들 ---

@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")
    return crud.create_user(db=db, user=user)

@app.post("/stores/", response_model=schemas.StoreResponse)
def create_store(store: schemas.StoreCreate, db: Session = Depends(get_db)):
    return crud.create_store(db=db, store=store)

@app.get("/stores/{store_id}", response_model=schemas.StoreResponse)
def read_store(store_id: int, db: Session = Depends(get_db)):
    db_store = crud.get_store(db, store_id=store_id)
    if db_store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return db_store

@app.post("/stores/{store_id}/categories/", response_model=schemas.CategoryResponse)
def create_category_for_store(store_id: int, category: schemas.CategoryCreate, db: Session = Depends(get_db)):
    return crud.create_category(db=db, category=category, store_id=store_id)

@app.post("/categories/{category_id}/menus/", response_model=schemas.MenuResponse)
def create_menu_for_category(category_id: int, menu: schemas.MenuCreate, db: Session = Depends(get_db)):
    return crud.create_menu(db=db, menu=menu, category_id=category_id)

@app.post("/stores/{store_id}/tables/", response_model=schemas.TableResponse)
def create_table_for_store(store_id: int, table: schemas.TableCreate, db: Session = Depends(get_db)):
    return crud.create_table(db=db, table=table, store_id=store_id)

@app.get("/tables/{table_id}/qrcode")
def get_qr_code(table_id: int, db: Session = Depends(get_db)):
    table = crud.get_table(db, table_id=table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    qr_url = f"http://localhost:5173/order/{table.qr_token}"
    return {"qr_code_url": qr_url, "qr_token": table.qr_token}

@app.get("/tables/by-token/{qr_token}")
def get_table_by_token(qr_token: str, db: Session = Depends(get_db)):
    table = db.query(models.Table).filter(models.Table.qr_token == qr_token).first()
    if not table:
        raise HTTPException(status_code=404, detail="유효하지 않은 QR 코드입니다.")
    return {
        "store_id": table.store_id,
        "table_id": table.id,
        "label": table.label
    }

# --- [Step 5 핵심] 주문 및 알림 ---

@app.post("/orders/", response_model=schemas.OrderResponse)
async def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    # 1. DB에 주문 저장
    new_order = crud.create_order(db=db, order=order)
    
    # 2. 웹소켓 알림 전송 (여기 내용을 수정!)
    try:
        # 주문 상세 항목들을 리스트로 변환
        items_list = []
        for item in new_order.items:
            items_list.append({
                "menu_name": item.menu_name,
                "quantity": item.quantity,
                "price": item.price,
                "subtotal": item.price * item.quantity
            })

        # 메시지에 items 추가
        message = json.dumps({
            "type": "NEW_ORDER",
            "order_id": new_order.id,
            "table_id": new_order.table_id,
            "total_price": new_order.total_price,
            "created_at": str(new_order.created_at),
            "items": items_list  # <--- [핵심] 상세 메뉴 리스트 추가됨
        }, ensure_ascii=False) # 한글 깨짐 방지
        
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