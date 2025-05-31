#!/usr/bin/env python3
"""測試官方 SDK 版本的 AssemblyAI 和 Deepgram"""
import asyncio
import os
import sys

# 添加專案路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import AppConfig
from services.audio.assemblyai_async import AsyncAssemblyAIService
from services.audio.deepgram_async import AsyncDeepgramService


async def test_services():
    """測試語音識別服務"""
    # 載入環境變數
    from dotenv import load_dotenv
    load_dotenv()
    
    # 使用 from_env() 方法載入配置
    config = AppConfig.from_env()
    
    print("🔍 測試官方 SDK 版本...")
    print("=" * 50)
    
    # 測試 AssemblyAI
    print("\n📍 測試 AssemblyAI 官方 SDK...")
    try:
        assemblyai_service = AsyncAssemblyAIService(config)
        status = await assemblyai_service.check_status()
        print(f"AssemblyAI 狀態: {status}")
        
        if status.get('available'):
            print("✅ AssemblyAI 官方 SDK 正常")
        else:
            print(f"❌ AssemblyAI 錯誤: {status.get('error')}")
    except Exception as e:
        print(f"❌ AssemblyAI 初始化失敗: {str(e)}")
    
    # 測試 Deepgram
    print("\n📍 測試 Deepgram 官方 SDK...")
    try:
        deepgram_service = AsyncDeepgramService(config)
        status = await deepgram_service.check_status()
        print(f"Deepgram 狀態: {status}")
        
        if status.get('available'):
            print("✅ Deepgram 官方 SDK 正常")
        else:
            print(f"❌ Deepgram 錯誤: {status.get('error')}")
    except Exception as e:
        print(f"❌ Deepgram 初始化失敗: {str(e)}")
    
    print("\n" + "=" * 50)
    print("✅ 測試完成")


if __name__ == "__main__":
    asyncio.run(test_services())