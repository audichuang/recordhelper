"""檢查測試用戶密碼"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from models import User
from config import AppConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_test_user():
    """檢查測試用戶並重設密碼"""
    config = AppConfig.from_env()
    engine = create_async_engine(config.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            # 查找測試用戶
            result = await session.execute(
                select(User).where(User.email == "test@example.com")
            )
            user = result.scalars().first()
            
            if user:
                logger.info(f"✅ 找到測試用戶: {user.username}")
                
                # 重設密碼
                user.set_password("password123")
                await session.commit()
                logger.info("✅ 密碼已重設為: password123")
                
                # 驗證密碼
                if user.check_password("password123"):
                    logger.info("✅ 密碼驗證成功")
                else:
                    logger.error("❌ 密碼驗證失敗")
            else:
                logger.error("❌ 未找到測試用戶")
                
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_test_user())