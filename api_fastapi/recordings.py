from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from typing import Optional, List
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
from services.audio.speech_to_text_async import AsyncSpeechToTextService
from services.ai.gemini_async import AsyncGeminiService
from config import AppConfig

logger = logging.getLogger(__name__)

# 創建路由器
recordings_router = APIRouter()

# Pydantic 模型
class RecordingSummary(BaseModel):
    """錄音摘要信息 - 用於列表顯示"""
    id: str
    title: str
    duration: Optional[float] = None
    file_size: int
    status: str
    created_at: str
    has_transcript: bool = False
    has_summary: bool = False

class RecordingResponse(BaseModel):
    id: str
    title: str
    duration: Optional[float] = None
    file_size: int
    status: str
    created_at: str
    transcript: Optional[str] = None
    summary: Optional[str] = None
    original_filename: str
    format: str
    mime_type: str

class RecordingList(BaseModel):
    recordings: List[RecordingResponse]
    total: int
    page: int
    per_page: int

class RecordingSummaryList(BaseModel):
    """錄音摘要列表 - 輕量級響應"""
    recordings: List[RecordingSummary]
    total: int
    page: int
    per_page: int

class UploadResponse(BaseModel):
    message: str
    recording_id: str
    status: str


@recordings_router.post("/upload", response_model=UploadResponse)
async def upload_recording(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """上傳錄音文件"""
    try:
        # 檢查文件類型
        if not file.content_type or not file.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能上傳音頻文件"
            )
        
        # 檢查文件大小 (100MB限制)
        max_size = 100 * 1024 * 1024  # 100MB
        content = await file.read()
        if len(content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="文件大小超過100MB限制"
            )
        
        # 獲取文件擴展名和MIME類型
        file_extension = os.path.splitext(file.filename)[1] if file.filename else '.wav'
        format_str = file_extension.lstrip('.').lower()
        
        # 確定MIME類型
        mime_type = file.content_type or 'audio/octet-stream'
        
        # 創建錄音記錄，直接將音頻數據存儲到DB
        recording = Recording(
            user_id=current_user.id,
            title=title or f"錄音 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            original_filename=file.filename or f"recording.{format_str}",
            audio_data=content,  # 直接存儲音頻數據
            file_size=len(content),
            format_str=format_str,
            mime_type=mime_type,
            status=RecordingStatus.UPLOADING
        )
        
        db.add(recording)
        await db.commit()
        await db.refresh(recording)
        
        # 背景任務處理語音轉文字和摘要
        # 注意：現在不傳遞文件路徑，而是傳遞錄音ID
        background_tasks.add_task(
            process_recording_async,
            str(recording.id)
        )
        
        logger.info(f"📤 錄音上傳成功: {recording.id}, 用戶: {current_user.id}, 大小: {len(content)/1024/1024:.2f}MB")
        
        return UploadResponse(
            message="錄音上傳成功，正在處理中...",
            recording_id=str(recording.id),
            status=RecordingStatus.PROCESSING.value
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 上傳錄音錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="上傳失敗"
        )


