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
        # --- 1. [그룹] 백종원 컴퍼니 ---
        group = models.Group(name="백종원컴퍼니")
        db.add(group)
        db.commit()
        db.refresh(group)
        print(f"🏢 그룹 생성: {group.name}")

        # --- 2. [가게] 홍콩반점 강남점 ---
        store = models.Store(
            name="홍콩반점 강남점",
            group_id=group.id,
            description="맛있는 짬뽕과 짜장면이 있는 곳!",
            address="서울시 강남구 역삼동 123-45",
            phone="02-555-1234"
        )
        db.add(store)
        db.commit()
        db.refresh(store)
        print(f"🏪 가게 생성: {store.name} (ID: {store.id})")

        # [영업시간 기본값]
        for i in range(7):
            db.add(models.OperatingHour(store_id=store.id, day_of_week=i, open_time="09:00", close_time="22:00"))
        db.commit()

        # --- 3. [계정] 계층별 사용자 생성 ---

        # (1) 슈퍼 관리자 (전체 총괄)
        super_admin = models.User(
            email="admin@tory.com",
            hashed_password=auth.get_password_hash("admin1234"),
            role=models.UserRole.SUPER_ADMIN,
            name="시스템관리자",
            phone="010-1111-1111",
            is_active=True
        )
        db.add(super_admin)

        # (2) 그룹 관리자 (본사 직원)
        group_admin = models.User(
            email="group@tory.com",
            hashed_password=auth.get_password_hash("1234"),
            role=models.UserRole.GROUP_ADMIN,
            name="백종원(본사)",
            phone="010-2222-2222",
            group_id=group.id,
            is_active=True
        )
        db.add(group_admin)

        # (3) 매장 점주 (사장님)
        store_owner = models.User(
            email="owner@tory.com",
            hashed_password=auth.get_password_hash("1234"),
            role=models.UserRole.STORE_OWNER,
            name="김사장",
            phone="010-3333-3333",
            store_id=store.id,
            group_id=group.id, # 점주도 그룹 소속일 수 있음
            is_active=True
        )
        db.add(store_owner)

        # (4) 매장 직원 (알바생)
        staff = models.User(
            email="staff@tory.com",
            hashed_password=auth.get_password_hash("1234"),
            role=models.UserRole.STAFF,
            name="이나은(알바)",
            phone="010-4444-4444",
            store_id=store.id,
            group_id=group.id,
            is_active=True
        )
        db.add(staff)
        
        db.commit()
        
        print("\n🎉 계정 생성 완료! 아래 정보로 로그인 테스트 해보세요.")
        print(f"1️⃣ 슈퍼 관리자: admin@tory.com / admin1234")
        print(f"2️⃣ 본사 관리자: group@tory.com / 1234")
        print(f"3️⃣ 매장 점주 : owner@tory.com / 1234")
        print(f"4️⃣ 매장 직원 : staff@tory.com / 1234")

    except Exception as e:
        print(f"❌ 데이터 생성 중 에러 발생: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_and_seed_data()