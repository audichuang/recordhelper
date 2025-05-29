"""創建測試用戶"""
import asyncio
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:9527/api"

async def create_test_user():
    """創建測試用戶"""
    async with httpx.AsyncClient() as client:
        # 註冊新用戶
        logger.info("📝 註冊測試用戶...")
        register_response = await client.post(
            f"{BASE_URL}/auth/register",
            json={
                "username": "test_user",
                "email": "test@example.com",
                "password": "password"
            }
        )
        
        if register_response.status_code == 200:
            logger.info("✅ 測試用戶創建成功")
            result = register_response.json()
            logger.info(f"  - 用戶ID: {result['user']['id']}")
            logger.info(f"  - 用戶名: {result['user']['username']}")
            logger.info(f"  - Email: {result['user']['email']}")
        else:
            logger.error(f"❌ 創建用戶失敗: {register_response.text}")

if __name__ == "__main__":
    asyncio.run(create_test_user())