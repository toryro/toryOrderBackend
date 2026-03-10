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
    # 1. 슈퍼 관리자 (모든 권한 허용)
    if current_user.role == models.UserRole.SUPER_ADMIN:
        return True
        
    # 2. 브랜드 관리자 (내 브랜드 소속 매장인지 확인)
    if current_user.role == models.UserRole.BRAND_ADMIN:
        store = db.query(models.Store).filter(models.Store.id == store_id).first()
        if not store or store.brand_id != current_user.brand_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="타 브랜드 매장에는 접근할 수 없습니다.")
        return True
        
    # 3. 점주 및 직원 (내가 소속된 매장인지 확인)
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
    # IP 하드코딩 대신 현재 접속된 서버 주소를 자동 파악
    base_url = str(request.base_url).rstrip("/")
    return {"url": f"{base_url}/images/{filename}"}

# =========================================================
# 브랜드/매장 생성 및 조회 API
# =========================================================
@app.post("/brands/", response_model=schemas.BrandResponse)
def create_brand(brand: schemas.BrandCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
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

    # ✨ [CCTV 추가] 브랜드 생성 기록
    create_audit_log(
        db=db, user_id=current_user.id, action="CREATE_BRAND", target_type="BRAND", target_id=db_brand.id,
        details=f"신규 브랜드 생성: [{db_brand.name}]"
    )

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
    
    target_brand_id = group.brand_id
    if current_user.role == models.UserRole.BRAND_ADMIN:
        target_brand_id = current_user.brand_id

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

        # ✨ [CCTV 추가] 매장 생성 기록
    create_audit_log(
        db=db, user_id=current_user.id, action="CREATE_STORE", target_type="STORE", target_id=new_store.id,
        details=f"새 매장 오픈: [{new_store.name}]"
    )

    return new_store

@app.get("/stores/{store_id}", response_model=schemas.StoreResponse)
def read_store(store_id: int, db: Session = Depends(get_db)):
    db_store = crud.get_store(db, store_id=store_id)
    if not db_store: raise HTTPException(status_code=404, detail="Store not found")
    
    # 1. DB 객체를 프론트엔드로 보내기 편한 사전(Dict) 형태로 변환합니다.
    store_data = schemas.StoreResponse.model_validate(db_store).model_dump()
    
    # 2. 모든 카테고리와 메뉴를 돌면서 '연결된 옵션 그룹'을 수동으로 찾아 넣어줍니다.
    for category in store_data.get("categories", []):
        for menu in category.get("menus", []):
            # 중간 다리(MenuOptionLink) 테이블에서 이 메뉴와 연결된 기록을 가져옵니다.
            links = db.query(models.MenuOptionLink).filter(
                models.MenuOptionLink.menu_id == menu["id"]
            ).order_by(models.MenuOptionLink.order_index).all()
            
            option_groups = []
            for link in links:
                # 다리에 적힌 옵션 그룹 ID를 통해 실제 옵션 그룹의 상세 정보를 가져옵니다.
                og = db.query(models.OptionGroup).filter(models.OptionGroup.id == link.option_group_id).first()
                if og:
                    # 가져온 옵션 그룹 정보도 사전 형태로 변환해 리스트에 담습니다.
                    og_data = schemas.OptionGroupResponse.model_validate(og).model_dump()
                    option_groups.append(og_data)
                    
            # 3. 꼼꼼하게 찾은 옵션 그룹들을 메뉴 데이터에 장착합니다!
            menu["option_groups"] = option_groups
            
    return store_data

@app.get("/groups/my/stores", response_model=List[schemas.StoreResponse])
def read_my_stores(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role == models.UserRole.SUPER_ADMIN: 
        return db.query(models.Store).order_by(models.Store.id).all()
    if current_user.role == models.UserRole.BRAND_ADMIN: 
        return db.query(models.Store).filter(models.Store.brand_id == current_user.brand_id).order_by(models.Store.id).all() if current_user.brand_id else []
    if current_user.role == models.UserRole.GROUP_ADMIN: 
        return db.query(models.Store).filter(models.Store.group_id == current_user.group_id).order_by(models.Store.id).all() if current_user.group_id else []
    if current_user.role == models.UserRole.STORE_OWNER: 
        return db.query(models.Store).filter(models.Store.id == current_user.store_id).order_by(models.Store.id).all() if current_user.store_id else []
    return []

# =========================================================
# 👤 계정 관리 API (관리자용)
# =========================================================
@app.get("/users/", response_model=List[schemas.UserResponse])
def read_all_users(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role == models.UserRole.SUPER_ADMIN:
        return db.query(models.User).all()
        
    if current_user.role == models.UserRole.BRAND_ADMIN:
        if not current_user.brand_id:
            return []
        return db.query(models.User).filter(
            models.User.brand_id == current_user.brand_id,
            models.User.role.in_([models.UserRole.STORE_OWNER, models.UserRole.STAFF])
        ).all()
        
    # ✨ [추가된 부분] 점주는 '자기 매장'에 소속된 계정(본인 및 직원)만 볼 수 있도록 허용!
    if current_user.role == models.UserRole.STORE_OWNER:
        if not current_user.store_id:
            return []
        return db.query(models.User).filter(models.User.store_id == current_user.store_id).all()
        
    raise HTTPException(status_code=403, detail="조회 권한이 없습니다.")

@app.post("/admin/users/", response_model=schemas.UserResponse)
def create_user_by_admin(user: schemas.UserCreate, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN, models.UserRole.STORE_OWNER]:
        raise HTTPException(status_code=403, detail="계정 생성 권한이 없습니다.")
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")
    
    # ✨ [CCTV 추가] 변수에 담아서 로그를 남기고 리턴!
    new_user = crud.create_user(db=db, user=user)
    role_kr = {"SUPER_ADMIN":"슈퍼관리자", "BRAND_ADMIN":"브랜드관리자", "STORE_OWNER":"점주", "STAFF":"직원"}.get(new_user.role, new_user.role)
    create_audit_log(
        db=db, user_id=current_user.id, action="CREATE_USER", target_type="USER", target_id=new_user.id,
        details=f"새 계정 발급: {new_user.name} / {new_user.email} ({role_kr})"
    )

    return crud.create_user(db=db, user=user)

@app.delete("/admin/users/{user_id}")
def delete_user_by_admin(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    user_to_delete = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_to_delete: 
        raise HTTPException(status_code=404, detail="User not found")

    # ✨ [수정된 부분] 직급별 맞춤형 삭제 권한 검증
    if current_user.role == models.UserRole.SUPER_ADMIN:
        pass # 슈퍼 관리자는 모두 삭제 가능
    elif current_user.role == models.UserRole.BRAND_ADMIN and user_to_delete.brand_id == current_user.brand_id:
        pass # 브랜드 관리자는 자기 브랜드 계정 삭제 가능
    elif current_user.role == models.UserRole.STORE_OWNER and user_to_delete.store_id == current_user.store_id and user_to_delete.role == models.UserRole.STAFF:
        pass # 점주는 자기 매장의 '직원'만 삭제 가능
    else:
        raise HTTPException(status_code=403, detail="삭제 권한이 없거나 다른 매장의 계정입니다.")

    # ✨ [CCTV 추가] 계정 삭제 기록
    create_audit_log(
        db=db, user_id=current_user.id, action="DELETE_USER", target_type="USER", target_id=user_id,
        details=f"계정 삭제됨: {user_to_delete.name} ({user_to_delete.email})"
    )

    db.delete(user_to_delete)
    db.commit()
    return {"message": "User deleted"}

# =========================================================
# 🍽️ 메뉴, 카테고리, 옵션, 테이블 관리 (권한 검증 완벽 적용)
# =========================================================
@app.post("/stores/{store_id}/categories/", response_model=schemas.CategoryResponse)
def create_category_for_store(
    store_id: int,
    category: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    verify_store_permission(db, current_user, store_id)
    db_category = models.Category(**category.dict(), store_id=store_id)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@app.post("/categories/{category_id}/menus/", response_model=schemas.MenuResponse)
def create_menu_for_category(
    category_id: int,
    menu: schemas.MenuCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    category = db.query(models.Category).filter(models.Category.id == category_id).first() 
    if not category:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
        
    verify_store_permission(db, current_user, category.store_id)
    
    db_menu = models.Menu(**menu.dict(exclude={"options"}), category_id=category_id, store_id=category.store_id)
    db.add(db_menu)
    db.commit()
    db.refresh(db_menu)

    # ✨ [CCTV 추가] 메뉴 추가 기록
    create_audit_log(
        db=db, user_id=current_user.id, action="CREATE_MENU", target_type="MENU", target_id=db_menu.id,
        details=f"새 메뉴 생성: [{db_menu.name}] (가격: {db_menu.price}원)"
    )

    return db_menu

@app.post("/menus/{menu_id}/option-groups/", response_model=schemas.OptionGroupResponse)
def create_option_group(
    menu_id: int, 
    group: schemas.OptionGroupCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_user)
):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, menu.store_id)
    
    return crud.create_option_group(db=db, group=group, menu_id=menu_id, store_id=menu.store_id)

@app.post("/stores/{store_id}/tables/", response_model=schemas.TableResponse)
def create_table_for_store(
    store_id: int, 
    table: schemas.TableCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_user)
):
    verify_store_permission(db, current_user, store_id)
    return crud.create_table(db=db, table=table, store_id=store_id)

@app.get("/tables/by-token/{qr_token}")
def get_table_by_token(qr_token: str, db: Session = Depends(get_db)):
    table = db.query(models.Table).filter(models.Table.qr_token == qr_token).first()
    if not table: raise HTTPException(status_code=404, detail="유효하지 않은 QR 코드입니다.")
    return {"store_id": table.store_id, "table_id": table.id, "label": table.name}

# =========================================================
# 🪑 테이블 수정 및 삭제 API 추가
# =========================================================

# 1. 테이블 이름 수정 API
@app.patch("/tables/{table_id}", response_model=schemas.TableResponse)
def update_table(
    table_id: int,
    table_update: schemas.TableUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="테이블을 찾을 수 없습니다.")
    
    # 내 매장의 테이블이 맞는지 권한 검증
    verify_store_permission(db, current_user, table.store_id)

    table.name = table_update.name
    db.commit()
    db.refresh(table)
    return table

# 2. 테이블 삭제 API
@app.delete("/tables/{table_id}")
def delete_table(
    table_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="테이블을 찾을 수 없습니다.")
    
    # 내 매장의 테이블이 맞는지 권한 검증
    verify_store_permission(db, current_user, table.store_id)

    db.delete(table)
    db.commit()
    return {"message": "테이블이 완전히 삭제되었습니다."}

# =========================================================
# 🔥 [주문 시스템 및 WebSocket]
# =========================================================
@app.post("/orders/", response_model=schemas.OrderResponse)
async def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    for item in order.items:
        # 교차 검증: 요청된 메뉴가 결제하려는 해당 매장의 메뉴인지 강제 확인
        menu = db.query(models.Menu).filter(
            models.Menu.id == item.menu_id,
            models.Menu.store_id == order.store_id
        ).first()
        if not menu: 
            raise HTTPException(status_code=400, detail=f"잘못된 메뉴 요청입니다 (ID: {item.menu_id})")
        
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
        if email is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    db = SessionLocal()
    try:
        user = crud.get_user_by_email(db, email=email)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # ✨ 완벽한 통합 권한 검증 (API와 동일한 기준 적용)
        has_permission = False
        
        # 1. 슈퍼 관리자 (프리패스)
        if user.role == models.UserRole.SUPER_ADMIN:
            has_permission = True
            
        # 2. 브랜드 관리자 (내 브랜드 매장인지 확인)
        elif user.role == models.UserRole.BRAND_ADMIN:
            store = db.query(models.Store).filter(models.Store.id == store_id).first()
            if store and store.brand_id == user.brand_id:
                has_permission = True
                
        # 3. 점주 및 직원 (내 소속 매장이 맞는지 철저히 확인)
        elif user.role in [models.UserRole.STORE_OWNER, models.UserRole.STAFF]:
            if user.store_id == store_id:
                has_permission = True
                
        # 권한이 없다면 웹소켓 연결 차단
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
def read_store_orders(
    store_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_user)
):
    verify_store_permission(db, current_user, store_id)
    return db.query(models.Order).filter(
        models.Order.store_id == store_id,
        models.Order.payment_status == "PAID",
        models.Order.is_completed == False  # ✨ [핵심] 조리 완료 안 된 주문만!
    ).order_by(models.Order.id.asc()).all() # ✨ [핵심] 먼저 들어온 주문부터 처리하도록 오름차순 정렬!

@app.patch("/orders/{order_id}/complete")
def complete_order(
    order_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_user)
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order: raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, order.store_id)
    
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
        send_discord_alert(f"결제 검증 중 치명적 에러 발생!\n내용: {str(e)}")
        print(f"❌ [에러] {e}", flush=True)
        raise HTTPException(status_code=400, detail=str(e))

# =========================================================
# 🔔 직원 호출 옵션 및 실시간 호출
# =========================================================
@app.get("/stores/{store_id}/call-options", response_model=List[schemas.CallOptionResponse])
def get_call_options(
    store_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_user)
):
    verify_store_permission(db, current_user, store_id)
    return db.query(models.CallOption).filter(models.CallOption.store_id == store_id).all()

