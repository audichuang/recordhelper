"""
異步資料庫模型
為FastAPI提供完整的異步資料庫操作支援
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from werkzeug.security import generate_password_hash, check_password_hash
import logging

from . import db
from .user import User as SyncUser
from .recording import Recording as SyncRecording, RecordingStatus
from .analysis import AnalysisResult as SyncAnalysisResult

logger = logging.getLogger(__name__)


class AsyncUser:
    """異步用戶模型操作類"""
    
    @staticmethod
    async def create(email: str, password: str, name: str) -> 'AsyncUser':
        """創建新用戶"""
        try:
            # 創建同步模型實例
            user = SyncUser(
                username=name,
                email=email,
                password=password
            )
            
            # 保存到資料庫
            db.session.add(user)
            db.session.commit()
            
            logger.info(f"創建用戶成功: {email}")
            return AsyncUser._from_sync_model(user)
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"創建用戶失敗: {e}")
            raise
    
    @staticmethod
    async def get_by_id(user_id: str) -> Optional['AsyncUser']:
        """根據ID獲取用戶"""
        try:
            user = db.session.get(SyncUser, user_id)
            return AsyncUser._from_sync_model(user) if user else None
        except Exception as e:
            logger.error(f"獲取用戶失敗: {e}")
            return None
    
    @staticmethod
    async def get_by_email(email: str) -> Optional['AsyncUser']:
        """根據email獲取用戶"""
        try:
            user = SyncUser.query.filter_by(email=email).first()
            return AsyncUser._from_sync_model(user) if user else None
        except Exception as e:
            logger.error(f"根據email獲取用戶失敗: {e}")
            return None
    
    @staticmethod
    def _from_sync_model(sync_user: SyncUser) -> 'AsyncUser':
        """從同步模型創建異步包裝器"""
        if not sync_user:
            return None
        
        async_user = AsyncUser()
        async_user.id = str(sync_user.id)
        async_user.username = sync_user.username
        async_user.email = sync_user.email
        async_user.name = sync_user.username  # 為了API一致性
        async_user.password_hash = sync_user.password_hash
        async_user.is_active = sync_user.is_active
        async_user.profile_data = sync_user.profile_data
        async_user.created_at = sync_user.created_at
        async_user.updated_at = sync_user.updated_at
        async_user._sync_model = sync_user
        
        return async_user
    
    def check_password(self, password: str) -> bool:
        """檢查密碼"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'username': self.username,
            'is_active': self.is_active,
            'profile_data': self.profile_data,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class AsyncRecording:
    """異步錄音模型操作類"""
    
    @staticmethod
    async def create(id: str, user_id: str, title: str, file_path: str, 
                    file_size: int, status: str = "uploaded") -> 'AsyncRecording':
        """創建新錄音記錄"""
        try:
            import os
            file_extension = os.path.splitext(file_path)[1][1:] if file_path else 'unknown'
            
            recording = SyncRecording(
                user_id=user_id,
                title=title,
                original_filename=os.path.basename(file_path),
                file_path=file_path,
                file_size=file_size,
                format=file_extension
            )
            recording.id = id
            recording.status = RecordingStatus(status)
            
            db.session.add(recording)
            db.session.commit()
            
            logger.info(f"創建錄音記錄成功: {id}")
            return AsyncRecording._from_sync_model(recording)
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"創建錄音記錄失敗: {e}")
            raise
    
    @staticmethod
    async def get_by_id(recording_id: str) -> Optional['AsyncRecording']:
        """根據ID獲取錄音"""
        try:
            recording = db.session.get(SyncRecording, recording_id)
            return AsyncRecording._from_sync_model(recording) if recording else None
        except Exception as e:
            logger.error(f"獲取錄音失敗: {e}")
            return None
    
    @staticmethod
    async def get_by_user_paginated(user_id: str, page: int = 1, per_page: int = 20) -> Tuple[List['AsyncRecording'], int]:
        """分頁獲取用戶的錄音列表"""
        try:
            # 查詢總數
            total = SyncRecording.query.filter_by(user_id=user_id).count()
            
            # 分頁查詢
            recordings = SyncRecording.query.filter_by(user_id=user_id)\
                .order_by(SyncRecording.created_at.desc())\
                .offset((page - 1) * per_page)\
                .limit(per_page)\
                .all()
            
            async_recordings = [AsyncRecording._from_sync_model(r) for r in recordings]
            
            return async_recordings, total
            
        except Exception as e:
            logger.error(f"獲取用戶錄音列表失敗: {e}")
            return [], 0
    
    @staticmethod
    async def count_by_user(user_id: str) -> int:
        """獲取用戶的錄音數量"""
        try:
            return SyncRecording.query.filter_by(user_id=user_id).count()
        except Exception as e:
            logger.error(f"獲取用戶錄音數量失敗: {e}")
            return 0
    
    @staticmethod
    async def get_user_statistics(user_id: str) -> Dict[str, Any]:
        """獲取用戶統計數據"""
        try:
            recordings = SyncRecording.query.filter_by(user_id=user_id).all()
            
            total_recordings = len(recordings)
            total_duration = sum(r.duration or 0 for r in recordings)
            total_file_size = sum(r.file_size for r in recordings)
            last_recording_date = None
            
            if recordings:
                last_recording = max(recordings, key=lambda r: r.created_at)
                last_recording_date = last_recording.created_at.isoformat()
            
            return {
                'total_recordings': total_recordings,
                'total_duration': total_duration,
                'total_file_size': total_file_size,
                'last_recording_date': last_recording_date
            }
            
        except Exception as e:
            logger.error(f"獲取用戶統計失敗: {e}")
            return {
                'total_recordings': 0,
                'total_duration': 0.0,
                'total_file_size': 0,
                'last_recording_date': None
            }
    
    @staticmethod
    def _from_sync_model(sync_recording: SyncRecording) -> 'AsyncRecording':
        """從同步模型創建異步包裝器"""
        if not sync_recording:
            return None
        
        async_recording = AsyncRecording()
        async_recording.id = str(sync_recording.id)
        async_recording.user_id = str(sync_recording.user_id)
        async_recording.title = sync_recording.title
        async_recording.file_path = sync_recording.file_path
        async_recording.file_size = sync_recording.file_size
        async_recording.duration = sync_recording.duration
        async_recording.status = sync_recording.status.value
        async_recording.created_at = sync_recording.created_at
        async_recording.updated_at = sync_recording.updated_at
        async_recording._sync_model = sync_recording
        
        return async_recording
    
    async def update_status(self, status: str):
        """更新狀態"""
        try:
            if hasattr(self, '_sync_model'):
                self._sync_model.status = RecordingStatus(status)
                self._sync_model.updated_at = datetime.utcnow()
                db.session.commit()
                self.status = status
        except Exception as e:
            db.session.rollback()
            logger.error(f"更新錄音狀態失敗: {e}")
            raise
    
    async def delete(self):
        """刪除錄音"""
        try:
            if hasattr(self, '_sync_model'):
                db.session.delete(self._sync_model)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"刪除錄音失敗: {e}")
            raise


