from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Date, Time, Float, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import enum

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    BRAND_ADMIN = "BRAND_ADMIN"
    GROUP_ADMIN = "GROUP_ADMIN"
    STORE_OWNER = "STORE_OWNER"
    STAFF = "STAFF"
    GENERAL_USER = "GENERAL_USER"

# 🚫 1그룹: 전역 데이터 (store_id 없음)
class Brand(Base):
    __tablename__ = "brands"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    business_number = Column(String, nullable=True)
    support_email = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)     
    homepage = Column(String, nullable=True)     
    
    groups = relationship("Group", back_populates="brand")
    stores = relationship("Store", back_populates="brand")
    admins = relationship("User", back_populates="brand")

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    brand = relationship("Brand", back_populates="groups")
    stores = relationship("Store", back_populates="group")
    admins = relationship("User", back_populates="group")

class Store(Base):
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    brand = relationship("Brand", back_populates="stores")
    is_direct_manage = Column(Boolean, default=False)

    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    description = Column(String, nullable=True)
    is_open = Column(Boolean, default=True)
    notice = Column(String, nullable=True)
    origin_info = Column(String, nullable=True)
    
    owner_name = Column(String, nullable=True)
    business_name = Column(String, nullable=True)
    business_address = Column(String, nullable=True)
    business_number = Column(String, nullable=True)

    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    group = relationship("Group", back_populates="stores")
    owner = relationship("User", back_populates="store")
    categories = relationship("Category", back_populates="store", order_by="Category.order_index")
    tables = relationship("Table", back_populates="store")
    orders = relationship("Order", back_populates="store")
    option_groups = relationship("OptionGroup", back_populates="store")
    operating_hours = relationship("OperatingHour", back_populates="store", cascade="all, delete-orphan")
    holidays = relationship("Holiday", back_populates="store", cascade="all, delete-orphan")
    staff_calls = relationship("StaffCall", back_populates="store", cascade="all, delete-orphan")
    call_options = relationship("CallOption", back_populates="store", cascade="all, delete-orphan")
    # ✨ [추가] 지점별 기본 가격 할증 (예: 강남점은 500)
    price_markup = Column(Integer, default=0)
    # ✨ [추가] 가맹점 로열티 산출 방식 및 값
    royalty_type = Column(String, default="PERCENTAGE") # "PERCENTAGE" 또는 "FIXED"
    royalty_amount = Column(Float, default=0.0) # 퍼센트 비율(%) 또는 고정금액(원)
    # ✨ [추가] 매장 지역 분류
    region = Column(String, default="미지정")
    # ✨ [신규 추가] 매장의 결제 정책 (PRE_PAY: 선불, POST_PAY: 후불)
    payment_policy = Column(String, default="PRE_PAY")

# ⚠️ 2그룹: 예외 (관리자 때문에 nullable=True 유지)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    role = Column(SAEnum(UserRole), default=UserRole.GENERAL_USER)
    
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True) # 예외 허용
    
    brand = relationship("Brand", back_populates="admins")
    group = relationship("Group", back_populates="admins")
    store = relationship("Store", back_populates="owner")

# ✅ 3그룹: 매장 전용 데이터 (nullable=False, index=True 강제)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    name = Column(String)
    description = Column(String, nullable=True)
    order_index = Column(Integer, default=0)
    is_hidden = Column(Boolean, default=False)
    
    store = relationship("Store", back_populates="categories")
    menus = relationship("Menu", back_populates="category", order_by="Menu.order_index", cascade="all, delete-orphan")

class Menu(Base):
    __tablename__ = "menus"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 신규 추가
    category_id = Column(Integer, ForeignKey("categories.id"))
    name = Column(String)
    price = Column(Integer)
    description = Column(String, nullable=True)
    is_sold_out = Column(Boolean, default=False)
    image_url = Column(String, nullable=True)
    order_index = Column(Integer, default=0)
    is_hidden = Column(Boolean, default=False)
    
    category = relationship("Category", back_populates="menus")
    menu_option_links = relationship("MenuOptionLink", back_populates="menu", cascade="all, delete-orphan")
    is_price_fixed = Column(Boolean, default=False) # 본사에서 가격 변경을 금지했는지 여부

    # 할인 및 타임세일
    is_discounted = Column(Boolean, default=False)
    discount_price = Column(Integer, default=0)
    time_sale_start = Column(String, nullable=True) # 예: "14:00"
    time_sale_end = Column(String, nullable=True)   # 예: "17:00"

