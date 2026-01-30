# crud.py (전체 덮어씌우기 또는 create_order 함수 교체)

from sqlalchemy.orm import Session
import models, schemas
import auth
from datetime import datetime

# ... (기존 유저, 그룹, 스토어 관련 함수들은 유지하되 create_store만 체크) ...

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        email=user.email, 
        hashed_password=hashed_password,
        role=user.role,
        store_id=user.store_id,
        group_id=user.group_id
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_group(db: Session, group: schemas.GroupCreate):
    db_group = models.Group(name=group.name)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

def get_groups(db: Session):
    return db.query(models.Group).all()

def create_store(db: Session, store: schemas.StoreCreate):
    # **store.dict()를 쓰면 open_time 같은 새 필드도 자동으로 들어갑니다.
    db_store = models.Store(**store.dict())
    db.add(db_store)
    db.commit()
    db.refresh(db_store)
    return db_store

def get_store(db: Session, store_id: int):
    return db.query(models.Store).filter(models.Store.id == store_id).first()

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

def create_option_group(db: Session, group: schemas.OptionGroupCreate, menu_id: int):
    db_group = models.OptionGroup(
        name=group.name,
        is_required=group.is_required,
        is_single_select=group.is_single_select,
        order_index=group.order_index,
        store_id=db.query(models.Menu).filter(models.Menu.id == menu_id).first().category.store_id
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    link = models.MenuOptionLink(menu_id=menu_id, option_group_id=db_group.id)
    db.add(link)
    db.commit()
    return db_group

def create_option(db: Session, option: schemas.OptionCreate, group_id: int):
    db_option = models.Option(**option.dict(), group_id=group_id)
    db.add(db_option)
    db.commit()
    db.refresh(db_option)
    return db_option

def create_table(db: Session, table: schemas.TableCreate, store_id: int):
    import uuid
    token = str(uuid.uuid4())
    db_table = models.Table(name=table.name, qr_token=token, store_id=store_id)
    db.add(db_table)
    db.commit()
    db.refresh(db_table)
    return db_table

def get_table(db: Session, table_id: int):
    return db.query(models.Table).filter(models.Table.id == table_id).first()

# [핵심] 주문 생성 (일일 번호 로직 포함)
def create_order(db: Session, order: schemas.OrderCreate):
    # 1. 일일 주문 번호 계산
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 오늘 날짜의 마지막 주문 조회
    last_order = db.query(models.Order).filter(
        models.Order.store_id == order.store_id,
        models.Order.created_at.like(f"{today_str}%")
    ).order_by(models.Order.daily_number.desc()).first()

    next_daily_number = (last_order.daily_number + 1) if last_order else 1

    # 2. 주문 생성
    db_order = models.Order(
        store_id=order.store_id,
        table_id=order.table_id,
        daily_number=next_daily_number, # 저장!
        total_price=0,
        is_completed=False
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    total_price = 0
    for item in order.items:
        menu = db.query(models.Menu).filter(models.Menu.id == item.menu_id).first()
        if not menu: continue
        item_price = menu.price
        options_summary = []
        for opt in item.options:
            item_price += opt.price
            options_summary.append(opt.name)
        
        line_total = item_price * item.quantity
        total_price += line_total

        db_item = models.OrderItem(
            order_id=db_order.id,
            menu_name=menu.name,
            price=item_price,
            quantity=item.quantity,
            options_desc=", ".join(options_summary) if options_summary else None
        )
        db.add(db_item)

    db_order.total_price = total_price
    db.commit()
    db.refresh(db_order)
    return db_order