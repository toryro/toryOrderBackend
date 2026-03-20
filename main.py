from fastapi import FastAPI, Request, UploadFile, File, WebSocket, WebSocketDisconnect, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from jose import jwt
from dotenv import load_dotenv
import os, uuid, shutil

# 환경변수 로드
load_dotenv()

# DB 및 내부 모듈
from database import engine, SessionLocal
from connection_manager import manager
import models, crud
import auth  # 루트 디렉토리의 auth.py (JWT 설정용)

# ✨ 라우터들 임포트 (auth 라우터는 내부 모듈과 이름이 겹치지 않게 별칭 사용)
from routers import auth as auth_router, stores, menus, orders, tables, system

# DB 테이블 자동 생성
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ToryOrder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

os.makedirs("uploads", exist_ok=True)
app.mount("/images", StaticFiles(directory="uploads"), name="images")

# =========================================================
# 📸 파일 업로드 API
# =========================================================
@app.post("/upload/")
async def upload_image(request: Request, file: UploadFile = File(...)):
    filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = f"uploads/{filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"url": f"{str(request.base_url).rstrip('/')}/images/{filename}"}

# =========================================================
# 🔥 주방 현황판 실시간 웹소켓 (복구 완료!)
# =========================================================
@app.websocket("/ws/{store_id}")
async def websocket_endpoint(websocket: WebSocket, store_id: int, token: str = Query(None)):
    if token is None:
        print("❌ [웹소켓 거절] 토큰이 없습니다.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    try:
        # 토큰 해독 및 유효성 검사
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            print("❌ [웹소켓 거절] 토큰에 이메일 정보가 없습니다.")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except jwt.ExpiredSignatureError:
        print("❌ [웹소켓 거절] 로그인 토큰이 만료되었습니다. 재로그인이 필요합니다.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    except Exception as e:
        print(f"❌ [웹소켓 거절] 토큰 해독 실패: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    db = SessionLocal()
    try:
        user = crud.get_user_by_email(db, email=email)
        if not user:
            print("❌ [웹소켓 거절] DB에서 해당 유저를 찾을 수 없습니다.")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        has_permission = False
        if user.role == models.UserRole.SUPER_ADMIN: 
            has_permission = True
        elif user.role == models.UserRole.BRAND_ADMIN:
            store = db.query(models.Store).filter(models.Store.id == store_id).first()
            if store and store.brand_id == user.brand_id: 
                has_permission = True
        elif user.role in [models.UserRole.STORE_OWNER, models.UserRole.STAFF]:
            if user.store_id == store_id: 
                has_permission = True
                
        if not has_permission:
            print(f"❌ [웹소켓 거절] 권한 부족 (Role: {user.role}, UserStore: {user.store_id}, ReqStore: {store_id})")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    finally:
        db.close()

    # 모든 검증을 통과하면 웹소켓 연결을 승인합니다!
    await manager.connect(websocket, store_id)
    try:
        while True:
            # 클라이언트(주방)가 연결을 끊을 때까지 대기
            data = await websocket.receive_text()

            # ✨ [신규] 받은 데이터를 같은 매장의 다른 기기 화면들에 그대로 전달 (화면 동기화)
            await manager.broadcast(data, store_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, store_id)


# =========================================================
# 🚀 라우터 연결 (Include Routers)
# =========================================================
app.include_router(auth_router.router)
app.include_router(stores.router)
app.include_router(menus.router)
app.include_router(orders.router)
app.include_router(tables.router)
app.include_router(system.router)