#!/usr/bin/env python3
"""
測試本地 Whisper 服務
使用方法: python test_local_whisper.py [音訊檔案路徑]
"""

import sys
import time
import logging
from pathlib import Path
from config import AppConfig
from local_whisper_service import LocalWhisperService

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_local_whisper(audio_file_path=None):
    """測試本地 Whisper 服務"""
    
    # 創建測試配置
    class TestConfig:
        local_whisper_model = "turbo"  # 使用最新的 turbo 模型
        local_whisper_language = "zh"  # 中文
        local_whisper_task = "transcribe"  # 轉錄
    
    try:
        print("=" * 60)
        print("本地 OpenAI Whisper 服務測試")
        print("=" * 60)
        
        # 初始化服務
        print("正在初始化本地 Whisper 服務...")
        config = TestConfig()
        service = LocalWhisperService(config)
        
        # 顯示服務資訊
        usage_info = service.get_usage_info()
        print(f"\n服務資訊:")
        for key, value in usage_info.items():
            print(f"  {key}: {value}")
        
        # 顯示可用模型
        models = service.get_available_models()
        print(f"\n可用模型: {', '.join(models)}")
        
        # 顯示支援語言
        languages = service.get_available_languages()
        print(f"\n支援語言數量: {len(languages)}")
        print(f"部分支援語言: {list(languages.items())[:10]}")
        
        # 如果提供音訊檔案，進行轉錄測試
        if audio_file_path:
            if not Path(audio_file_path).exists():
                print(f"\n錯誤: 找不到音訊檔案 {audio_file_path}")
                return
            
            print(f"\n正在轉錄音訊檔案: {audio_file_path}")
            print("-" * 40)
            
            # 基本轉錄
            start_time = time.time()
            result = service.transcribe_audio(audio_file_path)
            basic_time = time.time() - start_time
            
            print(f"基本轉錄結果 (耗時 {basic_time:.2f}秒):")
            print(f"  文字: {result}")
            print(f"  長度: {len(result)} 字符")
            
            # 詳細轉錄（包含時間戳）
            print("\n正在進行詳細轉錄（包含時間戳）...")
            start_time = time.time()
            detailed_result = service.transcribe_with_timestamps(audio_file_path)
            detailed_time = time.time() - start_time
            
            print(f"\n詳細轉錄結果 (耗時 {detailed_time:.2f}秒):")
            print(f"  文字: {detailed_result['text']}")
            print(f"  檢測語言: {detailed_result['language']}")
            print(f"  處理時間: {detailed_result['processing_time']:.2f}秒")
            print(f"  段落數量: {len(detailed_result['segments'])}")
            
            if detailed_result['segments']:
                print("\n時間戳詳情:")
                for i, segment in enumerate(detailed_result['segments'][:5]):  # 顯示前5個段落
                    start = segment['start']
                    end = segment['end']
                    text = segment['text'].strip()
                    print(f"  [{start:6.2f}s - {end:6.2f}s] {text}")
                
                if len(detailed_result['segments']) > 5:
                    print(f"  ... 還有 {len(detailed_result['segments']) - 5} 個段落")
        
        else:
            print("\n提示: 要測試音訊轉錄，請提供音訊檔案路徑")
            print("使用方法: python test_local_whisper.py [音訊檔案路徑]")
        
        print("\n測試完成！")
        
    except Exception as e:
        print(f"\n測試失敗: {e}")
        logging.error(f"測試錯誤: {e}", exc_info=True)

def main():
    """主函數"""
    audio_file = sys.argv[1] if len(sys.argv) > 1 else None
    test_local_whisper(audio_file)

if __name__ == "__main__":
    main() 