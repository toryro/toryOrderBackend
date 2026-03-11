from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, UploadFile, File, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
import json
import shutil
import uuid
import os
import requests 
from pydantic import BaseModel
from datetime import datetime

from jose import JWTError, jwt
from dotenv import load_dotenv
from sqlalchemy import or_, and_

# 환경변수 로드 (최상단 필수)
load_dotenv()

import models, schemas, crud, auth
from database import get_db, SessionLocal
from connection_manager import manager
import dependencies
from schemas import PaymentVerifyRequest

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시에는 프론트엔드 도메인으로 변경 권장
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

# =========================================================
# 🚨 디스코드 긴급 알림 (웹훅) 설정
# =========================================================
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def send_discord_alert(message: str):
    """치명적인 에러 발생 시 디스코드로 실시간 메시지를 발송합니다."""
    try:
        if DISCORD_WEBHOOK_URL and "discord.com" in DISCORD_WEBHOOK_URL:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚨 **[토리오더 긴급알림]**\n{message}"})
    except:
        pass 

# =========================================================

os.makedirs("uploads", exist_ok=True)
app.mount("/images", StaticFiles(directory="uploads"), name="images")

# 포트원 API 키 설정
PORTONE_API_KEY = os.getenv("PORTONE_API_KEY")
PORTONE_API_SECRET = os.getenv("PORTONE_API_SECRET")

def verify_store_permission(db: Session, current_user: models.User, store_id: int):
    """특정 매장에 대한 접근 권한을 계급별로 철저히 검증합니다."""
    if current_user.role == models.UserRole.SUPER_ADMIN:
        return True
    if current_user.role == models.UserRole.BRAND_ADMIN:
        store = db.query(models.Store).filter(models.Store.id == store_id).first()
        if not store or store.brand_id != current_user.brand_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="타 브랜드 매장에는 접근할 수 없습니다.")
        return True
    if current_user.role in [models.UserRole.STORE_OWNER, models.UserRole.STAFF]:
        if current_user.store_id != store_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="본인 소속 매장이 아니므로 접근할 수 없습니다.")
        return True
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="접근 권한이 없습니다.")

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
def read_users_me(current_user: models.User = Depends(dependencies.get_current_user)):
    return current_user

# --- 📸 이미지 업로드 API ---
@app.post("/upload/")
async def upload_image(request: Request, file: UploadFile = File(...)):
    filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = f"uploads/{filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    base_url = str(request.base_url).rstrip("/")
    return {"url": f"{base_url}/images/{filename}"}

# =========================================================
# 브랜드/매장 생성 및 조회 API
# =========================================================
@app.post("/brands/", response_model=schemas.BrandResponse)
def create_brand(brand: schemas.BrandCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role != models.UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="오직 슈퍼 관리자만 브랜드를 생성할 수 있습니다.")
    db_brand = models.Brand(**brand.dict())
    db.add(db_brand)
    db.commit()
    db.refresh(db_brand)
    create_audit_log(db=db, user_id=current_user.id, action="CREATE_BRAND", target_type="BRAND", target_id=db_brand.id, details=f"신규 브랜드 생성: [{db_brand.name}]")
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
def create_group(group: schemas.GroupCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN]:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
    target_brand_id = group.brand_id if current_user.role == models.UserRole.SUPER_ADMIN else current_user.brand_id
    db_group = models.Group(name=group.name, brand_id=target_brand_id)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

