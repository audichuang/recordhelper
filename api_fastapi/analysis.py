from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from models.async_models import User, Recording, Analysis
from .auth import get_current_user

logger = logging.getLogger(__name__)

# 創建路由器
analysis_router = APIRouter()

# Pydantic 模型
class AnalysisResponse(BaseModel):
    id: str
    recording_id: str
    transcript: str
    summary: str
    status: str
    created_at: str
    updated_at: str
    metadata: Optional[Dict[str, Any]] = None


@analysis_router.get("/{recording_id}")
async def get_analysis(
    recording_id: str,
    current_user: User = Depends(get_current_user)
):
    """獲取錄音的分析結果"""
    try:
        # 檢查錄音是否存在且屬於當前用戶
        recording = await Recording.get_by_id(recording_id)
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
        analysis = await Analysis.get_by_recording_id(recording_id)
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="分析結果不存在"
            )
        
        return AnalysisResponse(
            id=analysis.id,
            recording_id=analysis.recording_id,
            transcript=analysis.transcript,
            summary=analysis.summary,
            status=analysis.status,
            created_at=analysis.created_at.isoformat(),
            updated_at=analysis.updated_at.isoformat(),
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