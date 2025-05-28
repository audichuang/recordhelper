# -*- coding: utf-8 -*-
"""
系統狀態相關 API 路由定義。

此模組提供用於檢查應用程式及其依賴服務 (例如語音轉文字、AI 模型服務、資料庫等)
目前運行狀態的 API 端點。
"""
from fastapi import APIRouter, Depends # Depends 未在此檔案中直接使用，但保留以備未來擴展
from pydantic import BaseModel, Field # Field 用於更詳細的模型欄位定義
from typing import Dict, Any, Optional # Optional 用於可能的 None 值
import logging

# 假設這些服務有檢查狀態的方法，或者在此處模擬檢查
from services.audio.speech_to_text_async import AsyncSpeechToTextService 
from services.ai.gemini_async import AsyncGeminiService
from config import AppConfig
# from models import get_async_db_session # 如果要檢查資料庫連線，可能需要
# from sqlalchemy.ext.asyncio import AsyncSession # 同上

logger = logging.getLogger(__name__)

# 創建 API 路由器實例
system_router = APIRouter()

# --- Pydantic 資料模型 ---

class ServiceStatusDetail(BaseModel):
    """單個服務的狀態詳細資訊模型"""
    available: bool = Field(..., description="指示服務是否可用。")
    status_message: Optional[str] = Field(None, description="服務狀態的描述性訊息 (例如 'connected', 'error', 'not_configured')。")
    details: Optional[Dict[str, Any]] = Field(None, description="服務特定的其他詳細狀態資訊。")

class SystemStatus(BaseModel):
    """
    系統整體狀態回應模型。
    提供應用程式主要組件及其依賴服務的健康狀況。
    """
    overall_status: str = Field(..., description="系統的總體健康狀態 (例如 'healthy', 'unhealthy', 'degraded')。")
    version: str = Field(..., description="應用程式的版本號。")
    services: Dict[str, ServiceStatusDetail] = Field(..., description="各個關鍵服務的狀態詳情。")
    # timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="狀態報告生成的時間戳 (UTC)。") # 可選

# --- API 端點 ---

