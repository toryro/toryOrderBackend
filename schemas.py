from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

# 1. 공통 설정
class BaseSchema(BaseModel):
    class Config:
        from_attributes = True

# --- [추가됨] 사용자 (User) ---
class UserBase(BaseSchema):
    email: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    role: str

# --- 메뉴/카테고리 ---
class MenuBase(BaseSchema):
    name: str
    price: int
    description: Optional[str] = None
    is_sold_out: bool = False

class MenuCreate(MenuBase):
    pass

class MenuResponse(MenuBase):
    id: int
    category_id: int

class CategoryBase(BaseSchema):
    name: str

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    menus: List[MenuResponse] = []

# --- 테이블 ---
class TableCreate(BaseSchema):
    label: str

class TableResponse(BaseSchema):
    id: int
    label: str
    qr_token: str

# --- 매장 ---
class StoreBase(BaseSchema):
    name: str

class StoreCreate(StoreBase):
    owner_id: int

class StoreResponse(StoreBase):
    id: int
    categories: List[CategoryResponse] = []
    tables: List[TableResponse] = []

# --- 주문 ---
class OrderItemCreate(BaseSchema):
    menu_id: int
    quantity: int
    options: Dict = {}

class OrderCreate(BaseSchema):
    store_id: int
    table_id: int
    items: List[OrderItemCreate]
    
class OrderResponse(BaseSchema):
    id: int
    status: str
    total_price: int
    created_at: datetime