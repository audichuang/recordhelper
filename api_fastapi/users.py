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
    apple_id: Optional[str] = None
    registration_type: str = "email"  # email, apple, google
    full_name: Optional[str] = None

class UserStatistics(BaseModel):
    total_recordings: int
    total_duration: float
    total_file_size: int
    last_recording_date: Optional[str] = None

class AppleBindingRequest(BaseModel):
    user_id: str
    identity_token: str
    authorization_code: str
    email: Optional[str] = None
    full_name: Optional[str] = None


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
        
        # 判斷註冊類型
        registration_type = "email"
        if current_user.apple_id and not current_user.password_hash:
            registration_type = "apple"
        
        return UserProfile(
            id=str(current_user.id),
            email=current_user.email,
            username=current_user.username,
            created_at=current_user.created_at.isoformat() if current_user.created_at else None,
            recording_count=recording_count,
            apple_id=current_user.apple_id,
            registration_type=registration_type,
            full_name=current_user.full_name
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


@users_router.post("/bind-apple")
async def bind_apple_id(
    binding_data: AppleBindingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """綁定 Apple ID 到現有帳號"""
    try:
        # 檢查是否已經有 Apple ID
        if current_user.apple_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="該帳號已綁定 Apple ID"
            )
        
        # 檢查這個 Apple ID 是否已經被其他帳號使用
        existing_user = await db.execute(
            select(User).where(User.apple_id == binding_data.user_id)
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="此 Apple ID 已被其他帳號使用"
            )
        
        # 驗證 identity token（在生產環境中應該要驗證）
        # TODO: 實際驗證 Apple identity token
        
        # 更新用戶資料
        current_user.apple_id = binding_data.user_id
        if binding_data.full_name and not current_user.full_name:
            current_user.full_name = binding_data.full_name
        
        await db.commit()
        await db.refresh(current_user)
        
        return {"message": "Apple ID 綁定成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"綁定 Apple ID 錯誤: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="綁定失敗"
        )


@users_router.delete("/unbind-apple")
async def unbind_apple_id(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """解除綁定 Apple ID"""
    try:
        # 檢查是否有 Apple ID
        if not current_user.apple_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="該帳號未綁定 Apple ID"
            )
        
        # 檢查是否是透過 Apple ID 註冊的帳號（沒有密碼）
        if not current_user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="無法解除綁定：此帳號是透過 Apple ID 註冊，需要保留至少一種登入方式"
            )
        
        # 解除綁定
        current_user.apple_id = None
        
        await db.commit()
        await db.refresh(current_user)
        
        return {"message": "Apple ID 解除綁定成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"解除綁定 Apple ID 錯誤: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="解除綁定失敗"
        ) 