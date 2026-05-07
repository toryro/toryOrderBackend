from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Date, Time, Float, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import enum

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    BRAND_ADMIN = "BRAND_ADMIN"
    GROUP_ADMIN = "GROUP_ADMIN"
    STORE_OWNER = "STORE_OWNER"
    STAFF = "STAFF"
    GENERAL_USER = "GENERAL_USER"

# 🚫 1그룹: 전역 데이터 (store_id 없음)
class Brand(Base):
    __tablename__ = "brands"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    business_number = Column(String, nullable=True)
    support_email = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    homepage = Column(String, nullable=True)
    kakao_profile_key = Column(String, nullable=True)   # 브랜드 공용 알림톡 채널 프로필 키
    sms_sender_number = Column(String, nullable=True)   # 브랜드 공용 SMS 발신번호

    groups = relationship("Group", back_populates="brand")
    stores = relationship("Store", back_populates="brand")
    admins = relationship("User", back_populates="brand")

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    brand = relationship("Brand", back_populates="groups")
    stores = relationship("Store", back_populates="group")
    admins = relationship("User", back_populates="group")

class Store(Base):
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    brand = relationship("Brand", back_populates="stores")
    is_direct_manage = Column(Boolean, default=False)

    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    description = Column(String, nullable=True)
    is_open = Column(Boolean, default=True)
    notice = Column(String, nullable=True)
    origin_info = Column(String, nullable=True)
    
    owner_name = Column(String, nullable=True)
    business_name = Column(String, nullable=True)
    business_address = Column(String, nullable=True)
    business_number = Column(String, nullable=True)

    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    group = relationship("Group", back_populates="stores")
    owner = relationship("User", back_populates="store")
    categories = relationship("Category", back_populates="store", order_by="Category.order_index")
    tables = relationship("Table", back_populates="store")
    orders = relationship("Order", back_populates="store")
    option_groups = relationship("OptionGroup", back_populates="store")
    operating_hours = relationship("OperatingHour", back_populates="store", cascade="all, delete-orphan")
    holidays = relationship("Holiday", back_populates="store", cascade="all, delete-orphan")
    staff_calls = relationship("StaffCall", back_populates="store", cascade="all, delete-orphan")
    call_options = relationship("CallOption", back_populates="store", cascade="all, delete-orphan")
    # 지점별 기본 가격 할증 (예: 강남점은 500)
    price_markup = Column(Integer, default=0)
    # ✨ [추가] 가맹점 로열티 산출 방식 및 값
    royalty_type = Column(String, default="PERCENTAGE") # "PERCENTAGE" 또는 "FIXED"
    royalty_amount = Column(Float, default=0.0) # 퍼센트 비율(%) 또는 고정금액(원)
    # ✨ [추가] 매장 지역 분류
    region = Column(String, default="미지정")
    # ✨ [신규 추가] 매장의 결제 정책 (PRE_PAY: 선불, POST_PAY: 후불)
    payment_policy = Column(String, default="PRE_PAY")
    use_table_board = Column(Boolean, default=True)
    use_menu_detail = Column(Boolean, default=False) # 상세페이지 사용 여부
    has_pos = Column(Boolean, default=False) # ✨ POS 시스템 사용 여부
    printer_config = Column(String, default="NONE") # NONE, UNIFIED, SEPARATE
    auto_kitchen_print = Column(Boolean, default=False)
    allow_staff_order = Column(Boolean, default=True)
    closing_hour = Column(Integer, default=0)  # 영업 마감 시각 (0=자정, 3=새벽3시)

    # 영수증 프린터 (Printer 1) 연결 설정
    receipt_printer_type = Column(String, default="FILE")   # NETWORK, SERIAL, FILE
    receipt_printer_host = Column(String, default="")        # 네트워크: IP 주소
    receipt_printer_port = Column(String, default="9100")    # 네트워크: 포트 / 시리얼: COM3 등
    receipt_printer_baud = Column(Integer, default=9600)     # 시리얼 전송속도

    # 주방 프린터 (Printer 2) 연결 설정
    kitchen_printer_type = Column(String, default="FILE")
    kitchen_printer_host = Column(String, default="")
    kitchen_printer_port = Column(String, default="9100")
    kitchen_printer_baud = Column(Integer, default=9600)

    # 알림 설정 (PLATFORM: 플랫폼 공용채널 | OWN: 가게 자체채널 | BRAND: 브랜드채널 | DISABLED: 비활성)
    notification_type = Column(String, default="PLATFORM")
    kakao_profile_key = Column(String, nullable=True)   # OWN 타입일 때 가게 자체 프로필 키
    sms_sender_number = Column(String, nullable=True)   # OWN 타입일 때 가게 자체 발신번호

    # 긴급 모드: True이면 선불 결제를 차단하고 후불(현금/카드단말기)로 강제 전환
    is_emergency_mode = Column(Boolean, default=False)