@app.post("/stores/", response_model=schemas.StoreResponse)
def create_store(store: schemas.StoreCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role == models.UserRole.STORE_OWNER and current_user.store_id is not None:
        raise HTTPException(status_code=400, detail="이미 등록된 가게가 있습니다.")
    new_store = crud.create_store(db=db, store=store)
    if current_user.role == models.UserRole.STORE_OWNER:
        current_user.store_id = new_store.id
        db.add(current_user)
        db.commit()
    create_audit_log(db=db, user_id=current_user.id, action="CREATE_STORE", target_type="STORE", target_id=new_store.id, details=f"새 매장 오픈: [{new_store.name}]")
    return new_store

@app.get("/stores/{store_id}", response_model=schemas.StoreResponse)
def read_store(store_id: int, db: Session = Depends(get_db)):
    db_store = crud.get_store(db, store_id=store_id)
    if not db_store: raise HTTPException(status_code=404, detail="Store not found")
    store_data = schemas.StoreResponse.model_validate(db_store).model_dump()
    for category in store_data.get("categories", []):
        for menu in category.get("menus", []):
            links = db.query(models.MenuOptionLink).filter(models.MenuOptionLink.menu_id == menu["id"]).order_by(models.MenuOptionLink.order_index).all()
            option_groups = []
            for link in links:
                og = db.query(models.OptionGroup).filter(models.OptionGroup.id == link.option_group_id).first()
                if og: option_groups.append(schemas.OptionGroupResponse.model_validate(og).model_dump())
            menu["option_groups"] = option_groups
    return store_data

@app.get("/groups/my/stores", response_model=List[schemas.StoreResponse])
def read_my_stores(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role == models.UserRole.SUPER_ADMIN: return db.query(models.Store).order_by(models.Store.id).all()
    if current_user.role == models.UserRole.BRAND_ADMIN: return db.query(models.Store).filter(models.Store.brand_id == current_user.brand_id).order_by(models.Store.id).all() if current_user.brand_id else []
    if current_user.role == models.UserRole.GROUP_ADMIN: return db.query(models.Store).filter(models.Store.group_id == current_user.group_id).order_by(models.Store.id).all() if current_user.group_id else []
    if current_user.role == models.UserRole.STORE_OWNER: return db.query(models.Store).filter(models.Store.id == current_user.store_id).order_by(models.Store.id).all() if current_user.store_id else []
    return []

# =========================================================
# 👤 계정 관리 API (관리자용)
# =========================================================
@app.get("/users/", response_model=List[schemas.UserResponse])
def read_all_users(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role == models.UserRole.SUPER_ADMIN: return db.query(models.User).all()
    if current_user.role == models.UserRole.BRAND_ADMIN:
        return db.query(models.User).filter(models.User.brand_id == current_user.brand_id, models.User.role.in_([models.UserRole.STORE_OWNER, models.UserRole.STAFF])).all() if current_user.brand_id else []
    if current_user.role == models.UserRole.STORE_OWNER:
        return db.query(models.User).filter(models.User.store_id == current_user.store_id).all() if current_user.store_id else []
    raise HTTPException(status_code=403, detail="조회 권한이 없습니다.")

@app.post("/admin/users/", response_model=schemas.UserResponse)
def create_user_by_admin(user: schemas.UserCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN, models.UserRole.STORE_OWNER]:
        raise HTTPException(status_code=403, detail="계정 생성 권한이 없습니다.")
    if crud.get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")
    new_user = crud.create_user(db=db, user=user)
    create_audit_log(db=db, user_id=current_user.id, action="CREATE_USER", target_type="USER", target_id=new_user.id, details=f"새 계정 발급: {new_user.email}")
    return new_user

@app.delete("/admin/users/{user_id}")
def delete_user_by_admin(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    user_to_delete = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_to_delete: raise HTTPException(status_code=404, detail="User not found")
    if current_user.role == models.UserRole.SUPER_ADMIN: pass
    elif current_user.role == models.UserRole.BRAND_ADMIN and user_to_delete.brand_id == current_user.brand_id: pass
    elif current_user.role == models.UserRole.STORE_OWNER and user_to_delete.store_id == current_user.store_id and user_to_delete.role == models.UserRole.STAFF: pass
    else: raise HTTPException(status_code=403, detail="삭제 권한이 없거나 다른 매장의 계정입니다.")
    create_audit_log(db=db, user_id=current_user.id, action="DELETE_USER", target_type="USER", target_id=user_id, details=f"계정 삭제됨: {user_to_delete.email}")
    db.delete(user_to_delete)
    db.commit()
    return {"message": "User deleted"}

# =========================================================
# 🍽️ 메뉴, 카테고리, 옵션, 테이블 관리
# =========================================================
@app.post("/stores/{store_id}/categories/", response_model=schemas.CategoryResponse)
def create_category(store_id: int, category: schemas.CategoryCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    verify_store_permission(db, current_user, store_id)
    db_category = models.Category(**category.dict(), store_id=store_id)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@app.post("/categories/{category_id}/menus/", response_model=schemas.MenuResponse)
def create_menu(category_id: int, menu: schemas.MenuCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    category = db.query(models.Category).filter(models.Category.id == category_id).first() 
    if not category: raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    verify_store_permission(db, current_user, category.store_id)
    db_menu = models.Menu(**menu.dict(exclude={"options"}), category_id=category_id, store_id=category.store_id)
    db.add(db_menu)
    db.commit()
    db.refresh(db_menu)
    create_audit_log(db=db, user_id=current_user.id, action="CREATE_MENU", target_type="MENU", target_id=db_menu.id, details=f"새 메뉴 생성: [{db_menu.name}]")
    return db_menu

@app.post("/menus/{menu_id}/option-groups/", response_model=schemas.OptionGroupResponse)
def create_option_group(menu_id: int, group: schemas.OptionGroupCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)
    return crud.create_option_group(db=db, group=group, menu_id=menu_id, store_id=menu.store_id)

@app.post("/stores/{store_id}/tables/", response_model=schemas.TableResponse)
def create_table_for_store(store_id: int, table: schemas.TableCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    verify_store_permission(db, current_user, store_id)
    return crud.create_table(db=db, table=table, store_id=store_id)

@app.get("/tables/by-token/{qr_token}")
def get_table_by_token(qr_token: str, db: Session = Depends(get_db)):
    table = db.query(models.Table).filter(models.Table.qr_token == qr_token).first()
    if not table: raise HTTPException(status_code=404, detail="유효하지 않은 QR 코드입니다.")
    return {"store_id": table.store_id, "table_id": table.id, "label": table.name}

@app.patch("/tables/{table_id}", response_model=schemas.TableResponse)
def update_table(table_id: int, table_update: schemas.TableUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table: raise HTTPException(status_code=404, detail="테이블을 찾을 수 없습니다.")
    verify_store_permission(db, current_user, table.store_id)
    table.name = table_update.name
    db.commit()
    db.refresh(table)
    return table

@app.delete("/tables/{table_id}")
def delete_table(table_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table: raise HTTPException(status_code=404, detail="테이블을 찾을 수 없습니다.")
    verify_store_permission(db, current_user, table.store_id)
    db.delete(table)
    db.commit()
    return {"message": "테이블 삭제됨"}

# =========================================================
# 🔥 [주문 시스템 및 WebSocket]
# =========================================================
@app.post("/orders/", response_model=schemas.OrderResponse)
async def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    now = datetime.now()
    current_time_str = now.strftime("%H:%M") 
    current_weekday = now.weekday()          

    today_hours = db.query(models.OperatingHour).filter(models.OperatingHour.store_id == order.store_id, models.OperatingHour.day_of_week == current_weekday).first()
    if today_hours:
        if today_hours.is_closed:
            raise HTTPException(status_code=400, detail="오늘은 매장 휴무일입니다.")
        if today_hours.break_time_list and today_hours.break_time_list != "[]":
            try:
                break_times = json.loads(today_hours.break_time_list)
                for bt in break_times:
                    if bt.get("start") and bt.get("end"):
                        if bt["start"] <= current_time_str <= bt["end"]:
                            raise HTTPException(status_code=400, detail=f"현재 브레이크 타임({bt['start']} ~ {bt['end']}) 중이므로 주문할 수 없습니다. ☕")
            except: pass 

    for item in order.items:
        menu = db.query(models.Menu).filter(models.Menu.id == item.menu_id, models.Menu.store_id == order.store_id).first()
        if not menu: raise HTTPException(status_code=400, detail=f"잘못된 메뉴 요청입니다 (ID: {item.menu_id})")
        
    created_order = crud.create_order(db=db, order=order)
    db.commit()
    return created_order

@app.websocket("/ws/{store_id}")
async def websocket_endpoint(websocket: WebSocket, store_id: int, token: str = Query(None)):
    if token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    db = SessionLocal()
    try:
        user = crud.get_user_by_email(db, email=email)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        has_permission = False
        if user.role == models.UserRole.SUPER_ADMIN: has_permission = True
        elif user.role == models.UserRole.BRAND_ADMIN:
            store = db.query(models.Store).filter(models.Store.id == store_id).first()
            if store and store.brand_id == user.brand_id: has_permission = True
        elif user.role in [models.UserRole.STORE_OWNER, models.UserRole.STAFF]:
            if user.store_id == store_id: has_permission = True
                
        if not has_permission:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    finally:
        db.close()

    await manager.connect(websocket, store_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, store_id)

@app.get("/stores/{store_id}/orders", response_model=List[schemas.OrderResponse]) 
def read_store_orders(store_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    verify_store_permission(db, current_user, store_id)
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

@app.patch("/orders/{order_id}/complete")
def complete_order(order_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order: raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    verify_store_permission(db, current_user, order.store_id)
    order.is_completed = True 
    db.commit()
    return {"message": "Order completed"}

@app.post("/payments/complete")
async def verify_payment(payload: PaymentVerifyRequest, db: Session = Depends(get_db)):
    clean_imp_uid = payload.imp_uid.strip()
    clean_merchant_uid = payload.merchant_uid.strip()
    
    try: order_id = int(clean_merchant_uid.split("_")[1])
    except: raise HTTPException(status_code=400, detail="잘못된 주문 번호 형식")

    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order: raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    if order.payment_status == "PAID": return {"status": "already_paid", "message": "이미 처리된 주문입니다."}

    try:
        token_res = requests.post("https://api.iamport.kr/users/getToken", json={"imp_key": PORTONE_API_KEY, "imp_secret": PORTONE_API_SECRET})
        if token_res.status_code != 200: raise HTTPException(status_code=500, detail="PG사 토큰 발급 실패") 
        access_token = token_res.json()["response"]["access_token"]

        payment_data = None
        res1 = requests.get(f"https://api.iamport.kr/payments/{clean_imp_uid}", headers={"Authorization": access_token})
        if res1.status_code == 200: payment_data = res1.json().get("response")
        
        if not payment_data:
            res2 = requests.get(f"https://api.iamport.kr/payments/find/{clean_merchant_uid}", headers={"Authorization": access_token})
            if res2.status_code == 200: payment_data = res2.json().get("response")

        if not payment_data: raise HTTPException(status_code=404, detail="결제 정보를 찾을 수 없습니다.")
        if int(payment_data['amount']) != order.total_price: raise HTTPException(status_code=400, detail="금액 불일치")

        order.payment_status = "PAID"
        order.imp_uid = clean_imp_uid
        order.merchant_uid = clean_merchant_uid
        order.paid_amount = payment_data['amount']
        db.commit()

        try:
            items_list = [{"menu_name": item.menu_name, "quantity": item.quantity, "options": item.options_desc or ""} for item in order.items]
            created_at_val = order.created_at
            created_at_str = created_at_val.strftime("%Y-%m-%d %H:%M:%S") if hasattr(created_at_val, 'strftime') else str(created_at_val)

            message = json.dumps({
                "type": "NEW_ORDER", "order_id": order.id, "daily_number": order.daily_number,
                "table_name": order.table.name if order.table else "Unknown", "created_at": created_at_str, "items": items_list
            }, ensure_ascii=False)
            await manager.broadcast(message, store_id=int(order.store_id))
        except: pass

        return {"status": "success", "message": "완료", "daily_number": order.daily_number}
    except Exception as e:
        send_discord_alert(f"결제 검증 중 치명적 에러 발생!\n내용: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# =========================================================
# 🔔 직원 호출 옵션 및 실시간 호출 (에러 원인 해결!)
# =========================================================

# ✨ [완벽 수정됨] 1. 손님 폰에서도 볼 수 있도록 권한 검사 완전 해제 (중복 코드 1개로 통일)
@app.get("/stores/{store_id}/call-options", response_model=List[schemas.CallOptionResponse])
def get_call_options(store_id: int, db: Session = Depends(get_db)):
    return db.query(models.CallOption).filter(models.CallOption.store_id == store_id).all()

@app.post("/stores/{store_id}/call-options", response_model=schemas.CallOptionResponse)
def create_call_option(store_id: int, option: schemas.CallOptionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    verify_store_permission(db, current_user, store_id)
    new_option = models.CallOption(store_id=store_id, name=option.name)
    db.add(new_option)
    db.commit()
    db.refresh(new_option)
    return new_option

@app.delete("/call-options/{option_id}")
def delete_call_option(option_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    option = db.query(models.CallOption).filter(models.CallOption.id == option_id).first()
    if not option: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    verify_store_permission(db, current_user, option.store_id)
    db.delete(option)
    db.commit()
    return {"message": "deleted"}

@app.post("/stores/{store_id}/calls", response_model=schemas.StaffCallResponse)
async def create_staff_call(store_id: int, call: schemas.StaffCallCreate, db: Session = Depends(get_db)):
    new_call = models.StaffCall(store_id=store_id, table_id=call.table_id, message=call.message)
    db.add(new_call)
    db.commit()
    db.refresh(new_call)

    try:
        message = json.dumps({"type": "NEW_CALL", "message": f"🔔 새로운 직원 호출: {call.message}"}, ensure_ascii=False)
        await manager.broadcast(message, store_id=store_id)
    except: pass
    return new_call

@app.get("/stores/{store_id}/calls", response_model=List[schemas.StaffCallResponse])
def read_active_calls(store_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    verify_store_permission(db, current_user, store_id)
    calls = db.query(models.StaffCall).filter(models.StaffCall.store_id == store_id, models.StaffCall.is_completed == False).all()
    return [schemas.StaffCallResponse(id=c.id, table_id=c.table_id, message=c.message, created_at=c.created_at, is_completed=c.is_completed, table_name=c.table.name if c.table else "Unknown") for c in calls]

@app.patch("/calls/{call_id}/complete")
def complete_staff_call(call_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    call = db.query(models.StaffCall).filter(models.StaffCall.id == call_id).first()
    if not call: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    verify_store_permission(db, current_user, call.store_id)
    call.is_completed = True
    db.commit()
    return {"message": "completed"}

# =========================================================
# 🚀 프랜차이즈 본사: 메뉴 일괄 배포 
# =========================================================
@app.post("/brands/distribute-menu")
def distribute_menu(req: schemas.MenuDistributeRequest, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN]:
        raise HTTPException(status_code=403, detail="메뉴 배포 권한이 없습니다.")
    source_category = db.query(models.Category).filter(models.Category.id == req.source_category_id).first()
    if not source_category: raise HTTPException(status_code=404, detail="원본 카테고리를 찾을 수 없습니다.")

    success_count, update_count = 0, 0
    for store_id in req.target_store_ids:
        target_store = db.query(models.Store).filter(models.Store.id == store_id).first()
        if not target_store: continue

        og_mapping = {}
        target_category = db.query(models.Category).filter(models.Category.store_id == store_id, models.Category.name == source_category.name).first()
        if not target_category:
            target_category = models.Category(store_id=store_id, name=source_category.name, order_index=source_category.order_index)
            db.add(target_category)
            db.commit()
            db.refresh(target_category)

        for source_menu in source_category.menus:
            target_menu = db.query(models.Menu).filter(models.Menu.category_id == target_category.id, models.Menu.name == source_menu.name).first()
            calculated_price = source_menu.price + (target_store.price_markup or 0)
            
            if target_menu:
                target_menu.price = calculated_price 
                target_menu.is_price_fixed = source_menu.is_price_fixed 
                target_menu.description = source_menu.description
                target_menu.image_url = source_menu.image_url
                target_menu.order_index = source_menu.order_index
                update_count += 1
            else:
                target_menu = models.Menu(store_id=store_id, category_id=target_category.id, name=source_menu.name, price=calculated_price, is_price_fixed=source_menu.is_price_fixed, description=source_menu.description, image_url=source_menu.image_url, order_index=source_menu.order_index)
                db.add(target_menu)
                db.commit()
                db.refresh(target_menu)
                success_count += 1

            for link in source_menu.menu_option_links:
                source_og = db.query(models.OptionGroup).filter(models.OptionGroup.id == link.option_group_id).first()
                if not source_og: continue
                
                if source_og.id in og_mapping:
                    target_og = og_mapping[source_og.id]
                else:
                    target_og = db.query(models.OptionGroup).filter(models.OptionGroup.store_id == store_id, models.OptionGroup.name == source_og.name).first()
                    if not target_og:
                        target_og = models.OptionGroup(store_id=store_id, name=source_og.name, is_single_select=source_og.is_single_select, is_required=source_og.is_required, max_select=source_og.max_select)
                        db.add(target_og)
                        db.commit()
                        db.refresh(target_og)
                    og_mapping[source_og.id] = target_og
                
                target_og.is_single_select = source_og.is_single_select
                target_og.is_required = source_og.is_required
                target_og.max_select = source_og.max_select
                db.commit()
                    
                for s_opt in source_og.options:
                    t_opt = db.query(models.Option).filter(models.Option.group_id == target_og.id, models.Option.name == s_opt.name).first()
                    if t_opt:
                        t_opt.price = s_opt.price
                        t_opt.is_default = s_opt.is_default
                        t_opt.order_index = s_opt.order_index
                    else:
                        new_opt = models.Option(store_id=store_id, group_id=target_og.id, name=s_opt.name, price=s_opt.price, is_default=s_opt.is_default, order_index=s_opt.order_index)
                        db.add(new_opt)
                db.commit() 
                    
                if not db.query(models.MenuOptionLink).filter(models.MenuOptionLink.menu_id == target_menu.id, models.MenuOptionLink.option_group_id == target_og.id).first():
                    db.add(models.MenuOptionLink(menu_id=target_menu.id, option_group_id=target_og.id, order_index=link.order_index))
            db.commit()
    return {"message": f"배포 완료! (신규추가: {success_count}개, 업데이트: {update_count}개)"}

# --- 🏠 매장 기본 정보 수정 ---
@app.patch("/stores/{store_id}", response_model=schemas.StoreResponse)
def update_store_info(store_id: int, store_update: schemas.StoreUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    verify_store_permission(db, current_user, store_id)
    store = db.query(models.Store).filter(models.Store.id == store_id).first()
    if not store: raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")
    for key, value in store_update.dict(exclude_unset=True).items(): setattr(store, key, value)
    db.commit()
    db.refresh(store)
    return store

# --- 🍽️ 메뉴 수정 및 기타 API 유지 ---
@app.patch("/menus/{menu_id}", response_model=schemas.MenuResponse)
def update_menu(menu_id: int, menu_update: schemas.MenuUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)
    if current_user.role in [models.UserRole.STORE_OWNER, models.UserRole.STAFF]:
        if menu.is_price_fixed and menu_update.price is not None and menu_update.price != menu.price:
            raise HTTPException(status_code=403, detail="본사에서 강제 고정한 메뉴이므로 점주가 임의로 가격을 변경할 수 없습니다.")
    for key, value in menu_update.dict(exclude_unset=True).items(): setattr(menu, key, value)
    db.commit()
    db.refresh(menu)
    return menu

@app.delete("/menus/{menu_id}")
def delete_menu(menu_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)
    db.delete(menu)
    db.commit()
    return {"message": "삭제되었습니다."}

@app.patch("/option-groups/{group_id}", response_model=schemas.OptionGroupResponse)
def update_option_group(group_id: int, group_update: schemas.OptionGroupUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    group = db.query(models.OptionGroup).filter(models.OptionGroup.id == group_id).first()
    if not group: raise HTTPException(status_code=404, detail="옵션 그룹을 찾을 수 없습니다.")
    verify_store_permission(db, current_user, group.store_id)
    for key, value in group_update.dict(exclude_unset=True).items(): setattr(group, key, value)
    db.commit()
    db.refresh(group)
    return group

@app.patch("/options/{option_id}", response_model=schemas.OptionResponse)
def update_option(option_id: int, opt_update: schemas.OptionUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    opt = db.query(models.Option).filter(models.Option.id == option_id).first()
    if not opt: raise HTTPException(status_code=404, detail="옵션을 찾을 수 없습니다.")
    verify_store_permission(db, current_user, opt.store_id)
    for key, value in opt_update.dict(exclude_unset=True).items(): setattr(opt, key, value)
    db.commit()
    db.refresh(opt)
    return opt

@app.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category: raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    verify_store_permission(db, current_user, category.store_id)
    db.query(models.Menu).filter(models.Menu.category_id == category_id).delete()
    db.delete(category)
    db.commit()
    return {"message": "삭제되었습니다."}

@app.delete("/option-groups/{group_id}")
def delete_option_group(group_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    group = db.query(models.OptionGroup).filter(models.OptionGroup.id == group_id).first()
    if not group: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    verify_store_permission(db, current_user, group.store_id)
    db.query(models.Option).filter(models.Option.group_id == group_id).delete()
    db.query(models.MenuOptionLink).filter(models.MenuOptionLink.option_group_id == group_id).delete()
    db.delete(group)
    db.commit()
    return {"message": "삭제되었습니다."}

@app.delete("/options/{option_id}")
def delete_option(option_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    opt = db.query(models.Option).filter(models.Option.id == option_id).first()
    if not opt: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    verify_store_permission(db, current_user, opt.store_id)
    db.delete(opt)
    db.commit()
    return {"message": "삭제되었습니다."}

@app.get("/stores/{store_id}/option-groups/", response_model=List[schemas.OptionGroupResponse])
def get_option_groups(store_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    verify_store_permission(db, current_user, store_id)
    return db.query(models.OptionGroup).filter(models.OptionGroup.store_id == store_id).order_by(models.OptionGroup.order_index).all()

@app.post("/option-groups/{group_id}/options/", response_model=schemas.OptionResponse)
def create_option_for_group(group_id: int, option: schemas.OptionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    group = db.query(models.OptionGroup).filter(models.OptionGroup.id == group_id).first()
    if not group: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    verify_store_permission(db, current_user, group.store_id)
    return crud.create_option(db=db, option=option, group_id=group_id, store_id=group.store_id)

@app.post("/menus/{menu_id}/link-option-group/{group_id}")
def link_option_group_to_menu(menu_id: int, group_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)
    if not db.query(models.MenuOptionLink).filter_by(menu_id=menu_id, option_group_id=group_id).first():
        last_link = db.query(models.MenuOptionLink).filter_by(menu_id=menu_id).order_by(models.MenuOptionLink.order_index.desc()).first()
        db.add(models.MenuOptionLink(menu_id=menu_id, option_group_id=group_id, order_index=(last_link.order_index + 1) if last_link else 1))
        db.commit()
    return {"message": "연결 완료"}

@app.delete("/menus/{menu_id}/option-groups/{group_id}")
def unlink_option_group_from_menu(menu_id: int, group_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)
    link = db.query(models.MenuOptionLink).filter_by(menu_id=menu_id, option_group_id=group_id).first()
    if link:
        db.delete(link)
        db.commit()
    return {"message": "연결 해제 완료"}

class ReorderRequest(BaseModel):
    order_index: int

@app.patch("/menus/{menu_id}/option-groups/{group_id}/reorder")
def reorder_menu_option_group(menu_id: int, group_id: int, req: ReorderRequest, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)
    link = db.query(models.MenuOptionLink).filter_by(menu_id=menu_id, option_group_id=group_id).first()
    if link:
        link.order_index = req.order_index
        db.commit()
    return {"message": "순서 변경 완료"}

@app.post("/stores/{store_id}/option-groups/", response_model=schemas.OptionGroupResponse)
def create_standalone_option_group(store_id: int, group: schemas.OptionGroupCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_active_user)):
    verify_store_permission(db, current_user, store_id)
    db_group = models.OptionGroup(store_id=store_id, name=group.name, is_single_select=group.is_single_select, is_required=group.is_required, max_select=group.max_select, order_index=group.order_index)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

@app.get("/hq/stats", response_model=schemas.HQSalesStatResponse)
def get_hq_sales_stats(start_date: str, end_date: str, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN, models.UserRole.GROUP_ADMIN]:
        raise HTTPException(status_code=403, detail="본사 관리자만 접근할 수 있습니다.")
    query = db.query(models.Store)
    if current_user.role == models.UserRole.BRAND_ADMIN: query = query.filter(models.Store.brand_id == current_user.brand_id)
    elif current_user.role == models.UserRole.GROUP_ADMIN: query = query.filter(models.Store.group_id == current_user.group_id)
    stores = query.all()
    store_ids = [s.id for s in stores]

    if not store_ids: return {"total_revenue": 0, "total_order_count": 0, "total_royalty_fee": 0, "store_stats": []}

    orders = db.query(models.Order).filter(models.Order.store_id.in_(store_ids), models.Order.payment_status == "PAID", models.Order.created_at >= f"{start_date} 00:00:00", models.Order.created_at <= f"{end_date} 23:59:59").all()
    total_rev = sum(o.total_price for o in orders)

    store_data = {s.id: {"name": s.name, "brand_name": s.brand.name if s.brand else "독립 매장", "region": s.region or "미지정", "is_direct_manage": s.is_direct_manage, "rev": 0, "cnt": 0, "r_type": s.royalty_type or "PERCENTAGE", "r_amount": s.royalty_amount or 0.0} for s in stores}
    for o in orders:
        if o.store_id in store_data:
            store_data[o.store_id]["rev"] += o.total_price
            store_data[o.store_id]["cnt"] += 1

    store_stats = []
    total_royalty = 0 
    for sid, data in store_data.items():
        calc_royalty = int(data["rev"] * (data["r_amount"] / 100)) if data["r_type"] == "PERCENTAGE" else int(data["r_amount"])
        total_royalty += calc_royalty
        store_stats.append({"store_id": sid, "store_name": data["name"], "brand_name": data["brand_name"], "region": data["region"], "is_direct_manage": data["is_direct_manage"], "revenue": data["rev"], "order_count": data["cnt"], "royalty_fee": calc_royalty})
    store_stats.sort(key=lambda x: x["revenue"], reverse=True)

    return {"total_revenue": total_rev, "total_order_count": len(orders), "total_royalty_fee": total_royalty, "store_stats": store_stats}

@app.get("/stores/{store_id}/stats") 
def get_store_stats(store_id: int, start_date: str, end_date: str, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    verify_store_permission(db, current_user, store_id)
    orders = db.query(models.Order).filter(models.Order.store_id == store_id, models.Order.payment_status == "PAID", models.Order.created_at >= f"{start_date} 00:00:00", models.Order.created_at <= f"{end_date} 23:59:59").all()
    total_revenue = sum(o.total_price for o in orders)
    order_count = len(orders)
    
    menu_data, hourly_data, daily_data, monthly_data = {}, {f"{i:02d}": 0 for i in range(24)}, {}, {}

    for order in orders:
        try:
            d_part, t_part = str(order.created_at).split(" ")
            order_hour, order_month = t_part.split(":")[0], d_part[:7]
            hourly_data[order_hour] += order.total_price
            if d_part not in daily_data: daily_data[d_part] = {"sales": 0, "count": 0}
            daily_data[d_part]["sales"] += order.total_price
            daily_data[d_part]["count"] += 1
            if order_month not in monthly_data: monthly_data[order_month] = {"sales": 0, "count": 0}
            monthly_data[order_month]["sales"] += order.total_price
            monthly_data[order_month]["count"] += 1
            for item in order.items:
                if item.menu_name not in menu_data: menu_data[item.menu_name] = {"count": 0, "revenue": 0}
                menu_data[item.menu_name]["count"] += item.quantity
                menu_data[item.menu_name]["revenue"] += (item.price * item.quantity)
        except: pass

    menu_stats = sorted([{"name": k, "count": v["count"], "revenue": v["revenue"]} for k, v in menu_data.items()], key=lambda x: x["revenue"], reverse=True)
    return {
        "total_revenue": total_revenue, "order_count": order_count, "average_order_value": int(total_revenue / order_count) if order_count > 0 else 0,
        "menu_stats": menu_stats, "hourly_stats": [{"hour": k, "sales": v} for k, v in hourly_data.items()],
        "daily_stats": [{"date": k, "sales": v["sales"], "count": v["count"]} for k, v in sorted(daily_data.items(), reverse=True)],
        "monthly_stats": [{"month": k, "sales": v["sales"], "count": v["count"]} for k, v in sorted(monthly_data.items(), reverse=True)]
    }

@app.post("/admin/notices")
def create_notice(notice: schemas.NoticeCreate, db: Session = Depends(get_db)):
    new_notice = models.Notice(title=notice.title, content=notice.content, target_type=notice.target_type, target_brand_id=notice.target_brand_id, target_store_id=notice.target_store_id)
    db.add(new_notice)
    db.commit()
    return {"message": "발송 완료"}

@app.get("/notices/unread")
def get_unread_notices(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    read_notice_ids = [r.notice_id for r in db.query(models.NoticeRead).filter(models.NoticeRead.user_id == current_user.id).all()]
    filters = [models.Notice.is_active == True]
    if read_notice_ids: filters.append(models.Notice.id.notin_(read_notice_ids))
    target_filters = [models.Notice.target_type == "ALL"]
    if current_user.brand_id: target_filters.append(and_(models.Notice.target_type == "BRAND", models.Notice.target_brand_id == current_user.brand_id))
    if current_user.store_id: 
        target_filters.append(and_(models.Notice.target_type == "STORE", models.Notice.target_store_id == current_user.store_id))
        user_store = db.query(models.Store).filter(models.Store.id == current_user.store_id).first()
        if user_store and user_store.brand_id: target_filters.append(and_(models.Notice.target_type == "BRAND", models.Notice.target_brand_id == user_store.brand_id))
    return db.query(models.Notice).filter(and_(*filters), or_(*target_filters)).order_by(models.Notice.created_at.asc()).all()

@app.post("/notices/{notice_id}/read")
def mark_notice_read(notice_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    db.add(models.NoticeRead(user_id=current_user.id, notice_id=notice_id))
    db.commit()
    return {"message": "읽음 처리 완료"}

@app.get("/admin/notices/history")
def get_notice_history(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role == "SUPER_ADMIN": return db.query(models.Notice).order_by(models.Notice.created_at.desc()).all()
    elif current_user.role == "BRAND_ADMIN": return db.query(models.Notice).filter(or_(models.Notice.target_brand_id == current_user.brand_id, models.Notice.target_type == "BRAND")).order_by(models.Notice.created_at.desc()).all()
    return []

@app.get("/notices/my")
def get_my_notices(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    target_filters = [models.Notice.target_type == "ALL"]
    if current_user.brand_id: target_filters.append(and_(models.Notice.target_type == "BRAND", models.Notice.target_brand_id == current_user.brand_id))
    if current_user.store_id:
        target_filters.append(and_(models.Notice.target_type == "STORE", models.Notice.target_store_id == current_user.store_id))
        user_store = db.query(models.Store).filter(models.Store.id == current_user.store_id).first()
        if user_store and user_store.brand_id: target_filters.append(and_(models.Notice.target_type == "BRAND", models.Notice.target_brand_id == user_store.brand_id))
    
    notices = db.query(models.Notice).filter(or_(*target_filters)).order_by(models.Notice.created_at.desc()).all()
    read_notice_ids = {r.notice_id for r in db.query(models.NoticeRead).filter(models.NoticeRead.user_id == current_user.id).all()}
    
    return [{"id": n.id, "title": n.title, "content": n.content, "created_at": n.created_at, "is_read": n.id in read_notice_ids} for n in notices]

def create_audit_log(db: Session, user_id: int, action: str, target_type: str, target_id: int, details: str):
    db.add(models.AuditLog(user_id=user_id, action=action, target_type=target_type, target_id=target_id, details=details))
    db.commit()

@app.get("/admin/audit-logs")
def get_audit_logs(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    query = db.query(models.AuditLog).join(models.User)
    if current_user.role == "BRAND_ADMIN": query = query.filter(models.User.brand_id == current_user.brand_id)
    elif current_user.role != "SUPER_ADMIN": return []
    logs = query.order_by(models.AuditLog.created_at.desc()).limit(100).all()
    return [{"id": log.id, "user_name": log.user.name if log.user else "-", "user_email": log.user.email if log.user else "-", "action": log.action, "target_type": log.target_type, "details": log.details, "created_at": log.created_at} for log in logs]