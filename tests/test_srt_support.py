"""
測試各語音識別服務的 SRT 字幕格式支援
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# 添加項目根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import AppConfig
from services.audio.assemblyai_async import AsyncAssemblyAIService
from services.audio.deepgram_async import AsyncDeepgramService
from services.audio.gemini_audio_async import AsyncGeminiAudioService
from services.audio.srt_formatter import SRTFormatter

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_srt_formatter():
    """測試 SRT 格式化工具"""
    print("\n=== 測試 SRT 格式化工具 ===")
    
    # 測試時間戳格式化
    print("\n1. 測試時間戳格式化:")
    test_times = [0, 61.5, 3661.123]
    for time in test_times:
        formatted = SRTFormatter.format_timestamp(time)
        print(f"  {time}秒 -> {formatted}")
    
    # 測試單個字幕條目
    print("\n2. 測試單個字幕條目:")
    entry = SRTFormatter.create_subtitle_entry(
        1, 0, 5.5, "這是一個測試字幕", "說話者A"
    )
    print(entry)
    
    # 測試從單詞生成 SRT
    print("\n3. 測試從單詞數據生成 SRT:")
    words = [
        {'text': '你好', 'start': 0, 'end': 0.5, 'speaker': 'A'},
        {'text': '今天', 'start': 0.5, 'end': 1.0, 'speaker': 'A'},
        {'text': '天氣', 'start': 1.0, 'end': 1.5, 'speaker': 'A'},
        {'text': '真好', 'start': 1.5, 'end': 2.0, 'speaker': 'A'},
        {'text': '是啊', 'start': 3.0, 'end': 3.5, 'speaker': 'B'},
        {'text': '確實', 'start': 3.5, 'end': 4.0, 'speaker': 'B'},
        {'text': '不錯', 'start': 4.0, 'end': 4.5, 'speaker': 'B'},
    ]
    srt = SRTFormatter.generate_srt_from_words(words, max_chars_per_line=20)
    print(srt)
    
    # 測試從分段生成 SRT
    print("\n4. 測試從分段數據生成 SRT:")
    segments = [
        {'text': '你好，今天天氣真好。', 'start': 0, 'end': 2.0, 'speaker': '說話者A'},
        {'text': '是啊，確實不錯。', 'start': 3.0, 'end': 4.5, 'speaker': '說話者B'},
    ]
    srt = SRTFormatter.generate_srt_from_segments(segments)
    print(srt)


async def test_assemblyai_srt(config: AppConfig, test_audio_path: str):
    """測試 AssemblyAI 的 SRT 支援"""
    print("\n=== 測試 AssemblyAI SRT 支援 ===")
    
    try:
        service = AsyncAssemblyAIService(config)
        
        # 檢查服務狀態
        status = await service.check_status()
        if not status.get('available'):
            print("AssemblyAI 服務不可用:", status.get('error'))
            return
        
        print(f"AssemblyAI 服務可用，使用模型: {status.get('model')}")
        
        # 模擬轉錄結果（實際使用時會從真實音頻獲取）
        mock_result = {
            'transcript': '這是測試文本',
            'words': [
                {'text': '這是', 'start': 0, 'end': 500, 'speaker': 'A'},
                {'text': '測試', 'start': 500, 'end': 1000, 'speaker': 'A'},
                {'text': '文本', 'start': 1000, 'end': 1500, 'speaker': 'A'},
            ]
        }
        
        # 生成 SRT
        if mock_result.get('words'):
            # 轉換毫秒為秒
            words = []
            for word in mock_result['words']:
                words.append({
                    'text': word['text'],
                    'start': word['start'] / 1000,
                    'end': word['end'] / 1000,
                    'speaker': word.get('speaker')
                })
            
            srt_content = SRTFormatter.generate_srt_from_words(words)
            print("\n生成的 SRT 內容:")
            print(srt_content)
        
    except Exception as e:
        logger.error(f"AssemblyAI 測試失敗: {e}")


async def test_deepgram_srt(config: AppConfig, test_audio_path: str):
    """測試 Deepgram 的 SRT 支援"""
    print("\n=== 測試 Deepgram SRT 支援 ===")
    
    try:
        service = AsyncDeepgramService(config)
        
        # 檢查服務狀態
        status = await service.check_status()
        if not status.get('available'):
            print("Deepgram 服務不可用:", status.get('error'))
            return
        
        print(f"Deepgram 服務可用，使用模型: {status.get('model')}")
        
        # 模擬 Deepgram 返回的數據
        mock_utterances = [
            {'transcript': '你好，今天天氣如何？', 'start': 0, 'end': 2.5, 'speaker': 0},
            {'transcript': '很好，陽光明媚。', 'start': 3.0, 'end': 5.0, 'speaker': 1},
        ]
        
        # 轉換為分段格式
        segments = []
        for utterance in mock_utterances:
            segments.append({
                'text': utterance['transcript'],
                'start': utterance['start'],
                'end': utterance['end'],
                'speaker': f"Speaker {utterance['speaker']}"
            })
        
        srt_content = SRTFormatter.generate_srt_from_segments(segments)
        print("\n生成的 SRT 內容:")
        print(srt_content)
        
    except Exception as e:
        logger.error(f"Deepgram 測試失敗: {e}")


async def test_gemini_srt(config: AppConfig):
    """測試 Gemini Audio 的 SRT 支援"""
    print("\n=== 測試 Gemini Audio SRT 支援 ===")
    
    try:
        service = AsyncGeminiAudioService(config)
        
        # 測試 Gemini 轉錄文本解析
        mock_transcript = """[00:01] 說話者A：你好，今天我們要討論的主題是人工智慧。
