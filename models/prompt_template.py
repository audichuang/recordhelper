"""
Prompt Template model for storing AI prompt templates
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from models import Base


class PromptTemplate(Base):
    """Prompt template model for AI analysis customization"""
    __tablename__ = 'prompt_templates'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Template ownership
    is_system_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_user_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="prompt_templates")
    recordings: Mapped[list["Recording"]] = relationship("Recording", back_populates="prompt_template")
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'prompt': self.prompt,
            'is_system_template': self.is_system_template,
            'is_user_default': self.is_user_default,
            'user_id': str(self.user_id) if self.user_id else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f"<PromptTemplate(id={self.id}, name='{self.name}', is_system={self.is_system_template})>"