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
                'diarize': 'true'
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
            
            # 格式化返回結果
            return {
                'transcript': transcript,
                'language': self.language,
                'confidence': alternative.get('confidence', 0),
                'words': alternative.get('words', []),
                'provider': 'deepgram',
                'model': self.model
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