[00:05] 說話者B：是的，這是一個非常重要的話題。
[00:10] 說話者A：我們首先來看看機器學習的基本概念。
[00:15] 說話者B：好的，請繼續。"""
        
        segments = service._parse_gemini_transcript(mock_transcript)
        print("\n解析的分段:")
        for seg in segments:
            print(f"  [{seg['start']}-{seg['end']}] {seg['speaker']}: {seg['text']}")
        
        # 生成 SRT
        srt_content = SRTFormatter.generate_srt_from_segments(segments)
        print("\n生成的 SRT 內容:")
        print(srt_content)
        
    except Exception as e:
        logger.error(f"Gemini 測試失敗: {e}")


async def main():
    """主測試函數"""
    print("開始測試語音識別服務的 SRT 格式支援")
    
    # 載入配置（使用環境變數）
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    # 創建模擬配置對象
    class MockConfig:
        def __init__(self):
            self.assemblyai_api_keys = [os.getenv('ASSEMBLYAI_API_KEY', '')]
            self.assemblyai_model = 'best'
            self.assemblyai_language = 'zh'
            self.deepgram_api_keys = [os.getenv('DEEPGRAM_API_KEY', '')]
            self.deepgram_model = 'nova-2'
            self.deepgram_language = 'zh'
            self.google_api_keys = [os.getenv('GOOGLE_API_KEY', '')]
    
    config = MockConfig()
    
    # 測試音頻路徑（如果需要實際測試）
    test_audio_path = "test_audio.mp3"  # 替換為實際的測試音頻
    
    # 執行測試
    await test_srt_formatter()
    
    # 只在有相應 API key 時執行服務測試
    if config.assemblyai_api_keys[0]:
        await test_assemblyai_srt(config, test_audio_path)
    else:
        print("\n跳過 AssemblyAI 測試（未設置 API key）")
    
    if config.deepgram_api_keys[0]:
        await test_deepgram_srt(config, test_audio_path)
    else:
        print("\n跳過 Deepgram 測試（未設置 API key）")
    
    if config.google_api_keys[0]:
        await test_gemini_srt(config)
    else:
        print("\n跳過 Gemini 測試（未設置 API key）")
    
    print("\n✅ 所有測試完成！")


if __name__ == "__main__":
    asyncio.run(main())