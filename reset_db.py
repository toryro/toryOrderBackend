import sys
import time
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models
import auth

def print_divider():
    print("\n" + "="*60)

def reset_database():
    """단계 1: 기존 테이블 완전히 삭제 및 재생성"""
    print_divider()
    print("🗑️  [1/3] 데이터베이스 초기화를 시작합니다...")
    try:
        models.Base.metadata.drop_all(bind=engine)
        models.Base.metadata.create_all(bind=engine)
        print("✅ 데이터베이스 구조 생성 완료!")
    except Exception as e:
        print(f"❌ 초기화 오류: {e}")
        sys.exit(1)

def create_all_test_users(db: Session):
    """단계 2: 역할별 테스트 계정 일괄 생성"""
    print_divider()
    print("👤 [2/3] 테스트용 계정(역할별) 생성을 시작합니다.")
    
    users_to_create = [
        {"email": "admin@tory.com", "pw": "admin1234", "name": "최고관리자", "role": models.UserRole.SUPER_ADMIN},
        {"email": "brand@tory.com", "pw": "brand1234", "name": "브랜드장", "role": models.UserRole.BRAND_ADMIN},
        {"email": "owner@tory.com", "pw": "owner1234", "name": "김사장", "role": models.UserRole.STORE_OWNER},
        {"email": "staff@tory.com", "pw": "staff1234", "name": "이알바", "role": models.UserRole.STAFF},
    ]
    
    created_users = {}
    print("\n계정 생성 목록:")
    for u_info in users_to_create:
        hashed_pw = auth.get_password_hash(u_info["pw"])
        user = models.User(
            email=u_info["email"],
            hashed_password=hashed_pw,
            name=u_info["name"],
            role=u_info["role"],
            is_active=True
        )
        db.add(user)
        created_users[u_info["role"]] = user
        print(f" - {u_info['role']}: {u_info['email']} (비번: {u_info['pw']})")
    
    db.commit()
    print("\n✨ 모든 역할별 계정 생성 완료!")
    return created_users

def seed_initial_data(db: Session, users: dict):
    """단계 3: 기초 데이터 심기 및 계정 연결"""
    print_divider()
    print("🌱 [3/3] 테스트용 데이터(Seed) 및 계정 연결을 진행합니다.")
    
    try:
        # 1. 브랜드 생성 및 브랜드 관리자 연결
        brand = models.Brand(name="토리컴퍼니")
        db.add(brand)
        db.commit()
        db.refresh(brand)
        
        # 브랜드 관리자 계정에 brand_id 부여
        users[models.UserRole.BRAND_ADMIN].brand_id = brand.id
        print(f"👑 브랜드 생성: {brand.name} (관리자: {users[models.UserRole.BRAND_ADMIN].email})")

        # 2. 가게 생성 및 점주/직원 연결
        store = models.Store(
            name="토리오더 강남본점",
            brand_id=brand.id,
            owner_name="김사장",
            is_open=True,
            payment_policy="PRE_PAY", # 기본 선불 설정
            use_table_board=True
        )
        db.add(store)
        db.commit()
        db.refresh(store)
        
        # 점주와 직원 계정에 store_id 부여
        users[models.UserRole.STORE_OWNER].store_id = store.id
        users[models.UserRole.STAFF].store_id = store.id
        print(f"🏪 매장 생성: {store.name} (점주: {users[models.UserRole.STORE_OWNER].email})")

        # 3. 카테고리 및 메뉴 생성
        cat = models.Category(store_id=store.id, name="🔥 인기 메뉴", order_index=1)
        db.add(cat)
        db.commit()
        db.refresh(cat)

        menu = models.Menu(
            store_id=store.id,
            category_id=cat.id, 
            name="토리 시그니처 버거", 
            price=12000, 
            description="DateTime 필드 테스트용 메뉴",
            created_at=datetime.now() # 수정한 DateTime 필드 반영
        )
        db.add(menu)

        # 4. 테이블 생성 (현황판 테스트용)
        t1 = models.Table(store_id=store.id, name="1번 테이블", qr_token="test-token-1", current_status="EMPTY")
        t2 = models.Table(store_id=store.id, name="2번 테이블", qr_token="test-token-2", current_status="EMPTY")
        db.add_all([t1, t2])
        
        db.commit()
        print("🍔 샘플 메뉴 및 🪑 테이블 생성 완료")

    except Exception as e:
        print(f"❌ 데이터 시딩 실패: {e}")
        db.rollback()

def main():
    print_divider()
    print("🚀 Tory Order 통합 마스터 설정 (멀티 계정 버전)")
    print("⚠️  이 작업은 모든 데이터를 삭제하고 테스트 환경을 구축합니다.")
    print_divider()
    
    confirm = input("❗ 초기화 및 테스트 계정 생성을 진행하시겠습니까? (yes/no): ").lower()
    
    if confirm == 'yes':
        db = SessionLocal()
        try:
            reset_database()
            users = create_all_test_users(db)
            seed_initial_data(db, users)
            
            print_divider()
            print("🎊 초기 설정 및 테스트 계정 세팅 완료!")
            print("1. admin@tory.com (슈퍼관리자) -> 전체 관리")
            print("2. brand@tory.com (브랜드관리자) -> 본사 대시보드")
            print("3. owner@tory.com (점주) -> 매장 관리(AdminPage)")
            print("4. staff@tory.com (직원) -> 주방(KitchenPage) 바로 연결")
            print("\n로그인 후 바로 테스트를 시작하세요!")
            print_divider()
        finally:
            db.close()
    else:
        print("\n❌ 작업을 취소했습니다.")

if __name__ == "__main__":
    main()