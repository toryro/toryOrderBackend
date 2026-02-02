# check_sales.py
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("--- 💰 매출 데이터 진단 ---")

# 1. 전체 주문 수 확인
total_orders = db.execute(text("SELECT COUNT(*) FROM orders")).scalar()
print(f"📦 전체 주문 수: {total_orders}건")

# 2. 완료된 주문 수 확인 (매출에 집계되는 주문)
completed_orders = db.execute(text("SELECT COUNT(*) FROM orders WHERE is_completed = true")).scalar()
print(f"✅ 완료된 주문 수: {completed_orders}건")

if completed_orders == 0:
    print("⚠️ [주의] 완료된 주문이 0건입니다! 주방 화면에서 '완료' 버튼을 눌렀는지 확인하세요.")
else:
    print("   -> 데이터는 있습니다. main.py에 API 코드를 추가하고 서버를 재시작해보세요.")

# 3. 최근 주문 시간 확인 (시간대 문제 체크)
print("\n⏰ 최근 주문 시간 (DB 저장 기준):")
recent_orders = db.execute(text("SELECT created_at, is_completed FROM orders ORDER BY id DESC LIMIT 5")).fetchall()
for row in recent_orders:
    status = "완료됨" if row[1] else "미완료"
    print(f"   - 시간: {row[0]} | 상태: {status}")

db.close()