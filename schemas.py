# schemas.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from models import UserRole # models.py의 Enum 사용

# === 1. Base (공통) ===
class OptionBase(BaseModel):
    name: str
    price: int

class OptionGroupBase(BaseModel):
    name: str
    is_required: bool = False

class MenuBase(BaseModel):
    name: str
    price: int
    description: Optional[str] = None
    is_sold_out: bool = False
    image_url: Optional[str] = None 

class CategoryBase(BaseModel):
    name: str

class TableBase(BaseModel):
    name: str

class GroupBase(BaseModel): # [신규]
    name: str

class StoreBase(BaseModel):
    name: str

class OrderBase(BaseModel):
    store_id: int
    table_id: int

class UserBase(BaseModel):
    email: str

# === 2. Create (생성 요청) ===
class OptionCreate(OptionBase):
    pass

class OptionGroupCreate(OptionGroupBase):
    pass 

class MenuCreate(MenuBase):
    pass

class CategoryCreate(CategoryBase):
    pass

class TableCreate(TableBase):
    pass

class GroupCreate(GroupBase): # [신규]
    pass

class StoreCreate(StoreBase):
    # 가게 생성 시 그룹 소속일 수 있음 (선택)
    group_id: Optional[int] = None 

class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.STORE_OWNER # 기본값: 사장님
    group_id: Optional[int] = None # 그룹 관리자일 경우 입력

# 주문 상세
class OrderItemOptionCreate(BaseModel):
    name: str
    price: int

class OrderItemCreate(BaseModel):
    menu_id: int
    quantity: int
    options: List[OrderItemOptionCreate] = []

class OrderCreate(OrderBase):
    items: List[OrderItemCreate]

# === 3. Response (응답) ===
class OptionResponse(OptionBase):
    id: int
    group_id: int
    class Config:
        from_attributes = True

class OptionGroupResponse(OptionGroupBase):
    id: int
    menu_id: int
    options: List[OptionResponse] = [] 
    class Config:
        from_attributes = True

class MenuResponse(MenuBase):
    id: int
    category_id: int
    option_groups: List[OptionGroupResponse] = [] 
    class Config:
        from_attributes = True

class CategoryResponse(CategoryBase):
    id: int
    store_id: int
    menus: List[MenuResponse] = []
    class Config:
        from_attributes = True

class TableResponse(TableBase):
    id: int
    store_id: int
    qr_token: Optional[str] = None
    class Config:
        from_attributes = True

class StoreResponse(StoreBase):
    id: int
    group_id: Optional[int] = None
    categories: List[CategoryResponse] = []
    tables: List[TableResponse] = []
    class Config:
        from_attributes = True

class GroupResponse(GroupBase): # [신규]
    id: int
    class Config:
        from_attributes = True

class OrderItem(BaseModel):
    id: int
    menu_name: str
    price: int
    quantity: int
    options_desc: Optional[str] = None
    class Config:
        from_attributes = True

class OrderResponse(OrderBase):
    id: int
    total_price: int
    created_at: str # datetime -> str 변환
    is_completed: bool
    items: List[OrderItem] = []
    class Config:
        from_attributes = True

class UserResponse(UserBase):
    id: int
    is_active: bool
    role: UserRole      # Enum 타입
    group_id: Optional[int] = None
    store_id: Optional[int] = None

    class Config:
        from_attributes = True