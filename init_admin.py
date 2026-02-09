# init_admin.py (최초 1회 실행용)
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models, auth

# DB 테이블이 없으면 생성
models.Base.metadata.create_all(bind=engine)

def create_super_admin():
    db: Session = SessionLocal()
    
    # 이미 존재하는지 확인
    existing_admin = db.query(models.User).filter(models.User.role == models.UserRole.SUPER_ADMIN).first()
    if existing_admin:
        print(f"✅ 이미 슈퍼 관리자가 존재합니다: {existing_admin.email}")
        return

    # 슈퍼 관리자 계정 생성
    print("🚀 슈퍼 관리자 계정을 생성합니다...")
    email = input("이메일 입력 (예: admin@HQ.com): ")
    password = input("비밀번호 입력: ")
    name = input("이름 입력 (예: 시스템관리자): ")

    hashed_pw = auth.get_password_hash(password)
    
    super_admin = models.User(
        email=email,
        hashed_password=hashed_pw,
        name=name,
        role=models.UserRole.SUPER_ADMIN, # 핵심: 슈퍼 관리자 권한 부여
        is_active=True
    )
    
    db.add(super_admin)
    db.commit()
    print(f"✨ [성공] 슈퍼 관리자({email})가 생성되었습니다! 이제 로그인하여 브랜드를 생성할 수 있습니다.")
    db.close()

if __name__ == "__main__":
    create_super_admin()