@recordings_router.get("/", response_model=RecordingList)
async def get_recordings(
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """獲取用戶的錄音列表"""
    try:
        # 計算總數
        count_result = await db.execute(
            select(func.count(Recording.id)).where(Recording.user_id == current_user.id)
        )
        total = count_result.scalar() or 0
        
        # 獲取分頁數據
        offset = (page - 1) * per_page
        
        result = await db.execute(
            select(Recording)
            .where(Recording.user_id == current_user.id)
            .order_by(desc(Recording.created_at))
            .offset(offset)
            .limit(per_page)
        )
        
        recordings = result.scalars().all()
        
        recording_responses = []
        for recording in recordings:
            # 獲取相關的分析數據
            analysis_result = await db.execute(
                select(AnalysisResult).where(AnalysisResult.recording_id == recording.id)
            )
            analysis = analysis_result.scalars().first()
            
            recording_responses.append(RecordingResponse(
                id=str(recording.id),
                title=recording.title,
                duration=recording.duration,
                file_size=recording.file_size,
                status=recording.status.value if hasattr(recording.status, 'value') else recording.status,
                created_at=recording.created_at.isoformat() if recording.created_at else None,
                transcript=analysis.transcription if analysis else None,
                summary=analysis.summary if analysis else None,
                original_filename=recording.original_filename,
                format=recording.format,
                mime_type=recording.mime_type
            ))
        
        return RecordingList(
            recordings=recording_responses,
            total=total,
            page=page,
            per_page=per_page
        )
        
    except Exception as e:
        logger.error(f"獲取錄音列表錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取錄音列表失敗"
        )


@recordings_router.get("/summary", response_model=RecordingSummaryList)
async def get_recordings_summary(
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """獲取用戶的錄音摘要列表 - 輕量級響應，不包含完整轉錄和摘要文本"""
    try:
        # 計算總數
        count_result = await db.execute(
            select(func.count(Recording.id)).where(Recording.user_id == current_user.id)
        )
        total = count_result.scalar() or 0
        
        # 獲取分頁數據
        offset = (page - 1) * per_page
        
        result = await db.execute(
            select(Recording)
            .where(Recording.user_id == current_user.id)
            .order_by(desc(Recording.created_at))
            .offset(offset)
            .limit(per_page)
        )
        
        recordings = result.scalars().all()
        
        recording_summaries = []
        for recording in recordings:
            # 檢查是否有分析結果（不需要獲取完整內容）
            analysis_result = await db.execute(
                select(func.count(AnalysisResult.id)).where(AnalysisResult.recording_id == recording.id)
            )
            has_analysis = (analysis_result.scalar() or 0) > 0
            
            # 檢查分析結果是否有轉錄和摘要
            if has_analysis:
                analysis_check = await db.execute(
                    select(
                        func.length(AnalysisResult.transcription).label('transcript_length'),
                        func.length(AnalysisResult.summary).label('summary_length')
                    ).where(AnalysisResult.recording_id == recording.id)
                )
                lengths = analysis_check.first()
                has_transcript = lengths and (lengths.transcript_length or 0) > 0
                has_summary = lengths and (lengths.summary_length or 0) > 0
            else:
                has_transcript = False
                has_summary = False
            
            recording_summaries.append(RecordingSummary(
                id=str(recording.id),
                title=recording.title,
                duration=recording.duration,
                file_size=recording.file_size,
                status=recording.status.value if hasattr(recording.status, 'value') else recording.status,
                created_at=recording.created_at.isoformat() if recording.created_at else None,
                has_transcript=has_transcript,
                has_summary=has_summary
            ))
        
        return RecordingSummaryList(
            recordings=recording_summaries,
            total=total,
            page=page,
            per_page=per_page
        )
        
    except Exception as e:
        logger.error(f"獲取錄音摘要列表錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取錄音摘要列表失敗"
        )


@recordings_router.get("/{recording_id}", response_model=RecordingResponse)
async def get_recording(
    recording_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """獲取特定錄音的詳細信息"""
    try:
        result = await db.execute(
            select(Recording).where(Recording.id == uuid.UUID(recording_id))
        )
        recording = result.scalars().first()
        
        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="錄音不存在"
            )
        
        # 檢查權限
        if recording.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="沒有權限訪問此錄音"
            )
        
        # 獲取分析數據
        analysis_result = await db.execute(
            select(AnalysisResult).where(AnalysisResult.recording_id == recording.id)
        )
        analysis = analysis_result.scalars().first()
        
        return RecordingResponse(
            id=str(recording.id),
            title=recording.title,
            duration=recording.duration,
            file_size=recording.file_size,
            status=recording.status.value if hasattr(recording.status, 'value') else recording.status,
            created_at=recording.created_at.isoformat() if recording.created_at else None,
            transcript=analysis.transcription if analysis else None,
            summary=analysis.summary if analysis else None,
            original_filename=recording.original_filename,
            format=recording.format,
            mime_type=recording.mime_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取錄音詳情錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取錄音詳情失敗"
        )


@recordings_router.delete("/{recording_id}")
async def delete_recording(
    recording_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """刪除錄音"""
    try:
        result = await db.execute(
            select(Recording).where(Recording.id == uuid.UUID(recording_id))
        )
        recording = result.scalars().first()
        
        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="錄音不存在"
            )
        
        # 檢查權限
        if recording.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="沒有權限刪除此錄音"
            )
        
        # 音頻數據現在存儲在DB中，不需要刪除文件
        logger.info(f"🗑️ 刪除錄音 {recording_id}，數據存儲在DB中")
        
        # 刪除相關的分析結果
        analysis_result = await db.execute(
            select(AnalysisResult).where(AnalysisResult.recording_id == recording.id)
        )
        analysis = analysis_result.scalars().first()
        if analysis:
            await db.delete(analysis)
        
        # 刪除錄音（連同音頻數據）
        await db.delete(recording)
        await db.commit()
        
        return {"message": "錄音刪除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刪除錄音錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="刪除錄音失敗"
        )


