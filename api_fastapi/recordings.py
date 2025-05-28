# -*- coding: utf-8 -*-
"""
錄音相關 API 路由定義。

此模組處理所有與錄音檔案相關的操作，包括：
- 上傳新的錄音檔案。
- 列出使用者的錄音 (完整資訊或摘要)。
- 獲取特定錄音的詳細資訊。
- 刪除錄音。
- 觸發對錄音的重新處理 (例如，重新進行語音轉文字或 AI 摘要)。
- 下載錄音檔案。

所有端點都依賴使用者認證，並與資料庫互動以存儲和檢索錄音及分析結果。
"""
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, Response # JSONResponse 未在此檔案直接使用，但保持以備不時之需
from pydantic import BaseModel, Field # Field 可用於更詳細的模型欄位定義
from typing import Optional, List, Union # Union 用於可能的聯合類型
import logging
import os
import uuid
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from sqlalchemy.sql import func

from models import User, Recording, AnalysisResult, get_async_db_session, RecordingStatus
from .auth import get_current_user
# from services.audio.speech_to_text_async import AsyncSpeechToTextService # 已移至 recording_processing_service
# from services.ai.gemini_async import AsyncGeminiService # 已移至 recording_processing_service
from services.recording_processing_service import process_recording_async # 導入重構後的處理函數
from config import AppConfig

logger = logging.getLogger(__name__)

# 創建 API 路由器實例
recordings_router = APIRouter()

# --- Pydantic 資料模型 ---

class RecordingSummary(BaseModel):
    """
    錄音摘要資訊模型。
    用於在列表等輕量級場景下顯示錄音的關鍵摘要資訊。
    """
    id: str = Field(..., description="錄音的唯一識別碼 (UUID)。")
    title: str = Field(..., description="錄音標題。")
    duration: Optional[float] = Field(None, description="錄音時長 (秒)。如果尚未處理或處理失敗，可能為 None。")
    file_size: int = Field(..., description="原始錄音檔案的大小 (bytes)。")
    status: str = Field(..., description="錄音目前的處理狀態 (例如：'uploading', 'processing', 'completed', 'failed')。")
    created_at: str = Field(..., description="錄音記錄的創建時間 (ISO 8601 格式)。")
    has_transcript: bool = Field(False, description="指示此錄音是否有可用的文字稿。")
    has_summary: bool = Field(False, description="指示此錄音是否有可用的 AI 摘要。")

class RecordingResponse(BaseModel):
    """
    完整錄音資訊回應模型。
    用於獲取特定錄音的詳細資訊時返回，包含文字稿和摘要 (如果可用)。
    """
    id: str = Field(..., description="錄音的唯一識別碼 (UUID)。")
    title: str = Field(..., description="錄音標題。")
    duration: Optional[float] = Field(None, description="錄音時長 (秒)。")
    file_size: int = Field(..., description="原始錄音檔案的大小 (bytes)。")
    status: str = Field(..., description="錄音目前的處理狀態。")
    created_at: str = Field(..., description="錄音記錄的創建時間 (ISO 8601 格式)。")
    transcript: Optional[str] = Field(None, description="錄音的文字稿內容。如果尚未處理或處理失敗，可能為 None。")
    summary: Optional[str] = Field(None, description="錄音的 AI 摘要內容。如果尚未處理或處理失敗，可能為 None。")
    original_filename: str = Field(..., description="上傳時的原始檔案名稱。")
    format: str = Field(..., description="錄音檔案的格式 (例如 'mp3', 'wav')。")
    mime_type: str = Field(..., description="錄音檔案的 MIME 類型 (例如 'audio/mpeg', 'audio/wav')。")

class RecordingList(BaseModel):
    """
    錄音列表回應模型 (包含完整資訊)。
    用於分頁列出使用者擁有的錄音，每個錄音包含詳細資訊。
    """
    recordings: List[RecordingResponse] = Field(..., description="當前頁次的錄音列表 (完整資訊)。")
    total: int = Field(..., description="符合查詢條件的總錄音數量。")
    page: int = Field(..., description="目前頁碼 (從 1 開始)。")
    per_page: int = Field(..., description="每頁顯示的錄音數量。")