class AsyncAnalysis:
    """異步分析結果模型操作類"""
    
    @staticmethod
    async def create(recording_id: str, transcript: str, summary: str, 
                    status: str = "completed") -> 'AsyncAnalysis':
        """創建新分析結果"""
        try:
            analysis = SyncAnalysisResult(
                recording_id=recording_id,
                transcription=transcript,
                summary=summary,
                provider='fastapi_service'
            )
            
            db.session.add(analysis)
            db.session.commit()
            
            logger.info(f"創建分析結果成功: {recording_id}")
            return AsyncAnalysis._from_sync_model(analysis)
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"創建分析結果失敗: {e}")
            raise
    
    @staticmethod
    async def get_by_recording_id(recording_id: str) -> Optional['AsyncAnalysis']:
        """根據錄音ID獲取分析結果"""
        try:
            analysis = SyncAnalysisResult.query.filter_by(recording_id=recording_id).first()
            return AsyncAnalysis._from_sync_model(analysis) if analysis else None
        except Exception as e:
            logger.error(f"獲取分析結果失敗: {e}")
            return None
    
    @staticmethod
    def _from_sync_model(sync_analysis: SyncAnalysisResult) -> 'AsyncAnalysis':
        """從同步模型創建異步包裝器"""
        if not sync_analysis:
            return None
        
        async_analysis = AsyncAnalysis()
        async_analysis.id = str(sync_analysis.id)
        async_analysis.recording_id = str(sync_analysis.recording_id)
        async_analysis.transcript = sync_analysis.transcription  # 注意字段名稱差異
        async_analysis.summary = sync_analysis.summary
        async_analysis.status = "completed"  # 默認狀態
        async_analysis.created_at = sync_analysis.created_at
        async_analysis.updated_at = sync_analysis.updated_at
        async_analysis.metadata = sync_analysis.analysis_metadata
        async_analysis._sync_model = sync_analysis
        
        return async_analysis
    
    async def update(self, transcript: str = None, summary: str = None, status: str = None):
        """更新分析結果"""
        try:
            if hasattr(self, '_sync_model'):
                if transcript is not None:
                    self._sync_model.transcription = transcript
                    self.transcript = transcript
                if summary is not None:
                    self._sync_model.summary = summary
                    self.summary = summary
                
                self._sync_model.updated_at = datetime.utcnow()
                db.session.commit()
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"更新分析結果失敗: {e}")
            raise


# 為了保持API一致性，創建別名
User = AsyncUser
Recording = AsyncRecording
Analysis = AsyncAnalysis 