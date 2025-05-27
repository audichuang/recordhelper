#!/usr/bin/env python3
"""
項目結構重組驗證測試
確保所有服務能正常導入和初始化
"""

import sys
import os
import logging

# 添加項目根目錄到Python路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_imports():
    """測試所有主要模塊的導入"""
    print("🔍 測試模塊導入...")
    
    # 核心服務（必須成功）
    core_tests = [
        ("配置管理", "config", "AppConfig"),
        ("基礎模型", "models.base", "APIError, ProcessingStatus"),
        ("音頻統一服務", "services.audio.speech_to_text", "SpeechToTextService"),
        ("Whisper服務", "services.audio.whisper", "WhisperService"),
        ("Deepgram服務", "services.audio.deepgram", "DeepgramService"),
        ("Gemini音頻服務", "services.audio.gemini_audio", "GeminiAudioService"),
        ("音頻基礎服務", "services.audio.base", "AudioService"),
        ("Gemini AI服務", "services.ai.gemini", "GeminiService"),
        ("LINE Bot服務", "services.messaging.line_bot", "AsyncLineBotService"),
        ("Web路由服務", "services.web.routes", "create_web_routes"),
    ]
    
    # 可選服務（依賴額外套件）
    optional_tests = [
        ("本地Whisper服務", "services.audio.local_whisper", "LocalWhisperService"),
        ("Faster Whisper服務", "services.audio.faster_whisper", "FasterWhisperService"),
    ]
    
    success_count = 0
    total_tests = len(core_tests)
    
    # 測試核心服務
    for name, module, classes in core_tests:
        try:
            __import__(module)
            print(f"   ✅ {name}: {classes}")
            success_count += 1
        except ImportError as e:
            print(f"   ❌ {name}: 導入失敗 - {e}")
        except Exception as e:
            print(f"   ⚠️  {name}: 其他錯誤 - {e}")
    
    # 測試可選服務
    print("\n   可選服務（需要額外套件）:")
    for name, module, classes in optional_tests:
        try:
            __import__(module)
            print(f"   ✅ {name}: {classes}")
        except ImportError as e:
            print(f"   ⚠️  {name}: 套件未安裝 - {classes}")
        except Exception as e:
            print(f"   ❌ {name}: 其他錯誤 - {e}")
    
    print(f"\n📊 核心導入測試結果: {success_count}/{total_tests} 成功")
    return success_count == total_tests

def test_service_initialization():
    """測試服務初始化"""
    print("\n🚀 測試服務初始化...")
    
    try:
        from config import AppConfig
        config = AppConfig.from_env()
        print("   ✅ 配置載入成功")
        
        # 測試音頻服務
        from services.audio.speech_to_text import SpeechToTextService
        stt_service = SpeechToTextService(config)
        print(f"   ✅ 語音轉文字服務初始化成功 ({stt_service.get_provider_name()})")
        
        # 測試AI服務
        from services.ai.gemini import GeminiService
        ai_service = GeminiService(config)
        print("   ✅ Gemini AI服務初始化成功")
        
        # 測試LINE Bot服務
        from services.messaging.line_bot import AsyncLineBotService
        linebot_service = AsyncLineBotService(config)
        print("   ✅ LINE Bot服務初始化成功")
        
        return True
        
    except Exception as e:
        print(f"   ❌ 服務初始化失敗: {e}")
        return False

def test_directory_structure():
    """驗證目錄結構"""
    print("\n📁 驗證目錄結構...")
    
    import os
    
    expected_dirs = [
        "models",
        "services",
        "services/audio", 
        "services/ai",
        "services/messaging",
        "services/web",
        "tests",
        "docs"
    ]
    
    expected_files = [
        "config.py",
        "main.py",
        "models/__init__.py",
        "models/base.py",
        "services/__init__.py",
        "services/audio/__init__.py",
        "services/audio/speech_to_text.py",
        "services/ai/__init__.py",
        "services/ai/gemini.py",
        "services/messaging/__init__.py",
        "services/messaging/line_bot.py",
        "services/web/__init__.py",
        "services/web/routes.py",
        "tests/__init__.py"
    ]
    
    missing_dirs = []
    missing_files = []
    
    for dir_path in expected_dirs:
        if not os.path.isdir(dir_path):
            missing_dirs.append(dir_path)
    
    for file_path in expected_files:
        if not os.path.isfile(file_path):
            missing_files.append(file_path)
    
    if not missing_dirs and not missing_files:
        print("   ✅ 所有必要的目錄和文件都存在")
        return True
    else:
        if missing_dirs:
            print(f"   ❌ 缺少目錄: {missing_dirs}")
        if missing_files:
            print(f"   ❌ 缺少文件: {missing_files}")
        return False

def main():
    """主測試流程"""
    print("🏗️  項目結構重組驗證測試")
    print("=" * 50)
    
    # 測試導入
    import_success = test_imports()
    
    # 測試目錄結構
    structure_success = test_directory_structure()
    
    # 測試服務初始化
    init_success = test_service_initialization()
    
    # 總結
    print("\n" + "=" * 50)
    if import_success and structure_success and init_success:
        print("🎉 所有測試通過！項目結構重組成功！")
        print("\n✨ 重組優勢:")
        print("   📂 清晰的功能分類")
        print("   🔧 更好的模塊化")
        print("   🧪 測試代碼分離")
        print("   📚 文檔集中管理")
        print("   🚀 易於擴展和維護")
        return True
    else:
        print("❌ 部分測試失敗，請檢查項目結構")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 