import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSON

from . import Base # 從 __init__.py 導入 Base
# from .recording import Recording # 避免循環導入，使用字串引用 "Recording"

class AnalysisResult(Base):
    """分析結果模型"""
    __tablename__ = 'analysis_results'
    
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('recordings.id'), nullable=False, unique=True, index=True)
    transcription: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0 - 1.0
    language: Mapped[str] = mapped_column(String(10), default='zh', nullable=False)
    processing_time: Mapped[float | None] = mapped_column(Float, nullable=True)  # seconds
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # openai, deepgram, etc.
    analysis_metadata: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    
    # 關聯關係
    recording: Mapped["Recording"] = relationship("Recording", back_populates="analysis_result", lazy="selectin")

    def __init__(self, recording_id: uuid.UUID, transcription: str, summary: str, provider: str, 
                 confidence_score: float | None = None, language: str = 'zh', 
                 processing_time: float | None = None, analysis_metadata: dict | None = None, **kwargs):
        super().__init__(**kwargs)
        self.recording_id = recording_id
        self.transcription = transcription
        self.summary = summary
        self.provider = provider
        self.confidence_score = confidence_score
        self.language = language
        self.processing_time = processing_time
        self.analysis_metadata = analysis_metadata or {}
        
    def get_word_count(self) -> int:
        """獲取逐字稿字數"""
        return len(self.transcription)
        
    def get_summary_paragraphs(self) -> int:
        """獲取摘要段落數"""
        return len(self.summary.split('\n')) if self.summary else 0
        
    def get_confidence_percentage(self) -> float | None:
        """獲取信心度百分比"""
        if self.confidence_score is None:
            return None
        return round(self.confidence_score * 100, 1)
        
    def update_analysis(self, transcription: str | None = None, summary: str | None = None, 
                        confidence_score: float | None = None, analysis_metadata: dict | None = None):
        """更新分析結果"""
        if transcription is not None:
            self.transcription = transcription
        if summary is not None:
            self.summary = summary
        if confidence_score is not None:
            self.confidence_score = confidence_score
        if analysis_metadata is not None:
            if self.analysis_metadata is None: # 確保 analysis_metadata 已初始化
                self.analysis_metadata = {}
            self.analysis_metadata.update(analysis_metadata)
            
        # self.updated_at = datetime.now(timezone.utc) # onupdate 會自動處理
        
    def to_dict(self) -> dict:
        """轉換為字典"""
        return {
            'id': str(self.id),
            'recording_id': str(self.recording_id) if self.recording_id else None,
            'transcription': self.transcription,
            'summary': self.summary,
            'confidence_score': self.confidence_score,
            'confidence_percentage': self.get_confidence_percentage(),
            'language': self.language,
            'processing_time': self.processing_time,
            'provider': self.provider,
            'word_count': self.get_word_count(),
            'summary_paragraphs': self.get_summary_paragraphs(),
            'analysis_metadata': self.analysis_metadata if self.analysis_metadata else {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self) -> str:
        """字串表示"""
        return f'<AnalysisResult for Recording {str(self.recording_id)}>' 