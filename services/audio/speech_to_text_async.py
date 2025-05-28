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
import base64

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
    
    async def get_audio_duration_from_data(self, audio_data: bytes) -> Optional[float]:
        """
        從音頻數據計算時長
        
        Args:
            audio_data: 音頻文件的二進制數據
            
        Returns:
            音頻時長（秒），如果無法計算則返回None
        """
        try:
            if not HAS_AV:
                logger.warning("⚠️ 無法計算音頻時長：av庫未安裝")
                return None
            
            import io
            
            # 使用io.BytesIO創建一個內存中的文件對象
            audio_buffer = io.BytesIO(audio_data)
            
            # 使用av庫獲取音頻時長
            with av.open(audio_buffer) as container:
                if container.streams.audio:
                    audio_stream = container.streams.audio[0]
                    duration = float(container.duration) / av.time_base if container.duration else None
                    if duration:
                        logger.info(f"🕒 音頻時長: {duration:.2f}秒")
                        return duration
            
            logger.warning("⚠️ 無法獲取音頻時長")
            return None
            
        except Exception as e:
            logger.error(f"❌ 計算音頻時長失敗: {str(e)}")
            return None

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
    
    async def transcribe_audio_data(self, audio_data: bytes, format_type: str = "audio", mime_type: str = "audio/octet-stream") -> Dict[str, Any]:
        """
        使用指定服務轉錄音頻數據（從資料庫存儲的音頻），自動嘗試備用方案
        
        Args:
            audio_data: 音頻文件的二進制數據
            format_type: 音頻格式（如 mp3, wav）
            mime_type: MIME類型（如 audio/mp3）
            
        Returns:
            轉錄結果字典，包含轉錄文本和元數據
        """
        try:
            logger.info(f"🎙️ 開始轉錄音頻數據，格式: {format_type}, 大小: {len(audio_data)} bytes")
            
            # 計算音頻時長
            audio_duration = await self.get_audio_duration_from_data(audio_data)
            
            # 創建臨時文件進行處理（某些服務需要文件路徑）
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=f".{format_type}", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            try:
                # 嘗試使用智能備用方案轉錄
                result = await self._transcribe_with_fallback(temp_file_path)
                
                # 確保結果包含時長信息
                if 'duration' not in result or result['duration'] is None:
                    if audio_duration is not None:
                        result['duration'] = audio_duration
                        logger.info(f"📊 使用計算得到的音頻時長: {audio_duration:.2f}秒")
                    else:
                        logger.warning("⚠️ 無法獲取音頻時長信息")
                
                logger.info(f"✅ 音頻數據轉錄完成，轉錄文本長度: {len(result.get('transcript', result.get('text', '')))}")
                return result
                
            finally:
                # 清理臨時文件
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"⚠️ 清理臨時文件失敗: {e}")
                    
        except Exception as e:
            logger.error(f"❌ 音頻數據轉錄失敗: {str(e)}")
            raise
    
    async def transcribe_audio(self, audio_path: str) -> Dict[str, Any]:
        """
        使用指定服務轉錄音頻，自動嘗試備用方案
        
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
            
            # 使用智能備用方案轉錄
            result = await self._transcribe_with_fallback(audio_path)
            
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
    
    async def _transcribe_with_fallback(self, file_path: str) -> Dict[str, Any]:
        """
        使用智能備用方案轉錄音頻
        
        備用順序：
        1. 主要服務 (根據配置)
        2. 如果是 Gemini，嘗試輪換不同的 API key
        3. Deepgram (如果配置了)
        4. OpenAI Whisper (如果配置了)
        5. 本地 Whisper (最後選項)
        """
        last_error = None
        
        # 1. 嘗試主要服務
        try:
            logger.info(f"🔄 嘗試主要服務: {self.provider}")
            if self.provider == "openai":
                result = await self.whisper_service.transcribe(file_path)
            elif self.provider == "whisper_local":
                result = await self.local_whisper_service.transcribe(file_path)
            elif self.provider == "deepgram":
                result = await self.deepgram_service.transcribe(file_path)
            elif self.provider == "gemini_audio":
                result = await self._transcribe_with_gemini_no_fallback(file_path)
            else:
                raise ValueError(f"不支持的轉錄服務: {self.provider}")
            
            logger.info(f"✅ 主要服務 {self.provider} 轉錄成功")
            return result
            
        except Exception as e:
            last_error = e
            logger.warning(f"⚠️ 主要服務 {self.provider} 失敗: {str(e)}")
        
        # 2. 如果主要服務是 Gemini 且失敗了，嘗試輪換 API keys
        if self.provider == "gemini_audio":
            try:
                logger.info("🔄 嘗試 Gemini API key 輪換")
                result = await self._transcribe_with_gemini_key_rotation(file_path)
                logger.info("✅ Gemini API key 輪換成功")
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Gemini API key 輪換失敗: {str(e)}")
        
        # 3. 嘗試 Deepgram (如果不是主要服務且已配置)
        if self.provider != "deepgram" and self.deepgram_service and hasattr(self.deepgram_service, 'api_keys') and self.deepgram_service.api_keys:
            try:
                logger.info("🔄 嘗試備用服務: Deepgram")
                result = await self.deepgram_service.transcribe(file_path)
                result['backup_provider'] = 'deepgram'
                logger.info("✅ Deepgram 備用轉錄成功")
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Deepgram 備用服務失敗: {str(e)}")
        
        # 4. 嘗試 OpenAI Whisper (如果不是主要服務且已配置)
        if self.provider != "openai" and self.whisper_service and hasattr(self.whisper_service, 'api_key') and self.whisper_service.api_key:
            try:
                logger.info("🔄 嘗試備用服務: OpenAI Whisper")
                result = await self.whisper_service.transcribe(file_path)
                result['backup_provider'] = 'openai_whisper'
                logger.info("✅ OpenAI Whisper 備用轉錄成功")
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ OpenAI Whisper 備用服務失敗: {str(e)}")
        
        # 5. 最後嘗試本地 Whisper (僅在所有雲端服務都失敗時)
        if self.provider != "whisper_local":
            try:
                logger.info("🔄 嘗試最後備用: 本地 Whisper")
                result = await self.local_whisper_service.transcribe(file_path)
                result['backup_provider'] = 'local_whisper'
                logger.info("✅ 本地 Whisper 備用轉錄成功")
                return result
            except Exception as e:
                last_error = e
                logger.error(f"❌ 本地 Whisper 備用服務也失敗: {str(e)}")
        
        # 所有服務都失敗
        raise Exception(f"所有轉錄服務都失敗，最後錯誤: {str(last_error)}")
    
    async def _transcribe_with_gemini_no_fallback(self, file_path: str) -> Dict[str, Any]:
        """使用 Gemini Audio 轉錄，但不自動嘗試本地備用"""
        # 這個方法會直接調用 Gemini 服務，但不觸發內建的本地備用邏輯
        try:
            # 讀取文件
            async with aiofiles.open(file_path, 'rb') as audio_file:
                audio_data = await audio_file.read()
            
            # 重新實現簡化的 Gemini 轉錄邏輯
            api_key = self.gemini_audio_service._get_api_key()
            
            # 檢查文件大小
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            if file_size_mb > 100:
                raise ValueError(f"文件太大: {file_size_mb:.1f}MB，Gemini最大支援100MB")
            
            # 構建API請求
            import base64
            import aiohttp
            from pathlib import Path
            
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # 確定文件MIME類型
            file_ext = Path(file_path).suffix.lower()
            mime_type = 'audio/wav'
            if file_ext == '.mp3':
                mime_type = 'audio/mpeg'
            elif file_ext == '.m4a':
                mime_type = 'audio/mp4'
            elif file_ext == '.ogg':
                mime_type = 'audio/ogg'
            elif file_ext == '.flac':
                mime_type = 'audio/flac'
            
            url = f"{self.gemini_audio_service.base_url}/models/{self.gemini_audio_service.model}:generateContent?key={api_key}"
            
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
            
            headers = {'Content-Type': 'application/json'}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=300)
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
            
            transcript = ""
            for part in candidate['content']['parts']:
                if 'text' in part:
                    transcript += part['text']
            
            if not transcript.strip():
                raise Exception("轉錄結果為空")
            
            return {
                'transcript': transcript.strip(),
                'language': 'zh',
                'provider': 'gemini_audio',
                'model': self.gemini_audio_service.model,
                'file_size_mb': file_size_mb
            }
            
        except Exception as e:
            logger.error(f"Gemini 直接轉錄失敗: {str(e)}")
            raise
    
    async def _transcribe_with_gemini_key_rotation(self, file_path: str) -> Dict[str, Any]:
        """嘗試輪換 Gemini API keys"""
        if not hasattr(self.gemini_audio_service, 'api_keys') or len(self.gemini_audio_service.api_keys) <= 1:
            raise Exception("沒有額外的 Gemini API keys 可供輪換")
        
        # 嘗試其他的 API keys
        for i, api_key in enumerate(self.gemini_audio_service.api_keys):
            try:
                logger.info(f"🔑 嘗試 Gemini API key #{i+1}")
                
                # 暫時替換 API key
                original_get_api_key = self.gemini_audio_service._get_api_key
                self.gemini_audio_service._get_api_key = lambda: api_key
                
                try:
                    result = await self._transcribe_with_gemini_no_fallback(file_path)
                    logger.info(f"✅ Gemini API key #{i+1} 成功")
                    return result
                finally:
                    # 恢復原始方法
                    self.gemini_audio_service._get_api_key = original_get_api_key
                    
            except Exception as e:
                logger.warning(f"⚠️ Gemini API key #{i+1} 失敗: {str(e)}")
                continue
        
        raise Exception("所有 Gemini API keys 都失敗")
    
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