@app.post("/stores/{store_id}/call-options", response_model=schemas.CallOptionResponse)
def create_call_option(
    store_id: int, 
    option: schemas.CallOptionCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_user)
):
    verify_store_permission(db, current_user, store_id)
    new_option = models.CallOption(store_id=store_id, name=option.name)
    db.add(new_option)
    db.commit()
    db.refresh(new_option)
    return new_option

@app.delete("/call-options/{option_id}")
def delete_call_option(
    option_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_user)
):
    option = db.query(models.CallOption).filter(models.CallOption.id == option_id).first()
    if not option: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, option.store_id)
    
    db.delete(option)
    db.commit()
    return {"message": "deleted"}

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
def read_active_calls(
    store_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_user)
):
    verify_store_permission(db, current_user, store_id)
    calls = db.query(models.StaffCall).filter(models.StaffCall.store_id == store_id, models.StaffCall.is_completed == False).all()
    return [schemas.StaffCallResponse(id=c.id, table_id=c.table_id, message=c.message, created_at=c.created_at, is_completed=c.is_completed, table_name=c.table.name if c.table else "Unknown") for c in calls]

@app.patch("/calls/{call_id}/complete")
def complete_staff_call(
    call_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_user)
):
    call = db.query(models.StaffCall).filter(models.StaffCall.id == call_id).first()
    if not call: raise HTTPException(status_code=404, detail="찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, call.store_id)
    
    call.is_completed = True
    db.commit()
    return {"message": "completed"}

# =========================================================
# 🚀 프랜차이즈 본사: 메뉴 일괄 배포 (옵션 딥싱크 & 업데이트 적용)
# =========================================================
@app.post("/brands/distribute-menu")
def distribute_menu(
    req: schemas.MenuDistributeRequest, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_active_user)
):
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN]:
        raise HTTPException(status_code=403, detail="메뉴 배포 권한이 없습니다.")

    source_category = db.query(models.Category).filter(models.Category.id == req.source_category_id).first()
    if not source_category:
        raise HTTPException(status_code=404, detail="원본 카테고리를 찾을 수 없습니다.")

    success_count = 0
    update_count = 0

    for store_id in req.target_store_ids:
        target_store = db.query(models.Store).filter(models.Store.id == store_id).first()
        if not target_store:
            continue

        # ✨ [핵심 1] 이번 가맹점 동기화 중에 생성/매핑된 옵션 그룹을 기억하는 메모장
        # 형태: { 본사_옵션그룹_ID : 가맹점_옵션그룹_객체 }
        og_mapping = {}

        # 1. 카테고리 동기화
        target_category = db.query(models.Category).filter(
            models.Category.store_id == store_id, 
            models.Category.name == source_category.name
        ).first()
        
        if not target_category:
            target_category = models.Category(store_id=store_id, name=source_category.name, order_index=source_category.order_index)
            db.add(target_category)
            db.commit()
            db.refresh(target_category)

        # 2. 메뉴 및 옵션 딥싱크 (Deep Sync)
        for source_menu in source_category.menus:
            target_menu = db.query(models.Menu).filter(
                models.Menu.category_id == target_category.id, 
                models.Menu.name == source_menu.name
            ).first()
            
            # ✨ [핵심 계산 로직] 본사 가격 + 이 타겟 매장의 고유 할증 금액(강남점 +500)
            calculated_price = source_menu.price + (target_store.price_markup or 0)
            
            # 기존 메뉴 업데이트 또는 신규 생성
            if target_menu:
                target_menu.price = calculated_price # 👈 차등 가격 덮어쓰기
                target_menu.is_price_fixed = source_menu.is_price_fixed # 👈 고정 여부 복사
                target_menu.description = source_menu.description
                target_menu.image_url = source_menu.image_url
                target_menu.order_index = source_menu.order_index
                update_count += 1
            else:
                target_menu = models.Menu(
                    store_id=store_id, category_id=target_category.id,
                    name=source_menu.name, 
                    price=calculated_price, # 👈 차등 가격으로 생성
                    is_price_fixed=source_menu.is_price_fixed, # 👈 고정 여부 복사
                    description=source_menu.description, image_url=source_menu.image_url,
                    order_index=source_menu.order_index
                )
                db.add(target_menu)
                db.commit()
                db.refresh(target_menu)
                success_count += 1

            # 3. 옵션 그룹 매핑 및 복사 (이름 충돌 완벽 방어)
            for link in source_menu.menu_option_links:
                source_og = db.query(models.OptionGroup).filter(models.OptionGroup.id == link.option_group_id).first()
                if not source_og:
                    continue
                
                target_og = None
                
                # ✨ [핵심 2] 방어 로직 분기점
                if source_og.id in og_mapping:
                    target_og = og_mapping[source_og.id]
                else:
                    # 💡 [수정됨] 타겟 매장에 이미 같은 이름의 옵션 그룹이 존재하는지 매장 전체를 먼저 검색합니다!
                    target_og = db.query(models.OptionGroup).filter(
                        models.OptionGroup.store_id == store_id,
                        models.OptionGroup.name == source_og.name
                    ).first()
                    
                    if not target_og:
                        # 💡 매장 전체를 뒤져도 없을 때만 순수하게 새로 생성합니다.
                        target_og = models.OptionGroup(
                            store_id=store_id, name=source_og.name, 
                            is_single_select=source_og.is_single_select,
                            is_required=source_og.is_required, max_select=source_og.max_select
                        )
                        db.add(target_og)
                        db.commit()
                        db.refresh(target_og)
                    
                    # 새롭게 찾거나 만든 타겟 그룹을 메모장에 기록
                    og_mapping[source_og.id] = target_og
                
                # 옵션 그룹 설정 덮어쓰기
                target_og.is_single_select = source_og.is_single_select
                target_og.is_required = source_og.is_required
                target_og.max_select = source_og.max_select
                db.commit()
                    
                # 세부 옵션(0단계, 1단계 등) 딥싱크
                for s_opt in source_og.options:
                    t_opt = db.query(models.Option).filter(
                        models.Option.group_id == target_og.id,
                        models.Option.name == s_opt.name
                    ).first()
                    
                    if t_opt:
                        t_opt.price = s_opt.price
                        t_opt.is_default = s_opt.is_default
                        t_opt.order_index = s_opt.order_index
                    else:
                        new_opt = models.Option(
                            store_id=store_id, group_id=target_og.id,
                            name=s_opt.name, price=s_opt.price, 
                            is_default=s_opt.is_default, order_index=s_opt.order_index
                        )
                        db.add(new_opt)
                db.commit() 
                    
                # 타겟 메뉴와 타겟 옵션 그룹 최종 연결
                existing_link = db.query(models.MenuOptionLink).filter(
                    models.MenuOptionLink.menu_id == target_menu.id,
                    models.MenuOptionLink.option_group_id == target_og.id
                ).first()
                
                if not existing_link:
                    new_link = models.MenuOptionLink(menu_id=target_menu.id, option_group_id=target_og.id, order_index=link.order_index)
                    db.add(new_link)
            
            db.commit()

    # ✨ [CCTV 추가] 일괄 배포 결과 기록
    category_name = source_category.name if source_category else "알수없는 카테고리"
    create_audit_log(
        db=db, user_id=current_user.id, action="DISTRIBUTE_MENU", target_type="CATEGORY", target_id=req.source_category_id,
        details=f"메뉴 일괄 배포: '{category_name}' 카테고리를 타겟 매장 {len(req.target_store_ids)}곳에 덮어쓰기 완료"
    )

    return {"message": f"총 {len(req.target_store_ids)}개 매장 배포 완료! (신규추가: {success_count}개, 업데이트: {update_count}개)"}

