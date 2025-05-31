#!/usr/bin/env python3
"""檢查 AssemblyAI 回應的完整結構"""
import asyncio
import os
import sys
import json

# 添加專案路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import assemblyai as aai
from config import AppConfig


async def inspect_response():
    """檢查 AssemblyAI 回應"""
    print("🔍 檢查 AssemblyAI 回應結構...")
    
    # 載入配置
    config = AppConfig.from_env()
    
    # 設定 API 金鑰
    aai.settings.api_key = config.assemblyai_api_keys[0]
    
    # 配置
    aai_config = aai.TranscriptionConfig(
        language_code="zh",
        speech_model=aai.SpeechModel.best,
        speaker_labels=True,
        punctuate=True,
        format_text=True,
    )
    
    # 創建轉錄器
    transcriber = aai.Transcriber(config=aai_config)
    
    # 測試檔案
    test_file = "/Users/audi/Downloads/重陽橋30號_7.wav"
    
    print(f"📍 轉錄檔案: {test_file}")
    
    # 執行轉錄
    loop = asyncio.get_event_loop()
    transcript = await loop.run_in_executor(
        None, 
        transcriber.transcribe, 
        test_file
    )
    
    print("\n📝 Transcript 物件屬性:")
    for attr in dir(transcript):
        if not attr.startswith('_'):
            value = getattr(transcript, attr, None)
            if not callable(value):
                print(f"   {attr}: {value}")
    
    print("\n📊 音頻時長資訊:")
    print(f"   audio_duration: {transcript.audio_duration} ms")
    print(f"   轉換為秒: {transcript.audio_duration / 1000 if transcript.audio_duration else 'None'} s")
    
    # 嘗試訪問原始 JSON
    if hasattr(transcript, 'json_response'):
        print("\n📄 原始 JSON 回應:")
        print(json.dumps(transcript.json_response, indent=2)[:500] + "...")


if __name__ == "__main__":
    # 設定 SSL 證書
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    os.environ['HTTPX_CA_BUNDLE'] = certifi.where()
    
    asyncio.run(inspect_response())