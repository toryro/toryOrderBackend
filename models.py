# models.py

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import enum

# [역할 Enum]
class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    GROUP_ADMIN = "GROUP_ADMIN"
    STORE_OWNER = "STORE_OWNER"

# 1. 그룹 (프랜차이즈 본사)
class Group(Base):
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    
    stores = relationship("Store", back_populates="group")
    admins = relationship("User", back_populates="group")

# 2. 가게
class Store(Base):
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    
    group = relationship("Group", back_populates="stores")
    owner = relationship("User", back_populates="store")
    
    # 가게에 딸린 식구들
    categories = relationship("Category", back_populates="store")
    tables = relationship("Table", back_populates="store")
    orders = relationship("Order", back_populates="store")

# 3. 사용자 (사장님, 관리자)
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

# 4. 테이블 (QR 코드) [여기가 없어서 에러가 났던 겁니다!]
class Table(Base):
    __tablename__ = "tables"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String) # 예: "1번 테이블"
    qr_token = Column(String, unique=True, index=True) # QR 접속용 난수
    store_id = Column(Integer, ForeignKey("stores.id"))

    store = relationship("Store", back_populates="tables")
    orders = relationship("Order", back_populates="table")

# 5. 카테고리 (메뉴 분류)
class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    store_id = Column(Integer, ForeignKey("stores.id"))

    store = relationship("Store", back_populates="categories")
    menus = relationship("Menu", back_populates="category")

# 6. 메뉴
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
    option_groups = relationship("OptionGroup", back_populates="menu")

# 7. 옵션 그룹 (예: 맵기 선택, 추가 토핑)
class OptionGroup(Base):
    __tablename__ = "option_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String) # 예: "맵기 조절"
    is_required = Column(Boolean, default=False) # 필수 선택 여부
    menu_id = Column(Integer, ForeignKey("menus.id"))

    menu = relationship("Menu", back_populates="option_groups")
    options = relationship("Option", back_populates="group")

# 8. 옵션 상세 (예: 아주 매운맛 +500원)
class Option(Base):
    __tablename__ = "options"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    price = Column(Integer) # 추가 가격
    group_id = Column(Integer, ForeignKey("option_groups.id"))

    group = relationship("OptionGroup", back_populates="options")

# 9. 주문 (영수증)
class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    total_price = Column(Integer)
    is_completed = Column(Boolean, default=False) # 조리 완료 여부
    created_at = Column(String, default=lambda: str(datetime.now())) # 주문 시간
    
    store_id = Column(Integer, ForeignKey("stores.id"))
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=True)

    store = relationship("Store", back_populates="orders")
    table = relationship("Table", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

# 10. 주문 상세 아이템 (주문서에 적힌 메뉴들)
class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    
    menu_name = Column(String) # 메뉴 이름 박제 (나중에 메뉴판 바뀌어도 주문 내역은 유지)
    price = Column(Integer)    # 가격 박제
    quantity = Column(Integer)
    options_desc = Column(String, nullable=True) # 옵션 내용 (예: "매운맛, 치즈추가")

    order = relationship("Order", back_populates="items")