import sys
import time
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models
import auth

def print_divider():
    print("\n" + "="*50)

def reset_database():
    """1. 기존 테이블을 삭제하고 새로 생성합니다."""
    print_divider()
    print("🗑️  [1/3] 데이터베이스 초기화를 시작합니다...")
    time.sleep(1)
    
    try:
        print("💡 기존 테이블 삭제 중...")
        models.Base.metadata.drop_all(bind=engine)
        
        print("✨ 새 테이블 생성 중 (models.py 기준)...")
        models.Base.metadata.create_all(bind=engine)
        
        print("✅ 데이터베이스 구조 재설계 완료!")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        sys.exit(1)

def create_super_admin():
    """2. 슈퍼 관리자 계정을 생성합니다."""
    print_divider()
    print("👤 [2/3] 슈퍼 관리자(Super Admin) 설정을 시작합니다.")
    
    db: Session = SessionLocal()
    try:
        print("\n--- 관리자 정보 입력 ---")
        email = input("📧 관리자 이메일 (기본: admin@tory.com): ").strip() or "admin@tory.com"
        password = input("🔑 관리자 비밀번호 (기본: admin1234): ").strip() or "admin1234"
        name = input("📛 관리자 이름 (기본: ToryAdmin): ").strip() or "ToryAdmin"

        hashed_pw = auth.get_password_hash(password)
        
        super_admin = models.User(
            email=email,
            hashed_password=hashed_pw,
            name=name,
            role=models.UserRole.SUPER_ADMIN,
            is_active=True
        )
        
        db.add(super_admin)
        db.commit()
        print(f"\n✨ [성공] 슈퍼 관리자 계정이 생성되었습니다!")
        print(f"👉 아이디: {email}")
        print(f"👉 비번: {password}")
    except Exception as e:
        print(f"❌ 계정 생성 중 오류 발생: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    print_divider()
    print("🚀  Tory Order DB 통합 관리 시스템")
    print("⚠️  경고: 이 작업은 모든 기존 데이터를 영구적으로 삭제합니다.")
    print_divider()
    
    confirm = input("❗ 정말로 초기화하시겠습니까? (yes/no): ").lower()
    
    if confirm == 'yes':
        start_time = time.time()
        
        reset_database()
        create_super_admin()
        
        end_time = time.time()
        print_divider()
        print(f"🎊 모든 작업이 완료되었습니다! (소요시간: {end_time - start_time:.2f}초)")
        print("이제 'uvicorn main:app --reload'로 서버를 실행하세요.")
        print_divider()
    else:
        print("\n❌ 작업을 취소했습니다. 데이터가 유지됩니다.")

if __name__ == "__main__":
    main()