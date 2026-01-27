# schemas.py

from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from models import UserRole 

# === 1. Base (공통) ===
class OptionBase(BaseModel):
    name: str
    price: int

class OptionGroupBase(BaseModel):
    name: str
    is_required: bool = False
    is_single_select: bool = False # 단일 선택 여부

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

class GroupBase(BaseModel):
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

class GroupCreate(GroupBase):
    pass

class StoreCreate(StoreBase):
    group_id: Optional[int] = None 

class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.STORE_OWNER
    group_id: Optional[int] = None

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

# === 3. Response (응답) - [변경] model_config 사용 ===
class OptionResponse(OptionBase):
    id: int
    group_id: int
    model_config = ConfigDict(from_attributes=True)

class OptionGroupResponse(OptionGroupBase):
    id: int
    store_id: int
    options: List[OptionResponse] = [] 
    model_config = ConfigDict(from_attributes=True)

class MenuResponse(MenuBase):
    id: int
    category_id: int
    option_groups: List[OptionGroupResponse] = [] 
    model_config = ConfigDict(from_attributes=True)

class CategoryResponse(CategoryBase):
    id: int
    store_id: int
    menus: List[MenuResponse] = []
    model_config = ConfigDict(from_attributes=True)

class TableResponse(TableBase):
    id: int
    store_id: int
    qr_token: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class StoreResponse(StoreBase):
    id: int
    group_id: Optional[int] = None
    categories: List[CategoryResponse] = []
    tables: List[TableResponse] = []
    model_config = ConfigDict(from_attributes=True)

class GroupResponse(GroupBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class OrderItem(BaseModel):
    id: int
    menu_name: str
    price: int
    quantity: int
    options_desc: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class OrderResponse(OrderBase):
    id: int
    total_price: int
    created_at: str
    is_completed: bool
    items: List[OrderItem] = []
    model_config = ConfigDict(from_attributes=True)

class UserResponse(UserBase):
    id: int
    is_active: bool
    role: UserRole
    group_id: Optional[int] = None
    store_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)