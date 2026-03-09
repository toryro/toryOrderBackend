# seed.py

import uuid
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
    print("✅ 신규 테이블 생성 완료 (재고/레시피 제거 버전)")

    print("🌱 기초 데이터 심는 중...")

    try:
        # --- 1. [브랜드] 토리 컴퍼니 ---
        brand = models.Brand(name="토리컴퍼니")
        db.add(brand)
        db.commit()
        db.refresh(brand)
        print(f"👑 브랜드 생성: {brand.name}")

        # --- 2. [가게] 토리오더 강남본점 ---
        store = models.Store(
            name="토리오더 강남본점",
            brand_id=brand.id,
            description="가장 빠르고 스마트한 QR 주문 시스템, 토리오더!",
            address="서울시 강남구 테헤란로 123",
            phone="02-1234-5678",
            is_open=True
        )
        db.add(store)
        db.commit()
        db.refresh(store)
        print(f"🏪 매장 생성: {store.name}")

        # --- 3. [권한별 사용자 계정] ---
        users_data = [
            # 슈퍼 관리자
            models.User(email="super@tory.com", hashed_password=auth.get_password_hash("1234"), role=models.UserRole.SUPER_ADMIN, name="슈퍼관리자", is_active=True),
            # 브랜드 관리자
            models.User(email="brand@tory.com", hashed_password=auth.get_password_hash("1234"), role=models.UserRole.BRAND_ADMIN, name="브랜드관리자", brand_id=brand.id, is_active=True),
            # 매장 점주
            models.User(email="owner@tory.com", hashed_password=auth.get_password_hash("1234"), role=models.UserRole.STORE_OWNER, name="김사장", store_id=store.id, is_active=True),
            # 매장 직원
            models.User(email="staff@tory.com", hashed_password=auth.get_password_hash("1234"), role=models.UserRole.STAFF, name="박알바", store_id=store.id, is_active=True)
        ]
        db.bulk_save_objects(users_data)
        db.commit()
        print("👥 테스트용 계정 4개 생성 완료 (비밀번호는 모두 1234)")

        # --- 4. [카테고리 & 메뉴 & 옵션] 세팅 ---
        # 카테고리
        cat1 = models.Category(store_id=store.id, name="메인 요리", order_index=1)
        cat2 = models.Category(store_id=store.id, name="음료/주류", order_index=2)
        db.add_all([cat1, cat2])
        db.commit()

        # 옵션 그룹 (맵기 조절)
        opt_group = models.OptionGroup(store_id=store.id, name="맵기 조절", is_single_select=True, is_required=True)
        db.add(opt_group)
        db.commit()
        
        # 옵션 항목
        opt1 = models.Option(store_id=store.id, group_id=opt_group.id, name="순한맛", price=0, is_default=True)
        opt2 = models.Option(store_id=store.id, group_id=opt_group.id, name="매운맛", price=500, is_default=False)
        db.add_all([opt1, opt2])
        db.commit()

        # 메뉴
        menu1 = models.Menu(store_id=store.id, category_id=cat1.id, name="토리 시그니처 세트", price=15000, description="토리오더의 대표 메뉴입니다.")
        menu2 = models.Menu(store_id=store.id, category_id=cat2.id, name="시원한 생맥주", price=5000)
        db.add_all([menu1, menu2])
        db.commit()

        # 메뉴에 옵션 연결
        link = models.MenuOptionLink(menu_id=menu1.id, option_group_id=opt_group.id)
        db.add(link)
        db.commit()
        print("🍔 샘플 카테고리, 메뉴, 옵션 생성 완료")

        # --- 5. [테이블 & QR] ---
        table1 = models.Table(store_id=store.id, name="1번 테이블", qr_token=str(uuid.uuid4()))
        table2 = models.Table(store_id=store.id, name="2번 테이블", qr_token=str(uuid.uuid4()))
        db.add_all([table1, table2])
        db.commit()
        print("🪑 1번, 2번 테이블 생성 완료")

        # --- 6. [직원 호출 옵션] ---
        call_opts = [
            models.CallOption(store_id=store.id, name="물티슈 주세요"),
            models.CallOption(store_id=store.id, name="앞접시 주세요"),
            models.CallOption(store_id=store.id, name="물 좀 더 주세요")
        ]
        db.add_all(call_opts)
        db.commit()
        print("🔔 직원 호출 옵션 생성 완료")

        print("\n🎉 모든 기초 데이터 세팅이 완벽하게 끝났습니다! 🎉")
        print("--------------------------------------------------")
        print(" [로그인 계정 정보] (비밀번호: 1234)")
        print("  - 슈퍼 관리자: super@tory.com")
        print("  - 브랜드 관리: brand@tory.com")
        print("  - 사장님 계정: owner@tory.com")
        print("  - 알바생 계정: staff@tory.com")
        print("--------------------------------------------------")

    except Exception as e:
        db.rollback()
        print(f"\n❌ 에러 발생: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_and_seed_data()