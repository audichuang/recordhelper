"""修復 alembic 版本問題"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from config import AppConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_alembic_version():
    """修復 alembic 版本記錄"""
    config = AppConfig.from_env()
    engine = create_async_engine(config.database_url)
    
    try:
        async with engine.connect() as conn:
            # 檢查當前版本
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            current_version = result.scalar()
            logger.info(f"當前版本: {current_version}")
            
            if current_version == 'add_srt_timestamps':
                # 更新為正確的版本
                await conn.execute(text("UPDATE alembic_version SET version_num = 'd0e21926e0da'"))
                await conn.commit()
                logger.info("✅ 已將版本更新為 'd0e21926e0da'")
            else:
                logger.info(f"版本已經是: {current_version}")
                
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix_alembic_version())