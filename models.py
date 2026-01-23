# models.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Enum as SAEnum
from sqlalchemy.orm import relationship
from database import Base
import enum

# [안정성] 오타 방지를 위해 문자열 대신 Enum 클래스 사용
class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    GROUP_ADMIN = "GROUP_ADMIN"
    STORE_OWNER = "STORE_OWNER"

# [그룹 테이블] 프랜차이즈 본사 개념
class Group(Base):
    __tablename__ = "groups"
    
    # [속도] id와 name에 index=True를 주어 검색 속도 향상
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    
    # 관계 설정 (그룹이 삭제되면 소속 가게들은 어떻게 할지 정책 필요 - 여기선 유지)
    stores = relationship("Store", back_populates="group")
    admins = relationship("User", back_populates="group")

class Store(Base):
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    
    # [그룹-가게 관계] 그룹은 없을 수도 있음 (nullable=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True, index=True)
    
    group = relationship("Group", back_populates="stores")
    owner = relationship("User", back_populates="store")
    # ... (나머지 관계들)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True) # [속도] 로그인 시 검색하므로 필수 인덱스
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    
    # [안정성] DB에 이상한 문자열이 들어가는 것을 원천 차단
    role = Column(SAEnum(UserRole), default=UserRole.STORE_OWNER)
    
    # [소속] 그룹 관리자용 / 가게 사장님용
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)

    group = relationship("Group", back_populates="admins")
    store = relationship("Store", back_populates="owner")