import os
import time
import logging
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from config import AppConfig
from models import APIError


class DeepgramService:
    """Deepgram 語音轉文字服務"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.client = DeepgramClient(config.deepgram_api_key)
    
    def transcribe_audio(self, audio_file_path: str) -> str:
        """使用 Deepgram 轉換語音為文字"""
        try:
            start_time = time.time()
            
            # 檢查檔案大小
            file_size = os.path.getsize(audio_file_path)
            if file_size > 100 * 1024 * 1024:  # 100MB
                logging.warning(f"音訊檔案較大: {file_size / (1024*1024):.1f}MB，處理時間可能較長")
            
            # 讀取音訊檔案
            with open(audio_file_path, "rb") as audio_file:
                buffer_data = audio_file.read()
            
            # 創建音訊來源
            payload: FileSource = {
                "buffer": buffer_data,
            }
            
            # 配置轉錄選項
            options = PrerecordedOptions(
                model=self.config.deepgram_model,
                language=self.config.deepgram_language,
                smart_format=True,  # 自動格式化，添加標點符號
                punctuate=True,     # 添加標點符號
                diarize=False,      # 不需要說話人識別
                summarize=False,    # 不需要摘要（我們有 Gemini）
                detect_language=False if self.config.deepgram_language != "auto" else True,
            )
            
            # 進行轉錄
            response = self.client.listen.rest.v("1").transcribe_file(payload, options)
            
            processing_time = time.time() - start_time
            logging.info(f"Deepgram 處理時間: {processing_time:.2f}秒")
            
            # 提取轉錄文字
            if response.results and response.results.channels:
                transcript = response.results.channels[0].alternatives[0].transcript
                result = transcript.strip()
                logging.info(f"轉錄文字長度: {len(result)} 字符")
                return result
            else:
                raise APIError("Deepgram 未返回轉錄結果")
                
        except Exception as e:
            if "insufficient_quota" in str(e).lower():
                raise APIError("Deepgram API 配額不足")
            elif "rate_limit" in str(e).lower():
                raise APIError("Deepgram API 請求過於頻繁")
            elif "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                raise APIError("Deepgram API 金鑰無效或未授權")
            else:
                logging.error(f"Deepgram 轉錄失敗: {e}")
                raise APIError(f"Deepgram 語音轉文字服務錯誤: {e}")
    
    def get_usage_info(self) -> dict:
        """獲取使用量資訊"""
        try:
            # 這裡可以添加 Deepgram 使用量查詢邏輯
            # 目前先返回基本資訊
            return {
                "service": "Deepgram",
                "model": self.config.deepgram_model,
                "language": self.config.deepgram_language,
                "status": "ready"
            }
        except Exception as e:
            logging.warning(f"獲取 Deepgram 使用量失敗: {e}")
            return {
                "service": "Deepgram",
                "status": "error",
                "error": str(e)
            } 