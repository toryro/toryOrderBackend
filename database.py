# database.py

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# 1. .env 파일 로드 (환경변수 읽기)
load_dotenv()

# 2. 환경변수에서 DB 주소 가져오기
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("DATABASE_URL 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")

# 3. 엔진 생성 (PostgreSQL용)
# SQLite와 달리 check_same_thread 옵션은 필요 없습니다.
# pool_size: 동시에 처리할 수 있는 연결 수 (상용 트래픽 대비)
# max_overflow: 풀이 꽉 찼을 때 추가로 허용할 연결 수
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,
    max_overflow=10
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()