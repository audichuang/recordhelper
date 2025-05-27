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
            
            # 暫時返回模擬結果，因為實際的Gemini Audio API調用比較複雜
            # 在生產環境中，這裡會實現真正的Gemini音頻上傳和轉錄
            logger.warning("Gemini Audio服務暫時返回模擬結果")
            
            # 格式化返回結果
            return {
                'transcript': "這是Gemini Audio的模擬轉錄結果",
                'language': 'zh',
                'provider': 'gemini_audio',
                'model': self.model,
                'file_size_mb': file_size_mb
            }
            
        except Exception as e:
            logger.error(f"Gemini Audio轉錄失敗: {str(e)}")
            raise
    
    async def check_status(self) -> Dict[str, Any]:
        """檢查服務狀態"""
        try:
            # 暫時返回可用狀態
            return {
                "available": True,
                "model": self.model,
                "provider": "gemini_audio",
                "api_keys_count": len(self.api_keys),
                "note": "模擬模式"
            }
                        
        except Exception as e:
            return {
                "available": False,
                "error": str(e)
            } 