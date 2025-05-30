#!/usr/bin/env python3
"""
測試設備 Token 註冊流程
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_device_tokens():
    """檢查資料庫中的設備 Token"""
    conn = await asyncpg.connect(
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT', 5432)),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    
    try:
        print("🔍 檢查資料庫中的設備 Token...")
        
        # 查詢所有設備 token
        tokens = await conn.fetch("""
            SELECT dt.*, u.username, u.email
            FROM device_tokens dt
            JOIN users u ON dt.user_id = u.id
            ORDER BY dt.created_at DESC
        """)
        
        if tokens:
            print(f"📱 找到 {len(tokens)} 個設備 Token:")
            for i, token in enumerate(tokens, 1):
                print(f"\n{i}. 用戶: {token['username']} ({token['email']})")
                print(f"   Token: {token['token'][:20]}...")
                print(f"   平台: {token['platform']}")
                print(f"   設備: {token['device_name']} ({token['device_model']})")
                print(f"   OS: {token['os_version']}")
                print(f"   活躍: {token['is_active']}")
                print(f"   創建時間: {token['created_at']}")
                print(f"   最後使用: {token['last_used_at']}")
        else:
            print("❌ 沒有找到任何設備 Token")
            
            # 檢查是否有用戶
            users = await conn.fetch("SELECT id, username, email FROM users LIMIT 5")
            print(f"\n📋 資料庫中的用戶 ({len(users)} 個):")
            for user in users:
                print(f"  - {user['username']} ({user['email']}) ID: {user['id']}")
                
    finally:
        await conn.close()

async def test_device_token_api():
    """測試設備 Token API"""
    import httpx
    
    # 假設的測試數據
    test_token = "a" * 64  # 假的設備 token
    
    # 需要有效的用戶 token - 這裡需要從實際登入獲取
    print("\n🧪 測試設備 Token API...")
    print("注意：需要有效的認證 token 才能測試 API")
    print("請在 iOS 應用中登入後檢查是否有設備 token 發送請求")

if __name__ == "__main__":
    asyncio.run(check_device_tokens())
    asyncio.run(test_device_token_api())