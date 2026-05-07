from fastapi import FastAPI, Request, UploadFile, File, WebSocket, WebSocketDisconnect, Query, status, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from jose import jwt
from dotenv import load_dotenv
import os, uuid, shutil, asyncio, json

# 환경변수 로드
load_dotenv()

# =========================================================
# 🔭 Sentry 에러 모니터링
# =========================================================
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

def _sentry_before_send(event, hint):
    """401·403·404는 정상적인 인증/탐색 실패이므로 Sentry에 전송하지 않음."""
    exc_info = hint.get("exc_info")
    if exc_info:
        exc_value = exc_info[1]
        if hasattr(exc_value, "status_code") and exc_value.status_code in (401, 403, 404):
            return None
    return event

_sentry_dsn = os.getenv("SENTRY_DSN")
if _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),             # 슬로우 쿼리·DB 에러 추적
        ],
        traces_sample_rate=0.1,                  # 요청의 10%만 성능 트레이싱 (부하 최소화)
        environment=os.getenv("ENVIRONMENT", "development"),
        before_send=_sentry_before_send,
        send_default_pii=False,                  # 개인정보 자동 수집 비활성화
    )
# =========================================================

# DB 및 내부 모듈
from database import engine, SessionLocal
from connection_manager import manager
import models, crud
import auth  # 루트 디렉토리의 auth.py (JWT 설정용)
import dependencies

# ✨ 라우터들 임포트 (auth 라우터는 내부 모듈과 이름이 겹치지 않게 별칭 사용)
from routers import auth as auth_router, stores, menus, orders, tables, system, printer as printer_router

# DB 테이블 자동 생성
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ToryOrder API")

async def _heartbeat_loop():
    while True:
        await asyncio.sleep(30)
        await manager.ping_all()

@app.on_event("startup")
async def start_heartbeat():
    asyncio.create_task(_heartbeat_loop())

_cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
app.mount("/images", StaticFiles(directory="uploads"), name="images")

# =========================================================
# 📸 파일 업로드 API
# =========================================================
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

@app.post("/upload/")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다. (JPEG, PNG, WebP, GIF)")

    contents = await file.read()
    if len(contents) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="파일 크기는 5MB 이하여야 합니다.")

    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "jpg"
    filename = f"{uuid.uuid4()}.{ext}"
    with open(f"uploads/{filename}", "wb") as buffer:
        buffer.write(contents)

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
            data = await websocket.receive_text()
            parsed = json.loads(data)
            if parsed.get("type") == "SYNC_DISPLAY":
                manager.save_snapshot(store_id, parsed.get("displayOrders", []))
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
app.include_router(printer_router.router)

# =========================================================
# React SPA 서빙 (반드시 모든 라우터 등록 후 마지막에)
# =========================================================
from starlette.staticfiles import StaticFiles as _StarletteStaticFiles
from fastapi.responses import FileResponse as _FileResponse
from starlette.exceptions import HTTPException as _StarletteHTTPException

_SPA_DIR = os.getenv("SPA_DIR", "../frontend/dist")

if os.path.isdir(_SPA_DIR):
    class _SPAFiles(_StarletteStaticFiles):
        async def get_response(self, path, scope):
            try:
                response = await super().get_response(path, scope)
            except _StarletteHTTPException as e:
                if e.status_code == 404:
                    response = await super().get_response("index.html", scope)
                else:
                    raise
            # index.html은 항상 최신 버전을 내려받도록 캐시 방지
            if getattr(response, "headers", None) is not None:
                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type:
                    response.headers["cache-control"] = "no-cache, no-store, must-revalidate"
                    response.headers["pragma"] = "no-cache"
                    response.headers["expires"] = "0"
            return response

    app.mount("/", _SPAFiles(directory=_SPA_DIR, html=True), name="spa")