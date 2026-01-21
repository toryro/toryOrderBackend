from pydantic import BaseModel
from typing import List, Optional

# 1. 공통 설정 (ORM 모드 활성화)
class BaseSchema(BaseModel):
    class Config:
        from_attributes = True  # SQLAlchemy 객체를 Pydantic으로 변환 허용

# 2. 메뉴 관련 스키마
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

# 3. 카테고리 관련 스키마
class CategoryBase(BaseSchema):
    name: str

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    menus: List[MenuResponse] = []

# 4. 테이블 관련 스키마
class TableCreate(BaseSchema):
    label: str # 예: "1번 테이블"

class TableResponse(BaseSchema):
    id: int
    label: str
    qr_token: str

# 5. 매장(Store) 관련 스키마
class StoreBase(BaseSchema):
    name: str

class StoreCreate(StoreBase):
    owner_id: int # 임시로 직접 입력 (나중에 로그인 기능 붙이면 자동화)

class StoreResponse(StoreBase):
    id: int
    categories: List[CategoryResponse] = []
    tables: List[TableResponse] = []