# seed.py (초기 데이터 주입용)

from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models, auth

# DB 연결
db = SessionLocal()

def seed_data():
    print("🌱 데이터 심는 중...")

    try:
        # 1. 그룹 생성 (백종원 컴퍼니)
        group = models.Group(name="백종원컴퍼니")
        db.add(group)
        db.commit()
        db.refresh(group)
        print(f"✅ 그룹 생성: {group.name} (ID: {group.id})")

        # 2. 가게 생성 (홍콩반점)
        store = models.Store(
            name="홍콩반점 강남점",
            group_id=group.id
        )
        db.add(store)
        db.commit()
        db.refresh(store)
        print(f"✅ 가게 생성: {store.name} (ID: {store.id})")

        # 3. 사장님 계정 생성
        owner_email = "owner@tory.com"
        owner_password = "1234"
        
        # 이미 있으면 삭제하고 다시 만듦 (테스트 편의상)
        existing_user = db.query(models.User).filter(models.User.email == owner_email).first()
        if existing_user:
            db.delete(existing_user)
            db.commit()

        owner = models.User(
            email=owner_email,
            hashed_password=auth.get_password_hash(owner_password),
            role=models.UserRole.STORE_OWNER, # 역할: 사장님
            store_id=store.id,                # 소속: 위에서 만든 가게
            group_id=None,
            is_active=True
        )
        db.add(owner)
        db.commit()
        print(f"✅ 사장님 생성: {owner_email} (PW: {owner_password})")
        
        print("\n🎉 모든 준비가 끝났습니다!")
        print(f"👉 웹에서 로그인해보세요: ID: {owner_email} / PW: {owner_password}")

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()