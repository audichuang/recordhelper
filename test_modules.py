#!/usr/bin/env python3
"""
模塊化測試腳本
驗證重構後的各個模塊是否正常工作
"""

import os
import sys
import logging

# 設置基本日誌
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_config_module():
    """測試配置模塊"""
    try:
        from config import AppConfig
        
        # 測試環境變數檢查
        required_env_vars = [
            'LINE_CHANNEL_ACCESS_TOKEN',
            'LINE_CHANNEL_SECRET', 
            'OPENAI_API_KEY',
            'GOOGLE_API_KEY_1'
        ]
        
        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logging.warning(f"缺少環境變數: {missing_vars}")
            logging.info("配置模塊結構正常，但需要設置環境變數才能完整測試")
        else:
            config = AppConfig.from_env()
            logging.info(f"✅ 配置模塊正常 - API金鑰數量: {len(config.google_api_keys)}")
        
        return True
    except Exception as e:
        logging.error(f"❌ 配置模塊錯誤: {e}")
        return False

def test_models_module():
    """測試數據模型模塊"""
    try:
        from models import ProcessingStatus, SummaryStorage, AudioProcessingError, APIError
        
        # 測試處理狀態管理
        status = ProcessingStatus()
        test_msg_id = "test_123"
        test_user_id = "user_456"
        
        # 測試開始處理
        assert status.start_processing(test_msg_id, test_user_id) == True
        assert status.is_processing(test_msg_id) == True
        assert status.start_processing(test_msg_id, test_user_id) == False  # 重複處理
        
        # 測試完成處理
        status.complete_processing(test_msg_id, True)
        assert status.is_completed(test_msg_id) == True
        
        # 測試摘要存儲
        storage = SummaryStorage()
        summary_id = storage.store_summary(
            test_user_id, "測試轉錄文字", "測試摘要", 10.5, 100
        )
        assert storage.get_summary(summary_id) is not None
        
        logging.info("✅ 數據模型模塊正常")
        return True
    except Exception as e:
        logging.error(f"❌ 數據模型模塊錯誤: {e}")
        return False

def test_audio_service_module():
    """測試音訊服務模塊"""
    try:
        from audio_service import AudioService, TempFileManager
        
        # 測試 FFmpeg 檢查
        ffmpeg_available = AudioService.check_ffmpeg()
        logging.info(f"FFmpeg 可用性: {'✅' if ffmpeg_available else '❌'}")
        
        # 測試臨時檔案管理
        temp_manager = TempFileManager("/tmp")
        temp_file = temp_manager.create_temp_file(".test")
        assert temp_file.endswith(".test")
        temp_manager.cleanup()
        
        logging.info("✅ 音訊服務模塊正常")
        return True
    except Exception as e:
        logging.error(f"❌ 音訊服務模塊錯誤: {e}")
        return False

def test_whisper_service_module():
    """測試 Whisper 服務模塊"""
    try:
        from whisper_service import WhisperService
        from config import AppConfig
        
        # 創建模擬配置
        class MockConfig:
            openai_api_key = "test_key"
            whisper_model = "whisper-1"
            max_retries = 3
        
        service = WhisperService(MockConfig())
        logging.info("✅ Whisper 服務模塊結構正常")
        return True
    except Exception as e:
        logging.error(f"❌ Whisper 服務模塊錯誤: {e}")
        return False

def test_gemini_service_module():
    """測試 Gemini 服務模塊"""
    try:
        from gemini_service import GeminiService
        
        # 創建模擬配置
        class MockConfig:
            google_api_keys = ["test_key_1", "test_key_2"]
            gemini_model = "gemini-2.5-flash-preview-05-20"
            thinking_budget = 512
            max_retries = 3
            full_analysis = True
            max_segments_for_full_analysis = 50
            segment_processing_delay = 0.5
        
        service = GeminiService(MockConfig())
        logging.info("✅ Gemini 服務模塊結構正常")
        return True
    except Exception as e:
        logging.error(f"❌ Gemini 服務模塊錯誤: {e}")
        return False

def test_gemini_audio_service_module():
    """測試 Gemini 音頻服務模塊"""
    try:
        from gemini_audio_service import GeminiAudioService
        
        # 創建模擬配置
        class MockConfig:
            google_api_keys = ["test_key_1", "test_key_2"]
        
        service = GeminiAudioService(MockConfig())
        logging.info("✅ Gemini 音頻服務模塊結構正常")
        return True
    except Exception as e:
        logging.error(f"❌ Gemini 音頻服務模塊錯誤: {e}")
        return False

