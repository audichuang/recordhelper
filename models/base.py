import threading
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, Set, Optional
import logging


class AudioProcessingError(Exception):
    """音訊處理錯誤"""
    pass


class APIError(Exception):
    """API 調用錯誤"""
    pass


class SummaryStorage:
    """摘要存儲管理器"""
    
    def __init__(self):
        self.summaries: Dict[str, Dict] = {}
        self.lock = threading.Lock()
    
    def store_summary(self, user_id: str, transcribed_text: str, summary_text: str, 
                     processing_time: float, text_length: int) -> str:
        """存儲摘要並返回ID"""
        with self.lock:
            summary_id = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:12]
            
            self.summaries[summary_id] = {
                'user_id': user_id,
                'transcribed_text': transcribed_text,
                'summary_text': summary_text,
                'processing_time': processing_time,
                'text_length': text_length,
                'created_at': datetime.now(),
                'estimated_minutes': text_length / 180
            }
            
            return summary_id
    
    def get_summary(self, summary_id: str) -> Optional[Dict]:
        """獲取摘要"""
        with self.lock:
            return self.summaries.get(summary_id)
    
    def cleanup_old_summaries(self, hours: int = 24):
        """清理舊摘要"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            expired_ids = [
                sid for sid, info in self.summaries.items()
                if info['created_at'] < cutoff_time
            ]
            
            for sid in expired_ids:
                del self.summaries[sid]
            
            if expired_ids:
                logging.info(f"清理了 {len(expired_ids)} 個過期摘要")


class ProcessingStatus:
    """處理狀態管理器"""

    def __init__(self):
        self.processing_messages: Dict[str, Dict] = {}
        self.completed_messages: Set[str] = set()
        self.lock = threading.Lock()

    def is_processing(self, message_id: str) -> bool:
        """檢查訊息是否正在處理中"""
        with self.lock:
            return message_id in self.processing_messages

    def is_completed(self, message_id: str) -> bool:
        """檢查訊息是否已完成處理"""
        with self.lock:
            return message_id in self.completed_messages

    def start_processing(self, message_id: str, user_id: str) -> bool:
        """開始處理訊息，如果已在處理中則返回False"""
        with self.lock:
            if message_id in self.processing_messages or message_id in self.completed_messages:
                return False

            self.processing_messages[message_id] = {
                'user_id': user_id,
                'start_time': datetime.now(),
                'status': 'started'
            }
            return True

    def update_status(self, message_id: str, status: str):
        """更新處理狀態"""
        with self.lock:
            if message_id in self.processing_messages:
                self.processing_messages[message_id]['status'] = status
                self.processing_messages[message_id]['update_time'] = datetime.now()

    def complete_processing(self, message_id: str, success: bool = True):
        """完成處理"""
        with self.lock:
            if message_id in self.processing_messages:
                del self.processing_messages[message_id]
            self.completed_messages.add(message_id)

    def cleanup_old_records(self, hours: int = 24):
        """清理舊記錄"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            # 清理超時的處理中訊息
            expired_processing = []
            for msg_id, info in self.processing_messages.items():
                if info['start_time'] < cutoff_time:
                    expired_processing.append(msg_id)

            for msg_id in expired_processing:
                del self.processing_messages[msg_id]

            # 保持completed_messages在合理大小內（最近1000條）
            if len(self.completed_messages) > 1000:
                # 簡單的FIFO清理，實際生產環境可能需要更精細的策略
                excess = len(self.completed_messages) - 800
                completed_list = list(self.completed_messages)
                for i in range(excess):
                    self.completed_messages.discard(completed_list[i])


class SummaryStorage:
    """摘要存儲管理器"""
    
    def __init__(self):
        self.summaries: Dict[str, Dict] = {}
        self.lock = threading.Lock()
    
    def store_summary(self, user_id: str, transcribed_text: str, summary_text: str, 
                     processing_time: float, text_length: int) -> str:
        """存儲摘要並返回ID"""
        with self.lock:
            summary_id = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:12]
            
            self.summaries[summary_id] = {
                'user_id': user_id,
                'transcribed_text': transcribed_text,
                'summary_text': summary_text,
                'processing_time': processing_time,
                'text_length': text_length,
                'created_at': datetime.now(),
                'estimated_minutes': text_length / 180
            }
            
            return summary_id
    
    def get_summary(self, summary_id: str) -> Optional[Dict]:
        """獲取摘要"""
        with self.lock:
            return self.summaries.get(summary_id)
    
    def cleanup_old_summaries(self, hours: int = 24):
        """清理舊摘要"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            expired_ids = [
                sid for sid, info in self.summaries.items()
                if info['created_at'] < cutoff_time
            ]
            
            for sid in expired_ids:
                del self.summaries[sid]
            
            if expired_ids:
                import logging
                logging.info(f"清理了 {len(expired_ids)} 個過期摘要") 