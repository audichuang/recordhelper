from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any
import logging

from models.async_models import User, Recording
from .auth import get_current_user

logger = logging.getLogger(__name__)

# 創建路由器
users_router = APIRouter()

# Pydantic 模型
class UserProfile(BaseModel):
    id: str
    email: str
    name: str
    created_at: str
    recording_count: int = 0

class UserStatistics(BaseModel):
    total_recordings: int
    total_duration: float
    total_file_size: int
    last_recording_date: str = None


@users_router.get("/profile", response_model=UserProfile)
async def get_user_profile(current_user: User = Depends(get_current_user)):
    """獲取用戶個人資料"""
    try:
        # 獲取錄音數量
        recording_count = await Recording.count_by_user(current_user.id)
        
        return UserProfile(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name,
            created_at=current_user.created_at.isoformat(),
            recording_count=recording_count
        )
        
    except Exception as e:
        logger.error(f"獲取用戶資料錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取用戶資料失敗"
        )


@users_router.get("/statistics", response_model=UserStatistics)
async def get_user_statistics(current_user: User = Depends(get_current_user)):
    """獲取用戶統計數據"""
    try:
        stats = await Recording.get_user_statistics(current_user.id)
        
        return UserStatistics(
            total_recordings=stats.get('total_recordings', 0),
            total_duration=stats.get('total_duration', 0.0),
            total_file_size=stats.get('total_file_size', 0),
            last_recording_date=stats.get('last_recording_date')
        )
        
    except Exception as e:
        logger.error(f"獲取用戶統計錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取統計數據失敗"
        ) 