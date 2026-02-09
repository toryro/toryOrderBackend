from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Date, Time, Enum as SAEnum
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

class Brand(Base):
    __tablename__ = "brands"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    business_number = Column(String, nullable=True)
    support_email = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)     # 기존 유지
    homepage = Column(String, nullable=True)     # 기존 유지
    
    groups = relationship("Group", back_populates="brand")
    stores = relationship("Store", back_populates="brand")
    admins = relationship("User", back_populates="brand")

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
    
    # 🔥 [신규] 재고(Inventory) 연결
    inventories = relationship("Inventory", back_populates="store", cascade="all, delete-orphan")

# 🔥 [신규] 재고(식자재) 테이블
class Inventory(Base):
    __tablename__ = "inventories"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    name = Column(String) # 재료명 (예: 삼겹살, 양파)
    quantity = Column(Integer, default=0) # 현재 수량
    unit = Column(String, default="개") # 단위 (g, kg, 개, ml)
    safe_quantity = Column(Integer, default=10) # 안전재고 (이것보다 적으면 경고)
    
    store = relationship("Store", back_populates="inventories")
    recipe_links = relationship("Recipe", back_populates="inventory", cascade="all, delete-orphan")

# 🔥 [신규] 레시피(메뉴-재고 연결) 테이블
class Recipe(Base):
    __tablename__ = "recipes"
    id = Column(Integer, primary_key=True, index=True)
    menu_id = Column(Integer, ForeignKey("menus.id"))
    inventory_id = Column(Integer, ForeignKey("inventories.id"))
    amount_needed = Column(Integer) # 메뉴 1개당 차감될 양
    
    menu = relationship("Menu", back_populates="recipes")
    inventory = relationship("Inventory", back_populates="recipe_links")

class CallOption(Base):
    __tablename__ = "call_options"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    name = Column(String)
    store = relationship("Store", back_populates="call_options")

class OperatingHour(Base):
    __tablename__ = "operating_hours"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    day_of_week = Column(Integer)
    open_time = Column(String, nullable=True)
    close_time = Column(String, nullable=True)
    is_closed = Column(Boolean, default=False)
    store = relationship("Store", back_populates="operating_hours")

class Holiday(Base):
    __tablename__ = "holidays"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    date = Column(String)
    description = Column(String, nullable=True)
    store = relationship("Store", back_populates="holidays")

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
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    
    brand = relationship("Brand", back_populates="admins")
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
    
    # 🔥 [신규] 레시피 연결
    recipes = relationship("Recipe", back_populates="menu", cascade="all, delete-orphan")

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
    
    payment_status = Column(String, default="PENDING") 
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
    message = Column(String, default="직원 호출")
    is_completed = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: str(datetime.now()))
    store = relationship("Store", back_populates="staff_calls")
    table = relationship("Table", back_populates="staff_calls")