class RecordingSummaryList(BaseModel):
    """
    錄音摘要列表回應模型。
    用於分頁列出使用者擁有的錄音，每個錄音僅包含摘要資訊。
    """
    recordings: List[RecordingSummary] = Field(..., description="當前頁次的錄音摘要列表。")
    total: int = Field(..., description="符合查詢條件的總錄音數量。")
    page: int = Field(..., description="目前頁碼 (從 1 開始)。")
    per_page: int = Field(..., description="每頁顯示的錄音數量。")

class UploadResponse(BaseModel):
    """
    錄音上傳成功後的回應模型。
    """
    message: str = Field(..., description="操作結果的訊息。")
    recording_id: str = Field(..., description="新創建的錄音記錄的唯一識別碼 (UUID)。")
    status: str = Field(..., description="錄音上傳後的初始狀態 (通常表示正在處理中)。")

# --- API 端點 ---

@recordings_router.post(
    "/upload", 
    response_model=UploadResponse, 
    status_code=status.HTTP_202_ACCEPTED, # 202 Accepted 表示請求已接受處理，但尚未完成 (因背景任務)
    summary="上傳新的錄音檔案",
    description="允許使用者上傳音訊檔案。檔案將被儲存，並觸發背景任務進行語音轉文字和 AI 摘要處理。"
)
async def upload_recording(
    background_tasks: BackgroundTasks, # FastAPI 背景任務依賴，用於執行耗時操作
    file: UploadFile = File(..., description="要上傳的音訊檔案。"), # 透過 File(...) 接收上傳的檔案
    title: Optional[str] = Form(None, description="錄音的自訂標題 (可選)。如果未提供，將自動生成。"), # 表單欄位，可選
    current_user: User = Depends(get_current_user), # 依賴注入，獲取目前認證的使用者
    db: AsyncSession = Depends(get_async_db_session), # 異步資料庫會話依賴
    app_config: AppConfig = Depends(lambda: AppConfig.from_env()) # 應用程式設定依賴
):
    """
    處理錄音檔案上傳。

    使用者上傳音訊檔案後，此端點會：
    1.  驗證檔案類型和大小。
    2.  從檔案內容和元資料中提取資訊 (格式、MIME類型等)。
    3.  在資料庫中創建一個新的 `Recording` 記錄，並將音訊數據直接存儲在資料庫中。
    4.  將 `process_recording_async` 函數作為背景任務加入佇列，以進行後續的語音轉文字和 AI 摘要。
    5.  返回一個確認訊息，告知客戶端檔案已接受並正在處理中。

    Args:
        background_tasks (BackgroundTasks): FastAPI 的背景任務執行器。
        file (UploadFile): 使用者上傳的音訊檔案。
        title (Optional[str]): 錄音的選填標題。
        current_user (User): 目前已認證的使用者物件。
        db (AsyncSession): SQLAlchemy 異步資料庫會話。
        app_config (AppConfig): 應用程式的組態設定。

    Returns:
        UploadResponse: 包含成功訊息、新錄音 ID 及初始狀態的回應。

    Raises:
        HTTPException: 
            - 400 Bad Request: 如果上傳的檔案不是音訊格式。
            - 413 Request Entity Too Large: 如果檔案大小超過 `app_config.MAX_FILE_SIZE_MB` 限制。
            - 500 Internal Server Error: 如果在上傳或資料庫操作過程中發生未預期的錯誤。
    """
    logger.info(f"使用者 {current_user.email} (ID: {current_user.id}) 開始上傳檔案：{file.filename}")
    
    # 檢查檔案內容類型是否為音訊
    if not file.content_type or not file.content_type.startswith('audio/'):
        logger.warning(f"上傳失敗：使用者 {current_user.email} 上傳的檔案 '{file.filename}' 類型 '{file.content_type}' 非音訊。")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"檔案類型 '{file.content_type}' 不支援。請上傳有效的音訊檔案。"
        )
    
    # 讀取檔案內容以檢查大小
    content = await file.read() # 讀取檔案內容到記憶體
    max_size_bytes = app_config.MAX_FILE_SIZE_MB * 1024 * 1024 # 從設定轉換 MB 到 bytes
    
    if len(content) > max_size_bytes:
        logger.warning(f"上傳失敗：使用者 {current_user.email} 上傳的檔案 '{file.filename}' 大小 ({len(content)} bytes) 超過限制 ({max_size_bytes} bytes)。")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"檔案大小超過 {app_config.MAX_FILE_SIZE_MB}MB 的限制。"
        )
    
    # 提取檔案資訊
    original_filename = file.filename or "untitled_recording" # 提供預設檔名
    file_extension = os.path.splitext(original_filename)[1] if original_filename else '.dat' # 預設擴展名
    format_str = file_extension.lstrip('.').lower() # 移除點並轉小寫
    mime_type = file.content_type # 已在前面驗證過
    
    # 準備錄音標題
    recording_title = title or f"錄音 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    try:
        # 創建 Recording 物件並存入資料庫
        new_recording = Recording(
            user_id=current_user.id,
            title=recording_title,
            original_filename=original_filename,
            audio_data=content,  # 音訊數據直接存儲
            file_size=len(content),
            format=format_str, # 已更名為 format
            mime_type=mime_type,
            status=RecordingStatus.UPLOADING # 初始狀態，背景任務會更新
        )
        
        db.add(new_recording)
        await db.commit()
        await db.refresh(new_recording) # 刷新以獲取例如 DB 自動產生的 ID
        
        recording_id_str = str(new_recording.id)
        logger.info(f"檔案 '{original_filename}' (新 ID: {recording_id_str}) 已成功儲存至資料庫，大小: {len(content)/1024/1024:.2f}MB。")
        
        # 將錄音處理任務加入背景佇列
        # `process_recording_async` 函數已從 `services.recording_processing_service` 導入
        background_tasks.add_task(
            process_recording_async, 
            recording_id=recording_id_str # 傳遞錄音 ID 給背景任務
        )
        logger.info(f"錄音 ID {recording_id_str} 的背景處理任務已成功加入佇列。")
        
        return UploadResponse(
            message="錄音檔案已成功上傳並開始處理。",
            recording_id=recording_id_str,
            status=RecordingStatus.PROCESSING.value # 前端可預期此狀態
        )
        
    except HTTPException as http_exc: # 重新拋出已知的 HTTP 例外
        raise http_exc
    except Exception as e:
        logger.error(f"上傳錄音檔案 '{file.filename}' 時發生未預期錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="上傳錄音檔案過程中發生伺服器內部錯誤。"
        )

