"""
異步Gemini音頻處理服務
支援直接使用Gemini進行音頻轉文字
"""

import logging
import asyncio
import aiohttp
import aiofiles
from typing import Dict, Any, Optional
from pathlib import Path
import os
import random

from config import AppConfig

logger = logging.getLogger(__name__)


class AsyncGeminiAudioService:
    """異步Gemini音頻處理服務"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.api_keys = config.google_api_keys
        self.model = "gemini-2.0-flash"
        self.max_retries = config.max_retries
        
        if not self.api_keys:
            raise ValueError("Google API密鑰未設置")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
    
    def _get_api_key(self) -> str:
        """隨機選擇一個API密鑰"""
        return random.choice(self.api_keys)
    
    async def transcribe(self, file_path: str) -> Dict[str, Any]:
        """
        使用Gemini直接轉錄音頻文件
        
        Args:
            file_path: 音頻文件路徑
            
        Returns:
            轉錄結果字典
        """
        try:
            logger.info(f"Gemini Audio開始轉錄: {file_path}")
            
            # 檢查文件是否存在
            if not Path(file_path).exists():
                raise FileNotFoundError(f"音頻文件不存在: {file_path}")
            
            # 檢查文件大小
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            if file_size_mb > 100:  # Gemini限制100MB
                raise ValueError(f"文件太大: {file_size_mb:.1f}MB，Gemini最大支援100MB")
            
            # 讀取音頻文件
            async with aiofiles.open(file_path, 'rb') as audio_file:
                audio_data = await audio_file.read()
            
            # 獲取API密鑰
            api_key = self._get_api_key()
            
            # 構建API請求URL
            url = f"{self.base_url}/models/{self.model}:generateContent?key={api_key}"
            
            # 準備請求頭和請求體
            headers = {
                'Content-Type': 'application/json'
            }
            
            # 確定文件MIME類型
            file_ext = Path(file_path).suffix.lower()
            mime_type = 'audio/wav'  # 默認
            if file_ext == '.mp3':
                mime_type = 'audio/mpeg'
            elif file_ext == '.m4a':
                mime_type = 'audio/mp4'
            elif file_ext == '.ogg':
                mime_type = 'audio/ogg'
            elif file_ext == '.flac':
                mime_type = 'audio/flac'
            
            # 將音頻數據轉換為Base64
            import base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # 構建請求體
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": mime_type,
                                    "data": audio_base64
                                }
                            },
                            {
                                "text": "將這段音頻轉錄為文字。請使用原始語言，不要翻譯。"
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "topP": 0.95,
                    "topK": 40
                }
            }
            
            # 發送請求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=300)  # 5分鐘超時
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Gemini API錯誤 {response.status}: {error_text}")
                    
                    result = await response.json()
            
            # 解析結果
            if 'candidates' not in result or not result['candidates']:
                raise Exception("Gemini API返回無效結果")
            
            candidate = result['candidates'][0]
            if 'content' not in candidate or 'parts' not in candidate['content']:
                raise Exception("Gemini API返回無效內容結構")
            
            # 提取轉錄文字
            transcript = ""
            for part in candidate['content']['parts']:
                if 'text' in part:
                    transcript += part['text']
            
            if not transcript.strip():
                raise Exception("轉錄結果為空")
            
            # 格式化返回結果
            return {
                'transcript': transcript.strip(),
                'language': 'zh',  # 假設是中文，實際上Gemini會自動檢測
                'provider': 'gemini_audio',
                'model': self.model,
                'file_size_mb': file_size_mb
            }
            
        except Exception as e:
            logger.error(f"Gemini Audio轉錄失敗: {str(e)}")
            # 如果API調用失敗，使用備用的本地處理
            try:
                from .local_whisper_async import AsyncLocalWhisperService
                logger.info("嘗試使用本地Whisper作為備用")
                
                local_service = AsyncLocalWhisperService(self.config)
                result = await local_service.transcribe(file_path)
                
                # 標記為備用結果
                result['provider'] = 'local_whisper_backup'
                result['note'] = 'Gemini失敗後的備用結果'
                
                return result
            except Exception as backup_error:
                logger.error(f"備用轉錄也失敗: {str(backup_error)}")
                raise Exception(f"Gemini Audio轉錄失敗，備用方法也失敗: {str(e)}")
    
    async def check_status(self) -> Dict[str, Any]:
        """檢查服務狀態"""
        try:
            # 獲取API密鑰
            api_key = self._get_api_key()
            
            # 構建簡單的測試請求
            url = f"{self.base_url}/models?key={api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        return {
                            "available": True,
                            "model": self.model,
                            "provider": "gemini_audio",
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