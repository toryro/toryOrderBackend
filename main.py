from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models, schemas, crud
import qrcode
from io import BytesIO
from fastapi.middleware.cors import CORSMiddleware

# DB 테이블 생성
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# 1. CORS 설정 추가 (매우 중요!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시에는 프론트엔드 도메인만 넣어야 함
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- [중요] get_db 함수는 API들보다 위에 있어야 합니다 ---
# DB 세션 의존성 주입 (요청 때 열고, 응답 후 닫음)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- [디버깅용] 1번 사장님 강제 생성 API ---
@app.post("/users/init/", tags=["Debug"])
def create_initial_user(db: Session = Depends(get_db)):
    # 1. 이미 유저가 있는지 확인
    existing_user = db.query(models.User).filter(models.User.id == 1).first()
    if existing_user:
        return {"message": "이미 1번 유저가 있습니다.", "user_id": existing_user.id}
    
    # 2. 없으면 생성
    new_user = models.User(
        id=1, # 강제로 1번 부여
        email="boss@kimbap.com",
        hashed_password="dummy_password",
        role="OWNER"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"message": "1번 사장님 유저 생성 완료!", "user_id": new_user.id}

# 2. [추가] QR 토큰으로 매장/테이블 정보 찾기 API
# 프론트엔드가 이 주소를 제일 먼저 호출합니다.
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

# --- 1. 매장(Store) 관련 API ---

@app.post("/stores/", response_model=schemas.StoreResponse)
def create_store(store: schemas.StoreCreate, db: Session = Depends(get_db)):
    # 1번 유저(사장님)가 반드시 존재해야 함 (위의 /users/init/ 먼저 실행 필수)
    return crud.create_store(db=db, store=store)

@app.get("/stores/{store_id}", response_model=schemas.StoreResponse)
def read_store(store_id: int, db: Session = Depends(get_db)):
    db_store = crud.get_store(db, store_id=store_id)
    if db_store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return db_store

# --- 2. 카테고리 & 메뉴 등록 API ---

@app.post("/stores/{store_id}/categories/", response_model=schemas.CategoryResponse)
def create_category(store_id: int, category: schemas.CategoryCreate, db: Session = Depends(get_db)):
    return crud.create_category(db=db, category=category, store_id=store_id)

@app.post("/categories/{category_id}/menus/", response_model=schemas.MenuResponse)
def create_menu(category_id: int, menu: schemas.MenuCreate, db: Session = Depends(get_db)):
    return crud.create_menu(db=db, menu=menu, category_id=category_id)

# --- 3. 테이블 생성 및 QR 코드 이미지 출력 API ---

@app.post("/stores/{store_id}/tables/", response_model=schemas.TableResponse)
def create_table(store_id: int, table: schemas.TableCreate, db: Session = Depends(get_db)):
    return crud.create_table(db=db, table=table, store_id=store_id)

@app.get("/tables/{table_id}/qrcode")
def get_qr_code(table_id: int, db: Session = Depends(get_db)):
    # 1. 테이블 정보 조회
    table = crud.get_table(db, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    # 2. QR 코드에 담길 URL 생성
    qr_data = f"http://localhost:3000/order/{table.qr_token}"
    
    # 3. QR 이미지 생성
    img = qrcode.make(qr_data)
    buf = BytesIO()
    
    # [수정됨] format="PNG" 에러 해결 -> 그냥 "PNG"로 전달
    img.save(buf, "PNG") 
    buf.seek(0)
    
    # 4. 이미지 파일로 응답
    return Response(content=buf.getvalue(), media_type="image/png")