# --- 🏠 매장 기본 정보 수정 ---
@app.patch("/stores/{store_id}", response_model=schemas.StoreResponse)
def update_store_info(
    store_id: int,
    store_update: schemas.StoreUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    verify_store_permission(db, current_user, store_id)
    
    store = db.query(models.Store).filter(models.Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="매장을 찾을 수 없습니다.")
        
    update_data = store_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(store, key, value)
        
    db.commit()
    db.refresh(store)

    # ✨ [CCTV 추가] 매장 설정 변경 기록
    create_audit_log(
        db=db, user_id=current_user.id, action="UPDATE_STORE", target_type="STORE", target_id=store.id,
        details=f"매장 정보/정책 수정: [{store.name}]"
    )

    return store

# --- 🍽️ 메뉴 수정 ---
@app.patch("/menus/{menu_id}", response_model=schemas.MenuResponse)
def update_menu(
    menu_id: int,
    menu_update: schemas.MenuUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, menu.store_id)

    # 🛡️ [핵심 방어 로직] 본사가 가격을 고정(is_price_fixed=True)했는데, 점주나 직원이 가격을 바꾸려 한다면? -> 철벽 방어!
    if current_user.role in [models.UserRole.STORE_OWNER, models.UserRole.STAFF]:
        if menu.is_price_fixed and menu_update.price is not None and menu_update.price != menu.price:
            raise HTTPException(status_code=403, detail="본사에서 강제 고정한 메뉴이므로 점주가 임의로 가격을 변경할 수 없습니다.")

    update_data = menu_update.dict(exclude_unset=True)

    # ✨ [CCTV 추가] 무엇이 바뀌었는지 꼼꼼하게 추적
    changes = []
    if "price" in update_data and menu.price != update_data["price"]:
        changes.append(f"가격 {menu.price}원 -> {update_data['price']}원")
    if "name" in update_data and menu.name != update_data["name"]:
        changes.append(f"이름 '{menu.name}' -> '{update_data['name']}'")
    if "is_sold_out" in update_data and menu.is_sold_out != update_data["is_sold_out"]:
        status = "품절" if update_data["is_sold_out"] else "판매중"
        changes.append(f"상태 -> {status}")
        
    if changes:
        create_audit_log(
            db=db, user_id=current_user.id, action="UPDATE_MENU", target_type="MENU", target_id=menu.id,
            details=f"메뉴 수정 [{menu.name}]: " + ", ".join(changes)
        )

    for key, value in update_data.items():
        setattr(menu, key, value)
    
    db.commit()
    db.refresh(menu)
    return menu

# --- 🗑️ 메뉴 삭제 ---
@app.delete("/menus/{menu_id}")
def delete_menu(
    menu_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu:
        raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
        
    verify_store_permission(db, current_user, menu.store_id)

    # ✨ [CCTV 추가] 메뉴 삭제 기록
    create_audit_log(
        db=db, user_id=current_user.id, action="DELETE_MENU", target_type="MENU", target_id=menu.id,
        details=f"메뉴 삭제됨: {menu.name} (기존 가격: {menu.price}원)"
    )
    
    db.delete(menu)
    db.commit()
    return {"message": "메뉴가 완전히 삭제되었습니다."}

# --- ⚙️ 옵션 그룹 수정 ---
@app.patch("/option-groups/{group_id}", response_model=schemas.OptionGroupResponse)
def update_option_group(
    group_id: int,
    group_update: schemas.OptionGroupUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    group = db.query(models.OptionGroup).filter(models.OptionGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="옵션 그룹을 찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, group.store_id)
    
    update_data = group_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(group, key, value)
    
    db.commit()
    db.refresh(group)
    return group

# --- 📝 개별 옵션 수정 ---
@app.patch("/options/{option_id}", response_model=schemas.OptionResponse)
def update_option(
    option_id: int,
    opt_update: schemas.OptionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    opt = db.query(models.Option).filter(models.Option.id == option_id).first()
    if not opt:
        raise HTTPException(status_code=404, detail="옵션을 찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, opt.store_id)
    
    update_data = opt_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(opt, key, value)
        
    db.commit()
    db.refresh(opt)
    return opt

# =========================================================
# 🗑️ 카테고리 및 옵션 그룹 삭제 API 추가
# =========================================================

@app.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, category.store_id)
    
    # 카테고리 삭제 시 속해있는 메뉴도 깔끔하게 연쇄 삭제
    db.query(models.Menu).filter(models.Menu.category_id == category_id).delete()
    
    db.delete(category)
    db.commit()
    return {"message": "카테고리와 하위 메뉴가 삭제되었습니다."}

@app.delete("/option-groups/{group_id}")
def delete_option_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    group = db.query(models.OptionGroup).filter(models.OptionGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="옵션 그룹을 찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, group.store_id)
    
    # 하위 세부 옵션들 및 메뉴와의 연결 고리 먼저 삭제
    db.query(models.Option).filter(models.Option.group_id == group_id).delete()
    db.query(models.MenuOptionLink).filter(models.MenuOptionLink.option_group_id == group_id).delete()
    
    db.delete(group)
    db.commit()
    return {"message": "옵션 그룹이 완전히 삭제되었습니다."}

# --- 🗑️ 개별 옵션 삭제 ---
@app.delete("/options/{option_id}")
def delete_option(
    option_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    opt = db.query(models.Option).filter(models.Option.id == option_id).first()
    if not opt:
        raise HTTPException(status_code=404, detail="옵션을 찾을 수 없습니다.")
    
    verify_store_permission(db, current_user, opt.store_id)
    
    db.delete(opt)
    db.commit()
    return {"message": "옵션이 삭제되었습니다."}

# 1. 특정 매장의 모든 옵션 그룹 가져오기 (404 에러 해결!)
@app.get("/stores/{store_id}/option-groups/", response_model=List[schemas.OptionGroupResponse])
def get_option_groups(
    store_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_active_user)
):
    verify_store_permission(db, current_user, store_id)
    return db.query(models.OptionGroup).filter(models.OptionGroup.store_id == store_id).order_by(models.OptionGroup.order_index).all()

# 2. 특정 옵션 그룹에 새로운 옵션 항목 추가하기
@app.post("/option-groups/{group_id}/options/", response_model=schemas.OptionResponse)
def create_option_for_group(
    group_id: int, 
    option: schemas.OptionCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_active_user)
):
    group = db.query(models.OptionGroup).filter(models.OptionGroup.id == group_id).first()
    if not group: 
        raise HTTPException(status_code=404, detail="옵션 그룹을 찾을 수 없습니다.")
    verify_store_permission(db, current_user, group.store_id)
    return crud.create_option(db=db, option=option, group_id=group_id, store_id=group.store_id)

# 3. 메뉴와 옵션 그룹을 서로 연결(Link)하기
@app.post("/menus/{menu_id}/link-option-group/{group_id}")
def link_option_group_to_menu(
    menu_id: int, 
    group_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_active_user)
):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)

    # 이미 연결되어 있는지 확인
    existing_link = db.query(models.MenuOptionLink).filter_by(menu_id=menu_id, option_group_id=group_id).first()
    if not existing_link:
        # 가장 마지막 순서 뒤에 추가
        last_link = db.query(models.MenuOptionLink).filter_by(menu_id=menu_id).order_by(models.MenuOptionLink.order_index.desc()).first()
        next_order = (last_link.order_index + 1) if last_link else 1
        new_link = models.MenuOptionLink(menu_id=menu_id, option_group_id=group_id, order_index=next_order)
        db.add(new_link)
        db.commit()
    return {"message": "연결 완료"}

# 4. 메뉴와 옵션 그룹 연결 해제(Unlink)하기
@app.delete("/menus/{menu_id}/option-groups/{group_id}")
def unlink_option_group_from_menu(
    menu_id: int, 
    group_id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_active_user)
):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)

    link = db.query(models.MenuOptionLink).filter_by(menu_id=menu_id, option_group_id=group_id).first()
    if link:
        db.delete(link)
        db.commit()
    return {"message": "연결 해제 완료"}

# 5. 연결된 옵션 그룹 순서 변경용
class ReorderRequest(BaseModel):
    order_index: int

@app.patch("/menus/{menu_id}/option-groups/{group_id}/reorder")
def reorder_menu_option_group(
    menu_id: int, 
    group_id: int, 
    req: ReorderRequest, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_active_user)
):
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    if not menu: raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    verify_store_permission(db, current_user, menu.store_id)

    link = db.query(models.MenuOptionLink).filter_by(menu_id=menu_id, option_group_id=group_id).first()
    if link:
        link.order_index = req.order_index
        db.commit()
    return {"message": "순서 변경 완료"}