@recordings_router.get(
    "/", 
    response_model=RecordingList, 
    summary="獲取目前使用者的錄音列表 (完整資訊)",
    description="分頁列出目前已認證使用者擁有的所有錄音，並包含每個錄音的完整詳細資訊 (包括文字稿和摘要，如果可用)。"
)
async def get_recordings(
    page: int = Query(1, ge=1, description="請求的頁碼，從 1 開始。"), # 使用 Query 進行參數驗證和描述
    per_page: int = Query(20, ge=1, le=100, description="每頁顯示的錄音數量，介於 1 和 100 之間。"), # 限制每頁數量
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    獲取目前使用者的錄音列表 (包含完整資訊)。

    Args:
        page (int): 請求的頁碼 (預設為 1)。
        per_page (int): 每頁的錄音數量 (預設為 20)。
        current_user (User): 目前已認證的使用者。
        db (AsyncSession): 資料庫會話。

    Returns:
        RecordingList: 包含錄音列表、總數及分頁資訊的回應物件。
    
    Raises:
        HTTPException: 500 Internal Server Error 如果查詢過程中發生錯誤。
    """
    logger.info(f"使用者 {current_user.email} (ID: {current_user.id}) 請求錄音列表：第 {page} 頁，每頁 {per_page} 項。")
    try:
        # 計算符合條件的錄音總數
        count_stmt = select(func.count(Recording.id)).where(Recording.user_id == current_user.id)
        total_recordings_result = await db.execute(count_stmt)
        total = total_recordings_result.scalar_one_or_none() or 0
        logger.debug(f"使用者 {current_user.email} 的錄音總數為: {total}")

        # 計算查詢時的偏移量
        offset = (page - 1) * per_page
        
        # 查詢當前頁次的錄音數據
        recordings_stmt = (
            select(Recording)
            .where(Recording.user_id == current_user.id)
            .order_by(desc(Recording.created_at)) # 按創建時間降序排列
            .offset(offset)
            .limit(per_page)
        )
        recordings_result = await db.execute(recordings_stmt)
        db_recordings = recordings_result.scalars().all()
        
        # 建立回應列表
        recording_responses: List[RecordingResponse] = []
        for rec in db_recordings:
            # 查詢每個錄音對應的分析結果
            analysis_stmt = select(AnalysisResult).where(AnalysisResult.recording_id == rec.id)
            analysis_result = await db.execute(analysis_stmt)
            analysis = analysis_result.scalar_one_or_none() # 每個錄音最多一個分析結果
            
            recording_responses.append(RecordingResponse(
                id=str(rec.id),
                title=rec.title,
                duration=rec.duration,
                file_size=rec.file_size,
                status=rec.status.value if hasattr(rec.status, 'value') else str(rec.status), # 確保狀態是字串
                created_at=rec.created_at.isoformat() if rec.created_at else "",
                transcript=analysis.transcription if analysis else None,
                summary=analysis.summary if analysis else None,
                original_filename=rec.original_filename,
                format=rec.format, # Model 中已為 format
                mime_type=rec.mime_type
            ))
        
        logger.info(f"成功獲取使用者 {current_user.email} 的錄音列表 (第 {page} 頁)，共 {len(recording_responses)} 項。")
        return RecordingList(
            recordings=recording_responses,
            total=total,
            page=page,
            per_page=per_page
        )
        
    except Exception as e:
        logger.error(f"獲取使用者 {current_user.email} 的錄音列表時發生錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="無法獲取錄音列表，請稍後再試。"
        )

@recordings_router.get(
    "/summary", 
    response_model=RecordingSummaryList,
    summary="獲取目前使用者的錄音摘要列表",
    description="分頁列出目前已認證使用者擁有的所有錄音的摘要資訊，用於輕量級列表顯示。"
)
async def get_recordings_summary(
    page: int = Query(1, ge=1, description="請求的頁碼，從 1 開始。"),
    per_page: int = Query(20, ge=1, le=100, description="每頁顯示的錄音摘要數量，介於 1 和 100 之間。"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    獲取目前使用者的錄音摘要列表。
    此端點返回的資訊比 `/` 端點更簡潔，不包含完整的文字稿和 AI 摘要內容，
    適合用於快速概覽或列表展示。

    Args:
        page (int): 請求的頁碼。
        per_page (int): 每頁的錄音摘要數量。
        current_user (User): 目前已認證的使用者。
        db (AsyncSession): 資料庫會話。

    Returns:
        RecordingSummaryList: 包含錄音摘要列表、總數及分頁資訊的回應物件。

    Raises:
        HTTPException: 500 Internal Server Error 如果查詢過程中發生錯誤。
    """
    logger.info(f"使用者 {current_user.email} (ID: {current_user.id}) 請求錄音摘要列表：第 {page} 頁，每頁 {per_page} 項。")
    try:
        # 計算總錄音數
        count_stmt = select(func.count(Recording.id)).where(Recording.user_id == current_user.id)
        total_recordings_result = await db.execute(count_stmt)
        total = total_recordings_result.scalar_one_or_none() or 0
        logger.debug(f"使用者 {current_user.email} 的錄音摘要總數為: {total}")

        offset = (page - 1) * per_page
        
        # 查詢當前頁次的錄音基本資訊
        recordings_stmt = (
            select(Recording)
            .where(Recording.user_id == current_user.id)
            .order_by(desc(Recording.created_at))
            .offset(offset)
            .limit(per_page)
        )
        recordings_result = await db.execute(recordings_stmt)
        db_recordings = recordings_result.scalars().all()
        
        recording_summaries: List[RecordingSummary] = []
        for rec in db_recordings:
            # 檢查此錄音是否有分析結果 (文字稿或摘要)
            # 這裡可以優化：一次查詢所有相關 AnalysisResult，然後在 Python 中匹配，以減少 DB 查詢次數
            # 但為簡化，目前仍為每個錄音單獨查詢
            analysis_check_stmt = (
                select(AnalysisResult.transcription, AnalysisResult.summary)
                .where(AnalysisResult.recording_id == rec.id)
            )
            analysis_check_result = await db.execute(analysis_check_stmt)
            analysis_content = analysis_check_result.first() # first() 返回 Row 或 None
            
            has_transcript = False
            has_summary = False
            if analysis_content:
                # 檢查 transcription 和 summary 是否有實際內容 (非 None且非空字串)
                has_transcript = bool(analysis_content.transcription) 
                has_summary = bool(analysis_content.summary)
            
            recording_summaries.append(RecordingSummary(
                id=str(rec.id),
                title=rec.title,
                duration=rec.duration,
                file_size=rec.file_size,
                status=rec.status.value if hasattr(rec.status, 'value') else str(rec.status),
                created_at=rec.created_at.isoformat() if rec.created_at else "",
                has_transcript=has_transcript,
                has_summary=has_summary
            ))
            
        logger.info(f"成功獲取使用者 {current_user.email} 的錄音摘要列表 (第 {page} 頁)，共 {len(recording_summaries)} 項。")
        return RecordingSummaryList(
            recordings=recording_summaries,
            total=total,
            page=page,
            per_page=per_page
        )
        
    except Exception as e:
        logger.error(f"獲取使用者 {current_user.email} 的錄音摘要列表時發生錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="無法獲取錄音摘要列表，請稍後再試。"
        )

@recordings_router.get(
    "/{recording_id}", 
    response_model=RecordingResponse,
    summary="獲取特定錄音的詳細資訊",
    description="根據提供的錄音 ID，返回該錄音的完整詳細資訊，包括文字稿和 AI 摘要 (如果可用)。"
)
async def get_recording(
    recording_id: str = Path(..., description="要獲取資訊的錄音的唯一識別碼 (UUID)。"), # 使用 Path 進行路徑參數描述
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    獲取特定錄音的詳細資訊。

    Args:
        recording_id (str): 要查詢的錄音的 UUID。
        current_user (User): 目前已認證的使用者。
        db (AsyncSession): 資料庫會話。

    Returns:
        RecordingResponse: 包含錄音詳細資訊的回應物件。

    Raises:
        HTTPException:
            - 404 Not Found: 如果具有指定 ID 的錄音不存在。
            - 403 Forbidden: 如果目前使用者無權限訪問此錄音。
            - 500 Internal Server Error: 如果查詢過程中發生錯誤。
    """
    logger.info(f"使用者 {current_user.email} (ID: {current_user.id}) 請求錄音 ID: {recording_id} 的詳細資訊。")
    try:
        # 查詢錄音基本資訊
        stmt_recording = select(Recording).where(Recording.id == uuid.UUID(recording_id)) # 將 string ID 轉為 UUID
        result_recording = await db.execute(stmt_recording)
        recording = result_recording.scalar_one_or_none()
        
        if not recording:
            logger.warning(f"使用者 {current_user.email} 請求的錄音 ID {recording_id} 未找到。")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ID 為 {recording_id} 的錄音不存在。"
            )
        
        # 驗證使用者是否有權限訪問此錄音
        if recording.user_id != current_user.id:
            logger.warning(f"使用者 {current_user.email} (ID: {current_user.id}) 嘗試訪問不屬於他們的錄音 ID {recording_id} (屬於使用者 ID: {recording.user_id})。")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您沒有權限訪問此錄音的詳細資訊。"
            )
        
        # 查詢關聯的分析結果
        stmt_analysis = select(AnalysisResult).where(AnalysisResult.recording_id == recording.id)
        result_analysis = await db.execute(stmt_analysis)
        analysis = result_analysis.scalar_one_or_none()
        
        logger.info(f"成功獲取錄音 ID {recording_id} 的詳細資訊給使用者 {current_user.email}。")
        return RecordingResponse(
            id=str(recording.id),
            title=recording.title,
            duration=recording.duration,
            file_size=recording.file_size,
            status=recording.status.value if hasattr(recording.status, 'value') else str(recording.status),
            created_at=recording.created_at.isoformat() if recording.created_at else "",
            transcript=analysis.transcription if analysis else None,
            summary=analysis.summary if analysis else None,
            original_filename=recording.original_filename,
            format=recording.format,
            mime_type=recording.mime_type
        )
        
    except HTTPException as http_exc: # 重新拋出已知的 HTTP 例外
        raise http_exc
    except ValueError: # UUID 轉換失敗
        logger.warning(f"提供的錄音 ID '{recording_id}' 格式無效 (非 UUID)。")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"錄音 ID '{recording_id}' 格式無效。")
    except Exception as e:
        logger.error(f"獲取錄音 ID {recording_id} 詳細資訊時發生錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="無法獲取錄音詳細資訊，請稍後再試。"
        )

@recordings_router.delete(
    "/{recording_id}",
    status_code=status.HTTP_204_NO_CONTENT, # 成功刪除後通常返回 204 No Content
    summary="刪除指定的錄音",
    description="永久刪除使用者擁有的特定錄音及其相關的分析結果。此操作不可逆。"
)
async def delete_recording(
    recording_id: str = Path(..., description="要刪除的錄音的唯一識別碼 (UUID)。"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    刪除指定的錄音及其相關的分析結果。

    Args:
        recording_id (str): 要刪除的錄音的 UUID。
        current_user (User): 目前已認證的使用者。
        db (AsyncSession): 資料庫會話。

    Returns:
        Response: HTTP 204 No Content 表示成功刪除。
                 (FastAPI 在 response_model=None 且狀態碼為 204 時會自動這樣處理)
                 或者可以返回一個 MessageResponse 如 {"message": "錄音刪除成功"} 並使用 200 OK。
                 此處選擇 204 以符合 RESTful 實踐。

    Raises:
        HTTPException:
            - 404 Not Found: 如果具有指定 ID 的錄音不存在。
            - 403 Forbidden: 如果目前使用者無權限刪除此錄音。
            - 500 Internal Server Error: 如果刪除過程中發生錯誤。
    """
    logger.info(f"使用者 {current_user.email} (ID: {current_user.id}) 請求刪除錄音 ID: {recording_id}。")
    try:
        # 查詢要刪除的錄音
        stmt_recording = select(Recording).where(Recording.id == uuid.UUID(recording_id))
        result_recording = await db.execute(stmt_recording)
        recording_to_delete = result_recording.scalar_one_or_none()
        
        if not recording_to_delete:
            logger.warning(f"刪除失敗：使用者 {current_user.email} 請求刪除的錄音 ID {recording_id} 未找到。")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ID 為 {recording_id} 的錄音不存在，無法刪除。"
            )
        
        # 驗證使用者權限
        if recording_to_delete.user_id != current_user.id:
            logger.warning(f"刪除失敗：使用者 {current_user.email} (ID: {current_user.id}) 嘗試刪除不屬於他們的錄音 ID {recording_id} (屬於使用者 ID: {recording_to_delete.user_id})。")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您沒有權限刪除此錄音。"
            )
        
        # 刪除與此錄音相關的所有分析結果 (AnalysisResult)
        # 雖然 SQLAlchemy 的級聯刪除 (cascade) 可以處理這個，但明確刪除更安全
        stmt_delete_analysis = AnalysisResult.__table__.delete().where(AnalysisResult.recording_id == recording_to_delete.id)
        await db.execute(stmt_delete_analysis)
        logger.debug(f"已刪除錄音 ID {recording_id} 的相關分析結果。")
        
        # 刪除錄音本身 (包含 audio_data)
        await db.delete(recording_to_delete)
        await db.commit() # 提交所有刪除操作
        
        logger.info(f"使用者 {current_user.email} 成功刪除錄音 ID {recording_id} 及其相關數據。")
        # 對於 DELETE 操作，成功時通常返回 204 No Content，不需要回應主體。
        # FastAPI 會自動處理，如果 response_model=None 且狀態碼是 204。
        # 或者，如果需要返回訊息，可以取消註解下一行並更改狀態碼。
        # return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "錄音及其相關分析結果已成功刪除。"})
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException as http_exc:
        raise http_exc
    except ValueError: # UUID 轉換失敗
        logger.warning(f"提供的錄音 ID '{recording_id}' 格式無效 (非 UUID) 無法刪除。")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"錄音 ID '{recording_id}' 格式無效。")
    except Exception as e:
        logger.error(f"刪除錄音 ID {recording_id} 時發生錯誤: {str(e)}", exc_info=True)
        await db.rollback() # 發生錯誤時回滾事務
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="刪除錄音過程中發生內部錯誤。"
        )