# ⚠️ 2그룹: 예외 (관리자 때문에 nullable=True 유지)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    role = Column(SAEnum(UserRole), default=UserRole.GENERAL_USER)
    
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True) # 예외 허용
    
    brand = relationship("Brand", back_populates="admins")
    group = relationship("Group", back_populates="admins")
    store = relationship("Store", back_populates="owner")

# ✅ 3그룹: 매장 전용 데이터 (nullable=False, index=True 강제)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    name = Column(String)
    description = Column(String, nullable=True)
    order_index = Column(Integer, default=0)
    is_hidden = Column(Boolean, default=False)
    
    store = relationship("Store", back_populates="categories")
    menus = relationship("Menu", back_populates="category", order_by="Menu.order_index", cascade="all, delete-orphan")

class Menu(Base):
    __tablename__ = "menus"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 신규 추가
    category_id = Column(Integer, ForeignKey("categories.id"))
    name = Column(String)
    price = Column(Integer)
    description = Column(String, nullable=True)
    is_sold_out = Column(Boolean, default=False)
    image_url = Column(String, nullable=True)
    order_index = Column(Integer, default=0)
    is_hidden = Column(Boolean, default=False)
    
    category = relationship("Category", back_populates="menus")
    menu_option_links = relationship("MenuOptionLink", back_populates="menu", cascade="all, delete-orphan")
    is_price_fixed = Column(Boolean, default=False) # 본사에서 가격 변경을 금지했는지 여부
    is_tax_exempt = Column(Boolean, default=False)  # 면세 메뉴 여부 (현금영수증 VAT 계산에 사용)

    # 할인 및 타임세일
    is_discounted = Column(Boolean, default=False)
    discount_price = Column(Integer, nullable=True, default=0)
    time_sale_start = Column(String, nullable=True) # 예: "14:00"
    time_sale_end = Column(String, nullable=True)   # 예: "17:00"
    target_time = Column(Integer, default=15) # ✨ 신규: 메뉴별 기본 조리시간 (분)

class OptionGroup(Base):
    __tablename__ = "option_groups"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    name = Column(String)
    is_required = Column(Boolean, default=False)
    is_single_select = Column(Boolean, default=False) 
    order_index = Column(Integer, default=0) 
    max_select = Column(Integer, default=0)
    
    store = relationship("Store", back_populates="option_groups")
    options = relationship("Option", back_populates="group", order_by="Option.order_index")
    menu_links = relationship("MenuOptionLink", back_populates="group")

class Option(Base):
    __tablename__ = "options"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 신규 추가
    group_id = Column(Integer, ForeignKey("option_groups.id"))
    name = Column(String)
    price = Column(Integer)
    order_index = Column(Integer, default=0)
    is_default = Column(Boolean, default=False) 
    
    group = relationship("OptionGroup", back_populates="options")

class MenuOptionLink(Base):
    __tablename__ = "menu_option_links"
    menu_id = Column(Integer, ForeignKey("menus.id"), primary_key=True)
    option_group_id = Column(Integer, ForeignKey("option_groups.id"), primary_key=True)
    order_index = Column(Integer, default=0)
    menu = relationship("Menu", back_populates="menu_option_links")
    group = relationship("OptionGroup", back_populates="menu_links")

class Table(Base):
    __tablename__ = "tables"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False)
    name = Column(String)
    qr_token = Column(String, unique=True, index=True)
    order_type_setting = Column(String, default="SELECTABLE") # 'SELECTABLE', 'DINE_IN_ONLY', 'TAKEOUT_ONLY'
    table_type = Column(String, default="DINE_IN")  # 'DINE_IN' | 'TAKEOUT_COUNTER'

    store = relationship("Store", back_populates="tables")
    orders = relationship("Order", back_populates="table")
    staff_calls = relationship("StaffCall", back_populates="table")
    current_status = Column(String, default="EMPTY")
    occupied_at = Column(DateTime, nullable=True)

class CallOption(Base):
    __tablename__ = "call_options"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    name = Column(String)
    store = relationship("Store", back_populates="call_options")

