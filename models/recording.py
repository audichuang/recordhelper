import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import Column, String, BigInteger, Float, ForeignKey, Enum as SQLEnum, DateTime, LargeBinary
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON

from . import Base


class RecordingStatus(PyEnum):
    """錄音處理狀態"""
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Recording(Base):
    """錄音模型"""
    __tablename__ = 'recordings'
    
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    audio_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)  # bytes
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)  # seconds
    format: Mapped[str] = mapped_column(String(10), nullable=False)  # mp3, wav, etc.
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)  # audio/mp3, audio/wav, etc.
    status: Mapped[RecordingStatus] = mapped_column(SQLEnum(RecordingStatus, native_enum=False, length=50), default=RecordingStatus.UPLOADING, nullable=False)
    recording_metadata: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 關聯關係
    user: Mapped["User"] = relationship("User", back_populates="recordings", lazy="selectin")
    analysis_result: Mapped["AnalysisResult | None"] = relationship("AnalysisResult", back_populates="recording", uselist=False, cascade="all, delete-orphan", lazy="selectin")
    
    def __init__(self, user_id: uuid.UUID, title: str, original_filename: str, audio_data: bytes, file_size: int, format_str: str, mime_type: str, **kwargs):
        super().__init__(**kwargs)
        self.user_id = user_id
        self.title = title
        self.original_filename = original_filename
        self.audio_data = audio_data
        self.file_size = file_size
        self.format = format_str.lower()
        self.mime_type = mime_type
        self.status = RecordingStatus.UPLOADING
        
    def update_status(self, status: RecordingStatus):
        """更新處理狀態"""
        self.status = status
        
    def set_duration(self, duration: float):
        """設置音頻時長"""
        self.duration = duration
        
    def get_formatted_duration(self) -> str:
        """獲取格式化的時長"""
        if not self.duration:
            return "00:00"
        
        minutes = int(self.duration) // 60
        seconds = int(self.duration) % 60
        return f"{minutes:02d}:{seconds:02d}"
        
    def get_file_size_mb(self) -> float:
        """獲取文件大小（MB）"""
        return round(self.file_size / (1024 * 1024), 2)
        
    def has_analysis(self) -> bool:
        """檢查是否已有分析結果"""
        return self.analysis_result is not None
        
    def to_dict(self, include_analysis: bool = False, include_audio_data: bool = False) -> dict:
        """轉換為字典"""
        result = {
            'id': str(self.id),
            'user_id': str(self.user_id) if self.user_id else None,
            'title': self.title,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'file_size_mb': self.get_file_size_mb(),
            'duration': self.duration,
            'formatted_duration': self.get_formatted_duration(),
            'format': self.format,
            'mime_type': self.mime_type,
            'status': self.status.value if self.status else None,
            'metadata': self.recording_metadata if self.recording_metadata else {},
            'has_analysis': self.has_analysis(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_audio_data:
            result['audio_data'] = self.audio_data
        
        if include_analysis and self.analysis_result:
            result['analysis'] = self.analysis_result.to_dict()
            
        return result
    
    def __repr__(self) -> str:
        return f'<Recording {self.title}>' 