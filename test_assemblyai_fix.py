#!/usr/bin/env python3
"""測試 AssemblyAI 修正後的功能"""
import asyncio
import os
import sys

# 添加專案路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from config import AppConfig
from services.audio.assemblyai_async import AsyncAssemblyAIService


async def test_assemblyai():
    """測試 AssemblyAI 服務"""
    print("🔍 測試 AssemblyAI 修正...")
    print("=" * 50)
    
    # 載入配置
    config = AppConfig.from_env()
    
    # 創建服務
    service = AsyncAssemblyAIService(config)
    
    # 測試檔案
    test_file = "/Users/audi/Downloads/重陽橋30號_7.wav"
    
    if not os.path.exists(test_file):
        print(f"❌ 測試檔案不存在: {test_file}")
        return
    
    try:
        print(f"📍 測試檔案: {test_file}")
        print(f"📊 檔案大小: {os.path.getsize(test_file) / 1024 / 1024:.2f} MB")
        
        # 執行轉錄
        print("\n🎙️ 開始轉錄...")
        result = await service.transcribe(test_file)
        
        print("\n✅ 轉錄成功！")
        print(f"📝 結果:")
        print(f"   語言: {result.get('language')}")
        print(f"   時長: {result.get('duration', 0):.2f} 秒")
        print(f"   提供商: {result.get('provider')}")
        print(f"   模型: {result.get('model')}")
        print(f"   有 SRT: {result.get('has_srt')}")
        print(f"   單詞數: {len(result.get('words', []))}")
        
        # 顯示部分轉錄內容
        transcript = result.get('transcript', '')
        if transcript:
            print(f"\n📄 轉錄內容 (前100字):")
            print(f"   {transcript[:100]}...")
        
        # 顯示部分 SRT
        srt = result.get('srt', '')
        if srt:
            print(f"\n📄 SRT 內容 (前200字):")
            print(f"{srt[:200]}...")
            
    except Exception as e:
        print(f"\n❌ 測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    # 設定 SSL 證書
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    os.environ['HTTPX_CA_BUNDLE'] = certifi.where()
    
    asyncio.run(test_assemblyai())