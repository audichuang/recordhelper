"""
異步OpenAI Whisper語音識別服務
"""

import logging
import aiohttp
import aiofiles
from typing import Dict, Any, Optional
from pathlib import Path

from config import AppConfig

logger = logging.getLogger(__name__)


class AsyncWhisperService:
    """異步OpenAI Whisper服務"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.api_key = config.openai_api_key
        self.model = config.whisper_model
        self.base_url = "https://api.openai.com/v1"
        
        if not self.api_key:
            raise ValueError("OpenAI API密鑰未設置")
    
    async def transcribe(self, file_path: str) -> Dict[str, Any]:
        """
        轉錄音頻文件
        
        Args:
            file_path: 音頻文件路徑
            
        Returns:
            轉錄結果字典
        """
        try:
            logger.info(f"OpenAI Whisper開始轉錄: {file_path}")
            
            # 讀取音頻文件
            async with aiofiles.open(file_path, 'rb') as audio_file:
                audio_data = await audio_file.read()
            
            # 準備請求數據
            data = aiohttp.FormData()
            data.add_field('file', audio_data, 
                          filename=Path(file_path).name,
                          content_type='audio/mpeg')
            data.add_field('model', self.model)
            data.add_field('language', 'zh')  # 指定中文
            data.add_field('response_format', 'verbose_json')
            
            # 發送請求
            headers = {
                'Authorization': f'Bearer {self.api_key}'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/audio/transcriptions",
                    data=data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=300)  # 5分鐘超時
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"OpenAI API錯誤 {response.status}: {error_text}")
                    
                    result = await response.json()
            
            # 處理結果
            transcript = result.get('text', '').strip()
            if not transcript:
                raise Exception("轉錄結果為空")
            
            # 格式化返回結果
            return {
                'transcript': transcript,
                'language': result.get('language', 'zh'),
                'duration': result.get('duration'),
                'segments': result.get('segments', []),
                'provider': 'openai_whisper',
                'model': self.model
            }
            
        except Exception as e:
            logger.error(f"OpenAI Whisper轉錄失敗: {str(e)}")
            raise
    
    async def check_status(self) -> Dict[str, Any]:
        """檢查服務狀態"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/models",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        return {
                            "available": True,
                            "model": self.model,
                            "provider": "openai_whisper"
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