#!/usr/bin/env python3
"""
語音轉文字服務測試腳本
測試 OpenAI Whisper 和 Deepgram 切換功能
"""

import os
import sys
import logging
from config import AppConfig
from speech_to_text_service import SpeechToTextService

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_configuration():
    """測試配置載入"""
    print("🔧 測試配置載入...")
    
    try:
        config = AppConfig.from_env()
        print(f"✅ 配置載入成功")
        print(f"   語音轉文字服務: {config.speech_to_text_provider}")
        
        if config.speech_to_text_provider == "openai":
            print(f"   OpenAI API Key: {'已設定' if config.openai_api_key else '❌ 未設定'}")
            print(f"   Whisper 模型: {config.whisper_model}")
        elif config.speech_to_text_provider == "deepgram":
            key_count = len(config.deepgram_api_keys) if config.deepgram_api_keys else 0
            print(f"   Deepgram API Keys: {key_count} 個已設定")
            print(f"   Deepgram 模型: {config.deepgram_model}")
            print(f"   Deepgram 語言: {config.deepgram_language}")
        
        return config
    except Exception as e:
        print(f"❌ 配置載入失敗: {e}")
        return None

def test_service_initialization(config: AppConfig):
    """測試服務初始化"""
    print("\n🚀 測試服務初始化...")
    
    try:
        stt_service = SpeechToTextService(config)
        print(f"✅ 語音轉文字服務初始化成功")
        print(f"   當前服務: {stt_service.get_provider_name()}")
        
        # 獲取使用量資訊
        usage_info = stt_service.get_usage_info()
        print(f"   服務狀態: {usage_info}")
        
        return stt_service
    except Exception as e:
        print(f"❌ 服務初始化失敗: {e}")
        return None

def test_provider_switching():
    """測試服務提供商切換"""
    print("\n🔄 測試服務提供商切換...")
    
    # 測試不同的環境變數設定
    providers = ["openai", "deepgram"]
    
    for provider in providers:
        print(f"\n   測試 {provider} 服務...")
        
        # 暫時設定環境變數
        original_provider = os.environ.get("SPEECH_TO_TEXT_PROVIDER")
        os.environ["SPEECH_TO_TEXT_PROVIDER"] = provider
        
        try:
            config = AppConfig.from_env()
            print(f"     ✅ {provider} 配置載入成功")
            print(f"     選定服務: {config.speech_to_text_provider}")
        except Exception as e:
            print(f"     ❌ {provider} 配置失敗: {e}")
        finally:
            # 恢復原始設定
            if original_provider:
                os.environ["SPEECH_TO_TEXT_PROVIDER"] = original_provider
            elif "SPEECH_TO_TEXT_PROVIDER" in os.environ:
                del os.environ["SPEECH_TO_TEXT_PROVIDER"]

def test_dependencies():
    """測試依賴套件"""
    print("\n📦 測試依賴套件...")
    
    dependencies = [
        ("openai", "OpenAI"),
        ("deepgram", "Deepgram SDK")
    ]
    
    for module_name, display_name in dependencies:
        try:
            __import__(module_name)
            print(f"   ✅ {display_name} 已安裝")
        except ImportError:
            print(f"   ❌ {display_name} 未安裝 - 請執行: pip install {module_name}")

def print_usage_guide():
    """顯示使用指南"""
    print("\n📚 使用指南:")
    print("=" * 50)
    print("1. 安裝 Deepgram SDK:")
    print("   pip install deepgram-sdk>=4.0.0")
    print("\n2. 設定環境變數 (.env 文件):")
    print("   # 選擇語音轉文字服務")
    print("   SPEECH_TO_TEXT_PROVIDER=deepgram  # 或 openai")
    print("\n   # Deepgram 配置")
    print("   DEEPGRAM_API_KEY=你的_Deepgram_API_金鑰")
    print("   # 或支援多個 API Key 提高穩定性：")
    print("   DEEPGRAM_API_KEY_1=你的_第一個_Deepgram_API_金鑰")
    print("   DEEPGRAM_API_KEY_2=你的_第二個_Deepgram_API_金鑰")
    print("   DEEPGRAM_MODEL=nova-2")
    print("   DEEPGRAM_LANGUAGE=zh-TW")
    print("\n   # OpenAI 配置")
    print("   OPENAI_API_KEY=你的_OpenAI_API_金鑰")
    print("   WHISPER_MODEL_NAME=whisper-1")
    print("\n3. 重啟應用以應用變更")
    print("\n💰 成本比較:")
    print("   📈 OpenAI Whisper: $0.006/分鐘")
    print("   📉 Deepgram: $0.0043/分鐘 (便宜 ~28%)")
    print("\n🚀 功能特色:")
    print("   • 無縫切換服務提供商")
    print("   • 自動錯誤處理和重試")
    print("   • 統一的 API 介面")
    print("   • 實時狀態監控")

def main():
    """主測試流程"""
    print("🎙️ 語音轉文字服務測試")
    print("=" * 40)
    
    # 測試配置
    config = test_configuration()
    if not config:
        print("\n❌ 配置測試失敗，請檢查環境變數設定")
        print_usage_guide()
        return False
    
    # 測試服務初始化
    service = test_service_initialization(config)
    if not service:
        print("\n❌ 服務初始化失敗")
        return False
    
    # 測試依賴套件
    test_dependencies()
    
    # 測試服務切換
    test_provider_switching()
    
    print("\n✅ 所有測試完成！")
    print(f"🎯 當前使用: {service.get_provider_name()}")
    
    print_usage_guide()
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 