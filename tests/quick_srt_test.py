#!/usr/bin/env python3
"""
快速測試 AssemblyAI 和 Deepgram 的 SRT 輸出
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加父目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.audio.speech_to_text_async import SpeechToTextService
from services.audio.assemblyai_async import AssemblyAIProvider
from services.audio.deepgram_async import DeepgramProvider


async def test_single_provider(provider_name: str, file_path: str):
    """測試單一服務提供者"""
    print(f"\n{'='*50}")
    print(f"測試 {provider_name.upper()}")
    print('='*50)
    
    # 創建服務實例
    if provider_name == "assemblyai":
        provider = AssemblyAIProvider()
    elif provider_name == "deepgram":
        provider = DeepgramProvider()
    else:
        print(f"不支援的 provider: {provider_name}")
        return
    
    try:
        # 轉錄音檔
        print(f"正在處理: {file_path}")
        result = await provider.transcribe_audio(file_path)
        
        # 顯示結果
        print(f"\n轉錄成功: {result['success']}")
        
        if result['success']:
            # 顯示基本資訊
            print(f"轉錄文字長度: {len(result.get('transcript', ''))}")
            print(f"包含 SRT: {result.get('has_srt', False)}")
            
            # 如果有 SRT，顯示前幾行
            if result.get('has_srt') and result.get('srt'):
                srt_lines = result['srt'].strip().split('\n')
                print(f"\nSRT 總行數: {len(srt_lines)}")
                print("\nSRT 前 20 行:")
                print('-' * 40)
                for line in srt_lines[:20]:
                    print(line)
                
                # 儲存完整 SRT
                output_file = f"{provider_name}_output.srt"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(result['srt'])
                print(f"\n完整 SRT 已儲存到: {output_file}")
            
            # 顯示前 200 字的轉錄文字
            print(f"\n轉錄文字預覽:")
            print('-' * 40)
            print(result.get('transcript', '')[:200] + "...")
            
        else:
            print(f"錯誤: {result.get('error', '未知錯誤')}")
            
    except Exception as e:
        print(f"發生異常: {str(e)}")
        import traceback
        traceback.print_exc()


async def main():
    """主函數"""
    # 檢查命令行參數
    if len(sys.argv) < 2:
        print("使用方式: python quick_srt_test.py <音檔路徑> [provider]")
        print("provider 可選: assemblyai, deepgram, both (預設)")
        sys.exit(1)
    
    file_path = sys.argv[1]
    provider = sys.argv[2] if len(sys.argv) > 2 else "both"
    
    # 檢查檔案是否存在
    if not os.path.exists(file_path):
        print(f"錯誤: 檔案不存在 - {file_path}")
        sys.exit(1)
    
    print(f"測試檔案: {file_path}")
    print(f"檔案大小: {os.path.getsize(file_path) / 1024 / 1024:.2f} MB")
    
    # 執行測試
    if provider == "both":
        await test_single_provider("assemblyai", file_path)
        await test_single_provider("deepgram", file_path)
    elif provider in ["assemblyai", "deepgram"]:
        await test_single_provider(provider, file_path)
    else:
        print(f"不支援的 provider: {provider}")
        print("請使用: assemblyai, deepgram, 或 both")


if __name__ == "__main__":
    asyncio.run(main())