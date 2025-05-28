from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc

from models import User, Recording, AnalysisResult, AnalysisHistory, AnalysisType, AnalysisStatus, get_async_db_session
from .auth import get_current_user
from services.audio.speech_to_text_async import AsyncSpeechToTextService
from services.ai.gemini_async import AsyncGeminiService

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

class AnalysisHistoryResponse(BaseModel):
    id: str
    recording_id: str
    analysis_type: str
    content: str
    status: str
    provider: str
    version: int
    is_current: bool
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class RegenerateRequest(BaseModel):
    provider: Optional[str] = None  # 可選擇特定的服務提供者

class RegenerateResponse(BaseModel):
    message: str
    history_id: str
    status: str


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


@analysis_router.post("/{recording_id}/regenerate-transcription")
async def regenerate_transcription(
    recording_id: str,
    background_tasks: BackgroundTasks,
    request: RegenerateRequest = RegenerateRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """重新生成逐字稿"""
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
                detail="沒有權限訪問此錄音"
            )
        
        # 獲取當前最大版本號
        max_version_result = await db.execute(
            select(func.max(AnalysisHistory.version)).where(
                AnalysisHistory.recording_id == recording.id,
                AnalysisHistory.analysis_type == AnalysisType.TRANSCRIPTION
            )
        )
        max_version = max_version_result.scalar() or 0
        new_version = max_version + 1
        
        # 創建新的歷史記錄
        history = AnalysisHistory(
            recording_id=recording.id,
            analysis_type=AnalysisType.TRANSCRIPTION,
            content="",  # 暫時為空，後續填入
            provider=request.provider or "gemini",
            version=new_version,
            is_current=False,  # 暫時設為False，成功後更新
        )
        
        db.add(history)
        await db.commit()
        await db.refresh(history)
        
        # 背景任務處理轉錄
        background_tasks.add_task(
            process_transcription,
            str(history.id),
            recording.audio_data,
            request.provider or "gemini"
        )
        
        return RegenerateResponse(
            message="逐字稿重新生成已開始",
            history_id=str(history.id),
            status="processing"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新生成逐字稿錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重新生成逐字稿失敗"
        )


@analysis_router.post("/{recording_id}/regenerate-summary")
async def regenerate_summary(
    recording_id: str,
    background_tasks: BackgroundTasks,
    request: RegenerateRequest = RegenerateRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """重新生成摘要"""
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
                detail="沒有權限訪問此錄音"
            )
        
        # 檢查是否有當前的逐字稿
        current_analysis = await db.execute(
            select(AnalysisResult).where(AnalysisResult.recording_id == recording.id)
        )
        analysis = current_analysis.scalars().first()
        
        if not analysis or not analysis.transcription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="需要先有逐字稿才能生成摘要"
            )
        
        # 獲取當前最大版本號
        max_version_result = await db.execute(
            select(func.max(AnalysisHistory.version)).where(
                AnalysisHistory.recording_id == recording.id,
                AnalysisHistory.analysis_type == AnalysisType.SUMMARY
            )
        )
        max_version = max_version_result.scalar() or 0
        new_version = max_version + 1
        
        # 創建新的歷史記錄
        history = AnalysisHistory(
            recording_id=recording.id,
            analysis_type=AnalysisType.SUMMARY,
            content="",  # 暫時為空，後續填入
            provider=request.provider or "gemini",
            version=new_version,
            is_current=False,  # 暫時設為False，成功後更新
        )
        
        db.add(history)
        await db.commit()
        await db.refresh(history)
        
        # 背景任務處理摘要生成
        background_tasks.add_task(
            process_summary,
            str(history.id),
            analysis.transcription,
            request.provider or "gemini"
        )
        
        return RegenerateResponse(
            message="摘要重新生成已開始",
            history_id=str(history.id),
            status="processing"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新生成摘要錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重新生成摘要失敗"
        )


@analysis_router.get("/{recording_id}/history")
async def get_analysis_history(
    recording_id: str,
    analysis_type: Optional[str] = None,  # transcription 或 summary
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """獲取分析歷史記錄"""
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
                detail="沒有權限訪問此錄音歷史"
            )
        
        # 構建查詢
        query = select(AnalysisHistory).where(AnalysisHistory.recording_id == recording.id)
        
        if analysis_type:
            if analysis_type == "transcription":
                query = query.where(AnalysisHistory.analysis_type == AnalysisType.TRANSCRIPTION)
            elif analysis_type == "summary":
                query = query.where(AnalysisHistory.analysis_type == AnalysisType.SUMMARY)
        
        query = query.order_by(desc(AnalysisHistory.created_at))
        
        # 執行查詢
        history_result = await db.execute(query)
        histories = history_result.scalars().all()
        
        return [
            AnalysisHistoryResponse(
                id=str(history.id),
                recording_id=str(history.recording_id),
                analysis_type=history.analysis_type.value,
                content=history.content,
                status=history.status.value,
                provider=history.provider,
                version=history.version,
                is_current=history.is_current,
                error_message=history.error_message,
                created_at=history.created_at.isoformat() if history.created_at else None,
                updated_at=history.updated_at.isoformat() if history.updated_at else None
            )
            for history in histories
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取分析歷史錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取分析歷史失敗"
        )