# 註解：process_recording_async 函數已成功移至 services.recording_processing_service.py
# 並已在上方透過 `from services.recording_processing_service import process_recording_async` 導入。

@recordings_router.post(
    "/{recording_id}/reprocess", 
    status_code=status.HTTP_202_ACCEPTED, # 請求已接受，處理將在背景進行
    response_model=MessageResponse, # 返回簡單訊息
    summary="重新處理指定的錄音", 
    description="觸發對指定錄音檔案的異步語音轉文字和 AI 摘要的重新處理流程。"
)
async def reprocess_recording(
    recording_id: str = Path(..., description="要重新處理的錄音的唯一識別碼 (UUID)。"),
    background_tasks: BackgroundTasks, # FastAPI 背景任務執行器
    current_user: User = Depends(get_current_user), # 目前已認證的使用者
    db: AsyncSession = Depends(get_async_db_session) # 資料庫會話
):
    """
    重新處理指定的錄音檔案。

    此端點允許使用者請求對一個已存在的錄音進行重新處理。這在以下情況可能有用：
    - 先前的處理因暫時性問題而失敗。
    - 更新了語音轉文字或 AI 摘要的模型，希望使用新模型重新生成結果。
    - 使用者想要強制刷新分析結果。

    處理流程：
    1. 驗證錄音 ID 是否有效，並從資料庫中查詢對應的 `Recording` 物件。
    2. 檢查目前登入的使用者是否有權限對此錄音進行操作。
    3. 如果錄音存在且使用者有權限，則將 `process_recording_async` 函數
       (從 `services.recording_processing_service` 導入) 作為背景任務添加到 FastAPI 的 `BackgroundTasks` 中。
    4. 返回一個確認訊息，告知使用者重新處理請求已提交。實際處理將在背景中異步進行。

    注意：此操作不會立即返回處理結果。使用者可以稍後透過查詢錄音狀態或詳情來獲取處理進度或結果。

    Args:
        recording_id (str): 要重新處理的錄音的 UUID。
        background_tasks (BackgroundTasks): FastAPI 背景任務執行器。
        current_user (User): 目前已認證的使用者。
        db (AsyncSession): 資料庫會話。

    Returns:
        MessageResponse: 確認重新處理請求已提交的訊息。

    Raises:
        HTTPException:
            - 404 Not Found: 如果錄音不存在。
            - 403 Forbidden: 如果使用者無權限操作此錄音。
            - 400 Bad Request: 如果錄音 ID 格式無效。
            - 500 Internal Server Error: 如果在啟動重新處理過程中發生未預期錯誤。
    """
    logger.info(f"使用者 {current_user.email} (ID: {current_user.id}) 請求重新處理錄音 ID: {recording_id}。")
    try:
        # 根據 ID 查詢錄音記錄
        stmt = select(Recording).where(Recording.id == uuid.UUID(recording_id))
        result = await db.execute(stmt)
        recording_to_reprocess = result.scalar_one_or_none()
        
        if not recording_to_reprocess:
            logger.warning(f"重新處理請求失敗：使用者 {current_user.email} 請求的錄音 ID {recording_id} 未找到。")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ID 為 {recording_id} 的錄音不存在，無法重新處理。"
            )
        
        # 檢查使用者權限
        if recording_to_reprocess.user_id != current_user.id:
            logger.warning(f"重新處理請求失敗：使用者 {current_user.email} (ID: {current_user.id}) 無權限操作錄音 ID {recording_id} (屬於使用者 ID: {recording_to_reprocess.user_id})。")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您沒有權限重新處理此錄音。"
            )
        
        # 考慮：是否要在這裡將錄音狀態改為 PENDING_REPROCESSING 或類似狀態？
        # recording_to_reprocess.status = RecordingStatus.PENDING_REPROCESSING # 或 PROCESSING
        # db.add(recording_to_reprocess)
        # await db.commit()
        # logger.info(f"錄音 ID {recording_id} 狀態已更新，準備重新處理。")

        # 將 process_recording_async 加入背景任務
        background_tasks.add_task(
            process_recording_async, 
            recording_id=str(recording_to_reprocess.id) # 確保傳遞的是字串 ID
        )
        
        logger.info(f"錄音 ID {recording_id} 的重新處理任務已成功加入背景佇列。")
        return MessageResponse(message="重新處理請求已提交，將在背景中進行。")
        
    except HTTPException as http_exc:
        raise http_exc
    except ValueError: # UUID 轉換失敗
        logger.warning(f"提供的錄音 ID '{recording_id}' 格式無效 (非 UUID) 無法重新處理。")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"錄音 ID '{recording_id}' 格式無效。")
    except Exception as e:
        logger.error(f"啟動錄音 ID {recording_id} 的重新處理時發生未預期錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="啟動重新處理失敗，請稍後再試。"
        )

