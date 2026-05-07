from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from models import UserRole 
from datetime import datetime

# --- 브랜드(본사) 스키마 ---
class BrandBase(BaseModel):
    name: str
    logo_url: Optional[str] = None
    homepage: Optional[str] = None
    support_email: Optional[str] = None
    business_number: Optional[str] = None
    kakao_profile_key: Optional[str] = None
    sms_sender_number: Optional[str] = None

class BrandCreate(BrandBase):
    pass

class BrandUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    homepage: Optional[str] = None
    support_email: Optional[str] = None
    business_number: Optional[str] = None
    kakao_profile_key: Optional[str] = None
    sms_sender_number: Optional[str] = None

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
    break_time_list: Optional[str] = "[]"  # ✨ 여러 개의 휴게시간을 받을 준비 완료

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
    is_price_fixed: bool = False
    is_tax_exempt: bool = False
    target_time: Optional[int] = 15

    # 할인 및 타임세일
    is_discounted: bool = False
    discount_price: int = 0
    time_sale_start: Optional[str] = None
    time_sale_end: Optional[str] = None

class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    order_index: int = 0
    is_hidden: bool = False

# ✨ [수정됨] 테이블 기본 스키마에 포장/매장 설정 추가
class TableBase(BaseModel):
    name: str
    order_type_setting: Optional[str] = "SELECTABLE"  # 'SELECTABLE', 'DINE_IN_ONLY', 'TAKEOUT_ONLY'
    table_type: str = "DINE_IN"  # 'DINE_IN' | 'TAKEOUT_COUNTER'

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
    
    # ✨ [핵심 수정] DB에 값이 비어있을(NULL) 경우를 대비해 모두 Optional을 붙여줍니다!
    price_markup: Optional[int] = 0
    royalty_type: Optional[str] = "PERCENTAGE" 
    royalty_amount: Optional[float] = 0.0      
    region: Optional[str] = "미지정"
    payment_policy: Optional[str] = "PRE_PAY" 
    use_table_board: Optional[bool] = True
    use_menu_detail: Optional[bool] = False # 상세페이지 사용 여부
    has_pos: Optional[bool] = None
    printer_config: Optional[str] = "NONE"
    auto_kitchen_print: Optional[bool] = False
    allow_staff_order: Optional[bool] = True
    closing_hour: Optional[int] = 0

    receipt_printer_type: Optional[str] = "FILE"
    receipt_printer_host: Optional[str] = ""
    receipt_printer_port: Optional[str] = "9100"
    receipt_printer_baud: Optional[int] = 9600
    kitchen_printer_type: Optional[str] = "FILE"
    kitchen_printer_host: Optional[str] = ""
    kitchen_printer_port: Optional[str] = "9100"
    kitchen_printer_baud: Optional[int] = 9600
    notification_type: Optional[str] = "PLATFORM"
    kakao_profile_key: Optional[str] = None
    sms_sender_number: Optional[str] = None
    is_emergency_mode: Optional[bool] = False

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
    brand_id: Optional[int] = None 

    price_markup: int = 0
    royalty_type: str = "PERCENTAGE"   
    royalty_amount: float = 0.0
    region: Optional[str] = "미지정"
    is_direct_manage: Optional[bool] = None
    payment_policy: str = "PRE_PAY"
    use_table_board: bool = True
    use_menu_detail: bool = False #상세페이지 사용 여부
    has_pos: Optional[bool] = None
    printer_config: Optional[str] = None
    auto_kitchen_print: Optional[bool] = None
    allow_staff_order: Optional[bool] = None
    closing_hour: Optional[int] = None

    receipt_printer_type: Optional[str] = None
    receipt_printer_host: Optional[str] = None
    receipt_printer_port: Optional[str] = None
    receipt_printer_baud: Optional[int] = None
    kitchen_printer_type: Optional[str] = None
    kitchen_printer_host: Optional[str] = None
    kitchen_printer_port: Optional[str] = None
    kitchen_printer_baud: Optional[int] = None
    notification_type: Optional[str] = None
    kakao_profile_key: Optional[str] = None
    sms_sender_number: Optional[str] = None
    is_emergency_mode: Optional[bool] = None

