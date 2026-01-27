# doctor.py (로그인 문제 진단)

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models, auth

# 1. 환경변수 확인
load_dotenv()
db_url = os.getenv("DATABASE_URL")
print(f"📋 [진단 1] DB 주소 확인: {db_url}")

if not db_url:
    print("❌ [치명적 오류] .env 파일을 못 찾거나 DATABASE_URL이 없습니다.")
    exit()

# 2. DB 연결 시도
try:
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    print("✅ [진단 2] DB 연결 성공!")
except Exception as e:
    print(f"❌ [치명적 오류] DB 연결 실패: {e}")
    exit()

# 3. 관리자 계정 찾기
email = "admin@tory.com"
user = db.query(models.User).filter(models.User.email == email).first()

if not user:
    print(f"❌ [원인 발견] DB에 '{email}' 계정이 없습니다!")
    print("   👉 해결책: python init_db.py 를 다시 실행해서 계정을 만들어주세요.")
else:
    print(f"✅ [진단 3] 계정 발견! (ID: {user.id}, Role: {user.role})")

    # 4. 비밀번호 검증
    password = "admin1234"
    if auth.verify_password(password, user.hashed_password):
        print("✅ [진단 4] 비밀번호 검증 통과! (비밀번호는 맞음)")
        print("🎉 결론: 백엔드 데이터는 완벽합니다.")
        print("   👉 문제 추정: 서버를 껐다 켜보시거나, 프론트엔드에서 오타가 없는지 확인하세요.")
    else:
        print("❌ [원인 발견] 비밀번호가 틀립니다!")
        print("   👉 해결책: DB를 초기화하거나 비밀번호를 재설정해야 합니다.")

db.close()