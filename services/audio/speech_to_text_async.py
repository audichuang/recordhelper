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
import os

# 添加音頻處理庫
try:
    import av
    HAS_AV = True
except ImportError:
    HAS_AV = False
    logging.warning("⚠️ av庫未安裝，將無法計算音頻時長")

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
        
        logger.info(f"🔧 語音轉文字服務初始化完成，使用提供商: {self.provider}")
    
    async def get_audio_duration(self, audio_path: str) -> Optional[float]:
        """
        計算音頻文件時長
        
        Args:
            audio_path: 音頻文件路徑
            
        Returns:
            音頻時長（秒），如果無法計算則返回None
        """
        try:
            if not HAS_AV:
                logger.warning("⚠️ 無法計算音頻時長：av庫未安裝")
                return None
            
            if not os.path.exists(audio_path):
                logger.error(f"❌ 音頻文件不存在: {audio_path}")
                return None
            
            # 使用av庫獲取音頻時長
            with av.open(audio_path) as container:
                if container.streams.audio:
                    audio_stream = container.streams.audio[0]
                    duration = float(container.duration) / av.time_base if container.duration else None
                    if duration:
                        logger.info(f"🕒 音頻時長: {duration:.2f}秒")
                        return duration
            
            logger.warning(f"⚠️ 無法獲取音頻時長: {audio_path}")
            return None
            
        except Exception as e:
            logger.error(f"❌ 計算音頻時長失敗: {str(e)}")
            return None
    
    async def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """
        使用指定服務轉錄音頻
        
        Args:
            audio_path: 音頻文件路徑
            
        Returns:
            轉錄結果字典，包含轉錄文本和元數據
        """
        try:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"找不到音頻文件: {audio_path}")
            
            logger.info(f"🎙️ 開始轉錄音頻: {audio_path}")
            
            # 計算音頻時長
            audio_duration = await self.get_audio_duration(audio_path)
            
            # 根據配置選擇服務
            if self.provider == "openai":
                result = await self.whisper_service.transcribe(audio_path)
            elif self.provider == "whisper_local":
                result = await self.local_whisper_service.transcribe(audio_path)
            elif self.provider == "deepgram":
                result = await self.deepgram_service.transcribe(audio_path)
            elif self.provider == "gemini_audio":
                result = await self.gemini_audio_service.transcribe(audio_path)
            else:
                raise ValueError(f"不支持的轉錄服務: {self.provider}")
            
            # 確保結果包含時長信息
            if 'duration' not in result or result['duration'] is None:
                if audio_duration is not None:
                    result['duration'] = audio_duration
                    logger.info(f"📊 使用計算得到的音頻時長: {audio_duration:.2f}秒")
                else:
                    logger.warning("⚠️ 無法獲取音頻時長信息")
            
            logger.info(f"✅ 音頻轉錄完成: {audio_path}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 音頻轉錄失敗: {str(e)}")
            raise
    
    async def check_status(self) -> Dict[str, Any]:
        """檢查各個轉錄服務的狀態"""
        status = {
            "provider": self.provider,
            "services": {}
        }
        
        try:
            # 檢查OpenAI狀態
            if self.whisper_service:
                status["services"]["openai"] = await self.whisper_service.check_status()
            
            # 檢查本地Whisper狀態
            if self.local_whisper_service:
                status["services"]["whisper_local"] = await self.local_whisper_service.check_status()
            
            # 檢查Deepgram狀態
            if self.deepgram_service:
                status["services"]["deepgram"] = await self.deepgram_service.check_status()
            
            # 檢查Gemini Audio狀態
            if self.gemini_audio_service:
                status["services"]["gemini_audio"] = await self.gemini_audio_service.check_status()
            
            status["available"] = True
            logger.info(f"🔍 語音轉文字服務狀態檢查完成，主要提供商: {self.provider}")
            
        except Exception as e:
            status["available"] = False
            status["error"] = str(e)
            logger.error(f"❌ 語音轉文字服務狀態檢查失敗: {str(e)}")
        
        return status
    
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