"""
數據模型模組
包含所有數據結構和模型定義
""" 

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import asyncio
import logging

db = SQLAlchemy()
migrate = Migrate()

logger = logging.getLogger(__name__)

def init_db(app):
    """初始化數據庫（同步版本）"""
    db.init_app(app)
    migrate.init_app(app, db)
    return db

async def init_db_async():
    """初始化數據庫（異步版本）"""
    try:
        # 對於SQLAlchemy，我們需要使用同步方式初始化
        # 但可以在異步環境中調用
        logger.info("異步數據庫初始化開始")
        
        # 這裡可以添加任何異步初始化邏輯
        # 例如連接池設置、異步遷移等
        
        logger.info("異步數據庫初始化完成")
        
    except Exception as e:
        logger.error(f"異步數據庫初始化失敗: {e}")
        raise

# 導入所有模型
from .user import User
from .recording import Recording
from .analysis import AnalysisResult

__all__ = ['db', 'migrate', 'init_db', 'init_db_async', 'User', 'Recording', 'AnalysisResult'] 