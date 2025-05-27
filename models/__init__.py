"""
數據模型模組
包含所有數據結構和模型定義
""" 

import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

# 定義異步引擎和會話工廠的全局變量
async_engine = None
AsyncSessionLocal = None

class Base(DeclarativeBase):
    pass

async def get_async_db_session() -> AsyncSession:
    """獲取異步資料庫會話的依賴項"""
    if AsyncSessionLocal is None:
        raise RuntimeError("AsyncSessionLocal is not initialized. Call init_async_db first.")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            # 不在此處關閉，FastAPI 的 Depends 會處理或 Application lifespan
            pass 

async def init_async_db(database_url: str):
    """初始化異步資料庫連接"""
    global async_engine, AsyncSessionLocal
    
    logger.info(f"初始化異步資料庫引擎: {database_url}")
    async_engine = create_async_engine(database_url, echo=False) # 生產環境建議 echo=False
    
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False, # 對異步會話很重要
        class_=AsyncSession
    )
    logger.info("異步資料庫引擎和會話工廠初始化完成")

async def close_async_db():
    """關閉異步資料庫引擎"""
    global async_engine
    if async_engine:
        logger.info("關閉異步資料庫引擎")
        await async_engine.dispose()
        async_engine = None

# 導入所有模型
from .user import User
from .recording import Recording, RecordingStatus
from .analysis import AnalysisResult

__all__ = [
    'Base',
    'get_async_db_session',
    'init_async_db',
    'close_async_db',
    'User', 
    'Recording', 
    'RecordingStatus',
    'AnalysisResult'
] 