@recordings_router.get(
    "/{recording_id}/download",
    response_class=Response, # 直接使用 Response 以便更精確控制標頭和內容類型
    summary="下載指定的錄音檔案", 
    description="允許使用者下載其實際上傳的原始音頻檔案。檔案數據直接從資料庫中讀取。"
)
async def download_recording(
    recording_id: str = Path(..., description="要下載的錄音的唯一識別碼 (UUID)。"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    從資料庫下載指定的音頻文件。

    此端點提供使用者下載先前上傳的原始音頻檔案的功能。
    檔案數據直接從資料庫中的 `Recording.audio_data` 欄位讀取。

    處理流程：
    1. 根據提供的 `recording_id` (UUID 字串) 從資料庫查詢 `Recording` 物件。
    2. 如果找不到對應的錄音記錄，返回 404 Not Found。
    3. 驗證目前登入的使用者是否有權限下載此錄音 (即錄音是否屬於該使用者)。若無權限，返回 403 Forbidden。
    4. 如果錄音的 `audio_data` 為空，返回 500 Internal Server Error，表示數據遺失。
    5. 使用 FastAPI 的 `Response` 物件將音頻數據作為檔案下載返回給客戶端。
        - `media_type` 設置為錄音的 MIME 類型 (例如 'audio/wav', 'audio/mpeg')。
        - `Content-Disposition` 標頭設置為 'attachment'，並指定原始檔名，以提示瀏覽器下載檔案。

    Args:
        recording_id (str): 要下載的錄音的 UUID。
        current_user (User): 目前已認證的使用者。
        db (AsyncSession): 資料庫會話。

    Returns:
        Response: 包含音頻數據的檔案下載回應。

    Raises:
        HTTPException:
            - 404 Not Found: 如果錄音不存在。
            - 403 Forbidden: 如果使用者無權限下載此錄音。
            - 400 Bad Request: 如果錄音 ID 格式無效。
            - 500 Internal Server Error: 如果錄音數據遺失或發生其他內部錯誤。
    """
    logger.info(f"使用者 {current_user.email} (ID: {current_user.id}) 請求下載錄音 ID: {recording_id}。")
    try:
        # 查詢錄音記錄
        stmt = select(Recording).where(Recording.id == uuid.UUID(recording_id))
        result = await db.execute(stmt)
        recording_to_download = result.scalar_one_or_none()
        
        if not recording_to_download:
            logger.warning(f"下載請求失敗：使用者 {current_user.email} 請求的錄音 ID {recording_id} 未找到。")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ID 為 {recording_id} 的錄音不存在。"
            )
        
        # 驗證使用者權限
        if recording_to_download.user_id != current_user.id:
            logger.warning(f"下載請求失敗：使用者 {current_user.email} (ID: {current_user.id}) 無權限下載錄音 ID {recording_id} (屬於使用者 ID: {recording_to_download.user_id})。")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您沒有權限下載此錄音檔案。"
            )
        
        # 檢查音訊數據是否存在
        if not recording_to_download.audio_data:
            logger.error(f"下載失敗：錄音 ID {recording_id} (屬於使用者 {current_user.email}) 在資料庫中沒有有效的音頻數據。")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, # 或 404 ถ้า認為數據遺失等同於資源不可用
                detail="錄音的音頻數據遺失或損毀，無法提供下載。"
            )
            
        # 準備下載回應
        filename_to_serve = recording_to_download.original_filename or f"{recording_id}.dat" # 提供預設檔名
        media_type_to_serve = recording_to_download.mime_type or 'application/octet-stream' # 提供預設 MIME 類型
        
        logger.info(f"準備為使用者 {current_user.email} 下載錄音 ID {recording_id}，檔案名: '{filename_to_serve}'，MIME類型: {media_type_to_serve}，大小: {recording_to_download.file_size} bytes。")
        return Response(
            content=recording_to_download.audio_data,
            media_type=media_type_to_serve,
            headers={
                # 確保檔名中的特殊字元被正確處理，並提示瀏覽器下載
                "Content-Disposition": f"attachment; filename=\"{filename_to_serve.replace('\"', '_')}\"" 
            }
        )
        
    except HTTPException as http_exc:
        raise http_exc
    except ValueError: # UUID 轉換失敗
        logger.warning(f"提供的錄音 ID '{recording_id}' 格式無效 (非 UUID) 無法下載。")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"錄音 ID '{recording_id}' 格式無效。")
    except Exception as e:
        logger.error(f"下載錄音 ID {recording_id} 時發生未預期錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="下載錄音檔案時發生內部錯誤。"
        )