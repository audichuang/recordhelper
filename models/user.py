import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import JSON
from passlib.context import CryptContext

from . import Base

# 初始化 passlib context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    """用戶模型"""
    __tablename__ = 'users'
    
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 允許為空以支援 Apple 登入
    apple_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)  # Apple User ID
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 用戶完整姓名
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    profile_data: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 關聯關係
    recordings: Mapped[list["Recording"]] = relationship("Recording", back_populates="user", lazy="selectin", cascade="all, delete-orphan")
    
    def __init__(self, username: str, email: str, password: str = None, **kwargs):
        super().__init__(**kwargs)
        self.username = username
        self.email = email
        if password:
            self.set_password(password)
        # 設定其他屬性（如 apple_id, full_name）
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
    def set_password(self, password: str):
        """設置密碼（加密存儲）"""
        self.password_hash = pwd_context.hash(password)
        
    def check_password(self, password: str) -> bool:
        """檢查密碼"""
        if not self.password_hash:
            return False
        return pwd_context.verify(password, self.password_hash)
        
    def to_dict(self) -> dict:
        """轉換為字典"""
        return {
            'id': str(self.id),
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'profile_data': self.profile_data if self.profile_data else {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'apple_id': self.apple_id,
            'full_name': self.full_name
        }
    
    def __repr__(self) -> str:
        return f'<User {self.username}>'