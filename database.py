from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Docker DB 접속 정보
SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/qrorder"

# 데이터베이스 엔진 생성
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 세션 생성기 (DB 문을 열고 닫는 역할)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 모델들이 상속받을 기본 클래스
Base = declarative_base()

# [핵심] main.py가 찾던 그 함수!
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()