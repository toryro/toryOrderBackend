from sqlalchemy.orm import Session
import models, schemas
import auth

# --- 유저 관련 ---
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = auth.get_password_hash(user.password)
    # role, store_id, group_id 등 모든 필드를 동적으로 처리
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

# --- 그룹 관련 ---
def create_group(db: Session, group: schemas.GroupCreate):
    db_group = models.Group(name=group.name)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

def get_groups(db: Session):
    return db.query(models.Group).all()

# --- 가게 관련 ---
def create_store(db: Session, store: schemas.StoreCreate):
    # Pydantic 모델을 딕셔너리로 변환하여 전달 (새로운 필드가 추가돼도 자동 반영)
    db_store = models.Store(**store.dict())
    db.add(db_store)
    db.commit()
    db.refresh(db_store)
    return db_store

def get_store(db: Session, store_id: int):
    return db.query(models.Store).filter(models.Store.id == store_id).first()

# --- 카테고리 관련 [핵심 수정!] ---
def create_category(db: Session, category: schemas.CategoryCreate, store_id: int):
    # 👇 기존: models.Category(name=category.name, store_id=store_id) <- 순서, 숨김 누락됨
    # 👇 수정: **category.dict()를 사용하여 order_index, is_hidden 등 모든 필드 포함
    db_category = models.Category(**category.dict(), store_id=store_id)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

# --- 메뉴 관련 [핵심 수정!] ---
def create_menu(db: Session, menu: schemas.MenuCreate, category_id: int):
    # 👇 여기도 마찬가지로 모든 필드 포함
    db_menu = models.Menu(**menu.dict(), category_id=category_id)
    db.add(db_menu)
    db.commit()
    db.refresh(db_menu)
    return db_menu

# --- 옵션 관련 ---
def create_option_group(db: Session, group: schemas.OptionGroupCreate, menu_id: int):
    # 옵션 그룹 생성
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
    
    # 메뉴와 연결 (Link)
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

# --- 테이블 관련 ---
def create_table(db: Session, table: schemas.TableCreate, store_id: int):
    import uuid
    # QR 토큰 자동 생성
    token = str(uuid.uuid4())
    db_table = models.Table(name=table.name, qr_token=token, store_id=store_id)
    db.add(db_table)
    db.commit()
    db.refresh(db_table)
    return db_table

def get_table(db: Session, table_id: int):
    return db.query(models.Table).filter(models.Table.id == table_id).first()

# --- 주문 관련 ---
def create_order(db: Session, order: schemas.OrderCreate):
    # 1. 주문 객체 생성
    db_order = models.Order(
        store_id=order.store_id,
        table_id=order.table_id,
        total_price=0, # 나중에 계산
        is_completed=False
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    total_price = 0

    # 2. 주문 아이템 생성 및 가격 계산
    for item in order.items:
        # 메뉴 가격 조회
        menu = db.query(models.Menu).filter(models.Menu.id == item.menu_id).first()
        if not menu:
            continue
            
        item_price = menu.price
        options_summary = []

        # 옵션 가격 계산
        for opt in item.options:
            item_price += opt.price
            options_summary.append(opt.name) # "맵게", "치즈추가" 등

        # 아이템 총액
        line_total = item_price * item.quantity
        total_price += line_total

        # 상세 기록 저장
        db_item = models.OrderItem(
            order_id=db_order.id,
            menu_name=menu.name,
            price=item_price,
            quantity=item.quantity,
            options_desc=", ".join(options_summary) if options_summary else None
        )
        db.add(db_item)

    # 3. 주문 총액 업데이트
    db_order.total_price = total_price
    db.commit()
    db.refresh(db_order)
    return db_order