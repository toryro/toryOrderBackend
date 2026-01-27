from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Enum as SAEnum, Table
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import enum

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    GROUP_ADMIN = "GROUP_ADMIN"
    STORE_OWNER = "STORE_OWNER"

# [핵심] 메뉴-옵션그룹 연결 테이블 (다대다 관계)
menu_option_link = Table(
    "menu_option_link",
    Base.metadata,
    Column("menu_id", Integer, ForeignKey("menus.id"), primary_key=True),
    Column("option_group_id", Integer, ForeignKey("option_groups.id"), primary_key=True),
)

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
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    
    group = relationship("Group", back_populates="stores")
    owner = relationship("User", back_populates="store")
    categories = relationship("Category", back_populates="store")
    tables = relationship("Table", back_populates="store")
    orders = relationship("Order", back_populates="store")
    # [신규] 가게가 소유한 옵션 그룹 라이브러리
    option_groups = relationship("OptionGroup", back_populates="store")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    role = Column(SAEnum(UserRole), default=UserRole.STORE_OWNER)
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

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    store_id = Column(Integer, ForeignKey("stores.id"))
    store = relationship("Store", back_populates="categories")
    menus = relationship("Menu", back_populates="category")

class Menu(Base):
    __tablename__ = "menus"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    price = Column(Integer)
    description = Column(String, nullable=True)
    is_sold_out = Column(Boolean, default=False)
    image_url = Column(String, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"))

    category = relationship("Category", back_populates="menus")
    option_groups = relationship("OptionGroup", secondary=menu_option_link, back_populates="menus")

class OptionGroup(Base):
    __tablename__ = "option_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    is_required = Column(Boolean, default=False)
    
    # 👇 여기가 문제였습니다! 이 줄이 꼭 있어야 합니다.
    is_single_select = Column(Boolean, default=False) 
    
    store_id = Column(Integer, ForeignKey("stores.id")) 
    store = relationship("Store", back_populates="option_groups")
    options = relationship("Option", back_populates="group")
    menus = relationship("Menu", secondary=menu_option_link, back_populates="option_groups")

class Option(Base):
    __tablename__ = "options"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    price = Column(Integer)
    group_id = Column(Integer, ForeignKey("option_groups.id"))
    group = relationship("OptionGroup", back_populates="options")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    total_price = Column(Integer)
    is_completed = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: str(datetime.now()))
    store_id = Column(Integer, ForeignKey("stores.id"))
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=True)
    store = relationship("Store", back_populates="orders")
    table = relationship("Table", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    menu_name = Column(String)
    price = Column(Integer)
    quantity = Column(Integer)
    options_desc = Column(String, nullable=True)
    order = relationship("Order", back_populates="items")