"""
測試 SRT 和時間戳功能
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加專案根目錄到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import AppConfig
from services.audio.assemblyai_async import AsyncAssemblyAIService
from services.audio.deepgram_async import AsyncDeepgramService


async def test_assemblyai_srt():
    """測試 AssemblyAI 的 SRT 輸出"""
    print("\n=== 測試 AssemblyAI SRT 功能 ===")
    
    config = AppConfig.from_env()
    service = AsyncAssemblyAIService(config)
    
    # 使用測試音檔
    test_file = "test_audio.mp3"  # 請替換為實際的測試音檔路徑
    
    if not os.path.exists(test_file):
        print(f"⚠️ 測試音檔不存在: {test_file}")
        print("請提供一個測試音檔路徑")
        return
    
    try:
        result = await service.transcribe(test_file)
        
        print(f"\n✅ 轉錄成功！")
        print(f"逐字稿長度: {len(result.get('transcript', ''))}")
        print(f"是否有 SRT: {result.get('has_srt', False)}")
        
        if result.get('srt'):
            print(f"\n--- SRT 內容預覽 (前500字) ---")
            print(result['srt'][:500])
            print("...")
            
        if result.get('words'):
            print(f"\n單詞數量: {len(result['words'])}")
            print(f"前5個單詞:")
            for i, word in enumerate(result['words'][:5]):
                print(f"  {i+1}. '{word['text']}' [{word['start']:.2f}s - {word['end']:.2f}s]")
                
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")


async def test_deepgram_srt():
    """測試 Deepgram 的 SRT 輸出"""
    print("\n=== 測試 Deepgram SRT 功能 ===")
    
    config = AppConfig.from_env()
    service = AsyncDeepgramService(config)
    
    # 使用測試音檔
    test_file = "test_audio.mp3"  # 請替換為實際的測試音檔路徑
    
    if not os.path.exists(test_file):
        print(f"⚠️ 測試音檔不存在: {test_file}")
        return
    
    try:
        result = await service.transcribe(test_file)
        
        print(f"\n✅ 轉錄成功！")
        print(f"逐字稿長度: {len(result.get('transcript', ''))}")
        print(f"是否有 SRT: {result.get('has_srt', False)}")
        
        if result.get('srt'):
            print(f"\n--- SRT 內容預覽 (前500字) ---")
            print(result['srt'][:500])
            print("...")
            
        if result.get('words'):
            print(f"\n單詞數量: {len(result['words'])}")
            print(f"前5個單詞:")
            for i, word in enumerate(result['words'][:5]):
                print(f"  {i+1}. '{word['text']}' [{word['start']:.2f}s - {word['end']:.2f}s]")
                
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")


async def main():
    """主測試函數"""
    print("開始測試 SRT 和時間戳功能...")
    
    # 測試 AssemblyAI
    await test_assemblyai_srt()
    
    # 測試 Deepgram
    await test_deepgram_srt()
    
    print("\n測試完成！")


if __name__ == "__main__":
    asyncio.run(main())