async def process_recording_async(recording_id: str):
    """異步處理錄音文件（語音轉文字和摘要生成）"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from config import AppConfig
    
    config = AppConfig.from_env()
    engine = create_async_engine(config.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    try:
        # 更新錄音狀態為處理中
        async with async_session() as session:
            result = await session.execute(
                select(Recording).where(Recording.id == uuid.UUID(recording_id))
            )
            recording = result.scalars().first()
            
            if not recording:
                logger.error(f"❓ 找不到錄音: {recording_id}")
                return
            
            recording.status = RecordingStatus.PROCESSING
            await session.commit()
        
        # 初始化服務
        stt_service = AsyncSpeechToTextService(config)
        ai_service = AsyncGeminiService(config)
        
        # 語音轉文字
        logger.info(f"🎙️ 開始處理錄音 {recording_id} 的語音轉文字")
        try:
            result = await stt_service.transcribe_audio_data(
                recording.audio_data, 
                recording.format, 
                recording.mime_type
            )
        except Exception as e:
            logger.error(f"❌ 語音轉文字呼叫失敗: {str(e)}")
            raise
        
        # 從結果字典中提取文字和時長
        transcript = result.get('text')
        duration = result.get('duration')
        
        if not transcript:
            logger.error(f"❌ 語音轉文字失敗: {recording_id}")
            async with async_session() as session:
                result = await session.execute(
                    select(Recording).where(Recording.id == uuid.UUID(recording_id))
                )
                recording = result.scalars().first()
                recording.status = RecordingStatus.FAILED
                await session.commit()
            return
        
        # 生成摘要
        logger.info(f"📝 開始為錄音 {recording_id} 生成摘要")
        try:
            summary = await ai_service.generate_summary(transcript)
        except Exception as e:
            logger.error(f"❌ 摘要生成失敗: {str(e)}")
            summary = "摘要生成失敗，但錄音轉文字成功。請查看逐字稿。"
        
        # 更新數據庫
        async with async_session() as session:
            # 更新錄音記錄
            result = await session.execute(
                select(Recording).where(Recording.id == uuid.UUID(recording_id))
            )
            recording = result.scalars().first()
            
            if recording:
                recording.duration = duration
                recording.status = RecordingStatus.COMPLETED
                await session.commit()
            
            # 創建或更新分析結果
            result = await session.execute(
                select(AnalysisResult).where(AnalysisResult.recording_id == uuid.UUID(recording_id))
            )
            analysis = result.scalars().first()
            
            if analysis:
                analysis.transcription = transcript
                analysis.summary = summary
                analysis.provider = config.speech_to_text_provider
            else:
                analysis = AnalysisResult(
                    recording_id=uuid.UUID(recording_id),
                    transcription=transcript,
                    summary=summary,
                    provider=config.speech_to_text_provider
                )
                session.add(analysis)
            
            await session.commit()
        
        logger.info(f"✅ 錄音 {recording_id} 處理完成")
        
    except Exception as e:
        logger.error(f"❌ 處理錄音時發生錯誤: {e}")
        # 更新錄音狀態為失敗
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(Recording).where(Recording.id == uuid.UUID(recording_id))
                )
                recording = result.scalars().first()
                if recording:
                    recording.status = RecordingStatus.FAILED
                    await session.commit()
        except Exception as e2:
            logger.error(f"❌ 更新錄音狀態為失敗時發生錯誤: {e2}")
    finally:
        await engine.dispose()


@recordings_router.post("/{recording_id}/reprocess")
async def reprocess_recording(
    recording_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """重新處理錄音"""
    try:
        result = await db.execute(
            select(Recording).where(Recording.id == uuid.UUID(recording_id))
        )
        recording = result.scalars().first()
        
        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="錄音不存在"
            )
        
        # 檢查權限
        if recording.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="沒有權限處理此錄音"
            )
        
        # 重新處理
        background_tasks.add_task(
            process_recording_async,
            recording_id
        )
        
        return {"message": "重新處理已開始"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新處理錄音錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重新處理失敗"
        )


@recordings_router.get("/{recording_id}/download")
async def download_recording(
    recording_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """從資料庫下載音頻文件"""
    try:
        result = await db.execute(
            select(Recording).where(Recording.id == uuid.UUID(recording_id))
        )
        recording = result.scalars().first()
        
        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="錄音不存在"
            )
        
        # 檢查權限
        if recording.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="沒有權限下載此錄音"
            )
        
        # 從資料庫讀取音頻數據
        audio_data = recording.audio_data
        
        # 返回音頻數據
        return Response(
            content=audio_data,
            media_type=recording.mime_type,
            headers={"Content-Disposition": f"attachment; filename={recording.original_filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"從資料庫下載音頻文件錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="從資料庫下載音頻文件失敗"
        ) 