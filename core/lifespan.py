"""核心應用程式生命週期管理模組"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from config import AppConfig # 修正導入路徑 AppConfig
from models import init_async_db, close_async_db # 修正導入路徑 init_async_db, close_async_db

logger = logging.getLogger(__name__)

async def init_database(app_instance: FastAPI): # 新增 app_instance 參數
    """
    初始化資料庫連線。
    使用 app_instance.state.config 中的資料庫 URL。
    :param app_instance: FastAPI 應用程式實例
    """
    logger.info("正在初始化資料庫...")
    # 從 app.state.config 獲取 DATABASE_URL
    if hasattr(app_instance.state, 'config') and app_instance.state.config.DATABASE_URL:
        db_url = app_instance.state.config.DATABASE_URL
        await init_async_db(db_url)
        logger.info(f"資料庫初始化完成。URL: {db_url}")
    else:
        logger.error("資料庫設定 (DATABASE_URL) 未在 app.state.config 中找到。")
        # 考慮是否應引發錯誤或採取其他行動
        # raise ValueError("DATABASE_URL not configured in app.state.config")

@asynccontextmanager
async def lifespan(app: FastAPI): # app 參數已存在
    """
    應用程式生命週期管理器。

    :param app: FastAPI 應用程式實例
    """
    logger.info("應用程式啟動...")
    # 在 lifespan 啟動時，FastAPI 會自動將 app 實例傳遞過來
    # 此時 app.state.config 應該已經被 main_fastapi.py 中的 create_app 函數設定
    await init_database(app)  # 初始化資料庫，傳遞 app 實例
    yield
    logger.info("正在關閉資料庫連線...")
    await close_async_db()
    logger.info("資料庫連線已關閉。")
    logger.info("應用程式關閉。")
