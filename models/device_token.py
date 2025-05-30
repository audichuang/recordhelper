"""
設備推送 Token 模型
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from models import Base

class DeviceToken(Base):
    __tablename__ = "device_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String, nullable=False, unique=True)
    platform = Column(String, nullable=False)  # ios, android
    
    # 設備資訊
    device_name = Column(String)
    device_model = Column(String)
    os_version = Column(String)
    app_version = Column(String)
    
    # 狀態
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 關聯
    user = relationship("User", back_populates="device_tokens")
    
    # 索引
    __table_args__ = (
        Index("idx_device_tokens_user_id", "user_id"),
        Index("idx_device_tokens_token", "token"),
        Index("idx_device_tokens_user_platform", "user_id", "platform"),
    )