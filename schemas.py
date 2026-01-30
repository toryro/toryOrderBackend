# schemas.py (전체 덮어씌우기)

from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from models import UserRole 

class OptionBase(BaseModel):
    name: str
    price: int
    order_index: int = 0 
    is_default: bool = False 

class OptionGroupBase(BaseModel):
    name: str
    is_required: bool = False
    is_single_select: bool = False
    order_index: int = 0 

class MenuBase(BaseModel):
    name: str
    price: int
    description: Optional[str] = None
    is_sold_out: bool = False
    is_hidden: bool = False 
    image_url: Optional[str] = None 
    order_index: int = 0

class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None # [신규]
    order_index: int = 0
    is_hidden: bool = False

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

# Create
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

# Update 
class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None # [신규]
    order_index: Optional[int] = None
    is_hidden: Optional[bool] = None

class MenuUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    description: Optional[str] = None
    is_sold_out: Optional[bool] = None
    is_hidden: Optional[bool] = None 
    image_url: Optional[str] = None
    order_index: Optional[int] = None
    category_id: Optional[int] = None

class OptionUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    order_index: Optional[int] = None
    is_default: Optional[bool] = None 

class OptionGroupUpdate(BaseModel):
    name: Optional[str] = None
    is_single_select: Optional[bool] = None
    order_index: Optional[int] = None

# [신규] 테이블 이름 수정용
class TableUpdate(BaseModel):
    name: str

class OrderItemOptionCreate(BaseModel):
    name: str
    price: int
class OrderItemCreate(BaseModel):
    menu_id: int
    quantity: int
    options: List[OrderItemOptionCreate] = []
class OrderCreate(OrderBase):
    items: List[OrderItemCreate]

# Response
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
    
    # 👇 [신규] 여기에 table_name을 추가해야 주방 화면이 읽을 수 있습니다!
    table_name: Optional[str] = None 
    
    items: List[OrderItem] = []
    model_config = ConfigDict(from_attributes=True)

class UserResponse(UserBase):
    id: int
    is_active: bool
    role: UserRole
    group_id: Optional[int] = None
    store_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)