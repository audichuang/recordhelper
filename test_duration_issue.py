#!/usr/bin/env python3
"""
测试音频时长计算问题
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from services.audio.speech_to_text_async import AsyncSpeechToTextService
from config import AppConfig

load_dotenv()

async def test_duration_calculation():
    """测试音频时长计算"""
    
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
        
        # 测试时长计算
        config = AppConfig.from_env()
        stt_service = AsyncSpeechToTextService(config)
        
        print(f"\n🔍 开始测试时长计算...")
        
        # 从音频数据计算时长
        duration = await stt_service.get_audio_duration_from_data(recording['audio_data'])
        
        if duration:
            print(f"✅ 计算得到的时长: {duration:.3f} 秒")
            print(f"📊 预期时长: ~51 秒")
            print(f"❌ 差距: {abs(duration - 51):.3f} 秒")
        else:
            print("❌ 无法计算音频时长")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(test_duration_calculation())