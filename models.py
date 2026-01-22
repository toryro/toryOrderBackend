from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

# 1. 사용자 (점주)
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="OWNER")
    created_at = Column(DateTime, default=datetime.utcnow)

    stores = relationship("Store", back_populates="owner")

# 2. 매장
class Store(Base):
    __tablename__ = "stores"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    currency = Column(String, default="KRW")
    timezone = Column(String, default="Asia/Seoul")
    is_open = Column(Boolean, default=True)
    
    owner = relationship("User", back_populates="stores")
    tables = relationship("Table", back_populates="store")
    categories = relationship("Category", back_populates="store")
    orders = relationship("Order", back_populates="store")

# 3. 테이블
class Table(Base):
    __tablename__ = "tables"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    label = Column(String)
    qr_token = Column(String, unique=True, index=True)
    
    store = relationship("Store", back_populates="tables")

# 4. 카테고리
class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    name = Column(String, nullable=False)
    priority = Column(Integer, default=0)
    
    store = relationship("Store", back_populates="categories")
    menus = relationship("Menu", back_populates="category")

# 5. 메뉴
class Menu(Base):
    __tablename__ = "menus"
    
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False)
    image_url = Column(String, nullable=True)
    is_sold_out = Column(Boolean, default=False)
    
    category = relationship("Category", back_populates="menus")
    options = relationship("MenuOptionGroup", back_populates="menu")

# 6. 메뉴 옵션 그룹
class MenuOptionGroup(Base):
    __tablename__ = "menu_option_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    menu_id = Column(Integer, ForeignKey("menus.id"))
    name = Column(String, nullable=False)
    min_select = Column(Integer, default=1)
    max_select = Column(Integer, default=1)
    
    menu = relationship("Menu", back_populates="options")
    details = relationship("MenuOptionDetail", back_populates="group")

class MenuOptionDetail(Base):
    __tablename__ = "menu_option_details"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("menu_option_groups.id"))
    name = Column(String, nullable=False)
    extra_price = Column(Integer, default=0)
    
    group = relationship("MenuOptionGroup", back_populates="details")

# 7. 주문 (Order)
class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    table_id = Column(Integer, ForeignKey("tables.id"))
    total_price = Column(Integer, default=0)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    store = relationship("Store", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

# 8. 주문 상세 (OrderItem)
class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    menu_name = Column(String)
    price = Column(Integer)
    quantity = Column(Integer)
    options_json = Column(JSON, nullable=True)
    
    order = relationship("Order", back_populates="items")