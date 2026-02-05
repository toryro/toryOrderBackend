# reset_db.py
from database import engine
from models import Base

print("🗑️ 기존 테이블 삭제 중...")
Base.metadata.drop_all(bind=engine) # 모든 테이블 삭제

print("✨ 새 테이블 생성 중...")
Base.metadata.create_all(bind=engine) # 변경된 models.py 내용으로 다시 생성

print("✅ DB 초기화 완료!")