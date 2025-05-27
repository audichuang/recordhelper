import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import UUID, JSON
from . import db


class User(db.Model):
    """用戶模型"""
    __tablename__ = 'users'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    profile_data = db.Column(JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 關聯關係
    recordings = db.relationship('Recording', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.set_password(password)
        
    def set_password(self, password):
        """設置密碼（加密存儲）"""
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        """檢查密碼"""
        return check_password_hash(self.password_hash, password)
        
    def get_statistics(self):
        """獲取用戶統計信息"""
        from .recording import Recording
        from .analysis import AnalysisResult
        
        total_recordings = Recording.query.filter_by(user_id=self.id).count()
        total_duration = db.session.query(db.func.sum(Recording.duration)).filter_by(user_id=self.id).scalar() or 0
        
        # 本月錄音數量
        from datetime import datetime, timedelta
        current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_month_recordings = Recording.query.filter(
            Recording.user_id == self.id,
            Recording.created_at >= current_month_start
        ).count()
        
        # 平均時長
        avg_duration = total_duration / total_recordings if total_recordings > 0 else 0
        
        return {
            'total_recordings': total_recordings,
            'total_duration': total_duration,
            'current_month_recordings': current_month_recordings,
            'avg_duration': avg_duration
        }
    
    def to_dict(self):
        """轉換為字典"""
        return {
            'id': str(self.id),
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'profile_data': self.profile_data,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<User {self.username}>'