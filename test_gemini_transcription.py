#!/usr/bin/env python3
"""
測試修改後的 Gemini 音頻轉文字服務
"""

import logging
from gemini_audio_service import GeminiAudioService
from speech_to_text_service import SpeechToTextService
from config import AppConfig

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_interface_consistency():
    """測試接口一致性"""
    print("=== 測試 Gemini 音頻轉文字服務接口 ===\n")
    
    try:
        # 加載配置
        config = AppConfig.from_env()
        
        # 測試直接調用
        print("1. 測試直接調用 GeminiAudioService:")
        service = GeminiAudioService(config)
        usage_info = service.get_usage_info()
        print(f"服務名稱: {usage_info['service']}")
        print(f"提供商: {usage_info['provider']}")
        print(f"功能: {usage_info['features']}")
        print(f"狀態: {usage_info['status']}")
        print()
        
        # 測試通過統一接口調用
        print("2. 測試通過 SpeechToTextService 調用:")
        # 臨時改變配置來測試Gemini
        original_provider = config.speech_to_text_provider
        config.speech_to_text_provider = "gemini_audio"
        
        unified_service = SpeechToTextService(config)
        unified_usage_info = unified_service.get_usage_info()
        print(f"當前提供商: {unified_usage_info['current_provider']}")
        print(f"提供商名稱: {unified_service.get_provider_name()}")
        
        # 恢復原配置
        config.speech_to_text_provider = original_provider
        print()
        
        print("✅ 接口測試通過，Gemini 音頻服務已成功整合為純轉錄服務！")
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")

if __name__ == "__main__":
    test_interface_consistency() 