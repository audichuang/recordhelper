#!/usr/bin/env python3
"""
Deepgram 服務切換演示腳本
展示如何在 OpenAI Whisper 和 Deepgram 之間切換
"""

import os
import sys
import logging
from config import AppConfig
from services.audio.speech_to_text import SpeechToTextService

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def demo_service_switching():
    """演示服務切換功能"""
    print("🎙️ Deepgram 服務切換演示")
    print("=" * 50)
    
    # 保存原始環境變數
    original_provider = os.environ.get("SPEECH_TO_TEXT_PROVIDER")
    
    providers = [
        ("openai", "OpenAI Whisper"),
        ("deepgram", "Deepgram")
    ]
    
    for provider_key, provider_name in providers:
        print(f"\n🔄 切換到 {provider_name}...")
        
        # 設定環境變數
        os.environ["SPEECH_TO_TEXT_PROVIDER"] = provider_key
        
        try:
            # 重新載入配置
            config = AppConfig.from_env()
            print(f"   ✅ 配置載入成功")
            print(f"   📋 選定服務: {config.speech_to_text_provider}")
            
            # 初始化服務
            stt_service = SpeechToTextService(config)
            print(f"   🚀 服務初始化成功: {stt_service.get_provider_name()}")
            
            # 獲取服務資訊
            usage_info = stt_service.get_usage_info()
            print(f"   📊 服務狀態: {usage_info['status']}")
            
            if provider_key == "openai":
                print(f"   🎯 模型: {usage_info.get('model', 'N/A')}")
                print(f"   💰 成本: $0.006/分鐘")
            elif provider_key == "deepgram":
                print(f"   🎯 模型: {usage_info.get('model', 'N/A')}")
                print(f"   🌐 語言: {usage_info.get('language', 'N/A')}")
                print(f"   💰 成本: $0.0043/分鐘 (節省28%)")
            
        except Exception as e:
            print(f"   ❌ 切換失敗: {e}")
            if "API_KEY" in str(e):
                print(f"   💡 提示: 請設定 {provider_key.upper()}_API_KEY 環境變數")
    
    # 恢復原始設定
    if original_provider:
        os.environ["SPEECH_TO_TEXT_PROVIDER"] = original_provider
    elif "SPEECH_TO_TEXT_PROVIDER" in os.environ:
        del os.environ["SPEECH_TO_TEXT_PROVIDER"]

def show_cost_comparison():
    """顯示成本比較"""
    print("\n💰 成本效益分析")
    print("=" * 30)
    
    scenarios = [
        ("每日 1 小時錄音", 60, 30),
        ("每週 5 小時錄音", 300, 4),
        ("每月 20 小時錄音", 1200, 1)
    ]
    
    print(f"{'場景':<15} {'OpenAI':<10} {'Deepgram':<10} {'月節省':<10}")
    print("-" * 50)
    
    for scenario, minutes_per_month, _ in scenarios:
        openai_cost = minutes_per_month * 0.006
        deepgram_cost = minutes_per_month * 0.0043
        savings = openai_cost - deepgram_cost
        
        print(f"{scenario:<15} ${openai_cost:<9.2f} ${deepgram_cost:<9.2f} ${savings:<9.2f}")

def show_feature_comparison():
    """顯示功能比較"""
    print("\n🔍 功能特色比較")
    print("=" * 40)
    
    features = [
        ("精確度", "🎯 極高", "🎯 高"),
        ("速度", "⚡ 快", "⚡ 極快"),
        ("成本", "💰 較高", "💰 較低"),
        ("語言支援", "🌍 廣泛", "🌍 廣泛"),
        ("檔案大小限制", "📁 25MB", "📁 100MB"),
        ("即時轉錄", "❌ 不支援", "✅ 支援"),
        ("說話人識別", "❌ 不支援", "✅ 支援"),
        ("自訂詞彙", "❌ 不支援", "✅ 支援")
    ]
    
    print(f"{'功能':<12} {'OpenAI Whisper':<15} {'Deepgram':<15}")
    print("-" * 45)
    
    for feature, openai_val, deepgram_val in features:
        print(f"{feature:<12} {openai_val:<15} {deepgram_val:<15}")

def main():
    """主演示流程"""
    demo_service_switching()
    show_cost_comparison()
    show_feature_comparison()
    
    print("\n🎯 建議使用場景:")
    print("=" * 25)
    print("📈 選擇 OpenAI Whisper 當:")
    print("   • 需要最高精確度")
    print("   • 處理重要會議錄音")
    print("   • 成本不是主要考量")
    
    print("\n📉 選擇 Deepgram 當:")
    print("   • 需要控制成本")
    print("   • 大量錄音處理")
    print("   • 需要即時轉錄功能")
    print("   • 需要說話人識別")
    
    print("\n🚀 快速切換指令:")
    print("   切換到 Deepgram: export SPEECH_TO_TEXT_PROVIDER=deepgram")
    print("   切換到 OpenAI:   export SPEECH_TO_TEXT_PROVIDER=openai")
    print("   然後重啟服務:    python main.py")

if __name__ == "__main__":
    main() 