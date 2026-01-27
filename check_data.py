# check_data.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models

# 환경 변수 로드
load_dotenv()
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("--- 🔍 DB 데이터 점검 ---")

# 1. 가게 목록 확인
print("\n[🏪 가게 목록]")
stores = db.query(models.Store).all()
if not stores:
    print("❌ 등록된 가게가 하나도 없습니다! (이게 원인입니다)")
else:
    for s in stores:
        print(f"👉 ID: {s.id} | 이름: {s.name} | 그룹ID: {s.group_id}")

# 2. 유저 목록 확인
print("\n[👤 유저 목록]")
users = db.query(models.User).all()
for u in users:
    role_str = f"Role: {u.role.value}" if hasattr(u.role, 'value') else f"Role: {u.role}"
    print(f"👉 ID: {u.id} | 이메일: {u.email} | {role_str} | 담당 가게ID: {u.store_id}")

db.close()