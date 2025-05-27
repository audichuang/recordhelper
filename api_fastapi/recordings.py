from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
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
class RecordingResponse(BaseModel):
    id: str
    title: str
    file_path: str
    duration: Optional[float] = None
    file_size: int
    status: str
    created_at: str
    transcript: Optional[str] = None
    summary: Optional[str] = None

class RecordingList(BaseModel):
    recordings: List[RecordingResponse]
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
        
        # 生成唯一文件名
        recording_id = uuid.uuid4()
        file_extension = os.path.splitext(file.filename)[1] if file.filename else '.wav'
        filename = f"{recording_id}{file_extension}"
        
        # 確保上傳目錄存在
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        # 保存文件
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as f:
            f.write(content)
        
        # 創建錄音記錄
        recording = Recording(
            user_id=current_user.id,
            title=title or f"錄音 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            original_filename=file.filename,
            file_path=file_path,
            file_size=len(content),
            format_str=file_extension.lstrip('.').lower(),
            status=RecordingStatus.UPLOADING
        )
        
        db.add(recording)
        await db.commit()
        await db.refresh(recording)
        
        # 背景任務處理語音轉文字和摘要
        background_tasks.add_task(
            process_recording_async,
            str(recording.id),
            file_path
        )
        
        logger.info(f"錄音上傳成功: {recording.id}, 用戶: {current_user.id}")
        
        return UploadResponse(
            message="錄音上傳成功，正在處理中...",
            recording_id=str(recording.id),
            status=RecordingStatus.PROCESSING.value
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上傳錄音錯誤: {str(e)}")
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
                file_path=recording.file_path,
                duration=recording.duration,
                file_size=recording.file_size,
                status=recording.status.value if hasattr(recording.status, 'value') else recording.status,
                created_at=recording.created_at.isoformat() if recording.created_at else None,
                transcript=analysis.transcription if analysis else None,
                summary=analysis.summary if analysis else None
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
            file_path=recording.file_path,
            duration=recording.duration,
            file_size=recording.file_size,
            status=recording.status.value if hasattr(recording.status, 'value') else recording.status,
            created_at=recording.created_at.isoformat() if recording.created_at else None,
            transcript=analysis.transcription if analysis else None,
            summary=analysis.summary if analysis else None
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
        
        # 刪除文件
        try:
            if os.path.exists(recording.file_path):
                os.remove(recording.file_path)
        except Exception as e:
            logger.warning(f"刪除文件失敗: {e}")
        
        # 刪除相關的分析結果
        analysis_result = await db.execute(
            select(AnalysisResult).where(AnalysisResult.recording_id == recording.id)
        )
        analysis = analysis_result.scalars().first()
        if analysis:
            await db.delete(analysis)
        
        # 刪除錄音
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


async def process_recording_async(recording_id: str, file_path: str):
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
                logger.error(f"找不到錄音: {recording_id}")
                return
            
            recording.status = RecordingStatus.PROCESSING
            await session.commit()
        
        # 初始化服務
        stt_service = AsyncSpeechToTextService(config)
        ai_service = AsyncGeminiService(config)
        
        # 語音轉文字
        logger.info(f"開始處理錄音 {recording_id} 的語音轉文字")
        result = await stt_service.transcribe_audio(file_path)
        
        # 從結果字典中提取文字和時長
        transcript = result.get('transcript')
        duration = result.get('duration')
        
        if not transcript:
            logger.error(f"語音轉文字失敗: {recording_id}")
            async with async_session() as session:
                result = await session.execute(
                    select(Recording).where(Recording.id == uuid.UUID(recording_id))
                )
                recording = result.scalars().first()
                recording.status = RecordingStatus.FAILED
                await session.commit()
            return
        
        # 生成摘要
        logger.info(f"開始為錄音 {recording_id} 生成摘要")
        summary = await ai_service.generate_summary(transcript)
        
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
        
        logger.info(f"錄音 {recording_id} 處理完成")
        
    except Exception as e:
        logger.error(f"處理錄音時發生錯誤: {e}")
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
            logger.error(f"更新錄音狀態為失敗時發生錯誤: {e2}")
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
            recording_id,
            recording.file_path
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