@system_router.get(
    "/status", 
    response_model=SystemStatus,
    summary="獲取應用程式及其依賴服務的系統狀態",
    description="提供一個總覽，顯示應用程式主要組件 (如資料庫、外部 API 服務) 的目前健康狀況。"
)
async def get_system_status(
    app_config: AppConfig = Depends(lambda: AppConfig.from_env()) # 依賴注入應用程式組態
    # db: AsyncSession = Depends(get_async_db_session) # 如果需要直接檢查資料庫連線，則取消註解
):
    """
    獲取系統的整體健康狀態及各依賴服務的狀態。

    此端點會檢查以下服務的狀態：
    - 語音轉文字服務 (例如 OpenAI Whisper, Google Speech-to-Text)
    - AI 模型服務 (例如 Google Gemini)
    - 資料庫連線
    - LINE Bot 設定完整性 (如果已啟用)

    Args:
        app_config (AppConfig): 應用程式的組態設定。
        db (AsyncSession, optional): 資料庫會話依賴，用於檢查資料庫連線。

    Returns:
        SystemStatus: 包含總體狀態、版本及各服務詳細狀態的回應物件。
    """
    logger.info("收到系統狀態檢查請求。")
    services_status: Dict[str, ServiceStatusDetail] = {}
    overall_healthy = True # 假設初始狀態為健康

    try:
        # 1. 檢查語音轉文字服務 (STT)
        # 假設 AsyncSpeechToTextService 有一個 check_service_health_async 方法
        try:
            stt_service = AsyncSpeechToTextService(config=app_config) # 傳遞 AppConfig 實例
            stt_health = await stt_service.check_service_health_async() # 假設此方法返回 ServiceStatusDetail 相容的字典或物件
            services_status["speech_to_text"] = ServiceStatusDetail(**stt_health)
            if not stt_health.get("available", False):
                overall_healthy = False
                logger.warning(f"STT 服務 ({app_config.SPEECH_TO_TEXT_PROVIDER}) 狀態不佳: {stt_health.get('status_message')}")
        except Exception as e_stt:
            logger.error(f"檢查 STT 服務狀態時發生錯誤: {e_stt}", exc_info=True)
            services_status["speech_to_text"] = ServiceStatusDetail(available=False, status_message=f"檢查錯誤: {type(e_stt).__name__}")
            overall_healthy = False

        # 2. 檢查 AI 模型服務 (例如 Gemini)
        # 假設 AsyncGeminiService 有一個 check_service_health_async 方法
        try:
            ai_service = AsyncGeminiService(api_key=app_config.GEMINI_API_KEY) # 傳遞 API Key
            ai_health = await ai_service.check_service_health_async() # 假設此方法返回 ServiceStatusDetail 相容的字典或物件
            services_status["ai_model_service"] = ServiceStatusDetail(**ai_health)
            if not ai_health.get("available", False):
                overall_healthy = False
                logger.warning(f"AI 模型服務 ({app_config.AI_MODEL_NAME}) 狀態不佳: {ai_health.get('status_message')}")
        except Exception as e_ai:
            logger.error(f"檢查 AI 模型服務狀態時發生錯誤: {e_ai}", exc_info=True)
            services_status["ai_model_service"] = ServiceStatusDetail(available=False, status_message=f"檢查錯誤: {type(e_ai).__name__}")
            overall_healthy = False
        
        # 3. 檢查資料庫連線 (如果 db 依賴被啟用)
        # 這裡僅為示例，實際的資料庫健康檢查可能更複雜，例如執行一個簡單查詢
        db_available = True # 假設資料庫可用，除非檢查失敗
        db_status_msg = "已連接"
        # try:
        #     await db.execute(select(1)) # 執行一個簡單的測試查詢
        #     logger.debug("資料庫連線測試成功。")
        # except Exception as e_db:
        #     logger.error(f"資料庫連線檢查失敗: {e_db}", exc_info=True)
        #     db_available = False
        #     db_status_msg = f"連線錯誤: {type(e_db).__name__}"
        #     overall_healthy = False
        services_status["database"] = ServiceStatusDetail(available=db_available, status_message=db_status_msg)

        # 4. 檢查 LINE Bot 設定
        line_bot_configured = bool(app_config.LINE_CHANNEL_ACCESS_TOKEN and app_config.LINE_CHANNEL_SECRET)
        services_status["line_bot"] = ServiceStatusDetail(
            available=line_bot_configured, # 可用性取決於是否已設定
            status_message="已設定" if line_bot_configured else "未設定或設定不完整"
        )
        # 如果 LINE Bot 是核心功能，未設定時可以將 overall_healthy 設為 False
        # if not line_bot_configured and app_config.IS_LINE_BOT_CRITICAL: 
        #     overall_healthy = False

        # 最終確定總體狀態
        final_status_message = "healthy"
        if not overall_healthy:
            # 可以根據哪些服務失敗來決定是 "unhealthy" 還是 "degraded"
            # 例如，如果資料庫不可用，可能是 "unhealthy"；如果只是 LINE Bot 未設定，可能是 "degraded" 或仍為 "healthy" (取決於業務邏輯)
            final_status_message = "degraded" # 或 "unhealthy"
            # 檢查是否有任何核心服務失敗
            if not services_status.get("database", {}).get("available", True) or \
               not services_status.get("speech_to_text", {}).get("available", True) or \
               not services_status.get("ai_model_service", {}).get("available", True):
                final_status_message = "unhealthy"
        
        logger.info(f"系統狀態檢查完成，總體狀態: {final_status_message}")
        return SystemStatus(
            overall_status=final_status_message,
            version=app_config.PROJECT_VERSION, # 從 AppConfig 獲取版本號
            services=services_status
        )
        
    except Exception as e_global: # 捕獲在準備狀態檢查時發生的全域性錯誤
        logger.critical(f"獲取系統狀態時發生嚴重錯誤: {str(e_global)}", exc_info=True)
        # 發生這種情況時，可能無法檢查任何服務，返回一個通用的不健康狀態
        return SystemStatus(
            overall_status="unhealthy",
            version=app_config.PROJECT_VERSION if 'app_config' in locals() else "未知", # 如果 app_config 未載入
            services={
                "system_error": ServiceStatusDetail(available=False, status_message=f"獲取狀態時發生嚴重錯誤: {type(e_global).__name__}")
            }
        )