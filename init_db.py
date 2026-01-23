from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models, schemas, crud

models.Base.metadata.create_all(bind=engine)

def init_data():
    db = SessionLocal()
    
    try:
        print("🔄 데이터 초기화 시작...")

        # 1. 사장님 생성
        user_email = "admin@tory.com"
        if not crud.get_user_by_email(db, user_email):
            crud.create_user(db, schemas.UserCreate(email=user_email, password="password123"))
            print("✅ 유저 생성 완료")

        # 2. 가게 생성
        store_name = "김밥천국 강남본점"
        store = db.query(models.Store).filter(models.Store.name == store_name).first()
        if not store:
            store = crud.create_store(db, schemas.StoreCreate(name=store_name))
            print("✅ 가게 생성 완료")

        # 3. 카테고리 & 메뉴 & 옵션 생성
        
        # [카테고리: 분식류]
        cat_snack = db.query(models.Category).filter(models.Category.name=="분식류", models.Category.store_id==store.id).first()
        if not cat_snack:
            cat_snack = crud.create_category(db, schemas.CategoryCreate(name="분식류"), store.id)

        # [메뉴: 라면]
        ramen = db.query(models.Menu).filter(models.Menu.name=="라면", models.Menu.category_id==cat_snack.id).first()
        if not ramen:
            ramen = crud.create_menu(db, schemas.MenuCreate(name="라면", price=4000, description="계란 탁 파 송송"), cat_snack.id)
            print("  🍜 라면 메뉴 생성")

            # [옵션그룹 1: 맵기 조절 (필수)]
            spicy_group = crud.create_option_group(db, schemas.OptionGroupCreate(name="맵기 조절", is_required=True), ramen.id)
            crud.create_option(db, schemas.OptionCreate(name="순한맛", price=0), spicy_group.id)
            crud.create_option(db, schemas.OptionCreate(name="중간맛", price=0), spicy_group.id)
            crud.create_option(db, schemas.OptionCreate(name="매운맛", price=500), spicy_group.id)
            print("    └ 맵기 옵션 추가 완료")

            # [옵션그룹 2: 토핑 추가 (선택)]
            topping_group = crud.create_option_group(db, schemas.OptionGroupCreate(name="토핑 추가", is_required=False), ramen.id)
            crud.create_option(db, schemas.OptionCreate(name="치즈", price=500), topping_group.id)
            crud.create_option(db, schemas.OptionCreate(name="계란", price=500), topping_group.id)
            crud.create_option(db, schemas.OptionCreate(name="떡", price=1000), topping_group.id)
            print("    └ 토핑 옵션 추가 완료")

        # [메뉴: 김밥]
        kimbap = db.query(models.Menu).filter(models.Menu.name=="원조 김밥", models.Menu.category_id==cat_snack.id).first()
        if not kimbap:
            kimbap = crud.create_menu(db, schemas.MenuCreate(name="원조 김밥", price=3500, description="참기름 냄새 솔솔"), cat_snack.id)
            print("  🍙 김밥 메뉴 생성")

        # 4. 테이블 생성
        for i in range(1, 4):
            table_name = f"{i}번 테이블"
            if not db.query(models.Table).filter(models.Table.name==table_name).first():
                crud.create_table(db, schemas.TableCreate(name=table_name), store.id)

        print("\n🎉 [옵션 포함] 모든 데이터 준비 완료!")
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_data()