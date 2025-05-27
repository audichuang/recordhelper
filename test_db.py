#!/usr/bin/env python3
"""
測試資料庫連接和基本操作
"""

import asyncio
import uuid
from datetime import datetime, timezone

from config import AppConfig
from models import init_async_db, close_async_db, User, Recording, RecordingStatus

async def test_database_connection():
    """測試資料庫連接和基本操作"""
    print("初始化資料庫連接...")
    app_config = AppConfig.from_env()
    await init_async_db(app_config.database_url)
    
    try:
        # 導入 SQLAlchemy 異步 Session
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.future import select
        from sqlalchemy import func
        
        # 從 models/__init__.py 獲取 session 工廠
        from models import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            # 計算用戶數量
            result = await session.execute(select(func.count()).select_from(User))
            user_count = result.scalar()
            print(f"資料庫中的用戶數量: {user_count}")
            
            # 計算錄音數量
            result = await session.execute(select(func.count()).select_from(Recording))
            recording_count = result.scalar()
            print(f"資料庫中的錄音數量: {recording_count}")
            
            # 顯示所有用戶 (如果有的話)
            if user_count > 0:
                result = await session.execute(select(User))
                users = result.scalars().all()
                for user in users:
                    print(f"用戶: {user.username} ({user.email})")
            
            # 添加測試用戶 (如果沒有用戶)
            if user_count == 0:
                print("創建測試用戶...")
                test_user = User(
                    username="testuser",
                    email="test@example.com",
                    password="password123"
                )
                session.add(test_user)
                await session.commit()
                print(f"創建了測試用戶 ID: {test_user.id}")
            
            print("資料庫測試完成!")
            
    except Exception as e:
        print(f"測試時發生錯誤: {e}")
    finally:
        print("關閉資料庫連接...")
        await close_async_db()

if __name__ == "__main__":
    asyncio.run(test_database_connection()) 