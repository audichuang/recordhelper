import os
import time
import logging
import random
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from config import AppConfig
from models.base import APIError


class DeepgramService:
    """Deepgram 語音轉文字服務"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.api_keys = config.deepgram_api_keys.copy() if config.deepgram_api_keys else []
        self.current_key_index = 0
        self.max_retries = config.max_retries
        
        if not self.api_keys:
            raise ValueError("Deepgram API 金鑰列表為空")
        
        # 隨機化金鑰順序以分散負載
        random.shuffle(self.api_keys)
        
        # 初始化第一個客戶端
        self.client = DeepgramClient(self.api_keys[0])
        logging.info(f"Deepgram 服務初始化成功，共 {len(self.api_keys)} 個 API 金鑰")
    
    def _switch_api_key(self):
        """切換到下一個 API 金鑰"""
        if len(self.api_keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            new_key = self.api_keys[self.current_key_index]
            self.client = DeepgramClient(new_key)
            logging.info(f"切換到 Deepgram API 金鑰 #{self.current_key_index + 1}")
            return True
        return False
    
    def transcribe_audio(self, audio_file_path: str) -> str:
        """使用 Deepgram 轉換語音為文字（支援多 API Key 重試）"""
        last_error = None
        
        for attempt in range(self.max_retries + 1):
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
                logging.info(f"Deepgram 處理時間: {processing_time:.2f}秒 (API Key #{self.current_key_index + 1})")
                
                # 提取轉錄文字
                if response.results and response.results.channels:
                    transcript = response.results.channels[0].alternatives[0].transcript
                    result = transcript.strip()
                    logging.info(f"轉錄文字長度: {len(result)} 字符")
                    return result
                else:
                    raise APIError("Deepgram 未返回轉錄結果")
                    
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                if "insufficient_quota" in error_str or "quota" in error_str:
                    logging.warning(f"Deepgram API Key #{self.current_key_index + 1} 配額不足")
                    if not self._switch_api_key():
                        raise APIError("所有 Deepgram API 金鑰配額不足")
                elif "rate_limit" in error_str:
                    logging.warning(f"Deepgram API Key #{self.current_key_index + 1} 請求過於頻繁")
                    if not self._switch_api_key():
                        raise APIError("所有 Deepgram API 金鑰請求過於頻繁")
                elif "authentication" in error_str or "unauthorized" in error_str:
                    logging.warning(f"Deepgram API Key #{self.current_key_index + 1} 無效或未授權")
                    if not self._switch_api_key():
                        raise APIError("所有 Deepgram API 金鑰無效或未授權")
                else:
                    # 其他錯誤，記錄但繼續重試
                    logging.error(f"Deepgram 轉錄失敗 (嘗試 {attempt + 1}): {e}")
                    if attempt < self.max_retries:
                        self._switch_api_key()
                        time.sleep(1)  # 短暫延遲後重試
                    
        # 所有重試都失敗
        raise APIError(f"Deepgram 語音轉文字服務錯誤，已重試 {self.max_retries} 次: {last_error}")
    
    def get_usage_info(self) -> dict:
        """獲取使用量資訊"""
        try:
            # 這裡可以添加 Deepgram 使用量查詢邏輯
            # 目前先返回基本資訊
            return {
                "service": "Deepgram",
                "model": self.config.deepgram_model,
                "language": self.config.deepgram_language,
                "api_keys_count": len(self.api_keys),
                "current_key_index": self.current_key_index + 1,
                "status": "ready"
            }
        except Exception as e:
            logging.warning(f"獲取 Deepgram 使用量失敗: {e}")
            return {
                "service": "Deepgram",
                "status": "error",
                "error": str(e)
            } 