from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, Any
import logging

from services.audio.speech_to_text_async import AsyncSpeechToTextService
from services.ai.gemini_async import AsyncGeminiService
from config import AppConfig

logger = logging.getLogger(__name__)

# 創建路由器
system_router = APIRouter()

# Pydantic 模型
class SystemStatus(BaseModel):
    status: str
    version: str
    services: Dict[str, Any]


@system_router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """獲取系統狀態"""
    try:
        config = AppConfig.from_env()
        
        # 檢查語音轉文字服務
        speech_service = AsyncSpeechToTextService(config)
        speech_status = await speech_service.get_service_status()
        
        # 檢查AI服務
        ai_service = AsyncGeminiService(config)
        ai_status = await ai_service.check_status()
        
        return SystemStatus(
            status="healthy",
            version="2.0.0-fastapi",
            services={
                "speech_to_text": speech_status,
                "ai_summary": ai_status,
                "database": {"available": True, "status": "connected"},
                "line_bot": {
                    "available": bool(config.line_channel_access_token and config.line_channel_secret),
                    "status": "configured" if config.line_channel_access_token else "not_configured"
                }
            }
        )
        
    except Exception as e:
        logger.error(f"獲取系統狀態錯誤: {str(e)}")
        return SystemStatus(
            status="unhealthy",
            version="2.0.0-fastapi",
            services={
                "error": str(e)
            }
        ) 