from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Date, Time, Enum as SAEnum
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import enum

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"   # 전체 관리자
    GROUP_ADMIN = "GROUP_ADMIN"   # 본사/중간 관리자
    STORE_OWNER = "STORE_OWNER"   # 점주
    STAFF = "STAFF"               # 매장 직원 (신규)
    GENERAL_USER = "GENERAL_USER" # 일반 고객 (미래 대비)

class MenuOptionLink(Base):
    __tablename__ = "menu_option_links"
    menu_id = Column(Integer, ForeignKey("menus.id"), primary_key=True)
    option_group_id = Column(Integer, ForeignKey("option_groups.id"), primary_key=True)
    order_index = Column(Integer, default=0)
    menu = relationship("Menu", back_populates="menu_option_links")
    group = relationship("OptionGroup", back_populates="menu_links")

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    stores = relationship("Store", back_populates="group")
    admins = relationship("User", back_populates="group")

class Store(Base):
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    
    # 기본 정보
    address = Column(String, nullable=True)     # 가게 주소 (손님용)
    phone = Column(String, nullable=True)       # 전화번호
    description = Column(String, nullable=True) # 가게 소개
    staff_calls = relationship("StaffCall", back_populates="store", cascade="all, delete-orphan")
    
    # [신규] 영업 상태 강제 설정 (True: 영업중, False: 영업종료)
    is_open = Column(Boolean, default=True)

    # [신규] 추가 정보
    notice = Column(String, nullable=True)          # 가게 알림(공지사항)
    origin_info = Column(String, nullable=True)     # 원산지 표시
    
    # [신규] 사업자 정보
    owner_name = Column(String, nullable=True)      # 대표자명
    business_name = Column(String, nullable=True)   # 상호명
    business_address = Column(String, nullable=True)# 사업자 주소
    business_number = Column(String, nullable=True) # 사업자 등록번호

    # (아래 관계 설정 코드는 기존 유지)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    group = relationship("Group", back_populates="stores")
    owner = relationship("User", back_populates="store")
    categories = relationship("Category", back_populates="store", order_by="Category.order_index")
    tables = relationship("Table", back_populates="store")
    orders = relationship("Order", back_populates="store")
    option_groups = relationship("OptionGroup", back_populates="store")
    operating_hours = relationship("OperatingHour", back_populates="store", cascade="all, delete-orphan")
    holidays = relationship("Holiday", back_populates="store", cascade="all, delete-orphan")

# [신규] 요일별 영업시간 (0:월 ~ 6:일)
class OperatingHour(Base):
    __tablename__ = "operating_hours"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    day_of_week = Column(Integer) # 0=월, 1=화 ... 6=일
    open_time = Column(String, nullable=True) # "09:00"
    close_time = Column(String, nullable=True) # "22:00"
    is_closed = Column(Boolean, default=False) # 휴무 여부
    store = relationship("Store", back_populates="operating_hours")

# [신규] 임시 휴일 지정
class Holiday(Base):
    __tablename__ = "holidays"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    date = Column(String) # "2024-02-10"
    description = Column(String, nullable=True) # "설날 당일 휴무"
    store = relationship("Store", back_populates="holidays")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    # [신규] 상세 정보 필드
    name = Column(String, nullable=True)        # 사용자 실명 (예: 백종원)
    phone = Column(String, nullable=True)       # 연락처 (010-xxxx-xxxx)
    
    is_active = Column(Boolean, default=True)
    role = Column(SAEnum(UserRole), default=UserRole.GENERAL_USER)
    
    # 소속 정보
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    
    group = relationship("Group", back_populates="admins")
    store = relationship("Store", back_populates="owner")

class Table(Base):
    __tablename__ = "tables"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    qr_token = Column(String, unique=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    store = relationship("Store", back_populates="tables")
    orders = relationship("Order", back_populates="table")
    staff_calls = relationship("StaffCall", back_populates="table")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String, nullable=True)
    order_index = Column(Integer, default=0)
    is_hidden = Column(Boolean, default=False)
    store_id = Column(Integer, ForeignKey("stores.id"))
    store = relationship("Store", back_populates="categories")
    menus = relationship("Menu", back_populates="category", order_by="Menu.order_index", cascade="all, delete-orphan")

class Menu(Base):
    __tablename__ = "menus"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    price = Column(Integer)
    description = Column(String, nullable=True)
    is_sold_out = Column(Boolean, default=False)
    image_url = Column(String, nullable=True)
    order_index = Column(Integer, default=0)
    is_hidden = Column(Boolean, default=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship("Category", back_populates="menus")
    menu_option_links = relationship("MenuOptionLink", back_populates="menu", cascade="all, delete-orphan")

    @property
    def option_groups(self):
        sorted_links = sorted(self.menu_option_links, key=lambda x: x.order_index)
        groups = []
        for link in sorted_links:
            group = link.group
            group.order_index = link.order_index 
            groups.append(group)
        return groups

class OptionGroup(Base):
    __tablename__ = "option_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    is_required = Column(Boolean, default=False)
    is_single_select = Column(Boolean, default=False) 
    order_index = Column(Integer, default=0) 
    
    # [신규] 최대 선택 개수 (0: 무제한, 1~N: 제한)
    max_select = Column(Integer, default=0)

    store_id = Column(Integer, ForeignKey("stores.id")) 
    store = relationship("Store", back_populates="option_groups")
    options = relationship("Option", back_populates="group", order_by="Option.order_index")
    menu_links = relationship("MenuOptionLink", back_populates="group")

class Option(Base):
    __tablename__ = "options"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    price = Column(Integer)
    order_index = Column(Integer, default=0)
    is_default = Column(Boolean, default=False) 
    group_id = Column(Integer, ForeignKey("option_groups.id"))
    group = relationship("OptionGroup", back_populates="options")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    daily_number = Column(Integer, default=1)
    total_price = Column(Integer)
    is_completed = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: str(datetime.now()))
    store_id = Column(Integer, ForeignKey("stores.id"))
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=True)
    store = relationship("Store", back_populates="orders")
    table = relationship("Table", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

    @property
    def table_name(self):
        return self.table.name if self.table else "포장/미지정"

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    menu_name = Column(String)
    price = Column(Integer)
    quantity = Column(Integer)
    options_desc = Column(String, nullable=True)
    order = relationship("Order", back_populates="items")

class StaffCall(Base):
    __tablename__ = "staff_calls"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    table_id = Column(Integer, ForeignKey("tables.id"))
    
    # [확장성 핵심] 요청 내용 (예: "물", "앞치마", "직원 호출")
    message = Column(String, default="직원 호출")
    
    is_completed = Column(Boolean, default=False) # 처리 여부
    created_at = Column(String, default=lambda: str(datetime.now()))

    # 관계 설정
    store = relationship("Store", back_populates="staff_calls")
    table = relationship("Table", back_populates="staff_calls")