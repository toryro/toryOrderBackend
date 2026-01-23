from sqlalchemy.orm import Session
import models, schemas, auth
import uuid
from datetime import datetime

# --- 유저(User) 관련 ---
def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# --- 가게(Store) 관련 ---
def create_store(db: Session, store: schemas.StoreCreate):
    db_store = models.Store(
        name=store.name,
        group_id=store.group_id # [추가됨]
    )
    db.add(db_store)
    db.commit()
    db.refresh(db_store)
    return db_store

# [신규] 그룹 생성 함수
def create_group(db: Session, group: schemas.GroupCreate):
    db_group = models.Group(name=group.name)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

# [신규] 그룹 목록 조회 (슈퍼 관리자용)
def get_groups(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Group).offset(skip).limit(limit).all()

def get_store(db: Session, store_id: int):
    return db.query(models.Store).filter(models.Store.id == store_id).first()

# --- 테이블(Table) 관련 ---
def create_table(db: Session, table: schemas.TableCreate, store_id: int):
    random_token = str(uuid.uuid4())
    db_table = models.Table(
        name=table.name, 
        store_id=store_id,
        qr_token=random_token
    )
    db.add(db_table)
    db.commit()
    db.refresh(db_table)
    return db_table

def get_table(db: Session, table_id: int):
    return db.query(models.Table).filter(models.Table.id == table_id).first()

def get_table_by_token(db: Session, token: str):
    return db.query(models.Table).filter(models.Table.qr_token == token).first()

# --- 카테고리 & 메뉴 & 옵션 관련 ---
def create_category(db: Session, category: schemas.CategoryCreate, store_id: int):
    db_category = models.Category(name=category.name, store_id=store_id)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def create_menu(db: Session, menu: schemas.MenuCreate, category_id: int):
    db_menu = models.Menu(
        **menu.dict(), 
        category_id=category_id
    )
    db.add(db_menu)
    db.commit()
    db.refresh(db_menu)
    return db_menu

# [신규] 옵션 그룹 생성 (예: 맵기 조절)
def create_option_group(db: Session, group: schemas.OptionGroupCreate, menu_id: int):
    db_group = models.OptionGroup(
        **group.dict(),
        menu_id=menu_id
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

# [신규] 옵션 항목 생성 (예: 매운맛 +500원)
def create_option(db: Session, option: schemas.OptionCreate, group_id: int):
    db_option = models.Option(
        **option.dict(),
        group_id=group_id
    )
    db.add(db_option)
    db.commit()
    db.refresh(db_option)
    return db_option

# --- 주문 관련 (여기가 핵심!) ---
def create_order(db: Session, order: schemas.OrderCreate):
    # 1. 빈 주문서 먼저 만들기
    db_order = models.Order(
        store_id=order.store_id,
        table_id=order.table_id,
        total_price=0, 
        created_at=str(datetime.now()),
        is_completed=False
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    total_order_price = 0

    # 2. 주문 아이템 하나씩 처리
    for item in order.items:
        menu = db.query(models.Menu).filter(models.Menu.id == item.menu_id).first()
        if not menu:
            continue
            
        # 기본 가격
        item_price = menu.price
        
        # 옵션 가격 더하기 & 옵션 설명글 만들기 (예: "매운맛(+500), 치즈(+500)")
        options_desc_list = []
        
        for opt in item.options:
            item_price += opt.price # 옵션 가격 합산
            
            # 설명글 추가
            if opt.price > 0:
                options_desc_list.append(f"{opt.name}(+{opt.price}원)")
            else:
                options_desc_list.append(f"{opt.name}")
        
        # 최종 아이템 가격 (단가 * 수량)
        final_item_price = item_price * item.quantity
        total_order_price += final_item_price

        # 옵션 설명을 문자열로 합치기
        options_desc_str = ", ".join(options_desc_list) if options_desc_list else None

        # 주문 상세 저장
        db_item = models.OrderItem(
            order_id=db_order.id,
            menu_name=menu.name,
            price=item_price, # 옵션 포함된 단가
            quantity=item.quantity,
            options_desc=options_desc_str # [추가] 옵션 내역 저장
        )
        db.add(db_item)
    
    # 3. 총 주문 금액 업데이트
    db_order.total_price = total_order_price
    db.commit()
    db.refresh(db_order)
    return db_order