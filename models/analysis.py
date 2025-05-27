import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, JSON
from . import db


class AnalysisResult(db.Model):
    """分析結果模型"""
    __tablename__ = 'analysis_results'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id = db.Column(UUID(as_uuid=True), db.ForeignKey('recordings.id'), nullable=False, unique=True, index=True)
    transcription = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    confidence_score = db.Column(db.Float, nullable=True)  # 0.0 - 1.0
    language = db.Column(db.String(10), default='zh', nullable=False)
    processing_time = db.Column(db.Float, nullable=True)  # seconds
    provider = db.Column(db.String(50), nullable=False)  # openai, deepgram, etc.
    analysis_metadata = db.Column(JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __init__(self, recording_id, transcription, summary, provider, 
                 confidence_score=None, language='zh', processing_time=None, analysis_metadata=None):
        self.recording_id = recording_id
        self.transcription = transcription
        self.summary = summary
        self.provider = provider
        self.confidence_score = confidence_score
        self.language = language
        self.processing_time = processing_time
        self.analysis_metadata = analysis_metadata or {}
        
    def get_word_count(self):
        """獲取逐字稿字數"""
        return len(self.transcription)
        
    def get_summary_paragraphs(self):
        """獲取摘要段落數"""
        return len(self.summary.split('\n')) if self.summary else 0
        
    def get_confidence_percentage(self):
        """獲取信心度百分比"""
        if self.confidence_score is None:
            return None
        return round(self.confidence_score * 100, 1)
        
    def update_analysis(self, transcription=None, summary=None, confidence_score=None, analysis_metadata=None):
        """更新分析結果"""
        if transcription is not None:
            self.transcription = transcription
        if summary is not None:
            self.summary = summary
        if confidence_score is not None:
            self.confidence_score = confidence_score
        if analysis_metadata is not None:
            self.analysis_metadata.update(analysis_metadata)
            
        self.updated_at = datetime.utcnow()
        db.session.commit()
        
    def to_dict(self):
        """轉換為字典"""
        return {
            'id': str(self.id),
            'recording_id': str(self.recording_id),
            'transcription': self.transcription,
            'summary': self.summary,
            'confidence_score': self.confidence_score,
            'confidence_percentage': self.get_confidence_percentage(),
            'language': self.language,
            'processing_time': self.processing_time,
            'provider': self.provider,
            'word_count': self.get_word_count(),
            'summary_paragraphs': self.get_summary_paragraphs(),
            'analysis_metadata': self.analysis_metadata,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<AnalysisResult for Recording {self.recording_id}>' 