import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import Column, String, BigInteger, Float, ForeignKey, Enum as SQLEnum, DateTime, LargeBinary, Text, Boolean, Integer
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON

from . import Base


class RecordingStatus(PyEnum):
    """錄音處理狀態"""
    UPLOADING = "uploading"
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"  # 逐字稿處理中
    TRANSCRIBED = "transcribed"    # 逐字稿完成，摘要處理中
    SUMMARIZING = "summarizing"    # 摘要處理中
    COMPLETED = "completed"        # 全部完成
    FAILED = "failed"


class Recording(Base):
    """錄音模型 - 優化版，整合分析結果"""
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
    
    # 分析結果欄位（整合自 analysis_results 表）
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0 - 1.0
    language: Mapped[str] = mapped_column(String(10), default='zh', nullable=False)
    processing_time: Mapped[float | None] = mapped_column(Float, nullable=True)  # seconds
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)  # openai, deepgram, etc.
    analysis_metadata: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
    srt_content: Mapped[str | None] = mapped_column(Text, nullable=True)  # SRT 格式字幕內容
    has_timestamps: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # 是否有時間戳資料
    timestamps_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 儲存詳細的時間戳資料
    
    # 版本控制欄位
    transcription_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Prompt template 關聯
    prompt_template_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('prompt_templates.id'), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 關聯關係
    user: Mapped["User"] = relationship("User", back_populates="recordings", lazy="selectin")
    analysis_histories: Mapped[list["AnalysisHistory"]] = relationship("AnalysisHistory", back_populates="recording", cascade="all, delete-orphan", lazy="selectin")
    prompt_template: Mapped["PromptTemplate"] = relationship("PromptTemplate", back_populates="recordings", lazy="selectin")
    
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
        return bool(self.transcription or self.summary)
    
    def update_transcription(self, transcription: str, provider: str = None, confidence_score: float = None,
                           processing_time: float = None, metadata: dict = None,
                           srt_content: str = None, has_timestamps: bool = None,
                           timestamps_data: dict = None):
        """更新逐字稿（來自重新生成）"""
        self.transcription = transcription
        self.transcription_version += 1
        if provider:
            self.provider = provider
        if confidence_score is not None:
            self.confidence_score = confidence_score
        if processing_time is not None:
            self.processing_time = processing_time
        if metadata:
            if self.analysis_metadata is None:
                self.analysis_metadata = {}
            self.analysis_metadata.update(metadata)
        if srt_content is not None:
            self.srt_content = srt_content
        if has_timestamps is not None:
            self.has_timestamps = has_timestamps
        if timestamps_data is not None:
            self.timestamps_data = timestamps_data
    
    def update_summary(self, summary: str, provider: str = None, processing_time: float = None, metadata: dict = None):
        """更新摘要（來自重新生成）"""
        self.summary = summary
        self.summary_version += 1
        if provider:
            self.provider = provider
        if processing_time is not None:
            self.processing_time = processing_time
        if metadata:
            if self.analysis_metadata is None:
                self.analysis_metadata = {}
            self.analysis_metadata.update(metadata)
    
    def get_confidence_percentage(self) -> float | None:
        """獲取信心度百分比"""
        if self.confidence_score is None:
            return None
        return round(self.confidence_score * 100, 1)
        
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
        
        if include_analysis:
            result.update({
                'transcription': self.transcription,
                'summary': self.summary,
                'confidence_score': self.confidence_score,
                'confidence_percentage': self.get_confidence_percentage(),
                'language': self.language,
                'processing_time': self.processing_time,
                'provider': self.provider,
                'analysis_metadata': self.analysis_metadata if self.analysis_metadata else {},
                'srt_content': self.srt_content,
                'has_timestamps': self.has_timestamps,
                'timestamps_data': self.timestamps_data if self.timestamps_data else {},
                'transcription_version': self.transcription_version,
                'summary_version': self.summary_version
            })
            
        return result
    
    def __repr__(self) -> str:
        return f'<Recording {self.title}>' 