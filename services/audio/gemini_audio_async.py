"""
異步Gemini音頻處理服務
支援直接使用Gemini進行音頻轉文字，使用官方 Google GenAI SDK
"""

import logging
import asyncio
import aiofiles
from typing import Dict, Any, Optional
from pathlib import Path
import os
import random
import tempfile

from config import AppConfig

logger = logging.getLogger(__name__)


class AsyncGeminiAudioService:
    """異步Gemini音頻處理服務"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.api_keys = config.google_api_keys
        self.model = "gemini-2.5-flash-preview-05-20"
        self.max_retries = config.max_retries
        
        if not self.api_keys:
            raise ValueError("Google API密鑰未設置")
        
        # 延遲導入和初始化客戶端
        self._client = None
    
    def _get_api_key(self) -> str:
        """隨機選擇一個API密鑰"""
        return random.choice(self.api_keys)
    
    def _get_generation_config(self):
        """獲取統一的生成配置"""
        return {
            "max_output_tokens": 65536,
            "temperature": 1,
        }
    
    def _get_client(self):
        """獲取 GenAI 客戶端，延遲初始化"""
        if self._client is None:
            try:
                from google import genai
                api_key = self._get_api_key()
                self._client = genai.Client(api_key=api_key)
                logger.info("✅ 成功初始化 Google GenAI 客戶端")
            except ImportError as e:
                logger.error(f"❌ 無法導入 google.genai: {e}")
                raise
            except Exception as e:
                logger.error(f"❌ 初始化 GenAI 客戶端失敗: {e}")
                raise
        return self._client
    
    async def transcribe(self, file_path: str) -> Dict[str, Any]:
        """
        使用Gemini SDK轉錄音頻文件，包含說話者識別和時間戳
        
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
            
            # 在異步環境中執行同步操作
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._transcribe_sync, file_path, file_size_mb
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Gemini Audio轉錄失敗: {str(e)}")
            raise
    
    def _transcribe_sync(self, file_path: str, file_size_mb: float) -> Dict[str, Any]:
        """同步轉錄音頻（內部使用）"""
        logger.info(f"🎯 開始使用 Gemini Audio 轉錄: {file_path}")
        
        try:
            client = self._get_client()
            
            # 上傳文件
            logger.info("📤 上傳音頻文件到 Gemini")
            # 從文件擴展名推斷 MIME type
            file_ext = Path(file_path).suffix.lower()
            mime_type_map = {
                '.mp3': 'audio/mp3',
                '.wav': 'audio/wav',
                '.m4a': 'audio/mp4',
                '.aac': 'audio/aac',
                '.ogg': 'audio/ogg',
                '.flac': 'audio/flac',
                '.webm': 'audio/webm',
                '.audio': 'audio/mpeg'  # 預設為 mp3
            }
            mime_type = mime_type_map.get(file_ext, 'audio/mpeg')
            
            # 使用 UploadFileConfig 來指定 MIME type
            upload_config = {'mime_type': mime_type}
            uploaded_file = client.files.upload(file=file_path, config=upload_config)
            logger.info(f"✅ 文件上傳成功: {uploaded_file.name}, MIME type: {mime_type}")
            
            # 創建詳細的提示
            transcription_prompt = """請將我上傳的錄音檔，轉錄成文字稿
辨識錄音中的每位說話者並標記為「說話者 A」、「說話者 B」等。
將每位說話者的對話內容轉錄為逐字稿，並在每段對話前加上時間戳。
以下是輸出格式範例：
[00:01] 說話者A：你好，今天我們討論的是人工智慧的發展。
[00:05] 說話者B：是的，我認為這是一個非常有趣的主題。

請按照這個格式進行轉錄，確保：
1. 準確辨識出所有說話者
2. 提供精確的時間戳
3. 完整轉錄對話內容
4. 保持自然的語言流暢度"""

            # 發送轉錄請求
            logger.info("🎯 發送轉錄請求到 Gemini")
            response = client.models.generate_content(
                model=self.model,
                contents=[transcription_prompt, uploaded_file],
                config=self._get_generation_config()
            )
            
            if not response or not response.text:
                raise Exception("Gemini 返回空響應")
            
            transcription_text = response.text.strip()
            logger.info(f"✅ Gemini Audio 轉錄成功，文本長度: {len(transcription_text)}")
            
            return {
                'transcript': transcription_text,
                'text': transcription_text,
                'provider': 'gemini_audio_official_sdk',
                'model': self.model,
                'confidence': 0.95,
                'language': 'zh',
                'speaker_detection': True,
                'timestamp_enabled': True
            }
            
        except Exception as e:
            logger.error(f"❌ Gemini Audio 轉錄失敗: {str(e)}")
            raise Exception(f"Gemini Audio 轉錄失敗: {str(e)}")
    
    async def transcribe_with_custom_prompt(self, file_path: str, custom_prompt: str) -> Dict[str, Any]:
        """
        使用自定義提示進行轉錄
        
        Args:
            file_path: 音頻文件路徑
            custom_prompt: 自定義提示
            
        Returns:
            轉錄結果字典
        """
        try:
            logger.info(f"Gemini Audio開始自定義轉錄: {file_path}")
            
            # 檢查文件是否存在
            if not Path(file_path).exists():
                raise FileNotFoundError(f"音頻文件不存在: {file_path}")
            
            # 檢查文件大小
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            if file_size_mb > 100:
                raise ValueError(f"文件太大: {file_size_mb:.1f}MB，Gemini最大支援100MB")
            
            # 在異步環境中執行同步操作
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._transcribe_with_custom_prompt_sync, file_path, custom_prompt, file_size_mb
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Gemini Audio自定義轉錄失敗: {str(e)}")
            raise
    
    def _transcribe_with_custom_prompt_sync(self, file_path: str, custom_prompt: str, file_size_mb: float) -> Dict[str, Any]:
        """使用自定義提示進行同步轉錄"""
        logger.info(f"🎯 使用自定義提示進行 Gemini Audio 轉錄: {file_path}")
        
        try:
            client = self._get_client()
            
            # 上傳文件，帶上 MIME type
            file_ext = Path(file_path).suffix.lower()
            mime_type_map = {
                '.mp3': 'audio/mp3',
                '.wav': 'audio/wav',
                '.m4a': 'audio/mp4',
                '.aac': 'audio/aac',
                '.ogg': 'audio/ogg',
                '.flac': 'audio/flac',
                '.webm': 'audio/webm',
                '.audio': 'audio/mpeg'  # 預設為 mp3
            }
            mime_type = mime_type_map.get(file_ext, 'audio/mpeg')
            
            # 使用 UploadFileConfig 來指定 MIME type
            upload_config = {'mime_type': mime_type}
            uploaded_file = client.files.upload(file=file_path, config=upload_config)
            logger.info(f"✅ 文件上傳成功: {uploaded_file.name}, MIME type: {mime_type}")
            
            # 發送自定義提示請求
            response = client.models.generate_content(
                model=self.model,
                contents=[custom_prompt, uploaded_file],
                config=self._get_generation_config()
            )
            
            if not response or not response.text:
                raise Exception("Gemini 返回空響應")
            
            transcription_text = response.text.strip()
            logger.info(f"✅ 自定義提示轉錄成功，文本長度: {len(transcription_text)}")
            
            return {
                'transcript': transcription_text,
                'text': transcription_text,
                'provider': 'gemini_audio_custom_prompt',
                'model': self.model,
                'confidence': 0.95,
                'language': 'zh',
                'custom_prompt_used': True
            }
            
        except Exception as e:
            logger.error(f"❌ 自定義提示轉錄失敗: {str(e)}")
            raise Exception(f"自定義提示轉錄失敗: {str(e)}")
    
    async def check_status(self) -> Dict[str, Any]:
        """檢查服務狀態"""
        try:
            # 嘗試初始化客戶端以檢查狀態
            client = self._get_client()
            
            # 嘗試列出模型以驗證 API 連接
            await asyncio.get_event_loop().run_in_executor(
                None, self._check_models_sync, client
            )
            
            return {
                "available": True,
                "model": self.model,
                "provider": "gemini_audio_sdk",
                "api_keys_count": len(self.api_keys),
                "sdk_version": "google-genai",
                "features": ["speaker_diarization", "timestamps", "custom_prompts"]
            }
                        
        except Exception as e:
            return {
                "available": False,
                "error": str(e)
            }
    
    def _check_models_sync(self, client):
        """同步檢查模型列表"""
        try:
            # 嘗試列出可用模型
            models = list(client.models.list())
            logger.info(f"✅ Gemini API 連接正常，找到 {len(models)} 個模型")
            return True
        except Exception as e:
            logger.error(f"❌ Gemini API 連接失敗: {str(e)}")
            raise
    
    async def transcribe_with_key_rotation(self, file_path: str) -> Dict[str, Any]:
        """
        嘗試使用不同的 API key 進行轉錄
        
        Args:
            file_path: 音頻文件路徑
            
        Returns:
            轉錄結果字典
        """
        if len(self.api_keys) <= 1:
            raise Exception("沒有額外的 API keys 可供輪換")
        
        last_error = None
        
        for i, api_key in enumerate(self.api_keys):
            try:
                logger.info(f"🔑 嘗試 API key #{i+1}")
                
                # 創建新的客戶端使用指定的 API key
                from google import genai
                temp_client = genai.Client(api_key=api_key)
                
                # 檢查文件大小
                file_size = os.path.getsize(file_path)
                file_size_mb = file_size / (1024 * 1024)
                
                if file_size_mb > 100:
                    raise ValueError(f"文件太大: {file_size_mb:.1f}MB")
                
                # 在異步環境中執行轉錄
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self._transcribe_with_client_sync, file_path, temp_client
                )
                
                logger.info(f"✅ API key #{i+1} 轉錄成功")
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ API key #{i+1} 失敗: {str(e)}")
                continue
        
        raise Exception(f"所有 API keys 都失敗，最後錯誤: {str(last_error)}")
    
    def _transcribe_with_client_sync(self, file_path: str, client) -> Dict[str, Any]:
        """使用指定客戶端進行同步轉錄"""
        try:
            # 上傳文件，帶上 MIME type
            file_ext = Path(file_path).suffix.lower()
            mime_type_map = {
                '.mp3': 'audio/mp3',
                '.wav': 'audio/wav',
                '.m4a': 'audio/mp4',
                '.aac': 'audio/aac',
                '.ogg': 'audio/ogg',
                '.flac': 'audio/flac',
                '.webm': 'audio/webm',
                '.audio': 'audio/mpeg'  # 預設為 mp3
            }
            mime_type = mime_type_map.get(file_ext, 'audio/mpeg')
            
            # 使用 UploadFileConfig 來指定 MIME type
            upload_config = {'mime_type': mime_type}
            uploaded_file = client.files.upload(file=file_path, config=upload_config)
            
            # 創建轉錄提示
            transcription_prompt = """請將上傳的音頻文件轉錄為文字，包括說話者識別和時間戳。
格式：[時間] 說話者：內容"""
            
            # 發送請求
            response = client.models.generate_content(
                model=self.model,
                contents=[transcription_prompt, uploaded_file],
                config=self._get_generation_config()
            )
            
            if not response or not response.text:
                raise Exception("轉錄響應為空")
            
            return {
                'transcript': response.text.strip(),
                'text': response.text.strip(),
                'provider': 'gemini_audio_with_client',
                'model': self.model,
                'confidence': 0.95
            }
            
        except Exception as e:
            logger.error(f"❌ 客戶端轉錄失敗: {str(e)}")
            raise 