# --- ⚙️ 라이브러리 전용: 독립 옵션 그룹 생성 API ---
@app.post("/stores/{store_id}/option-groups/", response_model=schemas.OptionGroupResponse)
def create_standalone_option_group(
    store_id: int, 
    group: schemas.OptionGroupCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(dependencies.get_current_active_user)
):
    verify_store_permission(db, current_user, store_id)
    
    # 메뉴 연결 없이 순수하게 라이브러리에 그룹만 생성 (고유 ID 자동 부여)
    db_group = models.OptionGroup(
        store_id=store_id,
        name=group.name,
        is_single_select=group.is_single_select,
        is_required=group.is_required,
        max_select=group.max_select,
        order_index=group.order_index
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

# =========================================================
# 📈 프랜차이즈 본사: 통합 매출 대시보드 API
# =========================================================
@app.get("/hq/stats", response_model=schemas.HQSalesStatResponse)
def get_hq_sales_stats(
    start_date: str,
    end_date: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    # 1. 본사 권한 확인
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.BRAND_ADMIN, models.UserRole.GROUP_ADMIN]:
        raise HTTPException(status_code=403, detail="본사 관리자만 접근할 수 있습니다.")

    # 2. 내 권한으로 볼 수 있는 가맹점 목록 가져오기
    query = db.query(models.Store)
    if current_user.role == models.UserRole.BRAND_ADMIN:
        query = query.filter(models.Store.brand_id == current_user.brand_id)
    elif current_user.role == models.UserRole.GROUP_ADMIN:
        query = query.filter(models.Store.group_id == current_user.group_id)
    stores = query.all()
    store_ids = [s.id for s in stores]

    if not store_ids:
        return {"total_revenue": 0, "total_order_count": 0, "store_stats": []}

    # 3. 날짜 범위에 해당하는 결제 완료(PAID) 주문 모두 가져오기
    start_dt = f"{start_date} 00:00:00"
    end_dt = f"{end_date} 23:59:59"

    orders = db.query(models.Order).filter(
        models.Order.store_id.in_(store_ids),
        models.Order.payment_status == "PAID",
        models.Order.created_at >= start_dt,
        models.Order.created_at <= end_dt
    ).all()

    total_rev = sum(o.total_price for o in orders)
    total_cnt = len(orders)

    # 4. 매장별로 매출과 건수 집계
    store_data = {
        s.id: {
            "name": s.name, 
            "brand_name": s.brand.name if s.brand else "독립 매장", 
            "region": s.region or "미지정", # ✨ 지역 정보
            "is_direct_manage": s.is_direct_manage, # ✨ 직영/가맹 정보
            "rev": 0, "cnt": 0,
            "r_type": s.royalty_type or "PERCENTAGE", "r_amount": s.royalty_amount or 0.0
        } for s in stores
    }
    
    for o in orders:
        if o.store_id in store_data:
            store_data[o.store_id]["rev"] += o.total_price
            store_data[o.store_id]["cnt"] += 1

    # 5. 리스트로 만들고 정렬
    store_stats = []
    total_royalty = 0 
    
    for sid, data in store_data.items():
        if data["r_type"] == "PERCENTAGE":
            calc_royalty = int(data["rev"] * (data["r_amount"] / 100))
        else:
            calc_royalty = int(data["r_amount"]) 
            
        total_royalty += calc_royalty
        
        store_stats.append({
            "store_id": sid,
            "store_name": data["name"],
            "brand_name": data["brand_name"],
            "region": data["region"], # ✨ 포장
            "is_direct_manage": data["is_direct_manage"], # ✨ 포장
            "revenue": data["rev"],
            "order_count": data["cnt"],
            "royalty_fee": calc_royalty
        })
    store_stats.sort(key=lambda x: x["revenue"], reverse=True)

    return {
        "total_revenue": total_rev,
        "total_order_count": total_cnt,
        "total_royalty_fee": total_royalty, # ✨ 프론트엔드로 전달
        "store_stats": store_stats
    }

# =========================================================
# 💰 점주용: 개별 매장 매출 통계 API
# =========================================================
@app.get("/stores/{store_id}/stats", response_model=schemas.SalesStat)
def get_store_stats(
    store_id: int,
    start_date: str,
    end_date: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    # 1. 권한 검증 (내 매장이 맞는지 확인)
    verify_store_permission(db, current_user, store_id)

    # 2. 날짜 범위 지정 (00시 00분부터 23시 59분까지)
    start_dt = f"{start_date} 00:00:00"
    end_dt = f"{end_date} 23:59:59"

    # 3. 해당 기간에 결제 완료(PAID)된 모든 주문 가져오기
    orders = db.query(models.Order).filter(
        models.Order.store_id == store_id,
        models.Order.payment_status == "PAID",
        models.Order.created_at >= start_dt,
        models.Order.created_at <= end_dt
    ).all()

    total_revenue = sum(o.total_price for o in orders)
    order_count = len(orders)

    menu_data = {}
    hourly_data = {i: 0 for i in range(24)} # 0시부터 23시까지 기본값 0 세팅

    # 4. 주문 내역을 돌면서 메뉴별 / 시간대별 데이터 집계
    for order in orders:
        # 시간대 집계 (예: "2026-03-09 18:24:00" -> 18 추출)
        try:
            order_hour = int(str(order.created_at).split(" ")[1].split(":")[0])
            hourly_data[order_hour] += order.total_price
        except:
            pass

        # 메뉴별 집계
        for item in order.items:
            if item.menu_name not in menu_data:
                menu_data[item.menu_name] = {"count": 0, "revenue": 0}
            menu_data[item.menu_name]["count"] += item.quantity
            menu_data[item.menu_name]["revenue"] += (item.price * item.quantity)

    # 5. 프론트엔드가 요구하는 형식(리스트)으로 변환 및 정렬
    menu_stats = [
        {"name": name, "count": data["count"], "revenue": data["revenue"]}
        for name, data in menu_data.items()
    ]
    # 인기 메뉴 순위 (매출액 기준 내림차순 정렬)
    menu_stats.sort(key=lambda x: x["revenue"], reverse=True)

    hourly_stats = [
        {"hour": hour, "sales": sales}
        for hour, sales in hourly_data.items()
    ]

    return {
        "total_revenue": total_revenue,
        "order_count": order_count,
        "menu_stats": menu_stats,
        "hourly_stats": hourly_stats
    }

# =========================================================
# 📢 고도화된 타겟팅 공지사항 API
# =========================================================

# 1. 공지사항 발송 API (타겟 지정)
@app.post("/admin/notices")
def create_notice(notice: schemas.NoticeCreate, db: Session = Depends(get_db)):
    new_notice = models.Notice(
        title=notice.title, content=notice.content, 
        target_type=notice.target_type, target_brand_id=notice.target_brand_id, target_store_id=notice.target_store_id
    )
    db.add(new_notice)
    db.commit()

    # ✨ [CCTV 추가] 공지 발송 타겟 기록
    target_str = "플랫폼 전체"
    if notice.target_type == "BRAND": target_str = f"브랜드(ID:{notice.target_brand_id}) 전체"
    elif notice.target_type == "STORE": target_str = f"매장(ID:{notice.target_store_id})"

    create_audit_log(
        db=db, user_id=current_user.id, action="SEND_NOTICE", target_type="NOTICE", target_id=new_notice.id,
        details=f"[{target_str}]에 공지 발송: '{notice.title}'"
    )
    
    return {"message": "발송 완료"}

# 2. 안 읽은 공지사항 불러오기 API (팝업용)
@app.get("/notices/unread")
def get_unread_notices(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    # 1단계: 현재 유저가 이미 "읽음(확인)" 처리한 공지사항 ID 목록
    read_notice_ids = [r.notice_id for r in db.query(models.NoticeRead).filter(models.NoticeRead.user_id == current_user.id).all()]

    # 2단계: 안 읽은 공지만 필터링
    filters = [models.Notice.is_active == True]
    if read_notice_ids:
        filters.append(models.Notice.id.notin_(read_notice_ids))

    # 3단계: 유저 권한/소속에 따른 타겟팅 필터링
    target_filters = [models.Notice.target_type == "ALL"]
    
    if current_user.brand_id: 
        target_filters.append(and_(models.Notice.target_type == "BRAND", models.Notice.target_brand_id == current_user.brand_id))
    
    if current_user.store_id: 
        # 특정 매장 타겟팅 포함
        target_filters.append(and_(models.Notice.target_type == "STORE", models.Notice.target_store_id == current_user.store_id))
        
        # ✨ [핵심 수정] 내 매장이 속한 '브랜드'의 공지도 포함하기!
        user_store = db.query(models.Store).filter(models.Store.id == current_user.store_id).first()
        if user_store and user_store.brand_id:
            target_filters.append(and_(models.Notice.target_type == "BRAND", models.Notice.target_brand_id == user_store.brand_id))

    # 4단계: 교집합 & 합집합 쿼리 실행
    notices = db.query(models.Notice).filter(and_(*filters), or_(*target_filters)).order_by(models.Notice.created_at.asc()).all()
    return notices

# 3. 공지사항 읽음 처리 API
@app.post("/notices/{notice_id}/read")
def mark_notice_read(notice_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    read_entry = models.NoticeRead(user_id=current_user.id, notice_id=notice_id)
    db.add(read_entry)
    db.commit()
    return {"message": "읽음 처리 완료"}


# 4. 공지사항 발송 내역 조회 API (본사 게시판용)
@app.get("/admin/notices/history")
def get_notice_history(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    if current_user.role == "SUPER_ADMIN":
        return db.query(models.Notice).order_by(models.Notice.created_at.desc()).all()
    elif current_user.role == "BRAND_ADMIN":
        return db.query(models.Notice).filter(
            or_(
                models.Notice.target_brand_id == current_user.brand_id,
                models.Notice.target_type == "BRAND" 
            )
        ).order_by(models.Notice.created_at.desc()).all()
    return []


# 5. [점주/직원용] 내 수신 공지함 전체 목록 API (읽음 여부 포함)
@app.get("/notices/my")
def get_my_notices(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    target_filters = [models.Notice.target_type == "ALL"]
    
    if current_user.brand_id:
        target_filters.append(and_(models.Notice.target_type == "BRAND", models.Notice.target_brand_id == current_user.brand_id))
    
    if current_user.store_id:
        # 특정 매장 타겟팅 포함
        target_filters.append(and_(models.Notice.target_type == "STORE", models.Notice.target_store_id == current_user.store_id))
        
        # ✨ [핵심 수정] 내 매장이 속한 '브랜드'의 공지도 포함하기!
        user_store = db.query(models.Store).filter(models.Store.id == current_user.store_id).first()
        if user_store and user_store.brand_id:
            target_filters.append(and_(models.Notice.target_type == "BRAND", models.Notice.target_brand_id == user_store.brand_id))
    
    notices = db.query(models.Notice).filter(or_(*target_filters)).order_by(models.Notice.created_at.desc()).all()
    
    read_notice_ids = {r.notice_id for r in db.query(models.NoticeRead).filter(models.NoticeRead.user_id == current_user.id).all()}
    
    result = []
    for n in notices:
        result.append({
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "created_at": n.created_at,
            "is_read": n.id in read_notice_ids
        })
    return result

# =========================================================
# 🕵️ 시스템 감사 로그 (Audit Log) API
# =========================================================

# 1. 블랙박스에 기록을 남기는 도우미 함수 (다른 API 안에서 사용됨)
def create_audit_log(db: Session, user_id: int, action: str, target_type: str, target_id: int, details: str):
    log = models.AuditLog(user_id=user_id, action=action, target_type=target_type, target_id=target_id, details=details)
    db.add(log)
    db.commit()

# 2. 본사에서 블랙박스 기록을 열어보는 API
@app.get("/admin/audit-logs")
def get_audit_logs(db: Session = Depends(get_db), current_user: models.User = Depends(dependencies.get_current_user)):
    query = db.query(models.AuditLog).join(models.User)
    
    # 브랜드 관리자는 자기 브랜드 직원/점주들이 한 행동만 볼 수 있음
    if current_user.role == "BRAND_ADMIN":
        query = query.filter(models.User.brand_id == current_user.brand_id)
    elif current_user.role != "SUPER_ADMIN":
        return [] # 권한 없으면 빈값 리턴
        
    # 최신순으로 100개까지만 가져오기
    logs = query.order_by(models.AuditLog.created_at.desc()).limit(100).all()
    
    return [
        {
            "id": log.id,
            "user_name": log.user.name if log.user else "삭제된 사용자",
            "user_email": log.user.email if log.user else "-",
            "action": log.action,
            "target_type": log.target_type,
            "details": log.details,
            "created_at": log.created_at
        } for log in logs
    ]