class OptionGroup(Base):
    __tablename__ = "option_groups"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    name = Column(String)
    is_required = Column(Boolean, default=False)
    is_single_select = Column(Boolean, default=False) 
    order_index = Column(Integer, default=0) 
    max_select = Column(Integer, default=0)
    
    store = relationship("Store", back_populates="option_groups")
    options = relationship("Option", back_populates="group", order_by="Option.order_index")
    menu_links = relationship("MenuOptionLink", back_populates="group")

class Option(Base):
    __tablename__ = "options"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 신규 추가
    group_id = Column(Integer, ForeignKey("option_groups.id"))
    name = Column(String)
    price = Column(Integer)
    order_index = Column(Integer, default=0)
    is_default = Column(Boolean, default=False) 
    
    group = relationship("OptionGroup", back_populates="options")

class MenuOptionLink(Base):
    __tablename__ = "menu_option_links"
    menu_id = Column(Integer, ForeignKey("menus.id"), primary_key=True)
    option_group_id = Column(Integer, ForeignKey("option_groups.id"), primary_key=True)
    order_index = Column(Integer, default=0)
    menu = relationship("Menu", back_populates="menu_option_links")
    group = relationship("OptionGroup", back_populates="menu_links")

class Table(Base):
    __tablename__ = "tables"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    name = Column(String)
    qr_token = Column(String, unique=True, index=True)
    
    store = relationship("Store", back_populates="tables")
    orders = relationship("Order", back_populates="table")
    staff_calls = relationship("StaffCall", back_populates="table")

class CallOption(Base):
    __tablename__ = "call_options"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    name = Column(String)
    store = relationship("Store", back_populates="call_options")

class OperatingHour(Base):
    __tablename__ = "operating_hours"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    day_of_week = Column(Integer)
    open_time = Column(String, nullable=True)
    close_time = Column(String, nullable=True)
    is_closed = Column(Boolean, default=False)
    # ✨ [핵심] 여러 개의 브레이크 타임을 문자열(JSON) 형태로 한 번에 저장합니다.
    break_time_list = Column(String, default="[]")
    store = relationship("Store", back_populates="operating_hours")

class Holiday(Base):
    __tablename__ = "holidays"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    date = Column(String)
    description = Column(String, nullable=True)
    store = relationship("Store", back_populates="holidays")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    daily_number = Column(Integer, default=1)
    total_price = Column(Integer)
    is_completed = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: str(datetime.now()))
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=True)
    
    payment_status = Column(String, default="PENDING") 
    # ✨ [신규 추가] 조리 상태 저장용 컬럼
    cooking_status = Column(String, default="PENDING")
    payment_method = Column(String, nullable=True)
    imp_uid = Column(String, nullable=True)
    merchant_uid = Column(String, unique=True, nullable=True)
    paid_amount = Column(Integer, default=0)

    store = relationship("Store", back_populates="orders")
    table = relationship("Table", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

    @property
    def table_name(self):
        return self.table.name if self.table else "포장/미지정"

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 신규 추가
    order_id = Column(Integer, ForeignKey("orders.id"))
    menu_name = Column(String)
    price = Column(Integer)
    quantity = Column(Integer)
    options_desc = Column(String, nullable=True)
    is_cancelled = Column(Boolean, default=False)
    order = relationship("Order", back_populates="items")

class StaffCall(Base):
    __tablename__ = "staff_calls"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    table_id = Column(Integer, ForeignKey("tables.id"))
    message = Column(String, default="직원 호출")
    is_completed = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: str(datetime.now()))
    store = relationship("Store", back_populates="staff_calls")
    table = relationship("Table", back_populates="staff_calls")

class Notice(Base):
    __tablename__ = "notices"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    target_type = Column(String, nullable=False) 
    target_brand_id = Column(Integer, nullable=True)
    target_store_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class NoticeRead(Base):
    __tablename__ = "notice_reads"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    notice_id = Column(Integer, ForeignKey("notices.id"))
    read_at = Column(DateTime, default=datetime.utcnow)

# ✨ [신규 추가] 시스템 감사 로그 (블랙박스)
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(Integer, nullable=True)
    details = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 누가 했는지 이름을 쉽게 가져오기 위한 연결고리
    user = relationship("User")