class OperatingHour(Base):
    __tablename__ = "operating_hours"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    day_of_week = Column(Integer)
    open_time = Column(String, nullable=True)
    close_time = Column(String, nullable=True)
    is_closed = Column(Boolean, default=False)
    # ✨ [핵심] 여러 개의 브레이크 타임을 문자열(JSON) 형태로 한 번에 저장합니다.
    break_time_list = Column(String, default="[]")
    store = relationship("Store", back_populates="operating_hours")

class Holiday(Base):
    __tablename__ = "holidays"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    date = Column(String)
    description = Column(String, nullable=True)
    store = relationship("Store", back_populates="holidays")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    daily_number = Column(Integer, default=1)
    total_price = Column(Integer)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=True)
    
    payment_status = Column(String, default="PENDING") 
    cooking_status = Column(String, default="PENDING")
    target_time = Column(Integer, default=15) # ✨ 신규: 이 주문서의 목표 조리시간 (분)
    payment_method = Column(String, nullable=True)
    imp_uid = Column(String, nullable=True)
    merchant_uid = Column(String, unique=True, nullable=True)
    paid_amount = Column(Integer, default=0)
    order_type = Column(String, default="DINE_IN") # 'DINE_IN', 'TAKEOUT'

    customer_phone = Column(String, nullable=True)  # 포장 알림 수신 전화번호

    # 현금영수증
    cash_receipt_status = Column(String, nullable=True, default="NONE")  # NONE | ISSUED | FAILED | CANCELLED
    cash_receipt_number = Column(String, nullable=True)         # PortOne 승인번호 (receipt_tid)
    cash_receipt_type = Column(String, nullable=True)           # PERSONAL | BUSINESS
    cash_receipt_merchant_uid = Column(String, nullable=True)   # 발급 시 사용한 merchant_uid (취소에 필요)

    store = relationship("Store", back_populates="orders")
    table = relationship("Table", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

    @property
    def table_name(self):
        return self.table.name if self.table else "포장/미지정"

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 신규 추가
    order_id = Column(Integer, ForeignKey("orders.id"))
    menu_name = Column(String)
    price = Column(Integer)
    quantity = Column(Integer)
    options_desc = Column(String, nullable=True)
    is_cancelled = Column(Boolean, default=False)
    original_price = Column(Integer, nullable=True)  # 할인/옵션 적용 전 메뉴 기본 단가
    is_tax_exempt = Column(Boolean, default=False)   # 발주 시점의 면세 여부 (Menu에서 복사)
    order = relationship("Order", back_populates="items")

class StaffCall(Base):
    __tablename__ = "staff_calls"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True, nullable=False) # 🔥 수정됨
    table_id = Column(Integer, ForeignKey("tables.id"))
    message = Column(String, default="직원 호출")
    is_completed = Column(Boolean, default=False)
    created_at = Column(String, default=lambda: str(datetime.now()))
    store = relationship("Store", back_populates="staff_calls")
    table = relationship("Table", back_populates="staff_calls")

    # 응답 스키마(StaffCallResponse)가 table_name을 찾을 때 이걸 돌려줍니다.
    @property
    def table_name(self):
        return self.table.name if self.table else "알 수 없음"

class Notice(Base):
    __tablename__ = "notices"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    target_type = Column(String, nullable=False) 
    target_brand_id = Column(Integer, nullable=True)
    target_store_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class NoticeRead(Base):
    __tablename__ = "notice_reads"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    notice_id = Column(Integer, ForeignKey("notices.id"))
    read_at = Column(DateTime, default=datetime.utcnow)

# ✨ [신규 추가] 시스템 감사 로그 (블랙박스)
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(Integer, nullable=True)
    details = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 누가 했는지 이름을 쉽게 가져오기 위한 연결고리
    user = relationship("User")

# ✨ 신규: 포장 전용 1회용 가상 세션 (직원이 퇴석할 물리적 테이블이 없는 경우 사용)
class VirtualSession(Base):
    __tablename__ = "virtual_sessions"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    token = Column(String, unique=True, index=True) # 1회용 UUID 토큰
    is_active = Column(Boolean, default=True)       # 결제 완료 시 False로 변경하여 즉시 파기
    created_at = Column(DateTime, default=datetime.utcnow)

# ✨ 신규: 홀 테이블 방문 세션 (손님이 QR 스캔 시 발급, 퇴석 시 만료)
class TableSession(Base):
    __tablename__ = "table_sessions"
    id = Column(Integer, primary_key=True, index=True)
    table_id = Column(Integer, ForeignKey("tables.id"), index=True)
    session_token = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    table = relationship("Table")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User")