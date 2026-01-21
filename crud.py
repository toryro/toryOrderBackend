from sqlalchemy.orm import Session
import models, schemas
import uuid

# 1. 매장 생성
def create_store(db: Session, store: schemas.StoreCreate):
    db_store = models.Store(name=store.name, owner_id=store.owner_id)
    db.add(db_store)
    db.commit()
    db.refresh(db_store)
    return db_store

def get_store(db: Session, store_id: int):
    return db.query(models.Store).filter(models.Store.id == store_id).first()

# 2. 카테고리 생성
def create_category(db: Session, category: schemas.CategoryCreate, store_id: int):
    db_category = models.Category(**category.dict(), store_id=store_id)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

# 3. 메뉴 생성
def create_menu(db: Session, menu: schemas.MenuCreate, category_id: int):
    db_menu = models.Menu(**menu.dict(), category_id=category_id)
    db.add(db_menu)
    db.commit()
    db.refresh(db_menu)
    return db_menu

# 4. 테이블 생성 (QR 토큰 자동 생성)
def create_table(db: Session, table: schemas.TableCreate, store_id: int):
    # UUID를 이용해 유추 불가능한 랜덤 토큰 생성
    random_token = str(uuid.uuid4())
    
    db_table = models.Table(
        label=table.label,
        store_id=store_id,
        qr_token=random_token
    )
    db.add(db_table)
    db.commit()
    db.refresh(db_table)
    return db_table

def get_table(db: Session, table_id: int):
    return db.query(models.Table).filter(models.Table.id == table_id).first()