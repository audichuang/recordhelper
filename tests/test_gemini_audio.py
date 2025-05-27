#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gemini 音頻服務測試腳本
測試直接音頻處理功能
"""

import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 載入環境變數
load_dotenv()

# 新增專案根目錄到 Python 路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import AppConfig
from services.audio.from gemini_audio_service import import GeminiAudioService
from models.base import APIError


def test_gemini_audio_basic():
    """測試基本 Gemini 音頻功能"""
    print("🧪 測試 Gemini 音頻服務基本功能")
    
    try:
        # 載入配置
        config = AppConfig.from_env()
        
        # 創建服務
        service = GeminiAudioService(config)
        
        # 顯示服務資訊
        usage_info = service.get_usage_info()
        print(f"✅ 服務初始化成功")
        print(f"📊 服務資訊: {usage_info}")
        
        return True
        
    except Exception as e:
        print(f"❌ 基本功能測試失敗: {e}")
        return False


def test_gemini_audio_file(audio_file_path: str):
    """測試音頻文件處理"""
    print(f"🎵 測試音頻文件處理: {audio_file_path}")
    
    if not os.path.exists(audio_file_path):
        print(f"❌ 音頻文件不存在: {audio_file_path}")
        return False
    
    try:
        # 載入配置
        config = AppConfig.from_env()
        service = GeminiAudioService(config)
        
        # 檢查文件大小
        file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
        print(f"📁 文件大小: {file_size_mb:.1f}MB")
        
        if file_size_mb > 100:
            print("⚠️ 文件太大，Gemini 最大支援 100MB")
            return False
        
        # 測試 Token 計算
        print("🔢 計算 Token 數量...")
        try:
            tokens = service.count_tokens(audio_file_path)
            print(f"📊 Token 數量: {tokens}")
        except Exception as e:
            print(f"⚠️ Token 計算失敗: {e}")
        
        # 測試基本轉錄
        print("🎤 測試基本轉錄功能...")
        try:
            transcription = service.transcribe_audio(audio_file_path)
            print(f"✅ 轉錄成功")
            print(f"📝 轉錄長度: {len(transcription)} 字符")
            print(f"📄 轉錄預覽: {transcription[:200]}...")
            
        except Exception as e:
            print(f"❌ 轉錄失敗: {e}")
            return False
        
        # 測試轉錄+摘要組合功能
        print("📝 測試轉錄+摘要組合功能...")
        try:
            result = service.transcribe_and_summarize(audio_file_path)
            print(f"✅ 組合處理成功")
            print(f"📝 轉錄長度: {len(result['transcription'])} 字符")
            print(f"📋 摘要長度: {len(result['summary'])} 字符")
            print(f"⏱️ 處理時間: {result['processing_time']:.2f}秒")
            print(f"🎵 估計時長: {result['estimated_duration']:.1f}分鐘")
            
            print(f"\n📄 轉錄內容:\n{result['transcription'][:300]}...")
            print(f"\n📋 摘要內容:\n{result['summary'][:300]}...")
            
        except Exception as e:
            print(f"❌ 組合處理失敗: {e}")
            return False
        
        # 測試自定義分析
        print("🔍 測試自定義音頻分析...")
        try:
            analysis = service.analyze_audio_content(
                audio_file_path, 
                "請分析這個音頻的情緒基調、說話風格，並評估音頻品質。"
            )
            print(f"✅ 自定義分析成功")
            print(f"🔍 分析結果:\n{analysis[:300]}...")
            
        except Exception as e:
            print(f"❌ 自定義分析失敗: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ 音頻文件測試失敗: {e}")
        return False


def test_gemini_audio_formats():
    """測試不同音頻格式支援"""
    print("🎵 測試音頻格式支援")
    
    try:
        config = AppConfig.from_env()
        service = GeminiAudioService(config)
        
        # 測試不同格式的 MIME 類型檢測
        test_files = [
            "test.mp3",
            "test.wav", 
            "test.aiff",
            "test.aac",
            "test.ogg",
            "test.flac",
            "test.m4a"
        ]
        
        print("📋 支援的音頻格式:")
        for file_path in test_files:
            mime_type = service._detect_audio_mime_type(file_path)
            print(f"  {file_path} -> {mime_type}")
        
        usage_info = service.get_usage_info()
        print(f"📊 支援格式: {usage_info['supported_formats']}")
        print(f"📏 最大文件大小: {usage_info['max_file_size_mb']}MB")
        print(f"⏰ 最大時長: {usage_info['max_duration_hours']}小時")
        print(f"🛠️ 功能特性: {usage_info['features']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 格式測試失敗: {e}")
        return False


def main():
    """主測試函數"""
    print("🚀 Gemini 音頻服務測試開始")
    print("=" * 50)
    
    # 基本功能測試
    if not test_gemini_audio_basic():
        print("❌ 基本功能測試失敗，退出")
        return
    
    print()
    
    # 格式支援測試
    if not test_gemini_audio_formats():
        print("❌ 格式測試失敗")
    
    print()
    
    # 實際文件測試
    test_files = [
        "test_audio.mp3",
        "sample.wav",
        "/tmp/test_recording.mp3"  # 可能的測試文件路徑
    ]
    
    file_tested = False
    for audio_file in test_files:
        if os.path.exists(audio_file):
            print(f"🎯 找到測試文件: {audio_file}")
            if test_gemini_audio_file(audio_file):
                file_tested = True
                break
            print()
    
    if not file_tested:
        print("📁 沒有找到測試音頻文件")
        print("💡 建議：")
        print("   1. 在專案目錄放置一個名為 'test_audio.mp3' 的音頻文件")
        print("   2. 或修改 test_files 列表中的路徑")
        print("   3. 確保文件小於 100MB")
    
    print()
    print("✅ Gemini 音頻服務測試完成")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ 測試被用戶中斷")
    except Exception as e:
        logging.error(f"測試過程發生錯誤: {e}")
        print(f"❌ 測試失敗: {e}") 