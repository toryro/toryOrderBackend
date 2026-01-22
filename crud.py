from sqlalchemy.orm import Session
import models, schemas
import uuid

# --- [추가됨] 사용자 (User) ---
def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    # 실제 서비스에선 비밀번호를 암호화(Hash)해야 하지만, 실습용이라 그냥 저장합니다.
    fake_hashed_password = user.password + "notreallyhashed"
    db_user = models.User(email=user.email, hashed_password=fake_hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# --- 매장 ---
def create_store(db: Session, store: schemas.StoreCreate):
    db_store = models.Store(name=store.name, owner_id=store.owner_id)
    db.add(db_store)
    db.commit()
    db.refresh(db_store)
    return db_store

def get_store(db: Session, store_id: int):
    return db.query(models.Store).filter(models.Store.id == store_id).first()

# --- 카테고리 & 메뉴 ---
def create_category(db: Session, category: schemas.CategoryCreate, store_id: int):
    db_category = models.Category(**category.dict(), store_id=store_id)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def create_menu(db: Session, menu: schemas.MenuCreate, category_id: int):
    db_menu = models.Menu(**menu.dict(), category_id=category_id)
    db.add(db_menu)
    db.commit()
    db.refresh(db_menu)
    return db_menu

# --- 테이블 ---
def create_table(db: Session, table: schemas.TableCreate, store_id: int):
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

# --- 주문 생성 로직 ---
def create_order(db: Session, order: schemas.OrderCreate):
    total_price = 0
    db_order_items = []
    
    # 1. 가격 계산 및 아이템 준비
    for item in order.items:
        menu = db.query(models.Menu).filter(models.Menu.id == item.menu_id).first()
        if not menu:
            continue
            
        item_price = menu.price * item.quantity
        total_price += item_price
        
        db_order_item = models.OrderItem(
            #menu_id=menu.id,
            menu_name=menu.name,
            price=menu.price,
            quantity=item.quantity,
            options_json=item.options
        )
        db_order_items.append(db_order_item)
    
    # 2. 주문서(Master) 저장
    db_order = models.Order(
        store_id=order.store_id,
        table_id=order.table_id,
        total_price=total_price,
        status="PENDING"
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    # 3. 상세 품목(Items) 저장
    for db_item in db_order_items:
        db_item.order_id = db_order.id
        db.add(db_item)
        
    db.commit()
    
    return db_order