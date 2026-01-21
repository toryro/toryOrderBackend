from fastapi import FastAPI
from database import engine
import models

# 서버 시작 시 테이블 자동 생성
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "QR Order Backend Running!"}