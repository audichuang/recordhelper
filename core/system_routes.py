"""核心應用程式系統路由設定模組"""
import logging
from fastapi import FastAPI, APIRouter

logger = logging.getLogger(__name__)

def setup_health_routes(app: FastAPI):
    """
    設定應用程式的健康檢查路由。

    :param app: FastAPI 應用程式實例
    """
    router = APIRouter()

    @router.get("/", summary="根目錄", description="應用程式的根目錄，通常用於簡單的存活確認。")
    async def root():
        """
        根目錄路由。
        """
        logger.info("接收到根目錄請求。")
        return {"message": "歡迎來到 FastAPI 應用程式！"}

    @router.get("/health", summary="健康檢查", description="執行健康檢查並回報應用程式狀態。")
    async def health_check():
        """
        健康檢查路由。
        """
        logger.info("執行健康檢查...")
        # TODO: 在此處添加更全面的健康檢查邏輯，例如檢查資料庫連線、外部服務等
        return {"status": "ok", "message": "應用程式運行正常。"}

    app.include_router(router)
    logger.info("健康檢查路由設定完成。")
