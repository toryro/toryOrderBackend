# models.py (전체 덮어씌우기)

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Enum as SAEnum, Table
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import enum

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    GROUP_ADMIN = "GROUP_ADMIN"
    STORE_OWNER = "STORE_OWNER"

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
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    group = relationship("Group", back_populates="stores")
    owner = relationship("User", back_populates="store")
    categories = relationship("Category", back_populates="store", order_by="Category.order_index")
    tables = relationship("Table", back_populates="store")
    orders = relationship("Order", back_populates="store")
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
    # [신규] 카테고리 설명
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
    total_price = Column(Integer)
    is_completed = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: str(datetime.now()))
    store_id = Column(Integer, ForeignKey("stores.id"))
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=True)
    
    store = relationship("Store", back_populates="orders")
    table = relationship("Table", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

    # 👇 [신규] 테이블 이름을 자동으로 가져오는 속성 추가
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