def test_speech_to_text_service_module():
    """測試語音轉文字服務模塊"""
    try:
        from speech_to_text_service import SpeechToTextService
        
        # 創建模擬配置
        class MockConfig:
            speech_to_text_provider = "openai"
            openai_api_key = "test_key"
            whisper_model = "whisper-1"
            deepgram_api_keys = ["test_deepgram_key"]
            deepgram_model = "nova-2"
            deepgram_language = "zh-TW"
            local_whisper_model = "base"
            local_whisper_language = "zh"
            local_whisper_task = "transcribe"
            local_whisper_device = "cpu"
            google_api_keys = ["test_google_key"]  # 為 Gemini 音頻服務添加
        
        service = SpeechToTextService(MockConfig())
        logging.info("✅ 語音轉文字服務模塊結構正常")
        return True
    except Exception as e:
        logging.error(f"❌ 語音轉文字服務模塊錯誤: {e}")
        return False

def test_line_bot_service_module():
    """測試 LINE Bot 服務模塊"""
    try:
        from line_bot_service import AsyncLineBotService
        
        # 創建模擬配置
        class MockConfig:
            line_channel_access_token = "test_token"
            line_channel_secret = "test_secret"
            openai_api_key = "test_openai_key"
            google_api_keys = ["test_google_key"]
            whisper_model = "whisper-1"
            gemini_model = "gemini-2.5-flash-preview-05-20"
            thinking_budget = 512
            max_retries = 3
            temp_dir = "/tmp"
            max_workers = 4
            webhook_timeout = 25
            full_analysis = True
            max_segments_for_full_analysis = 50
            segment_processing_delay = 0.5
        
        # 注意：這裡不實際創建服務，只測試導入
        logging.info("✅ LINE Bot 服務模塊結構正常")
        return True
    except Exception as e:
        logging.error(f"❌ LINE Bot 服務模塊錯誤: {e}")
        return False

def test_web_routes_module():
    """測試 Web 路由模塊"""
    try:
        from web_routes import create_web_routes
        from flask import Flask
        
        app = Flask(__name__)
        
        # 創建模擬配置和服務
        class MockConfig:
            max_workers = 4
            webhook_timeout = 25
            thinking_budget = 512
            max_retries = 3
            google_api_keys = ["test_key"]
            full_analysis = True
            max_segments_for_full_analysis = 50
        
        class MockLineBotService:
            def __init__(self):
                self.handler = None
                self.processing_status = None
                self.summary_storage = None
                self.gemini_service = None
        
        # 測試路由創建（不實際創建，只測試導入）
        logging.info("✅ Web 路由模塊結構正常")
        return True
    except Exception as e:
        logging.error(f"❌ Web 路由模塊錯誤: {e}")
        return False

def test_main_module():
    """測試主模塊"""
    try:
        from main import create_app, setup_logging
        
        # 測試日誌設置
        setup_logging()
        
        logging.info("✅ 主模塊結構正常")
        return True
    except Exception as e:
        logging.error(f"❌ 主模塊錯誤: {e}")
        return False

def main():
    """運行所有測試"""
    print("🧪 開始模塊化測試...")
    print("=" * 50)
    
    tests = [
        ("配置模塊", test_config_module),
        ("數據模型模塊", test_models_module),
        ("音訊服務模塊", test_audio_service_module),
        ("Gemini 服務模塊", test_gemini_service_module),
        ("Gemini 音頻服務模塊", test_gemini_audio_service_module),
        ("語音轉文字服務模塊", test_speech_to_text_service_module),
        ("LINE Bot 服務模塊", test_line_bot_service_module),
        ("Web 路由模塊", test_web_routes_module),
        ("主模塊", test_main_module),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n🔍 測試 {test_name}...")
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logging.error(f"測試 {test_name} 時發生異常: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 測試結果:")
    print(f"✅ 通過: {passed}")
    print(f"❌ 失敗: {failed}")
    print(f"📈 成功率: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 所有模塊測試通過！重構成功！")
        return True
    else:
        print(f"\n⚠️  有 {failed} 個模塊需要修復")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 