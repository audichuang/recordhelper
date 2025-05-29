"""
異步Deepgram語音識別服務
"""

import logging
import aiohttp
import aiofiles
from typing import Dict, Any, Optional
from pathlib import Path
import random

from config import AppConfig
from .srt_formatter import SRTFormatter

logger = logging.getLogger(__name__)


class AsyncDeepgramService:
    """異步Deepgram語音識別服務"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.api_keys = config.deepgram_api_keys or []
        self.model = config.deepgram_model
        self.language = config.deepgram_language
        self.base_url = "https://api.deepgram.com/v1"
        
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
            
            # 讀取音頻文件
            async with aiofiles.open(file_path, 'rb') as audio_file:
                audio_data = await audio_file.read()
            
            # 準備請求參數
            params = {
                'model': self.model,
                'language': self.language,
                'punctuate': 'true',
                'utterances': 'true',
                'diarize': 'true',
                'smart_format': 'true'
            }
            
            # 準備請求頭
            api_key = self._get_api_key()
            headers = {
                'Authorization': f'Token {api_key}',
                'Content-Type': 'audio/wav'
            }
            
            # 發送請求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/listen",
                    data=audio_data,
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=300)  # 5分鐘超時
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Deepgram API錯誤 {response.status}: {error_text}")
                    
                    result = await response.json()
            
            # 處理結果
            if 'results' not in result or not result['results']['channels']:
                raise Exception("Deepgram API返回無效結果")
            
            channel = result['results']['channels'][0]
            if 'alternatives' not in channel or not channel['alternatives']:
                raise Exception("Deepgram API沒有返回轉錄結果")
            
            alternative = channel['alternatives'][0]
            transcript = alternative.get('transcript', '').strip()
            
            if not transcript:
                raise Exception("轉錄結果為空")
            
            # 提取時間軸資訊
            utterances = result['results'].get('utterances', [])
            
            # 格式化時間軸文本（類似 Gemini 的格式）
            timeline_transcript = self._format_timeline_transcript(utterances)
            
            # 生成 SRT 格式字幕
            srt_content = ''
            words = []
            
            # 從 words 數據提取時間戳資訊
            if 'words' in alternative:
                for word_info in alternative['words']:
                    words.append({
                        'text': word_info.get('word', ''),
                        'start': word_info.get('start', 0),
                        'end': word_info.get('end', 0),
                        'confidence': word_info.get('confidence', 0),
                        'speaker': word_info.get('speaker')  # Deepgram 的 diarize 功能
                    })
                
                # 生成 SRT
                srt_content = SRTFormatter.generate_srt_from_words(words, sentence_level=True)
            
            # 如果沒有 words 數據但有 utterances，使用 utterances 生成 SRT
            elif utterances:
                segments = []
                for utterance in utterances:
                    segments.append({
                        'text': utterance.get('transcript', ''),
                        'start': utterance.get('start', 0),
                        'end': utterance.get('end', 0),
                        'speaker': f"Speaker {utterance.get('speaker', 0)}" if utterance.get('speaker') is not None else None
                    })
                
                srt_content = SRTFormatter.generate_srt_from_segments(segments)
            
            # 格式化返回結果
            return {
                'transcript': transcript,
                'transcription': transcript,  # 為了相容性
                'timeline_transcript': timeline_transcript,
                'language': self.language,
                'confidence': alternative.get('confidence', 0),
                'provider': 'deepgram',
                'model': self.model,
                'has_timeline': True,
                'words': words,
                'srt': srt_content,
                'has_srt': bool(srt_content)
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
                    "error": "API密鑰未設置"
                }
            
            api_key = self._get_api_key()
            headers = {
                'Authorization': f'Token {api_key}'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/projects",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        return {
                            "available": True,
                            "model": self.model,
                            "language": self.language,
                            "provider": "deepgram",
                            "api_keys_count": len(self.api_keys)
                        }
                    else:
                        return {
                            "available": False,
                            "error": f"API響應錯誤: {response.status}"
                        }
                        
        except Exception as e:
            return {
                "available": False,
                "error": str(e)
            }
    
    def _format_timeline_transcript(self, utterances: list) -> str:
        """
        將 Deepgram 的 words 數據格式化為帶時間軸的逐字稿
        
        Args:
            words: Deepgram 返回的 words 陣列
            
        Returns:
            格式化的時間軸逐字稿
        """
        if not utterances:
            return ""
        
        timeline_parts = []
        current_sentence = []
        sentence_start_time = None
        
        for i, word_data in enumerate(utterances):
            word = word_data.get('transcript', '')
            start_time = word_data.get('start', 0)
            end_time = word_data.get('end', 0)
            
            # 記錄句子開始時間
            if sentence_start_time is None:
                sentence_start_time = start_time
            
            current_sentence.append(word)
            
            # 檢查是否為句子結尾（標點符號或最後一個詞）
            is_sentence_end = (
                word.endswith(('。', '！', '？', '.', '!', '?')) or
                i == len(utterances) - 1
            )
            
            if is_sentence_end:
                # 格式化時間戳
                start_timestamp = self._format_timestamp(sentence_start_time)
                end_timestamp = self._format_timestamp(end_time)
                
                # 組合句子
                sentence_text = ' '.join(current_sentence)
                timeline_parts.append(f"[{start_timestamp} - {end_timestamp}] {sentence_text}")
                
                # 重置
                current_sentence = []
                sentence_start_time = None
        
        return '\n'.join(timeline_parts)
    
    def _format_timestamp(self, seconds: float) -> str:
        """
        將秒數格式化為時間戳格式 (MM:SS)
        
        Args:
            seconds: 秒數
            
        Returns:
            格式化的時間戳
        """
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}" 