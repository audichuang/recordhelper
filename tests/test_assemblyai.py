"""
測試 AssemblyAI 語音轉文字服務
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import AppConfig
from services.audio.assemblyai_async import AsyncAssemblyAIService
from services.audio.speech_to_text_async import AsyncSpeechToTextService


async def test_assemblyai_direct():
    """直接測試 AssemblyAI 服務"""
    print("=== 測試 AssemblyAI 直接調用 ===")
    
    # 創建配置
    config = AppConfig.from_env()
    
    # 檢查是否有配置 API 金鑰
    if not hasattr(config, 'assemblyai_api_keys') or not config.assemblyai_api_keys:
        print("❌ 未配置 AssemblyAI API 金鑰")
        print("請在 .env 檔案中設置 ASSEMBLYAI_API_KEY 或 ASSEMBLYAI_API_KEY_1")
        return
    
    try:
        # 創建服務實例
        service = AsyncAssemblyAIService(config)
        
        # 檢查服務狀態
        print("\n檢查服務狀態...")
        status = await service.check_status()
        print(f"服務狀態: {status}")
        
        if not status.get('available'):
            print("❌ AssemblyAI 服務不可用")
            return
        
        # 準備測試音檔
        test_audio = "/tmp/test_audio.mp3"
        if not os.path.exists(test_audio):
            print(f"⚠️ 測試音檔不存在: {test_audio}")
            print("請準備一個測試音檔並放置在該位置")
            return
        
        # 轉錄音檔
        print(f"\n開始轉錄音檔: {test_audio}")
        result = await service.transcribe(test_audio)
        
        # 顯示結果
        print("\n轉錄結果:")
        print(f"- 提供商: {result.get('provider')}")
        print(f"- 模型: {result.get('model')}")
        print(f"- 語言: {result.get('language')}")
        print(f"- 時長: {result.get('duration')} 秒")
        print(f"- 信心度: {result.get('confidence')}")
        print(f"- 轉錄文本長度: {len(result.get('transcript', ''))}")
        print(f"- 單詞數: {len(result.get('words', []))}")
        
        # 顯示前100個字
        transcript = result.get('transcript', '')
        if transcript:
            print(f"\n轉錄文本預覽:")
            print(transcript[:200] + "..." if len(transcript) > 200 else transcript)
        
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_assemblyai_through_service():
    """通過 SpeechToText 服務測試 AssemblyAI"""
    print("\n\n=== 測試通過 SpeechToText 服務調用 AssemblyAI ===")
    
    # 創建配置並設置使用 AssemblyAI
    config = AppConfig.from_env()
    config.speech_to_text_provider = "assemblyai"
    
    # 檢查是否有配置 API 金鑰
    if not hasattr(config, 'assemblyai_api_keys') or not config.assemblyai_api_keys:
        print("❌ 未配置 AssemblyAI API 金鑰")
        return
    
    try:
        # 創建服務實例
        service = AsyncSpeechToTextService(config)
        
        # 檢查服務狀態
        print("\n檢查所有語音服務狀態...")
        status = await service.check_status()
        print(f"當前提供商: {status.get('provider')}")
        
        # 顯示各服務狀態
        for service_name, service_status in status.get('services', {}).items():
            available = "✅" if service_status.get('available') else "❌"
            print(f"{available} {service_name}: {service_status}")
        
        # 準備測試音檔
        test_audio = "/tmp/test_audio.mp3"
        if not os.path.exists(test_audio):
            print(f"\n⚠️ 測試音檔不存在: {test_audio}")
            return
        
        # 轉錄音檔
        print(f"\n開始轉錄音檔: {test_audio}")
        result = await service.transcribe_audio(test_audio)
        
        # 顯示結果
        print("\n轉錄結果:")
        print(f"- 實際使用的提供商: {result.get('provider')}")
        print(f"- 備用提供商: {result.get('backup_provider', '無')}")
        print(f"- 轉錄文本長度: {len(result.get('transcription', ''))}")
        
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_assemblyai_fallback():
    """測試 AssemblyAI 作為備用方案"""
    print("\n\n=== 測試 AssemblyAI 作為備用方案 ===")
    
    # 創建配置，使用其他提供商但 AssemblyAI 作為備用
    config = AppConfig.from_env()
    config.speech_to_text_provider = "deepgram"  # 使用 Deepgram 作為主要提供商
    
    # 檢查是否有配置 AssemblyAI API 金鑰
    if not hasattr(config, 'assemblyai_api_keys') or not config.assemblyai_api_keys:
        print("❌ 未配置 AssemblyAI API 金鑰，跳過備用測試")
        return
    
    print(f"主要提供商: {config.speech_to_text_provider}")
    print("AssemblyAI 將作為備用方案")
    
    # 這裡可以測試當主要服務失敗時，是否會自動切換到 AssemblyAI


async def main():
    """主測試函數"""
    print("AssemblyAI 語音轉文字服務測試")
    print("=" * 50)
    
    # 執行各項測試
    await test_assemblyai_direct()
    await test_assemblyai_through_service()
    await test_assemblyai_fallback()
    
    print("\n測試完成！")


if __name__ == "__main__":
    asyncio.run(main())