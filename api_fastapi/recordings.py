from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import logging
import os
import uuid
import asyncio
from datetime import datetime

from models.async_models import User, Recording, Analysis
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
    duration: Optional[float]
    file_size: int
    status: str
    created_at: datetime
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
    current_user: User = Depends(get_current_user)
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
        recording_id = str(uuid.uuid4())
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
        recording = await Recording.create(
            id=recording_id,
            user_id=current_user.id,
            title=title or f"錄音 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            file_path=file_path,
            file_size=len(content),
            status="uploaded"
        )
        
        # 背景任務處理語音轉文字和摘要
        background_tasks.add_task(
            process_recording_async,
            recording_id,
            file_path
        )
        
        logger.info(f"錄音上傳成功: {recording_id}, 用戶: {current_user.id}")
        
        return UploadResponse(
            message="錄音上傳成功，正在處理中...",
            recording_id=recording_id,
            status="processing"
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
    current_user: User = Depends(get_current_user)
):
    """獲取用戶的錄音列表"""
    try:
        recordings, total = await Recording.get_by_user_paginated(
            user_id=current_user.id,
            page=page,
            per_page=per_page
        )
        
        recording_responses = []
        for recording in recordings:
            # 獲取相關的分析數據
            analysis = await Analysis.get_by_recording_id(recording.id)
            
            recording_responses.append(RecordingResponse(
                id=recording.id,
                title=recording.title,
                file_path=recording.file_path,
                duration=recording.duration,
                file_size=recording.file_size,
                status=recording.status,
                created_at=recording.created_at,
                transcript=analysis.transcript if analysis else None,
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
    current_user: User = Depends(get_current_user)
):
    """獲取特定錄音的詳細信息"""
    try:
        recording = await Recording.get_by_id(recording_id)
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
        analysis = await Analysis.get_by_recording_id(recording_id)
        
        return RecordingResponse(
            id=recording.id,
            title=recording.title,
            file_path=recording.file_path,
            duration=recording.duration,
            file_size=recording.file_size,
            status=recording.status,
            created_at=recording.created_at,
            transcript=analysis.transcript if analysis else None,
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
    current_user: User = Depends(get_current_user)
):
    """刪除錄音"""
    try:
        recording = await Recording.get_by_id(recording_id)
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
        
        # 刪除數據庫記錄
        await recording.delete()
        
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
    """異步處理錄音（語音轉文字 + AI摘要）"""
    try:
        logger.info(f"開始處理錄音: {recording_id}")
        
        # 更新狀態為處理中
        recording = await Recording.get_by_id(recording_id)
        if not recording:
            logger.error(f"錄音不存在: {recording_id}")
            return
        
        await recording.update_status("processing")
        
        # 初始化服務
        config = AppConfig.from_env()
        speech_service = AsyncSpeechToTextService(config)
        ai_service = AsyncGeminiService(config)
        
        # 第一步：語音轉文字
        logger.info(f"開始語音轉文字: {recording_id}")
        transcript_result = await speech_service.transcribe_audio(file_path)
        
        if not transcript_result or not transcript_result.get('transcript'):
            raise Exception("語音轉文字失敗")
        
        transcript = transcript_result['transcript']
        
        # 第二步：生成AI摘要
        logger.info(f"開始生成摘要: {recording_id}")
        summary = await ai_service.generate_summary(transcript)
        
        # 創建或更新分析記錄
        analysis = await Analysis.get_by_recording_id(recording_id)
        if analysis:
            await analysis.update(
                transcript=transcript,
                summary=summary,
                status="completed"
            )
        else:
            await Analysis.create(
                recording_id=recording_id,
                transcript=transcript,
                summary=summary,
                status="completed"
            )
        
        # 更新錄音狀態
        await recording.update_status("completed")
        
        logger.info(f"錄音處理完成: {recording_id}")
        
    except Exception as e:
        logger.error(f"處理錄音錯誤 {recording_id}: {str(e)}")
        
        # 更新錄音狀態為失敗
        try:
            recording = await Recording.get_by_id(recording_id)
            if recording:
                await recording.update_status("failed")
        except Exception as update_error:
            logger.error(f"更新錄音狀態失敗: {update_error}")


@recordings_router.post("/{recording_id}/reprocess")
async def reprocess_recording(
    recording_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """重新處理錄音"""
    try:
        recording = await Recording.get_by_id(recording_id)
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