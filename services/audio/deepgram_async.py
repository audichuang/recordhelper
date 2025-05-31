"""
異步 Deepgram 語音識別服務 - 使用官方 SDK
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path
import random

from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from config import AppConfig
from .srt_formatter import SRTFormatter

logger = logging.getLogger(__name__)


class AsyncDeepgramService:
    """異步 Deepgram 語音識別服務 - 使用官方 SDK"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.api_keys = config.deepgram_api_keys or []
        self.model = config.deepgram_model
        self.language = config.deepgram_language
        
        if not self.api_keys:
            logger.warning("Deepgram API密鑰未設置")
    
    def _get_api_key(self) -> str:
        """隨機選擇一個API密鑰"""
        if not self.api_keys:
            raise ValueError("Deepgram API密鑰未設置")
        return random.choice(self.api_keys)
    
    async def transcribe(self, file_path: str) -> Dict[str, Any]:
        """
        轉錄音頻文件
        
        Args:
            file_path: 音頻文件路徑
            
        Returns:
            轉錄結果字典
        """
        try:
            logger.info(f"Deepgram開始轉錄: {file_path}")
            
            if not self.api_keys:
                raise ValueError("Deepgram API密鑰未設置")
            
            # 創建 Deepgram 客戶端
            api_key = self._get_api_key()
            deepgram = DeepgramClient(api_key)
            
            # 讀取音頻文件
            with open(file_path, 'rb') as audio_file:
                buffer_data = audio_file.read()
            
            # 設置轉錄選項
            options = PrerecordedOptions(
                model=self.model,
                language=self.language,
                punctuate=True,
                utterances=True,
                diarize=True,
                smart_format=True,
                paragraphs=True
            )
            
            # 準備音頻源
            payload: FileSource = {
                "buffer": buffer_data,
            }
            
            # 執行轉錄（在異步環境中執行同步操作）
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: deepgram.listen.rest.v('1').transcribe_file(
                    payload, options
                )
            )
            
            # 處理結果
            if not response.results or not response.results.channels:
                raise Exception("Deepgram API返回無效結果")
            
            channel = response.results.channels[0]
            if not channel.alternatives:
                raise Exception("Deepgram API沒有返回轉錄結果")
            
            alternative = channel.alternatives[0]
            transcript = alternative.transcript
            
            if not transcript:
                raise Exception("轉錄結果為空")
            
            # 處理單詞時間戳
            words = []
            if hasattr(alternative, 'words') and alternative.words:
                for word_info in alternative.words:
                    words.append({
                        'text': word_info.word,
                        'start': word_info.start,
                        'end': word_info.end,
                        'confidence': word_info.confidence,
                        'speaker': word_info.speaker if hasattr(word_info, 'speaker') else None
                    })
            
            # 生成 SRT 格式字幕
            srt_content = ''
            if words:
                srt_content = SRTFormatter.generate_srt_from_words(words, sentence_level=True)
            
            # 計算音頻時長
            duration = None
            if hasattr(response.results, 'metadata') and hasattr(response.results.metadata, 'duration'):
                duration = response.results.metadata.duration
            elif words:
                # 如果沒有 metadata，從最後一個詞計算
                duration = words[-1]['end']
            
            logger.info(f"🔍 Deepgram 時長數據: duration={duration}s")
            
            return {
                'transcript': transcript,
                'language': self.language,
                'duration': duration,
                'words': words,
                'confidence': alternative.confidence if hasattr(alternative, 'confidence') else None,
                'provider': 'deepgram',
                'model': self.model,
                'srt': srt_content,
                'has_srt': bool(srt_content),
                'using_official_sdk': True
            }
            
        except Exception as e:
            logger.error(f"Deepgram轉錄失敗: {str(e)}")
            raise
    
    async def check_status(self) -> Dict[str, Any]:
        """檢查服務狀態"""
        try:
            if not self.api_keys:
                return {
                    "available": False,
                    "error": "沒有配置 API 密鑰"
                }
            
            # 創建客戶端測試連接
            api_key = self._get_api_key()
            deepgram = DeepgramClient(api_key)
            
            # 簡單測試客戶端是否可以創建
            return {
                "available": True,
                "model": self.model,
                "language": self.language,
                "provider": "deepgram",
                "api_keys_count": len(self.api_keys),
                "using_official_sdk": True
            }
            
        except Exception as e:
            return {
                "available": False,
                "error": str(e)
            }