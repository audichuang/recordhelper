import logging
from typing import Optional
from config import AppConfig
from models import APIError
from whisper_service import WhisperService
from deepgram_service import DeepgramService


class SpeechToTextService:
    """統一的語音轉文字服務接口"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.provider = config.speech_to_text_provider.lower()
        
        # 初始化對應的服務
        if self.provider == "openai":
            self.service = WhisperService(config)
            logging.info("使用 OpenAI Whisper 語音轉文字服務")
        elif self.provider == "deepgram":
            self.service = DeepgramService(config)
            logging.info("使用 Deepgram 語音轉文字服務")
        else:
            raise ValueError(f"不支援的語音轉文字服務提供商: {config.speech_to_text_provider}")
    
    def transcribe_audio(self, audio_file_path: str) -> str:
        """轉換語音為文字"""
        try:
            if self.provider == "openai":
                return self.service.transcribe_audio(audio_file_path)
            elif self.provider == "deepgram":
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
    
    def get_provider_name(self) -> str:
        """獲取當前服務提供商名稱"""
        provider_names = {
            "openai": "OpenAI Whisper",
            "deepgram": "Deepgram"
        }
        return provider_names.get(self.provider, self.provider) 