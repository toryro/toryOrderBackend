from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os, uuid, shutil

load_dotenv()

from database import engine
import models

# ✨ 모든 라우터들을 임포트합니다.
from routers import auth, stores, menus, orders, tables, system

# DB 테이블 자동 생성 (알아서 체크해서 없는 테이블만 만듭니다)
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

# --- (기존의 파일 업로드, 웹소켓 등 메인에 둘 기능은 여기에 남겨둡니다) ---

# =========================================================
# 🚀 라우터 연결 (Include Routers)
# =========================================================
app.include_router(auth.router)
app.include_router(stores.router)
app.include_router(menus.router)
app.include_router(orders.router)
app.include_router(tables.router)
app.include_router(system.router)  # ✨ 마지막 시스템 라우터까지 연결 완료!