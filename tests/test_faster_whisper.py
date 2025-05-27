#!/usr/bin/env python3
"""
測試 Faster-Whisper 服務
使用方法: python test_faster_whisper.py [音訊檔案路徑]
"""

import sys
import time
import logging
from pathlib import Path
from services.audio.from faster_whisper_service import import FasterWhisperService

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_faster_whisper(audio_file_path=None):
    """測試 Faster-Whisper 服務"""
    
    # 創建測試配置
    class TestConfig:
        local_whisper_model = "small"  # 使用 small 模型平衡速度和準確性
        local_whisper_language = "zh"  # 中文
        local_whisper_task = "transcribe"  # 轉錄
    
    try:
        print("=" * 60)
        print("Faster-Whisper 高性能語音轉文字服務測試")
        print("=" * 60)
        
        # 初始化服務
        print("正在初始化 Faster-Whisper 服務...")
        config = TestConfig()
        service = FasterWhisperService(config)
        
        # 顯示服務資訊
        usage_info = service.get_usage_info()
        print(f"\n服務資訊:")
        for key, value in usage_info.items():
            print(f"  {key}: {value}")
        
        # 顯示可用模型
        models = service.get_available_models()
        print(f"\n可用模型: {', '.join(models)}")
        
        # 如果提供音訊檔案，進行轉錄測試
        if audio_file_path:
            if not Path(audio_file_path).exists():
                print(f"\n錯誤: 找不到音訊檔案 {audio_file_path}")
                return
            
            print(f"\n正在轉錄音訊檔案: {audio_file_path}")
            print("-" * 40)
            
            # 基本轉錄
            print("開始基本轉錄...")
            start_time = time.time()
            result = service.transcribe_audio(audio_file_path)
            basic_time = time.time() - start_time
            
            print(f"\n基本轉錄結果 (耗時 {basic_time:.2f}秒):")
            print(f"  文字: {result}")
            print(f"  長度: {len(result)} 字符")
            
            # 詳細轉錄（包含時間戳）
            print("\n開始詳細轉錄（包含時間戳）...")
            start_time = time.time()
            detailed_result = service.transcribe_with_timestamps(audio_file_path)
            detailed_time = time.time() - start_time
            
            print(f"\n詳細轉錄結果 (耗時 {detailed_time:.2f}秒):")
            print(f"  文字: {detailed_result['text']}")
            print(f"  檢測語言: {detailed_result['language']}")
            print(f"  語言概率: {detailed_result.get('language_probability', 0):.2f}")
            print(f"  處理時間: {detailed_result['processing_time']:.2f}秒")
            print(f"  音訊長度: {detailed_result.get('audio_duration', 0):.2f}秒")
            print(f"  速度比率: {detailed_result.get('speed_ratio', 0):.2f}x")
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
            
            # 性能基準測試
            print("\n進行性能基準測試...")
            benchmark = service.benchmark_performance(audio_file_path)
            
            if "error" not in benchmark:
                print(f"\n性能測試結果:")
                print(f"  處理時間: {benchmark['processing_time']:.2f}秒")
                print(f"  記憶體使用: {benchmark['memory_used']:.1f}MB")
                print(f"  峰值記憶體: {benchmark['peak_memory']:.1f}MB")
                print(f"  每秒字數: {benchmark['words_per_second']:.1f} 字/秒")
        
        else:
            print("\n提示: 要測試音訊轉錄，請提供音訊檔案路徑")
            print("使用方法: python test_faster_whisper.py [音訊檔案路徑]")
            
            # 顯示建議的測試模型
            print("\n建議測試配置:")
            print("  Mac M4 Pro 速度優先: small 模型")
            print("  Mac M4 Pro 準確性優先: turbo 模型")
            print("  記憶體受限: tiny 或 base 模型")
        
        print("\n測試完成！")
        print("\n性能說明:")
        print("  - Faster-Whisper 比原版 OpenAI Whisper 快 4-8 倍")
        print("  - 使用 int8 量化減少記憶體使用")
        print("  - 充分利用 Mac M4 Pro 的多核心 CPU")
        
    except Exception as e:
        print(f"\n測試失敗: {e}")
        logging.error(f"測試錯誤: {e}", exc_info=True)

def compare_models():
    """比較不同模型的性能"""
    print("\nMac M4 Pro 模型性能比較:")
    print("┌─────────┬─────────┬─────────┬──────────┬──────────┐")
    print("│ 模型    │ 大小    │ 速度    │ 準確性   │ 記憶體   │")
    print("├─────────┼─────────┼─────────┼──────────┼──────────┤")
    print("│ tiny    │ 39MB    │ 極快    │ 普通     │ 低       │")
    print("│ base    │ 74MB    │ 快      │ 好       │ 低       │")
    print("│ small   │ 244MB   │ 較快    │ 很好     │ 中等     │")
    print("│ medium  │ 769MB   │ 中等    │ 很高     │ 高       │")
    print("│ turbo   │ 809MB   │ 快      │ 最高     │ 高       │")
    print("└─────────┴─────────┴─────────┴──────────┴──────────┘")

def main():
    """主函數"""
    audio_file = sys.argv[1] if len(sys.argv) > 1 else None
    
    if len(sys.argv) > 1 and sys.argv[1] == "--compare":
        compare_models()
    else:
        test_faster_whisper(audio_file)

if __name__ == "__main__":
    main() 