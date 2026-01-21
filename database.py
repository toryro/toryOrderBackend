from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Docker DB 접속 정보
SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/qrorder"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)