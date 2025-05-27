import logging
from typing import Optional
from config import AppConfig
from models import APIError
from whisper_service import WhisperService
from deepgram_service import DeepgramService
from local_whisper_service import LocalWhisperService
from faster_whisper_service import FasterWhisperService


class SpeechToTextService:
    """統一的語音轉文字服務接口"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.provider = config.speech_to_text_provider.lower()
        
        # 初始化對應的服務
        if self.provider == "openai":
            self.service = WhisperService(config)
            logging.info("使用 OpenAI Whisper API 語音轉文字服務")
        elif self.provider == "deepgram":
            self.service = DeepgramService(config)
            logging.info("使用 Deepgram 語音轉文字服務")
        elif self.provider == "local_whisper":
            self.service = LocalWhisperService(config)
            logging.info("使用本地 OpenAI Whisper 語音轉文字服務")
        elif self.provider == "faster_whisper":
            self.service = FasterWhisperService(config)
            logging.info("使用 Faster-Whisper 高性能語音轉文字服務")
        else:
            raise ValueError(f"不支援的語音轉文字服務提供商: {config.speech_to_text_provider}")
    
    def transcribe_audio(self, audio_file_path: str) -> str:
        """轉換語音為文字"""
        try:
            if self.provider in ["openai", "deepgram", "local_whisper", "faster_whisper"]:
                return self.service.transcribe_audio(audio_file_path)
            else:
                raise APIError(f"未知的語音轉文字服務: {self.provider}")
        except Exception as e:
            logging.error(f"語音轉文字服務錯誤 ({self.provider}): {e}")
            raise
    
    def get_usage_info(self) -> dict:
        """獲取使用量資訊"""
        try:
            usage_info = self.service.get_usage_info()
            usage_info["current_provider"] = self.provider
            return usage_info
        except Exception as e:
            logging.warning(f"獲取使用量資訊失敗: {e}")
            return {
                "current_provider": self.provider,
                "status": "error",
                "error": str(e)
            }
    
    def transcribe_with_timestamps(self, audio_file_path: str) -> dict:
        """轉錄音訊並返回包含時間戳的詳細資訊（本地 Whisper 服務支援）"""
        if self.provider in ["local_whisper", "faster_whisper"]:
            return self.service.transcribe_with_timestamps(audio_file_path)
        else:
            # 對於其他服務，返回基本轉錄結果
            text = self.transcribe_audio(audio_file_path)
            return {
                "text": text,
                "language": "unknown",
                "segments": [],
                "processing_time": 0,
                "note": f"時間戳功能僅在本地 Whisper 服務中支援，當前使用: {self.get_provider_name()}"
            }
    
    def get_provider_name(self) -> str:
        """獲取當前服務提供商名稱"""
        provider_names = {
            "openai": "OpenAI Whisper API",
            "deepgram": "Deepgram",
            "local_whisper": "本地 OpenAI Whisper",
            "faster_whisper": "Faster-Whisper (高性能)"
        }
        return provider_names.get(self.provider, self.provider) 