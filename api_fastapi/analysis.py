# -*- coding: utf-8 -*-
"""
錄音分析結果相關 API 路由定義。

此模組主要負責提供已處理錄音的分析結果，例如語音轉文字的文字稿和 AI 生成的摘要。
"""
from fastapi import APIRouter, HTTPException, Depends, status, Path # Path 用於路徑參數描述
from pydantic import BaseModel, Field # Field 用於更詳細的模型欄位定義
from typing import Optional, Dict, Any, List # List 未直接使用，但保留以備未來擴展
import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models import User, Recording, AnalysisResult, get_async_db_session
from .auth import get_current_user

logger = logging.getLogger(__name__)

# 創建路由器
analysis_router = APIRouter()

# --- Pydantic 資料模型 ---

class AnalysisResponse(BaseModel):
    """
    錄音分析結果回應模型。
    定義了獲取特定錄音分析結果時返回的資料結構。
    """
    id: str = Field(..., description="分析結果的唯一識別碼 (UUID)。")
    recording_id: str = Field(..., description="與此分析相關聯的錄音的唯一識別碼 (UUID)。")
    transcription: Optional[str] = Field(None, description="語音轉文字產生的文字稿。如果處理失敗或無內容，可能為 None。")
    summary: Optional[str] = Field(None, description="AI 生成的摘要內容。如果處理失敗或無內容，可能為 None。")
    provider: Optional[str] = Field(None, description="執行語音轉文字的服務提供者 (例如 'openai', 'google')。")
    model_used: Optional[str] = Field(None, description="用於分析的 AI 模型名稱 (例如 'whisper-1', 'gemini-pro')。") # 新增欄位
    created_at: Optional[str] = Field(None, description="分析結果創建時間 (ISO 8601 格式)。")
    updated_at: Optional[str] = Field(None, description="分析結果最後更新時間 (ISO 8601 格式)。")
    # metadata: Optional[Dict[str, Any]] = Field(None, description="其他與分析相關的元數據 (例如，語言偵測結果、情緒分析等)。") 
    # 暫時移除 metadata，因為 AnalysisResult 模型中沒有此欄位，若未來加入可取消註解

# --- API 端點 ---

@analysis_router.get(
    "/{recording_id}", 
    response_model=AnalysisResponse,
    summary="獲取指定錄音的分析結果",
    description="根據錄音 ID 檢索並返回其語音轉文字稿和 AI 生成的摘要等分析資訊。"
)
async def get_analysis(
    recording_id: str = Path(..., description="要獲取分析結果的錄音的唯一識別碼 (UUID)。"),
    current_user: User = Depends(get_current_user), # 依賴注入，確保使用者已認證
    db: AsyncSession = Depends(get_async_db_session)  # 異步資料庫會話依賴
):
    """
    獲取指定錄音的分析結果。

    在回傳分析結果前，此端點會：
    1.  驗證 `recording_id` 是否對應一個存在的 `Recording` 記錄。
    2.  檢查目前登入的使用者是否有權限訪問該錄音 (即錄音是否屬於該使用者)。
    3.  如果錄音存在且使用者有權限，則查詢關聯的 `AnalysisResult` 記錄。
    4.  如果找到了分析結果，則將其格式化為 `AnalysisResponse` 並返回。

    Args:
        recording_id (str): 要獲取分析結果的錄音的 UUID。
        current_user (User): 目前已認證的使用者物件。
        db (AsyncSession): SQLAlchemy 異步資料庫會話。

    Returns:
        AnalysisResponse: 包含分析結果詳細資訊的回應物件。

    Raises:
        HTTPException:
            - 404 Not Found: 如果錄音或其分析結果不存在。
            - 403 Forbidden: 如果使用者無權限訪問此錄音的分析結果。
            - 400 Bad Request: 如果提供的 `recording_id` 格式無效。
            - 500 Internal Server Error: 如果在查詢過程中發生未預期的資料庫錯誤。
    """
    logger.info(f"使用者 {current_user.email} (ID: {current_user.id}) 請求錄音 ID: {recording_id} 的分析結果。")
    
    try:
        parsed_recording_id = uuid.UUID(recording_id) # 驗證並轉換 recording_id 為 UUID
    except ValueError:
        logger.warning(f"無效的錄音 ID 格式：'{recording_id}'。請求者：{current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"提供的錄音 ID '{recording_id}' 格式無效。請使用有效的 UUID。"
        )

    try:
        # 步驟 1 & 2: 查詢錄音並驗證使用者權限
        stmt_recording = select(Recording).where(Recording.id == parsed_recording_id)
        result_recording = await db.execute(stmt_recording)
        recording = result_recording.scalar_one_or_none()
        
        if not recording:
            logger.warning(f"分析請求失敗：使用者 {current_user.email} 請求的錄音 ID {parsed_recording_id} 未找到。")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ID 為 {parsed_recording_id} 的錄音不存在。"
            )
        
        if recording.user_id != current_user.id:
            logger.warning(f"權限不足：使用者 {current_user.email} (ID: {current_user.id}) 嘗試訪問不屬於他們的錄音 ID {parsed_recording_id} (屬於使用者 ID: {recording.user_id}) 的分析結果。")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您沒有權限訪問此錄音的分析結果。"
            )
        
        # 步驟 3: 查詢分析結果
        stmt_analysis = select(AnalysisResult).where(AnalysisResult.recording_id == parsed_recording_id)
        result_analysis = await db.execute(stmt_analysis)
        analysis = result_analysis.scalar_one_or_none()
        
        if not analysis:
            logger.warning(f"分析結果未找到：錄音 ID {parsed_recording_id} (屬於使用者 {current_user.email}) 尚無分析結果。可能是仍在處理中或處理失敗。")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="此錄音的分析結果不存在或尚未完成。請稍後再試，或檢查錄音狀態。"
            )
        
        # 步驟 4: 格式化並返回回應
        logger.info(f"成功獲取錄音 ID {parsed_recording_id} 的分析結果給使用者 {current_user.email}。")
        return AnalysisResponse(
            id=str(analysis.id),
            recording_id=str(analysis.recording_id),
            transcription=analysis.transcription,
            summary=analysis.summary,
            provider=analysis.provider or "未知", # 提供預設值以防 None
            model_used=analysis.model_used or "未知", # 新增欄位，提供預設值
            created_at=analysis.created_at.isoformat() if analysis.created_at else None,
            updated_at=analysis.updated_at.isoformat() if analysis.updated_at else None,
            # metadata=analysis.metadata # 若 AnalysisResult 模型將來有 metadata 欄位
        )
        
    except HTTPException as http_exc: # 重新拋出已知的 HTTP 例外
        raise http_exc
    except Exception as e:
        logger.error(f"獲取錄音 ID {parsed_recording_id} 的分析結果時發生未預期錯誤 (請求者: {current_user.email}): {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="無法獲取錄音分析結果，請稍後再試。"
        )