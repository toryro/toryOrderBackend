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
        # 3. 그룹 생성
        group = models.Group(name="백종원컴퍼니")
        db.add(group)
        db.commit()
        db.refresh(group)

        # 4. 가게 생성
        store = models.Store(
            name="홍콩반점 강남점",
            address="서울시 강남구 역삼동 123-45",
            phone="02-555-1234",
            description="맛있는 짬뽕과 짜장면이 있는 곳!",
            group_id=group.id
        )
        db.add(store)
        db.commit()
        db.refresh(store)
        print(f"✅ 가게 생성 완료! [ID: {store.id}] 이름: {store.name}")

        # [신규] 영업시간 기본값 생성 (월~일)
        for i in range(7):
            hour = models.OperatingHour(
                store_id=store.id,
                day_of_week=i,
                open_time="09:00",
                close_time="21:00",
                is_closed=False
            )
            db.add(hour)
        db.commit()
        print("✅ 영업시간 데이터 생성 완료")

        # 5. 관리자 생성
        admin = models.User(
            email="admin@tory.com",
            hashed_password=auth.get_password_hash("admin1234"),
            role=models.UserRole.SUPER_ADMIN,
            is_active=True
        )
        db.add(admin)

        # 6. 사장님 생성
        owner = models.User(
            email="owner@tory.com",
            hashed_password=auth.get_password_hash("1234"),
            role=models.UserRole.STORE_OWNER,
            store_id=store.id,
            is_active=True
        )
        db.add(owner)
        db.commit()
        print(f"✅ 사장님 생성: owner@tory.com (비번: 1234)")
        
        print("\n🎉 준비 완료! 아래 정보를 꼭 확인하세요.")
        print(f"👉 관리자 페이지 주소: http://localhost:5173/admin/{store.id}")

    except Exception as e:
        print(f"❌ 데이터 생성 중 에러 발생: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_and_seed_data()