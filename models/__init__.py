# -*- coding: utf-8 -*-
"""
資料庫模型定義與異步資料庫會話管理模組。

此模組負責：
1.  定義所有 SQLAlchemy 資料庫模型的基類 (`Base`)。
2.  初始化異步資料庫引擎 (`async_engine`) 和會話工廠 (`AsyncSessionLocal`)。
3.  提供一個 FastAPI 依賴項 (`get_async_db_session`) 以獲取異步資料庫會話。
4.  提供在應用程式啟動和關閉時初始化和關閉資料庫連接的函數 (`init_async_db`, `close_async_db`)。
5.  從各個子模組中匯入所有 SQLAlchemy 模型，使其可以透過 `models.<ModelName>` 的方式被其他模組引用。
"""

import asyncio # asyncio 未在此檔案直接使用，但異步操作依賴它
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

# --- 全域變數定義 ---
# `async_engine`：SQLAlchemy 異步引擎實例，用於與資料庫通訊。
# `AsyncSessionLocal`：異步會話工廠，用於創建資料庫會話。
# 這些變數在 `init_async_db` 中初始化。
async_engine: Optional[create_async_engine] = None
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None

# --- SQLAlchemy 模型基類 ---
class Base(DeclarativeBase):
    """
    所有 SQLAlchemy 資料庫模型的聲明性基類。
    所有應用程式中的資料庫模型都應繼承自此類別。
    """
    pass

# --- 資料庫會話管理 ---

async def get_async_db_session() -> AsyncSession:
    """
    FastAPI 依賴項，用於獲取一個 SQLAlchemy 異步資料庫會話。

    此函數應作為一個依賴項注入到需要資料庫存取的 API 路由操作函數中。
    它會從 `AsyncSessionLocal` 會話工廠創建一個新的會話，並在請求處理完畢後
    (無論成功或失敗) 自動關閉該會話。

    Yields:
        AsyncSession: 一個 SQLAlchemy 異步資料庫會話實例。

    Raises:
        RuntimeError: 如果 `AsyncSessionLocal` 尚未透過 `init_async_db` 初始化。
    """
    if AsyncSessionLocal is None:
        logger.error("AsyncSessionLocal 尚未初始化。請確保在應用程式啟動時已調用 init_async_db。")
        raise RuntimeError("AsyncSessionLocal is not initialized. Call init_async_db first.")
    
    # 從會話工廠創建一個新的異步會話
    async with AsyncSessionLocal() as session:
        try:
            yield session # 將會話提供給依賴此函數的路由操作
            # logger.debug(f"資料庫會話 {id(session)} 已成功讓出。")
        except Exception as e_session:
            logger.error(f"資料庫會話 {id(session)} 發生例外: {e_session}", exc_info=True)
            # 可以在此處決定是否需要回滾，但通常 FastAPI 的錯誤處理中介軟體或路由本身會處理
            # await session.rollback() # 視情況而定
            raise # 重新拋出例外，以便 FastAPI 或上層錯誤處理器捕獲
        finally:
            # logger.debug(f"資料庫會話 {id(session)} 即將關閉 (由 async with 自動處理)。")
            # `async with AsyncSessionLocal() as session:` 會自動處理會話的關閉 (session.close())。
            # 不需要在此處顯式調用 session.close()。
            pass

async def init_async_db(database_url: str, db_echo: bool = False):
    """
    初始化異步資料庫引擎和會話工廠。

    此函數應在應用程式啟動時 (例如，在 FastAPI 的 lifespan 事件中) 被調用一次。
    它會根據提供的資料庫 URL 創建一個全域的 SQLAlchemy 異步引擎 (`async_engine`)
    和一個異步會話工廠 (`AsyncSessionLocal`)。

    Args:
        database_url (str): 資料庫連接字串 (例如 "postgresql+asyncpg://user:pass@host:port/db")。
        db_echo (bool): 是否啟用 SQLAlchemy 引擎的日誌輸出 (echo=True 會輸出所有執行的 SQL 語句)。
                        生產環境中建議設為 False。
    """
    global async_engine, AsyncSessionLocal # 聲明我們要修改全域變數
    
    if async_engine:
        logger.warning("init_async_db 被多次調用。異步資料庫引擎已存在，將跳過重新初始化。")
        return

    logger.info(f"正在初始化異步資料庫引擎，目標 URL: {database_url} (Echo: {db_echo})")
    try:
        async_engine = create_async_engine(database_url, echo=db_echo)
        
        AsyncSessionLocal = async_sessionmaker(
            bind=async_engine,
            autocommit=False,       # 異步模式下，通常不使用 autocommit
            autoflush=False,        # 異步模式下，通常不使用 autoflush
            expire_on_commit=False, # 對於異步會話和背景任務，設為 False 很重要，以防止在提交後物件過期
            class_=AsyncSession     # 指定使用 AsyncSession 類別
        )
        logger.info("異步資料庫引擎和會話工廠已成功初始化。")
    except Exception as e_init:
        logger.critical(f"初始化異步資料庫引擎失敗: {e_init}", exc_info=True)
        # 根據應用程式的錯誤處理策略，這裡可能需要重新拋出例外或以其他方式處理失敗
        raise

async def close_async_db():
    """
    關閉並清理異步資料庫引擎。

    此函數應在應用程式關閉時 (例如，在 FastAPI 的 lifespan 事件中) 被調用一次。
    它會釋放資料庫引擎持有的所有連接資源。
    """
    global async_engine, AsyncSessionLocal # 聲明我們要修改全域變數
    if async_engine:
        logger.info("正在關閉異步資料庫引擎...")
        try:
            await async_engine.dispose() # 異步釋放引擎資源
            logger.info("異步資料庫引擎已成功關閉。")
        except Exception as e_close:
            logger.error(f"關閉異步資料庫引擎時發生錯誤: {e_close}", exc_info=True)
        finally:
            async_engine = None
            AsyncSessionLocal = None # 同時清理會話工廠
    else:
        logger.info("異步資料庫引擎未初始化或已關閉，無需執行關閉操作。")

# --- 模型匯入 ---
# 從各個模型檔案中導入定義的 SQLAlchemy 模型類別。
# 這樣做可以讓其他模組透過 `from models import User` 等方式方便地引用這些模型。
from .user import User
from .recording import Recording, RecordingStatus # RecordingStatus 是 Enum，也一併匯出
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