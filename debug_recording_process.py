#!/usr/bin/env python3
"""
调试录音处理过程中的时长问题
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from services.audio.speech_to_text_async import AsyncSpeechToTextService
from config import AppConfig
import json

load_dotenv()

async def debug_recording_process():
    """调试录音处理过程"""
    
    # 从数据库获取有问题的音频数据
    conn = await asyncpg.connect(
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT', 5432)),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    
    try:
        # 获取"短录音"的音频数据
        recording = await conn.fetchrow('''
            SELECT audio_data, format, mime_type, file_size
            FROM recordings 
            WHERE title = '短錄音'
            ORDER BY created_at DESC 
            LIMIT 1
        ''')
        
        if not recording:
            print("❌ 找不到'短录音'记录")
            return
            
        print(f"📊 录音信息:")
        print(f"   文件大小: {recording['file_size']} bytes")
        print(f"   格式: {recording['format']}")
        print(f"   MIME类型: {recording['mime_type']}")
        
        # 模拟完整的转录过程
        config = AppConfig.from_env()
        stt_service = AsyncSpeechToTextService(config)
        
        print(f"\n🔍 开始模拟完整的转录过程...")
        print(f"🔧 当前语音转文字提供商: {config.speech_to_text_provider}")
        
        # 执行完整的转录过程
        result = await stt_service.transcribe_audio_data(
            recording['audio_data'], 
            recording['format'], 
            recording['mime_type']
        )
        
        print(f"\n📋 转录结果:")
        print(f"   文本长度: {len(result.get('transcript', ''))}")
        print(f"   时长: {result.get('duration')} 秒")
        print(f"   提供商: {result.get('provider')}")
        print(f"   模型: {result.get('model')}")
        print(f"   置信度: {result.get('confidence')}")
        
        # 检查是否有SRT内容
        if result.get('srt'):
            print(f"   SRT内容长度: {len(result.get('srt'))}")
            
        # 检查是否有时间戳数据
        if result.get('words'):
            print(f"   单词时间戳数量: {len(result.get('words'))}")
            
        # 详细检查时长相关数据
        print(f"\n🔍 详细时长信息:")
        for key, value in result.items():
            if 'duration' in key.lower() or 'time' in key.lower():
                print(f"   {key}: {value}")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(debug_recording_process())