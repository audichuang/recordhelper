import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy.dialects.postgresql import UUID, JSON
from . import db


class RecordingStatus(Enum):
    """錄音處理狀態"""
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Recording(db.Model):
    """錄音模型"""
    __tablename__ = 'recordings'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)  # bytes
    duration = db.Column(db.Float, nullable=True)  # seconds
    format = db.Column(db.String(10), nullable=False)  # mp3, wav, etc.
    status = db.Column(db.Enum(RecordingStatus), default=RecordingStatus.UPLOADING, nullable=False)
    recording_metadata = db.Column(JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 關聯關係
    analysis_result = db.relationship('AnalysisResult', backref='recording', uselist=False, cascade='all, delete-orphan')
    
    def __init__(self, user_id, title, original_filename, file_path, file_size, format):
        self.user_id = user_id
        self.title = title
        self.original_filename = original_filename
        self.file_path = file_path
        self.file_size = file_size
        self.format = format.lower()
        
    def update_status(self, status: RecordingStatus):
        """更新處理狀態"""
        self.status = status
        self.updated_at = datetime.utcnow()
        db.session.commit()
        
    def set_duration(self, duration: float):
        """設置音頻時長"""
        self.duration = duration
        self.updated_at = datetime.utcnow()
        db.session.commit()
        
    def get_formatted_duration(self):
        """獲取格式化的時長"""
        if not self.duration:
            return "00:00"
        
        minutes = int(self.duration) // 60
        seconds = int(self.duration) % 60
        return f"{minutes:02d}:{seconds:02d}"
        
    def get_file_size_mb(self):
        """獲取文件大小（MB）"""
        return round(self.file_size / (1024 * 1024), 2)
        
    def has_analysis(self):
        """檢查是否已有分析結果"""
        return self.analysis_result is not None
        
    def to_dict(self, include_analysis=False):
        """轉換為字典"""
        result = {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'title': self.title,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'file_size_mb': self.get_file_size_mb(),
            'duration': self.duration,
            'formatted_duration': self.get_formatted_duration(),
            'format': self.format,
            'status': self.status.value,
            'metadata': self.recording_metadata,
            'has_analysis': self.has_analysis(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if include_analysis and self.analysis_result:
            result['analysis'] = self.analysis_result.to_dict()
            
        return result
    
    def __repr__(self):
        return f'<Recording {self.title}>' 