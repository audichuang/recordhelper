#!/usr/bin/env python3
"""
FastAPI 錄音助手 - 主程序
支援語音轉文字、AI摘要、LINE Bot等功能
"""

import logging
import os
# import asyncio # 從 core.lifespan 導入 lifespan 後不再直接需要
# from contextlib import asynccontextmanager # 從 core.lifespan 導入 lifespan 後不再直接需要
from fastapi import FastAPI, HTTPException, Request # Depends, UploadFile, File, Form 未在此文件直接使用
# from fastapi.middleware.cors import CORSMiddleware # 已移至 core.middleware
# from fastapi.middleware.trustedhost import TrustedHostMiddleware # 已移至 core.middleware
# from fastapi.responses import JSONResponse # 已移至 core.error_handlers
# from fastapi.security import HTTPBearer # 未在此文件直接使用
import uvicorn
# import coloredlogs # 已移至 core.logging_config

from config import AppConfig
# from models import init_async_db, close_async_db, get_async_db_session # init_async_db, close_async_db 從 core.lifespan 間接使用
from api_fastapi import init_api_routes
from services.messaging.line_bot_fastapi import LineWebhookHandler

# 從核心模組導入設定函數
from core.logging_config import setup_logging
from core.lifespan import lifespan # 導入重構後的 lifespan
from core.middleware import setup_middleware
from core.error_handlers import setup_error_handlers
from core.system_routes import setup_health_routes


# 應用程式啟動時立即設定日誌
# 注意: AppConfig.from_env() 可能需要在 setup_logging 外部調用一次，如果 AppConfig 的實例也需要在其他地方使用
# 或者，修改 setup_logging 讓它可以接受 AppConfig 實例或從環境變數讀取
config_for_logging = AppConfig.from_env()
setup_logging(log_level=config_for_logging.LOG_LEVEL.upper(), log_dir=config_for_logging.LOG_DIR, log_filename=config_for_logging.LOG_FILENAME)
logger = logging.getLogger(__name__)


# lifespan 管理已移至 core.lifespan.py
# init_database 函數已移至 core.lifespan.py


def create_app(config: AppConfig = None) -> FastAPI:
    """
    創建並設定 FastAPI 應用程式實例。
    此函數現在將大部分核心設定工作委派給 `core` 目錄中的模組。
    """
    if config is None:
        config = AppConfig.from_env()
    
    logger.info("🚀 正在創建 FastAPI 應用程式...")
    # 創建FastAPI應用，並傳入從 core.lifespan 導入的生命週期管理器
    app = FastAPI(
        title=config.PROJECT_NAME or "錄音助手 API",
        description=config.PROJECT_DESCRIPTION or "支援語音轉文字、AI摘要、LINE Bot集成的API服務",
        version=config.PROJECT_VERSION or "2.0.0",
        docs_url="/docs", # API 文件路徑
        redoc_url="/redoc", # ReDoc 路徑
        lifespan=lifespan # 使用從 core.lifespan 導入的生命週期管理器
    )
    
    # 儲存配置到應用狀態，以便在 lifespan 和其他地方訪問
    app.state.config = config
    
    # 設定核心應用程式組件
    setup_middleware(app, config)       # 設定中介軟體 (例如 CORS, TrustedHost)
    setup_error_handlers(app)   # 設定全域錯誤處理程序
    setup_health_routes(app)    # 設定健康檢查和根路由
    
    # 初始化應用程式特定的 API 路由
    init_api_routes(app, config)
    
    # 初始化 LINE Bot webhook（如果啟用）
    # 這部分邏輯保持在 main_fastapi.py，因為它與特定服務集成相關
    if config.line_channel_access_token and config.line_channel_secret:
        webhook_handler = LineWebhookHandler(config) # LineWebhookHandler 可能需要 app.state.config
        setup_line_webhook(app, webhook_handler)
        logger.info("📱 LINE Bot webhook 已設定並啟用。")
    else:
        logger.info("⚠️ LINE Bot 未設定，相關功能將不可用。")
        
    logger.info("✅ FastAPI 應用程式初始化完成。")
    return app


