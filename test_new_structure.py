"""測試新的數據庫結構"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from config import AppConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_new_structure():
    """測試新的數據庫結構是否正確"""
    config = AppConfig.from_env()
    engine = create_async_engine(config.database_url)
    
    try:
        async with engine.connect() as conn:
            # 檢查 recordings 表的新欄位
            result = await conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'recordings' 
                AND column_name IN (
                    'transcription', 'summary', 'confidence_score', 
                    'language', 'processing_time', 'provider',
                    'analysis_metadata', 'srt_content', 'has_timestamps',
                    'timestamps_data', 'transcription_version', 'summary_version'
                )
                ORDER BY column_name
            """))
            
            columns = result.fetchall()
            logger.info("✅ Recordings 表的新欄位:")
            for col in columns:
                logger.info(f"  - {col[0]}: {col[1]}")
            
            # 檢查 analysis_results 表是否還存在
            result = await conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_name = 'analysis_results'
            """))
            
            count = result.scalar()
            if count == 0:
                logger.info("✅ analysis_results 表已成功移除")
            else:
                logger.warning("⚠️ analysis_results 表仍然存在")
            
            # 檢查 analysis_history 表的索引
            result = await conn.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'analysis_history' 
                AND indexname LIKE '%recording_id_type%'
            """))
            
            indexes = result.fetchall()
            if indexes:
                logger.info("✅ analysis_history 表的複合索引已創建")
            else:
                logger.warning("⚠️ analysis_history 表的複合索引未創建")
                
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_new_structure())