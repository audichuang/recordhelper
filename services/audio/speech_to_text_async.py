"""
異步語音轉文字服務
支持多種語音識別服務：OpenAI Whisper、Deepgram、本地Whisper等
"""

import logging
import asyncio
import aiofiles
import aiohttp
from typing import Dict, Any, Optional
from pathlib import Path

from config import AppConfig
from .whisper_async import AsyncWhisperService
from .deepgram_async import AsyncDeepgramService
from .local_whisper_async import AsyncLocalWhisperService
from .gemini_audio_async import AsyncGeminiAudioService

logger = logging.getLogger(__name__)


class AsyncSpeechToTextService:
    """異步語音轉文字服務"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.provider = config.speech_to_text_provider.lower()
        
        # 初始化不同的服務
        self.whisper_service = AsyncWhisperService(config)
        self.deepgram_service = AsyncDeepgramService(config)
        self.local_whisper_service = AsyncLocalWhisperService(config)
        self.gemini_audio_service = AsyncGeminiAudioService(config)
        
        logger.info(f"語音轉文字服務初始化完成，使用提供商: {self.provider}")
    
    async def transcribe_audio(self, file_path: str) -> Dict[str, Any]:
        """
        轉錄音頻文件
        
        Args:
            file_path: 音頻文件路徑
            
        Returns:
            包含轉錄結果的字典
        """
        try:
            logger.info(f"開始轉錄音頻: {file_path}")
            
            # 檢查文件是否存在
            if not Path(file_path).exists():
                raise FileNotFoundError(f"音頻文件不存在: {file_path}")
            
            # 根據配置選擇服務提供商
            if self.provider == "openai":
                result = await self._transcribe_with_openai(file_path)
            elif self.provider == "deepgram":
                result = await self._transcribe_with_deepgram(file_path)
            elif self.provider == "local":
                result = await self._transcribe_with_local_whisper(file_path)
            elif self.provider == "gemini":
                result = await self._transcribe_with_gemini_audio(file_path)
            else:
                # 默認使用OpenAI
                logger.warning(f"未知的語音服務提供商: {self.provider}，使用OpenAI作為默認")
                result = await self._transcribe_with_openai(file_path)
            
            logger.info(f"音頻轉錄完成: {file_path}")
            return result
            
        except Exception as e:
            logger.error(f"音頻轉錄失敗: {str(e)}")
            
            # 嘗試備用服務
            try:
                logger.info("嘗試使用備用語音服務...")
                if self.provider != "openai":
                    result = await self._transcribe_with_openai(file_path)
                elif self.provider != "local":
                    result = await self._transcribe_with_local_whisper(file_path)
                else:
                    raise e
                
                logger.info("備用語音服務轉錄成功")
                return result
                
            except Exception as backup_error:
                logger.error(f"備用語音服務也失敗: {str(backup_error)}")
                raise Exception(f"所有語音服務都失敗: {str(e)}")
    
    async def _transcribe_with_openai(self, file_path: str) -> Dict[str, Any]:
        """使用OpenAI Whisper轉錄"""
        return await self.whisper_service.transcribe(file_path)
    
    async def _transcribe_with_deepgram(self, file_path: str) -> Dict[str, Any]:
        """使用Deepgram轉錄"""
        return await self.deepgram_service.transcribe(file_path)
    
    async def _transcribe_with_local_whisper(self, file_path: str) -> Dict[str, Any]:
        """使用本地Whisper轉錄"""
        return await self.local_whisper_service.transcribe(file_path)
    
    async def _transcribe_with_gemini_audio(self, file_path: str) -> Dict[str, Any]:
        """使用Gemini Audio轉錄"""
        return await self.gemini_audio_service.transcribe(file_path)
    
    async def get_service_status(self) -> Dict[str, Any]:
        """獲取服務狀態"""
        status = {
            "current_provider": self.provider,
            "services": {}
        }
        
        # 檢查各個服務的狀態
        try:
            status["services"]["openai"] = await self.whisper_service.check_status()
        except Exception as e:
            status["services"]["openai"] = {"available": False, "error": str(e)}
        
        try:
            status["services"]["deepgram"] = await self.deepgram_service.check_status()
        except Exception as e:
            status["services"]["deepgram"] = {"available": False, "error": str(e)}
        
        try:
            status["services"]["local"] = await self.local_whisper_service.check_status()
        except Exception as e:
            status["services"]["local"] = {"available": False, "error": str(e)}
        
        try:
            status["services"]["gemini_audio"] = await self.gemini_audio_service.check_status()
        except Exception as e:
            status["services"]["gemini_audio"] = {"available": False, "error": str(e)}
        
        return status 