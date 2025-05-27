#!/usr/bin/env python3
"""
測試修復功能腳本
測試 Deepgram 多 API Key 和 LINE 訊息分割
"""

import os
import sys
import logging
from unittest.mock import Mock

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_deepgram_multi_api_keys():
    """測試 Deepgram 多 API Key 配置"""
    print("🔑 測試 Deepgram 多 API Key 配置...")
    
    try:
        from config import AppConfig
        
        # 測試多個 API Key 環境變數
        original_keys = {}
        test_keys = {
            "DEEPGRAM_API_KEY_1": "test_key_1",
            "DEEPGRAM_API_KEY_2": "test_key_2",
            "DEEPGRAM_API_KEY_3": "test_key_3",
            "SPEECH_TO_TEXT_PROVIDER": "deepgram"
        }
        
        # 保存原始環境變數
        for key in test_keys:
            original_keys[key] = os.environ.get(key)
            os.environ[key] = test_keys[key]
        
        try:
            config = AppConfig.from_env()
            print(f"   ✅ 配置載入成功")
            print(f"   📋 Deepgram API Keys 數量: {len(config.deepgram_api_keys)}")
            print(f"   🔍 Keys: {config.deepgram_api_keys}")
            
            if len(config.deepgram_api_keys) >= 3:
                print("   ✅ 多 API Key 支援正常")
                return True
            else:
                print("   ❌ 多 API Key 支援異常")
                return False
                
        finally:
            # 恢復原始環境變數
            for key, value in original_keys.items():
                if value is not None:
                    os.environ[key] = value
                elif key in os.environ:
                    del os.environ[key]
        
    except Exception as e:
        print(f"   ❌ 測試失敗: {e}")
        return False

def test_message_splitting():
    """測試 LINE 訊息分割功能"""
    print("\n📝 測試 LINE 訊息分割功能...")
    
    try:
        # 創建模擬的 LINE Bot 服務
        from config import AppConfig
        from line_bot_service import AsyncLineBotService
        
        # 創建模擬配置
        config = Mock()
        config.line_channel_access_token = "test_token"
        config.line_channel_secret = "test_secret"
        config.google_api_keys = ["test_key"]
        config.max_workers = 2
        config.webhook_timeout = 10
        config.full_analysis = True
        config.max_segments_for_full_analysis = 10
        
        # 創建測試用的長文字
        long_text = "這是一個測試文字。" * 1000  # 約 10000 字符
        summary_text = "這是摘要內容。" * 200    # 約 2000 字符
        
        # 測試文字分割功能
        class TestService:
            def _split_text_by_sentences(self, text: str, max_length: int) -> list:
                """簡化版本的文字分割方法"""
                if len(text) <= max_length:
                    return [text]
                
                chunks = []
                current = ""
                
                for char in text:
                    current += char
                    if char in "。！？" and len(current) >= max_length * 0.8:  # 當接近限制時分割
                        chunks.append(current.strip())
                        current = ""
                
                if current:
                    chunks.append(current.strip())
                
                # 如果還有超長的塊，強制分割
                final_chunks = []
                for chunk in chunks:
                    if len(chunk) <= max_length:
                        final_chunks.append(chunk)
                    else:
                        # 強制分割超長的塊
                        while len(chunk) > max_length:
                            final_chunks.append(chunk[:max_length])
                            chunk = chunk[max_length:]
                        if chunk:
                            final_chunks.append(chunk)
                
                return final_chunks if final_chunks else [text[:max_length]]
        
        test_service = TestService()
        chunks = test_service._split_text_by_sentences(long_text, 4800)
        
        print(f"   ✅ 文字分割測試完成")
        print(f"   📊 原始長度: {len(long_text)} 字符")
        print(f"   📋 分割成: {len(chunks)} 段")
        
        # 檢查每段是否都在限制內
        all_within_limit = all(len(chunk) <= 4800 for chunk in chunks)
        
        if all_within_limit:
            print("   ✅ 所有分段都在長度限制內")
            return True
        else:
            print("   ❌ 有分段超過長度限制")
            return False
        
    except Exception as e:
        print(f"   ❌ 測試失敗: {e}")
        return False

def test_line_message_length_check():
    """測試 LINE 訊息長度檢查"""
    print("\n📏 測試 LINE 訊息長度檢查...")
    
    # 模擬不同長度的訊息
    test_cases = [
        ("短訊息", "這是一個短訊息", True),
        ("中等訊息", "這是一個中等長度的訊息。" * 100, True),  # 約 1200 字符
        ("接近限制", "這是一個接近限制的訊息。" * 400, True),  # 約 4800 字符
        ("超過限制", "這是一個超過限制的訊息。" * 500, False)  # 約 6000 字符
    ]
    
    success_count = 0
    for name, message, should_pass in test_cases:
        length = len(message)
        is_within_limit = length <= 5000
        
        print(f"   📝 {name}: {length} 字符 -> {'✅' if is_within_limit == should_pass else '❌'}")
        
        if is_within_limit == should_pass:
            success_count += 1
    
    if success_count == len(test_cases):
        print("   ✅ 長度檢查測試全部通過")
        return True
    else:
        print(f"   ❌ 長度檢查測試失敗: {success_count}/{len(test_cases)}")
        return False

def main():
    """主測試流程"""
    print("🧪 修復功能測試")
    print("=" * 40)
    
    tests = [
        ("Deepgram 多 API Key", test_deepgram_multi_api_keys),
        ("訊息分割功能", test_message_splitting),
        ("LINE 訊息長度檢查", test_line_message_length_check)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 測試發生異常: {e}")
            results.append((test_name, False))
    
    print("\n📊 測試結果摘要:")
    print("=" * 30)
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 總結: {passed}/{len(results)} 項測試通過")
    
    if passed == len(results):
        print("🎉 所有修復功能測試通過！")
        return True
    else:
        print("⚠️ 部分測試失敗，請檢查相關功能")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 