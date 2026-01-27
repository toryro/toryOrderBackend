# seed.py

from sqlalchemy.orm import Session
from sqlalchemy import text
from database import SessionLocal, engine
import models, auth

# DB 연결
db = SessionLocal()

def reset_and_seed_data():
    print("🔥 기존 데이터베이스를 초기화(삭제) 하는 중...")
    
    # 1. PostgreSQL 전용 강제 초기화 (CASCADE)
    try:
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE;"))
            conn.execute(text("CREATE SCHEMA public;"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public;")) 
            conn.commit()
        print("✅ 기존 테이블 강제 삭제 완료")
    except Exception as e:
        print(f"⚠️ 초기화 중 경고 (무시해도 됨): {e}")

    # 2. 새로운 모델 구조대로 테이블 다시 생성
    models.Base.metadata.create_all(bind=engine)
    print("✅ 신규 테이블 생성 완료")

    print("🌱 기초 데이터 심는 중...")

    try:
        # 3. 그룹 생성 (백종원 컴퍼니)
        group = models.Group(name="백종원컴퍼니")
        db.add(group)
        db.commit()
        db.refresh(group)
        print(f"✅ 그룹 생성: {group.name}")

        # 4. 가게 생성 (홍콩반점)
        store = models.Store(
            name="홍콩반점 강남점",
            group_id=group.id
        )
        db.add(store)
        db.commit()
        db.refresh(store)
        print(f"✅ 가게 생성: {store.name}")

        # 5. 슈퍼 관리자 생성 (admin)
        admin = models.User(
            email="admin@tory.com",
            hashed_password=auth.get_password_hash("admin1234"),
            role=models.UserRole.SUPER_ADMIN,
            is_active=True
        )
        db.add(admin)
        print(f"✅ 슈퍼 관리자 생성: admin@tory.com")

        # 6. 사장님 계정 생성 (owner)
        owner = models.User(
            email="owner@tory.com",
            hashed_password=auth.get_password_hash("1234"),
            role=models.UserRole.STORE_OWNER,
            store_id=store.id,
            is_active=True
        )
        db.add(owner)
        db.commit()
        print(f"✅ 사장님 생성: owner@tory.com")
        
        print("\n🎉 모든 준비가 끝났습니다!")
        print("👉 이제 서버를 켜고 접속해보세요!")

    except Exception as e:
        print(f"❌ 데이터 생성 중 에러 발생: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_and_seed_data()