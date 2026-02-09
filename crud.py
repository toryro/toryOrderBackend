from sqlalchemy.orm import Session
from models import Order, OrderItem
import models, schemas, auth
from datetime import datetime, timedelta

# =========================================================
# 👤 사용자(User) 관리
# =========================================================
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        email=user.email, 
        hashed_password=hashed_password,
        role=user.role,
        name=user.name,
        phone=user.phone,
        store_id=user.store_id,
        group_id=user.group_id,
        brand_id=user.brand_id # [중요] 브랜드 ID 저장
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user: return None
    
    if user_update.password: db_user.hashed_password = auth.get_password_hash(user_update.password)
    if user_update.name is not None: db_user.name = user_update.name
    if user_update.phone is not None: db_user.phone = user_update.phone
    if user_update.is_active is not None: db_user.is_active = user_update.is_active
    if user_update.role is not None: db_user.role = user_update.role
    
    db.commit()
    db.refresh(db_user)
    return db_user

# =========================================================
# 🏢 그룹 및 매장(Store) 관리
# =========================================================
def create_group(db: Session, group: schemas.GroupCreate):
    brand_id = getattr(group, "brand_id", None)
    db_group = models.Group(name=group.name, brand_id=brand_id)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

def get_groups(db: Session):
    return db.query(models.Group).all()

def get_store(db: Session, store_id: int):
    return db.query(models.Store).filter(models.Store.id == store_id).first()

# 🔥 [수정됨] 매장 생성 함수 (에러 해결 핵심)
def create_store(db: Session, store: schemas.StoreCreate):
    # 1. 스키마 데이터를 딕셔너리로 변환
    store_data = store.dict()
    
    # 2. Store 모델에 없는 필드 제거 (open_time, close_time 분리)
    open_time = store_data.pop("open_time", "09:00")
    close_time = store_data.pop("close_time", "22:00") 
    
    # 3. 정제된 데이터로 Store 생성
    db_store = models.Store(**store_data)
    db.add(db_store)
    db.commit()
    db.refresh(db_store)

    # 4. [자동 생성] 요일별 영업시간 기본값 (월~일) 세팅
    default_hours = []
    for day in range(7):
        hour = models.OperatingHour(
            store_id=db_store.id,
            day_of_week=day,
            open_time=open_time,
            close_time=close_time,
            is_closed=False
        )
        default_hours.append(hour)
    
    db.add_all(default_hours)
    db.commit()
    return db_store

# =========================================================
# 🍽️ 메뉴 및 카테고리 관리
# =========================================================
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
    menu = db.query(models.Menu).filter(models.Menu.id == menu_id).first()
    store_id = menu.category.store_id
    
    db_group = models.OptionGroup(
        name=group.name,
        is_required=group.is_required,
        is_single_select=group.is_single_select,
        max_select=group.max_select, 
        order_index=group.order_index,
        store_id=store_id
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    
    link = models.MenuOptionLink(menu_id=menu_id, option_group_id=db_group.id, order_index=0)
    db.add(link)
    db.commit()
    return db_group

def create_option(db: Session, option: schemas.OptionCreate, group_id: int):
    db_option = models.Option(**option.dict(), group_id=group_id)
    db.add(db_option)
    db.commit()
    db.refresh(db_option)
    return db_option

# =========================================================
# 🪑 테이블 및 주문 관리
# =========================================================
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

def create_order(db: Session, order: schemas.OrderCreate):
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    weekday = now.weekday()

    op_hour = db.query(models.OperatingHour).filter(
        models.OperatingHour.store_id == order.store_id,
        models.OperatingHour.day_of_week == weekday
    ).first()

    open_time_str = op_hour.open_time if (op_hour and op_hour.open_time) else "09:00"
    today_open_dt = datetime.strptime(f"{today_str} {open_time_str}:00", "%Y-%m-%d %H:%M:%S")

    if now < today_open_dt:
        end_dt = today_open_dt
        start_dt = end_dt - timedelta(days=1)
    else:
        start_dt = today_open_dt
        end_dt = start_dt + timedelta(days=1)

    last_order = db.query(models.Order).filter(
        models.Order.store_id == order.store_id,
        models.Order.created_at >= str(start_dt),
        models.Order.created_at < str(end_dt)
    ).order_by(models.Order.daily_number.desc()).first()

    next_daily_number = (last_order.daily_number + 1) if last_order else 1

    db_order = models.Order(
        store_id=order.store_id,
        table_id=order.table_id,
        daily_number=next_daily_number,
        total_price=0,
        is_completed=False,
        created_at=now 
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    total_price = 0
    for item in order.items:
        menu = db.query(models.Menu).filter(models.Menu.id == item.menu_id).first()
        if not menu: continue
        
        current_item_price = menu.price
        for opt in item.options:
            current_item_price += opt.price
        
        total_price += current_item_price * item.quantity

        db_item = models.OrderItem(
            order_id=db_order.id,
            menu_name=menu.name,
            price=current_item_price,
            quantity=item.quantity,
            options_desc=item.options_desc 
        )
        db.add(db_item)

    db_order.total_price = total_price
    db.commit()
    db.refresh(db_order)
    return db_order