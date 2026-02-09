from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from models import UserRole 

# --- 브랜드(본사) 스키마 ---
class BrandBase(BaseModel):
    name: str
    logo_url: Optional[str] = None      
    homepage: Optional[str] = None      
    support_email: Optional[str] = None
    business_number: Optional[str] = None

class BrandCreate(BrandBase):
    pass

class BrandResponse(BrandBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# [신규] 메뉴 배포 요청
class MenuDistributeRequest(BaseModel):
    source_category_id: int 
    target_store_ids: List[int] = [] 

# [신규] 재고(Inventory) 스키마
class InventoryBase(BaseModel):
    name: str
    quantity: int = 0
    unit: str = "개"
    safe_quantity: int = 10

class InventoryCreate(InventoryBase):
    pass

class InventoryUpdate(BaseModel):
    quantity: Optional[int] = None
    safe_quantity: Optional[int] = None

class InventoryResponse(InventoryBase):
    id: int
    store_id: int
    model_config = ConfigDict(from_attributes=True)

# [신규] 레시피(Recipe) 스키마
class RecipeCreate(BaseModel):
    inventory_id: int
    amount_needed: int

class RecipeResponse(BaseModel):
    id: int
    inventory_name: str # 편의를 위해 재고 이름 포함
    amount_needed: int
    unit: str
    model_config = ConfigDict(from_attributes=True)

# 영업시간
class OperatingHourBase(BaseModel):
    day_of_week: int
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    is_closed: bool = False

class OperatingHourUpdate(OperatingHourBase):
    pass

class OperatingHourResponse(OperatingHourBase):
    id: int
    store_id: int
    model_config = ConfigDict(from_attributes=True)

# 휴일
class HolidayBase(BaseModel):
    date: str
    description: Optional[str] = None

class HolidayCreate(HolidayBase):
    pass

class HolidayResponse(HolidayBase):
    id: int
    store_id: int
    model_config = ConfigDict(from_attributes=True)

# --- 기존 스키마들 ---
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
    max_select: int = 0

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
    description: Optional[str] = None
    order_index: int = 0
    is_hidden: bool = False

class TableBase(BaseModel):
    name: str

class GroupBase(BaseModel):
    name: str
    brand_id: Optional[int] = None 

class GroupCreate(GroupBase):
    pass

class GroupResponse(GroupBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class StoreBase(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    notice: Optional[str] = None
    origin_info: Optional[str] = None
    owner_name: Optional[str] = None
    business_name: Optional[str] = None
    business_address: Optional[str] = None
    business_number: Optional[str] = None
    
    brand_id: Optional[int] = None
    is_direct_manage: bool = False

    open_time: Optional[str] = None
    close_time: Optional[str] = None

class StoreCreate(StoreBase):
    group_id: Optional[int] = None 

class StoreUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    notice: Optional[str] = None
    origin_info: Optional[str] = None
    owner_name: Optional[str] = None
    business_name: Optional[str] = None
    business_address: Optional[str] = None
    business_number: Optional[str] = None
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    is_open: Optional[bool] = None 
    brand_id: Optional[int] = None # 추가됨

class StoreResponse(StoreBase):
    id: int
    is_open: bool
    group_id: Optional[int] = None
    operating_hours: List[OperatingHourResponse] = [] 
    holidays: List[HolidayResponse] = [] 
    categories: List["CategoryResponse"] = []
    tables: List["TableResponse"] = []
    model_config = ConfigDict(from_attributes=True)

class OrderBase(BaseModel):
    store_id: int
    table_id: int

class UserBase(BaseModel):
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    role: UserRole = UserRole.GENERAL_USER

class OptionCreate(OptionBase): pass
class OptionGroupCreate(OptionGroupBase): pass 
class MenuCreate(MenuBase): pass
class CategoryCreate(CategoryBase): pass
class TableCreate(TableBase): pass

class UserCreate(UserBase):
    password: str
    group_id: Optional[int] = None
    store_id: Optional[int] = None
    brand_id: Optional[int] = None 

class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None 
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
    is_required: Optional[bool] = None
    max_select: Optional[int] = None
    order_index: Optional[int] = None

class TableUpdate(BaseModel):
    name: str

class OrderItemOptionCreate(BaseModel):
    name: str
    price: int

class OrderItemCreate(BaseModel):
    menu_id: int
    quantity: int
    options: List[OrderItemOptionCreate] = []
    options_desc: Optional[str] = None

class OrderCreate(OrderBase):
    items: List[OrderItemCreate]

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
    # 🔥 [신규] 레시피 정보 포함
    recipes: List[RecipeResponse] = [] 
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

class OrderItem(BaseModel):
    id: int
    menu_name: str
    price: int
    quantity: int
    options_desc: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class OrderResponse(OrderBase):
    id: int
    daily_number: int
    total_price: int
    created_at: str
    is_completed: bool
    table_name: Optional[str] = None 
    items: List[OrderItem] = []
    payment_status: str
    model_config = ConfigDict(from_attributes=True)

class UserResponse(UserBase):
    id: int
    is_active: bool
    group_id: Optional[int] = None
    store_id: Optional[int] = None
    brand_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class SalesStat(BaseModel):
    total_revenue: int
    order_count: int
    hourly_stats: List[dict]
    menu_stats: List[dict]

class CallOptionCreate(BaseModel):
    name: str

class CallOptionResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)

class StaffCallCreate(BaseModel):
    table_id: int
    message: str = "직원 호출" 

class StaffCallResponse(BaseModel):
    id: int
    table_id: int
    table_name: str
    message: str
    created_at: str
    is_completed: bool
    model_config = ConfigDict(from_attributes=True)

class PaymentVerifyRequest(BaseModel):
    imp_uid: str
    merchant_uid: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# [순환 참조 방지]
class StoreResponse(StoreBase):
    id: int
    is_open: bool
    group_id: Optional[int] = None
    operating_hours: List[OperatingHourResponse] = [] 
    holidays: List[HolidayResponse] = [] 
    categories: List[CategoryResponse] = [] 
    tables: List[TableResponse] = []
    model_config = ConfigDict(from_attributes=True)