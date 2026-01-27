# init_db.py

from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models, auth

# DB 테이블이 없으면 생성 (혹시 몰라 한 번 더 실행)
models.Base.metadata.create_all(bind=engine)

def init_db():
    db = SessionLocal()
    
    try:
        # 1. 이미 슈퍼 관리자가 있는지 확인
        # (models.UserRole.SUPER_ADMIN을 사용해 정확하게 찾습니다)
        existing_admin = db.query(models.User).filter(
            models.User.role == models.UserRole.SUPER_ADMIN
        ).first()
        
        if existing_admin:
            print(f"✅ 이미 슈퍼 관리자가 존재합니다: {existing_admin.email}")
            return

        # 2. 없다면, 새로 생성
        print("🔨 슈퍼 관리자 계정을 생성합니다...")
        
        # === [설정] 초기 슈퍼 관리자 정보 ===
        admin_email = "admin@tory.com"
        admin_password = "admin1234"  # 나중에 꼭 바꾸세요!
        # =================================
        
        hashed_pwd = auth.get_password_hash(admin_password)
        
        super_admin = models.User(
            email=admin_email,
            hashed_password=hashed_pwd,
            role=models.UserRole.SUPER_ADMIN, # ★ 핵심: 역할을 SUPER_ADMIN으로 지정
            is_active=True
        )
        
        db.add(super_admin)
        db.commit()
        db.refresh(super_admin)
        
        print(f"🎉 슈퍼 관리자 생성 완료!")
        print(f"👉 ID: {admin_email}")
        print(f"👉 PW: {admin_password}")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 시스템 초기화 시작...")
    init_db()