# setup_middleware 函數已移至 core.middleware.py
# setup_health_routes 函數已移至 core.system_routes.py


def setup_line_webhook(app: FastAPI, webhook_handler: LineWebhookHandler):
    """
    設定 LINE Bot webhook 路由。
    此函數處理與 LINE Bot 特定的路由和服務設定。
    """
    @app.post("/webhook", summary="LINE Webhook 端點 (主要)", description="接收並處理來自 LINE Platform 的 Webhook 事件。")
    async def line_webhook(request: Request):
        """LINE Bot webhook端點"""
        try:
            signature = request.headers.get('X-Line-Signature')
            if not signature:
                logger.error("❌ 接收到 LINE Webhook 請求，但缺少 X-Line-Signature 標頭。")
                raise HTTPException(status_code=400, detail="Missing X-Line-Signature header")
            
            body = await request.body()
            logger.debug(f"接收到 LINE Webhook 請求: Body - {body.decode()[:200]}...") # 記錄部分 body 內容以供調試
            
            await webhook_handler.handle_webhook(body, signature)
            logger.info("✅ LINE Webhook 事件處理成功。")
            return {"status": "ok"}
            
        except HTTPException as http_exc:
            logger.error(f"❌ LINE Webhook 處理時發生 HTTP 例外: {http_exc.detail}")
            raise # 重新拋出 HTTP 例外，讓 FastAPI 的錯誤處理器處理
        except Exception as e:
            logger.error(f"❌ LINE Webhook 處理時發生未預期錯誤: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Webhook 處理失敗，請查看伺服器日誌。")
    
    # 保留備用路徑，以防舊設定仍在使用
    @app.post("/webhook/line", summary="LINE Webhook 端點 (備用)", description="接收並處理來自 LINE Platform 的 Webhook 事件 (備用路徑)。")
    async def line_webhook_alt(request: Request):
        """LINE Bot webhook端點（備用路徑）"""
        logger.info("收到請求至備用 LINE Webhook 路徑 /webhook/line。")
        return await line_webhook(request)

# setup_error_handlers 函數已移至 core.error_handlers.py
# init_database 函數已移至 core.lifespan.py (並在 lifespan 中調用)


def main():
    """主函數，用於啟動 uvicorn 伺服器。"""
    try:
        # 載入配置 (main 函數中的 config 主要用於 uvicorn 啟動)
        # create_app 內部也會載入 config，但此處的 config 用於端口等伺服器參數
        config = AppConfig.from_env()
        
        # 創建應用
        # app 實例由 create_app() 返回，該函數已處理日誌設定外的核心設定
        app = create_app(config) # 傳遞 config，以便 create_app 可以使用
        
        # 獲取端口和主機設置
        port = config.PORT
        host = config.HOST
        
        logger.info(f"🌏 伺服器準備啟動於 http://{host}:{port}")
        logger.info(f"📚 API 文件位於: http://{host}:{port}/docs")
        logger.info(f"⚙️ Uvicorn reload 模式: {'啟用' if config.RELOAD else '禁用'}")
        logger.info(f"🛠️ Uvicorn workers 數量: {config.WORKERS}")
        
        # 啟動 uvicorn 伺服器
        uvicorn.run(
            "main_fastapi:app", # 指向 FastAPI 應用程式實例 (檔案名:變數名)
            host=host,
            port=port,
            reload=config.RELOAD,
            workers=config.WORKERS,
            log_level=config.LOG_LEVEL.lower() # uvicorn 的 log_level 參數需要小寫
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 收到中斷信號 (Ctrl+C)，正在優雅關閉服務...")
    except Exception as e:
        logger.critical(f"💥 伺服器啟動失敗: {e}", exc_info=True)
        # 在拋出前確保所有日誌都已刷出 (如果需要)
        logging.shutdown() 
        raise
    finally:
        logger.info("🚪 服務已關閉。")


if __name__ == "__main__":
    main() 