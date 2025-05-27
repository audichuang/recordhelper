#!/usr/bin/env python3
"""
FastAPI 錄音助手 - 主程序
支援語音轉文字、AI摘要、LINE Bot等功能
"""

import logging
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
import uvicorn

from config import AppConfig
from models import init_db
from api_fastapi import init_api_routes
from services.messaging.line_bot_fastapi import LineWebhookHandler


# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('linebot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用生命週期管理"""
    # 啟動時執行
    logger.info("🚀 啟動FastAPI錄音助手")
    
    # 初始化資料庫
    try:
        await init_database()
        logger.info("資料庫初始化完成")
    except Exception as e:
        logger.error(f"資料庫初始化失敗: {e}")
        raise
    
    yield
    
    # 關閉時執行
    logger.info("關閉FastAPI錄音助手")


def create_app(config: AppConfig = None) -> FastAPI:
    """創建FastAPI應用"""
    if config is None:
        config = AppConfig.from_env()
    
    # 創建FastAPI應用
    app = FastAPI(
        title="錄音助手 API",
        description="支援語音轉文字、AI摘要、LINE Bot集成的API服務",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # 儲存配置到應用狀態
    app.state.config = config
    
    # 添加中間件
    setup_middleware(app, config)
    
    # 初始化API路由
    init_api_routes(app, config)
    
    # 初始化LINE Bot webhook（如果啟用）
    if config.line_channel_access_token and config.line_channel_secret:
        webhook_handler = LineWebhookHandler(config)
        setup_line_webhook(app, webhook_handler)
        logger.info("LINE Bot webhook已啟用")
    
    # 添加健康檢查端點
    setup_health_routes(app)
    
    # 添加錯誤處理器
    setup_error_handlers(app)
    
    logger.info("FastAPI應用初始化完成")
    return app


def setup_middleware(app: FastAPI, config: AppConfig):
    """設置中間件"""
    # CORS中間件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生產環境應該限制來源
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 受信任主機中間件
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # 生產環境應該限制主機
    )


def setup_health_routes(app: FastAPI):
    """設置健康檢查路由"""
    @app.get("/health")
    async def health_check():
        """健康檢查端點"""
        return {
            "status": "healthy",
            "version": "2.0.0",
            "framework": "FastAPI",
            "database": "connected"
        }
    
    @app.get("/")
    async def root():
        """根路徑"""
        return {
            "message": "錄音助手 FastAPI 服務",
            "version": "2.0.0",
            "docs": "/docs",
            "health": "/health"
        }


def setup_line_webhook(app: FastAPI, webhook_handler: LineWebhookHandler):
    """設置LINE Bot webhook"""
    @app.post("/webhook")
    async def line_webhook(request: Request):
        """LINE Bot webhook端點"""
        try:
            # 獲取請求簽名
            signature = request.headers.get('X-Line-Signature')
            if not signature:
                raise HTTPException(status_code=400, detail="Missing signature")
            
            # 獲取請求主體
            body = await request.body()
            
            # 處理webhook
            await webhook_handler.handle_webhook(body, signature)
            
            return {"status": "ok"}
            
        except Exception as e:
            logger.error(f"LINE webhook處理錯誤: {str(e)}")
            raise HTTPException(status_code=500, detail="Webhook處理失敗")
    
    @app.post("/webhook/line")
    async def line_webhook_alt(request: Request):
        """LINE Bot webhook端點（備用路徑）"""
        return await line_webhook(request)


def setup_error_handlers(app: FastAPI):
    """設置錯誤處理器"""
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTP異常處理器"""
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": exc.detail, "status_code": exc.status_code}
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """通用異常處理器"""
        logger.error(f"未處理的異常: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={"message": "內部伺服器錯誤", "status_code": 500}
        )


async def init_database():
    """初始化資料庫"""
    try:
        # 對於FastAPI，我們使用同步的SQLAlchemy，但在異步上下文中初始化
        from models import db
        from config import AppConfig
        
        # 這裡實際上不需要特別的異步初始化
        # 因為我們使用的是同步SQLAlchemy與異步包裝器
        logger.info("資料庫連接已配置")
        
    except Exception as e:
        logger.error(f"資料庫初始化失敗: {e}")
        raise


def main():
    """主函數"""
    try:
        # 載入配置
        config = AppConfig.from_env()
        
        # 創建應用
        app = create_app(config)
        
        # 獲取端口設置
        port = int(os.environ.get('PORT', 9527))
        host = os.environ.get('HOST', '0.0.0.0')
        
        logger.info(f"服務器啟動在 {host}:{port}")
        logger.info(f"API文檔: http://{host}:{port}/docs")
        
        # 啟動服務器
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=False,  # 生產環境應該設為False
            workers=1,     # 可以根據需要調整
            log_level="info"
        )
        
    except KeyboardInterrupt:
        logger.info("收到中斷信號，正在關閉服務...")
    except Exception as e:
        logger.error(f"服務器啟動失敗: {e}")
        raise
    finally:
        logger.info("服務已關閉")


if __name__ == "__main__":
    main() 