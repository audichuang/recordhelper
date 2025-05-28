import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Text, Float, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON

from . import Base


class AnalysisType(PyEnum):
    """分析類型"""
    TRANSCRIPTION = "transcription"
    SUMMARY = "summary"


class AnalysisStatus(PyEnum):
    """分析狀態"""
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisHistory(Base):
    """分析歷史模型 - 記錄每次重新生成的逐字稿和摘要"""
    __tablename__ = 'analysis_history'
    
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('recordings.id'), nullable=False, index=True)
    analysis_type: Mapped[AnalysisType] = mapped_column(SQLEnum(AnalysisType, native_enum=False, length=50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AnalysisStatus] = mapped_column(SQLEnum(AnalysisStatus, native_enum=False, length=50), default=AnalysisStatus.PROCESSING, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0 - 1.0
    language: Mapped[str] = mapped_column(String(10), default='zh', nullable=False)
    processing_time: Mapped[float | None] = mapped_column(Float, nullable=True)  # seconds
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # openai, deepgram, gemini, etc.
    version: Mapped[int] = mapped_column(default=1, nullable=False)  # 版本號，每次重新生成遞增
    is_current: Mapped[bool] = mapped_column(default=True, nullable=False)  # 是否為當前使用的版本
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)  # 失敗時的錯誤訊息
    analysis_metadata: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 關聯關係
    recording: Mapped["Recording"] = relationship("Recording", lazy="selectin")

    def __init__(self, recording_id: uuid.UUID, analysis_type: AnalysisType, content: str, 
                 provider: str, version: int = 1, confidence_score: float | None = None, 
                 language: str = 'zh', processing_time: float | None = None, 
                 analysis_metadata: dict | None = None, **kwargs):
        super().__init__(**kwargs)
        self.recording_id = recording_id
        self.analysis_type = analysis_type
        self.content = content
        self.provider = provider
        self.version = version
        self.confidence_score = confidence_score
        self.language = language
        self.processing_time = processing_time
        self.analysis_metadata = analysis_metadata or {}
        self.status = AnalysisStatus.PROCESSING
        self.is_current = True
        
    def mark_as_completed(self):
        """標記為完成"""
        self.status = AnalysisStatus.COMPLETED
        
    def mark_as_failed(self, error_message: str):
        """標記為失敗"""
        self.status = AnalysisStatus.FAILED
        self.error_message = error_message
        
    def set_as_current(self):
        """設置為當前版本"""
        self.is_current = True
        
    def unset_as_current(self):
        """取消當前版本標記"""
        self.is_current = False
        
    def get_word_count(self) -> int:
        """獲取內容字數"""
        return len(self.content)
        
    def get_confidence_percentage(self) -> float | None:
        """獲取信心度百分比"""
        if self.confidence_score is None:
            return None
        return round(self.confidence_score * 100, 1)
        
    def to_dict(self) -> dict:
        """轉換為字典"""
        return {
            'id': str(self.id),
            'recording_id': str(self.recording_id),
            'analysis_type': self.analysis_type.value,
            'content': self.content,
            'status': self.status.value,
            'confidence_score': self.confidence_score,
            'confidence_percentage': self.get_confidence_percentage(),
            'language': self.language,
            'processing_time': self.processing_time,
            'provider': self.provider,
            'version': self.version,
            'is_current': self.is_current,
            'error_message': self.error_message,
            'word_count': self.get_word_count(),
            'analysis_metadata': self.analysis_metadata if self.analysis_metadata else {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self) -> str:
        return f'<AnalysisHistory {self.analysis_type.value} v{self.version} for Recording {str(self.recording_id)}>'