async def process_transcription(history_id: str, audio_data: bytes, provider: str):
    """背景任務：處理轉錄"""
    try:
        from models import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            # 獲取歷史記錄
            history_result = await db.execute(
                select(AnalysisHistory).where(AnalysisHistory.id == uuid.UUID(history_id))
            )
            history = history_result.scalars().first()
            
            if not history:
                logger.error(f"歷史記錄不存在: {history_id}")
                return
            
            # 獲取錄音資料以取得正確的 MIME type
            recording_result = await db.execute(
                select(Recording).where(Recording.id == history.recording_id)
            )
            recording = recording_result.scalars().first()
            mime_type = recording.mime_type if recording and recording.mime_type else "audio/octet-stream"
            
            try:
                # 初始化語音轉文字服務
                from config import AppConfig
                app_config = AppConfig.from_env()
                stt_service = AsyncSpeechToTextService(app_config)
                
                # 執行轉錄
                transcription_result = await stt_service.transcribe_audio_data(
                    audio_data=audio_data,
                    format_type="audio",
                    mime_type=mime_type
                )
                
                # 更新歷史記錄
                history.content = transcription_result.get("transcription", "")
                history.confidence_score = transcription_result.get("confidence")
                history.processing_time = transcription_result.get("processing_time")
                
                # 儲存時間軸資訊到 metadata
                metadata = transcription_result.get("metadata", {})
                if transcription_result.get("has_timeline"):
                    metadata["has_timeline"] = True
                    metadata["timeline_transcript"] = transcription_result.get("timeline_transcript", "")
                    metadata["words"] = transcription_result.get("words", [])
                
                history.analysis_metadata = metadata
                history.mark_as_completed()
                
                # 記錄內容長度以確認有收到轉錄結果
                logger.info(f"設定歷史記錄內容，長度: {len(history.content)}")
                logger.info(f"歷史記錄狀態: {history.status}")
                
                # 將 history 物件加入 session 以確保變更被追蹤
                db.add(history)
                
                # 取消舊的current標記
                old_histories = await db.execute(
                    select(AnalysisHistory).where(
                        AnalysisHistory.recording_id == history.recording_id,
                        AnalysisHistory.analysis_type == AnalysisType.TRANSCRIPTION,
                        AnalysisHistory.is_current == True,
                        AnalysisHistory.id != history.id  # 排除當前記錄
                    )
                )
                for old_history in old_histories.scalars():
                    old_history.unset_as_current()
                    db.add(old_history)  # 確保變更被追蹤
                
                # 設置為當前版本
                history.set_as_current()
                
                # 更新主分析結果
                analysis_result = await db.execute(
                    select(AnalysisResult).where(AnalysisResult.recording_id == history.recording_id)
                )
                analysis = analysis_result.scalars().first()
                
                if analysis:
                    analysis.transcription = history.content
                    analysis.confidence_score = history.confidence_score
                    analysis.processing_time = history.processing_time
                    analysis.provider = history.provider
                    analysis.analysis_metadata = history.analysis_metadata
                    db.add(analysis)  # 確保變更被追蹤
                    logger.info(f"更新分析結果，轉錄長度: {len(analysis.transcription)}")
                
                await db.commit()
                logger.info(f"轉錄完成: {history_id}")
                
            except Exception as e:
                history.mark_as_failed(str(e))
                await db.commit()
                logger.error(f"轉錄失敗: {history_id}, 錯誤: {str(e)}")
                
    except Exception as e:
        logger.error(f"處理轉錄背景任務錯誤: {str(e)}")


async def process_summary(history_id: str, transcription: str, provider: str):
    """背景任務：處理摘要生成"""
    try:
        from models import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            # 獲取歷史記錄
            history_result = await db.execute(
                select(AnalysisHistory).where(AnalysisHistory.id == uuid.UUID(history_id))
            )
            history = history_result.scalars().first()
            
            if not history:
                logger.error(f"歷史記錄不存在: {history_id}")
                return
            
            try:
                # 初始化摘要服務
                from config import AppConfig
                app_config = AppConfig.from_env()
                summary_service = AsyncGeminiService(app_config)
                
                # 執行摘要生成
                summary_text = await summary_service.generate_summary(transcription)
                summary_result = {
                    "summary": summary_text,
                    "processing_time": None,
                    "metadata": {"provider": provider or "gemini"}
                }
                
                # 更新歷史記錄
                history.content = summary_result.get("summary", "")
                history.processing_time = summary_result.get("processing_time")
                history.analysis_metadata = summary_result.get("metadata", {})
                history.mark_as_completed()
                
                # 記錄內容長度以確認有收到摘要結果
                logger.info(f"設定摘要歷史記錄內容，長度: {len(history.content)}")
                
                # 將 history 物件加入 session 以確保變更被追蹤
                db.add(history)
                
                # 取消舊的current標記
                old_histories = await db.execute(
                    select(AnalysisHistory).where(
                        AnalysisHistory.recording_id == history.recording_id,
                        AnalysisHistory.analysis_type == AnalysisType.SUMMARY,
                        AnalysisHistory.is_current == True,
                        AnalysisHistory.id != history.id  # 排除當前記錄
                    )
                )
                for old_history in old_histories.scalars():
                    old_history.unset_as_current()
                    db.add(old_history)  # 確保變更被追蹤
                
                # 設置為當前版本
                history.set_as_current()
                
                # 更新主分析結果
                analysis_result = await db.execute(
                    select(AnalysisResult).where(AnalysisResult.recording_id == history.recording_id)
                )
                analysis = analysis_result.scalars().first()
                
                if analysis:
                    analysis.summary = history.content
                    analysis.processing_time = history.processing_time
                    analysis.provider = history.provider
                    analysis.analysis_metadata = history.analysis_metadata
                    db.add(analysis)  # 確保變更被追蹤
                    logger.info(f"更新分析結果，摘要長度: {len(analysis.summary)}")
                
                await db.commit()
                logger.info(f"摘要生成完成: {history_id}")
                
            except Exception as e:
                history.mark_as_failed(str(e))
                await db.commit()
                logger.error(f"摘要生成失敗: {history_id}, 錯誤: {str(e)}")
                
    except Exception as e:
        logger.error(f"處理摘要生成背景任務錯誤: {str(e)}") 