from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc

from models import User, Recording, get_async_db_session
from .auth import get_current_user

logger = logging.getLogger(__name__)

# 創建路由器
users_router = APIRouter()

# Pydantic 模型
class UserProfile(BaseModel):
    id: str
    email: str
    username: str
    created_at: str
    recording_count: int = 0

class UserStatistics(BaseModel):
    total_recordings: int
    total_duration: float
    total_file_size: int
    last_recording_date: Optional[str] = None


@users_router.get("/profile", response_model=UserProfile)
async def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """獲取用戶個人資料"""
    try:
        # 獲取錄音數量
        result = await db.execute(
            select(func.count()).select_from(Recording).where(
                Recording.user_id == current_user.id
            )
        )
        recording_count = result.scalar() or 0
        
        return UserProfile(
            id=str(current_user.id),
            email=current_user.email,
            username=current_user.username,
            created_at=current_user.created_at.isoformat() if current_user.created_at else None,
            recording_count=recording_count
        )
        
    except Exception as e:
        logger.error(f"獲取用戶資料錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取用戶資料失敗"
        )


@users_router.get("/statistics", response_model=UserStatistics)
async def get_user_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """獲取用戶統計數據"""
    try:
        # 獲取總錄音數量
        count_result = await db.execute(
            select(func.count()).select_from(Recording).where(
                Recording.user_id == current_user.id
            )
        )
        total_recordings = count_result.scalar() or 0
        
        # 獲取總時長
        duration_result = await db.execute(
            select(func.sum(Recording.duration)).where(
                Recording.user_id == current_user.id
            )
        )
        total_duration = duration_result.scalar() or 0.0
        
        # 獲取總檔案大小
        size_result = await db.execute(
            select(func.sum(Recording.file_size)).where(
                Recording.user_id == current_user.id
            )
        )
        total_file_size = size_result.scalar() or 0
        
        # 獲取最近錄音日期
        date_result = await db.execute(
            select(Recording.created_at).where(
                Recording.user_id == current_user.id
            ).order_by(desc(Recording.created_at)).limit(1)
        )
        last_recording = date_result.scalars().first()
        last_recording_date = last_recording.created_at.isoformat() if last_recording and last_recording.created_at else None
        
        return UserStatistics(
            total_recordings=total_recordings,
            total_duration=total_duration,
            total_file_size=total_file_size,
            last_recording_date=last_recording_date
        )
        
    except Exception as e:
        logger.error(f"獲取用戶統計錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取統計數據失敗"
        ) 