class OrderBase(BaseModel):
    store_id: int
    table_id: Optional[int] = None

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
    is_price_fixed: Optional[bool] = None
    is_discounted: Optional[bool] = None
    discount_price: Optional[int] = None
    time_sale_start: Optional[str] = None
    time_sale_end: Optional[str] = None

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

# ✨ [수정됨] 테이블 업데이트 시 설정값도 수정 가능하도록 변경
class TableUpdate(BaseModel):
    name: Optional[str] = None
    order_type_setting: Optional[str] = None

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
    is_post_pay: bool = False
    order_type: str = "DINE_IN"
    session_token: Optional[str] = None
    customer_phone: Optional[str] = None  # 포장 알림 수신 전화번호 (선택)

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
    discount_price: Optional[int] = 0
    option_groups: List[OptionGroupResponse] = []
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
    order_type_setting: str
    table_type: str = "DINE_IN"
    current_status: str = "EMPTY"
    occupied_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
    is_virtual: bool = False


class OrderItem(BaseModel):
    id: int
    menu_name: str
    price: int
    quantity: int
    options_desc: Optional[str] = None
    is_cancelled: Optional[bool] = False
    original_price: Optional[int] = None
    is_tax_exempt: Optional[bool] = False
    model_config = ConfigDict(from_attributes=True)

class OrderResponse(OrderBase):
    id: int
    daily_number: int
    total_price: int
    created_at: datetime
    is_completed: bool
    table_name: Optional[str] = None
    items: List[OrderItem] = []
    payment_status: str
    payment_method: Optional[str] = None
    paid_amount: Optional[int] = 0
    cooking_status: Optional[str] = "PENDING"
    target_time: Optional[int] = 15
    order_type: str = "DINE_IN"
    cash_receipt_status: Optional[str] = "NONE"
    cash_receipt_number: Optional[str] = None
    cash_receipt_type: Optional[str] = None
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
    virtual_session_token: Optional[str] = None
    session_token: Optional[str] = None  # 포장 카운터 세션 결제 완료 후 파기용

class CashReceiptRequest(BaseModel):
    identifier_type: str  # "phone" | "card" | "business"
    identifier: str       # 휴대폰번호, 카드번호, 사업자번호 (숫자만)
    trade_type: str = "PERSONAL"  # "PERSONAL"(소득공제) | "BUSINESS"(지출증빙)

class CollectPaymentRequest(BaseModel):
    payment_method: str  # "card" | "cash" | "POS" | "기타"
    cash_receipt: Optional[CashReceiptRequest] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

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

# --- 본사(HQ) 통합 매출 통계 스키마 ---
class HQStoreStat(BaseModel):
    store_id: int
    store_name: str
    brand_name: Optional[str] = None 
    region: str 
    is_direct_manage: bool 
    revenue: int
    order_count: int
    royalty_fee: int 

class HQSalesStatResponse(BaseModel):
    total_revenue: int
    total_order_count: int
    total_royalty_fee: int 
    store_stats: List[HQStoreStat]

class NoticeCreate(BaseModel):
    title: str
    content: str
    target_type: str
    target_brand_id: Optional[int] = None
    target_store_id: Optional[int] = None

class OrderCancelRequest(BaseModel):
    reason: str = "관리자 화면에서 직접 취소"
    amount: Optional[int] = None  
    cancelled_item_ids: List[int] = []

    # 상태 변경을 위한 요청 데이터 스키마
class TableStatusUpdate(BaseModel):
    status: str # "EMPTY", "OCCUPIED", "CLEANING_REQUESTED"

# --- 가상 세션(VirtualSession) 신규 스키마 ---
class VirtualSessionResponse(BaseModel):
    id: int
    store_id: int
    token: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Table 조회 응답 통합용 ---
# 프론트엔드의 OrderPage.jsx가 테이블과 가상 세션을 똑같이 처리할 수 있도록 
# 응답 규격을 맞춰줍니다.
class TableTokenResponse(BaseModel):
    table_id: Optional[int] = None
    store_id: int
    label: str
    order_type_setting: str
    is_virtual: bool = False
    session_token: Optional[str] = None  # 홀 테이블 방문 세션 토큰