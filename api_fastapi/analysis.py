from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models import User, Recording, AnalysisResult, get_async_db_session
from .auth import get_current_user

logger = logging.getLogger(__name__)

# 創建路由器
analysis_router = APIRouter()

# Pydantic 模型
class AnalysisResponse(BaseModel):
    id: str
    recording_id: str
    transcription: str
    summary: str
    provider: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@analysis_router.get("/{recording_id}")
async def get_analysis(
    recording_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """獲取錄音的分析結果"""
    try:
        # 檢查錄音是否存在且屬於當前用戶
        recording_result = await db.execute(
            select(Recording).where(Recording.id == uuid.UUID(recording_id))
        )
        recording = recording_result.scalars().first()
        
        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="錄音不存在"
            )
        
        if recording.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="沒有權限訪問此錄音分析"
            )
        
        # 獲取分析結果
        analysis_result = await db.execute(
            select(AnalysisResult).where(AnalysisResult.recording_id == recording.id)
        )
        analysis = analysis_result.scalars().first()
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="分析結果不存在"
            )
        
        return AnalysisResponse(
            id=str(analysis.id),
            recording_id=str(analysis.recording_id),
            transcription=analysis.transcription,
            summary=analysis.summary,
            provider=analysis.provider or "",
            created_at=analysis.created_at.isoformat() if analysis.created_at else None,
            updated_at=analysis.updated_at.isoformat() if analysis.updated_at else None,
            metadata=analysis.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取分析結果錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取分析結果失敗"
        ) 