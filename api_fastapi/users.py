# -*- coding: utf-8 -*-
"""
使用者相關 API 路由定義。

此模組包含獲取使用者個人資料、統計數據等與使用者帳號相關的 API 端點。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr # EmailStr 可用於未來擴展，例如在 Profile 中顯示 Email
from typing import Dict, Any, Optional, List # List 可用於未來擴展
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc

from models import User, Recording, get_async_db_session
from .auth import get_current_user

logger = logging.getLogger(__name__)

# 創建路由器
users_router = APIRouter()

# --- Pydantic 回應模型 ---

class UserProfile(BaseModel):
    """
    使用者個人資料回應模型。
    定義了在獲取使用者個人資料時返回的資料結構。
    """
    id: str                     # 使用者 UUID
    email: EmailStr             # 使用者電子郵件
    username: str               # 使用者名稱
    created_at: Optional[str]   # 帳號建立時間 (ISO 格式字串)，可能為 None
    recording_count: int = 0    # 使用者擁有的錄音數量，預設為 0

class UserStatistics(BaseModel):
    """
    使用者統計數據回應模型。
    定義了在獲取使用者相關統計資訊時返回的資料結構。
    """
    total_recordings: int               # 使用者擁有的總錄音數量
    total_duration_seconds: float       # 所有錄音的總時長 (秒)
    total_file_size_bytes: int          # 所有錄音的總檔案大小 (bytes)
    last_recording_date: Optional[str]  # 最近一次錄音的日期 (ISO 格式字串)，如果沒有錄音則為 None

# --- API 端點 ---

@users_router.get("/profile", response_model=UserProfile, summary="獲取目前使用者個人資料", description="返回目前已認證使用者的基本個人資料及其錄音總數。")
async def get_user_profile(
    current_user: User = Depends(get_current_user), # 依賴注入，獲取目前已認證的使用者
    db: AsyncSession = Depends(get_async_db_session)  # 異步資料庫會話依賴
):
    """
    獲取目前已認證使用者的個人資料。

    Args:
        current_user (User): 由 `get_current_user` 依賴注入的目前使用者物件。
        db (AsyncSession): 資料庫會話依賴。

    Returns:
        UserProfile: 包含使用者 ID、電子郵件、使用者名稱、帳號建立時間及錄音總數的個人資料物件。

    Raises:
        HTTPException: 若在查詢過程中發生資料庫錯誤或其他未預期錯誤，則拋出 HTTP 500 錯誤。
    """
    logger.info(f"使用者 {current_user.email} (ID: {current_user.id}) 請求個人資料。")
    try:
        # 計算使用者擁有的錄音數量
        stmt_count_recordings = select(func.count(Recording.id)).where(
            Recording.user_id == current_user.id
        )
        result_count = await db.execute(stmt_count_recordings)
        recording_count = result_count.scalar_one_or_none() or 0 # 若無錄音，scalar_one_or_none 可能返回 None，故用 or 0
        
        logger.debug(f"使用者 {current_user.email} 的錄音數量為: {recording_count}")
        
        return UserProfile(
            id=str(current_user.id), # 將 UUID 轉換為字串
            email=current_user.email,
            username=current_user.username,
            created_at=current_user.created_at.isoformat() if current_user.created_at else None, # 確保 created_at 存在才轉換
            recording_count=recording_count
        )
        
    except Exception as e:
        logger.error(f"獲取使用者 {current_user.email} 個人資料時發生錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="無法獲取使用者個人資料，請稍後再試。"
        )


@users_router.get("/statistics", response_model=UserStatistics, summary="獲取目前使用者統計數據", description="返回目前已認證使用者的錄音相關統計數據，如總錄音數、總時長等。")
async def get_user_statistics(
    current_user: User = Depends(get_current_user), # 依賴注入，獲取目前已認證的使用者
    db: AsyncSession = Depends(get_async_db_session)  # 異步資料庫會話依賴
):
    """
    獲取目前已認證使用者的錄音相關統計數據。

    Args:
        current_user (User): 由 `get_current_user` 依賴注入的目前使用者物件。
        db (AsyncSession): 資料庫會話依賴。

    Returns:
        UserStatistics: 包含總錄音數、總時長 (秒)、總檔案大小 (bytes) 及最近錄音日期的統計物件。

    Raises:
        HTTPException: 若在查詢過程中發生資料庫錯誤或其他未預期錯誤，則拋出 HTTP 500 錯誤。
    """
    logger.info(f"使用者 {current_user.email} (ID: {current_user.id}) 請求統計數據。")
    try:
        # 查詢總錄音數量
        stmt_total_recordings = select(func.count(Recording.id)).where(
            Recording.user_id == current_user.id
        )
        result_total_recordings = await db.execute(stmt_total_recordings)
        total_recordings = result_total_recordings.scalar_one_or_none() or 0
        logger.debug(f"使用者 {current_user.email} 的總錄音數量: {total_recordings}")

        # 查詢總錄音時長 (假設 Recording.duration 儲存的是秒數)
        stmt_total_duration = select(func.sum(Recording.duration)).where(
            Recording.user_id == current_user.id
        )
        result_total_duration = await db.execute(stmt_total_duration)
        total_duration_seconds = result_total_duration.scalar_one_or_none() or 0.0
        logger.debug(f"使用者 {current_user.email} 的總錄音時長: {total_duration_seconds} 秒")

        # 查詢總檔案大小 (假設 Recording.file_size 儲存的是 bytes)
        stmt_total_size = select(func.sum(Recording.file_size)).where(
            Recording.user_id == current_user.id
        )
        result_total_size = await db.execute(stmt_total_size)
        total_file_size_bytes = result_total_size.scalar_one_or_none() or 0
        logger.debug(f"使用者 {current_user.email} 的總檔案大小: {total_file_size_bytes} bytes")
        
        # 查詢最近一次錄音的日期
        stmt_last_recording_date = select(Recording.created_at).where(
            Recording.user_id == current_user.id
        ).order_by(desc(Recording.created_at)).limit(1) # 依創建時間降序排列，取第一個
        
        result_last_date = await db.execute(stmt_last_recording_date)
        last_recording_datetime_obj = result_last_date.scalar_one_or_none() # 可能為 datetime 物件或 None
        
        last_recording_date_iso = None
        if last_recording_datetime_obj:
            last_recording_date_iso = last_recording_datetime_obj.isoformat()
            logger.debug(f"使用者 {current_user.email} 的最近錄音日期: {last_recording_date_iso}")
        else:
            logger.debug(f"使用者 {current_user.email} 尚無錄音記錄。")
            
        return UserStatistics(
            total_recordings=total_recordings,
            total_duration_seconds=total_duration_seconds,
            total_file_size_bytes=total_file_size_bytes,
            last_recording_date=last_recording_date_iso
        )
        
    except Exception as e:
        logger.error(f"獲取使用者 {current_user.email} 統計數據時發生錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="無法獲取使用者統計數據，請稍後再試。"
        )