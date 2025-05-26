import os
import time
import logging
import openai
from config import AppConfig
from models import APIError


class WhisperService:
    def __init__(self, config: AppConfig):
        self.config = config
        self.openai_client = openai
        self.openai_client.api_key = config.openai_api_key

    def transcribe_audio(self, audio_file_path: str) -> str:
        """使用Whisper轉換語音為文字 - 優化版本"""
        try:
            start_time = time.time()
            
            # 檢查檔案大小，如果超過25MB則警告
            file_size = os.path.getsize(audio_file_path)
            if file_size > 25 * 1024 * 1024:  # 25MB
                logging.warning(f"音訊檔案較大: {file_size / (1024*1024):.1f}MB，處理時間可能較長")
            
            with open(audio_file_path, "rb") as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model=self.config.whisper_model,
                    file=audio_file,
                    language="zh",
                    response_format="text",  # 直接返回文字，減少處理時間
                    prompt="以下是中文語音內容，請準確轉錄："  # 添加提示提高準確性
                )

            processing_time = time.time() - start_time
            logging.info(f"Whisper 處理時間: {processing_time:.2f}秒")

            result = transcript.strip() if isinstance(transcript, str) else transcript.text.strip()
            logging.info(f"轉錄文字長度: {len(result)} 字符")
            
            return result
        except openai.APIError as e:
            if "insufficient_quota" in str(e):
                raise APIError("OpenAI API 配額不足")
            elif "rate_limit" in str(e):
                raise APIError("API 請求過於頻繁")
            else:
                raise APIError(f"OpenAI API 錯誤: {e}")
        except Exception as e:
            logging.error(f"Whisper 轉錄失敗: {e}")
            raise APIError(f"語音轉文字服務錯誤: {e}")
    
    def get_usage_info(self) -> dict:
        """獲取使用量資訊"""
        try:
            return {
                "service": "OpenAI Whisper",
                "model": self.config.whisper_model,
                "status": "ready"
            }
        except Exception as e:
            logging.warning(f"獲取 OpenAI Whisper 使用量失敗: {e}")
            return {
                "service": "OpenAI Whisper",
                "status": "error",
                "error": str(e)
            } 