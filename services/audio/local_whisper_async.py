"""
異步本地Whisper語音識別服務
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path
import concurrent.futures

from config import AppConfig

logger = logging.getLogger(__name__)


class AsyncLocalWhisperService:
    """異步本地Whisper服務"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.model_name = config.local_whisper_model
        self.language = config.local_whisper_language
        self.task = config.local_whisper_task
        self.device = config.local_whisper_device
        self.model = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        
        # 延遲載入模型
        logger.info(f"本地Whisper服務初始化，模型: {self.model_name}")
    
    def _load_model(self):
        """載入Whisper模型（同步操作）"""
        if self.model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info(f"載入本地Whisper模型: {self.model_name}")
                self.model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type="float16" if self.device == "cuda" else "int8"
                )
                logger.info("本地Whisper模型載入完成")
            except ImportError:
                raise ImportError("faster_whisper未安裝，請安裝: pip install faster-whisper")
            except Exception as e:
                logger.error(f"載入Whisper模型失敗: {e}")
                raise
    
    def _transcribe_sync(self, file_path: str) -> Dict[str, Any]:
        """同步轉錄（在執行緒池中運行）"""
        try:
            self._load_model()
            
            logger.info(f"本地Whisper開始轉錄: {file_path}")
            
            # 使用faster-whisper進行轉錄
            segments, info = self.model.transcribe(
                file_path,
                language=self.language if self.language != "auto" else None,
                task=self.task,
                beam_size=5,
                best_of=5,
                temperature=0.0
            )
            
            # 收集所有文字段落
            transcript_parts = []
            segment_list = []
            
            for segment in segments:
                transcript_parts.append(segment.text)
                segment_list.append({
                    'start': segment.start,
                    'end': segment.end,
                    'text': segment.text
                })
            
            transcript = ' '.join(transcript_parts).strip()
            
            if not transcript:
                raise Exception("轉錄結果為空")
            
            return {
                'transcript': transcript,
                'language': info.language,
                'language_probability': info.language_probability,
                'duration': info.duration,
                'segments': segment_list,
                'provider': 'local_whisper',
                'model': self.model_name
            }
            
        except Exception as e:
            logger.error(f"本地Whisper轉錄失敗: {str(e)}")
            raise
    
    async def transcribe(self, file_path: str) -> Dict[str, Any]:
        """
        轉錄音頻文件（異步）
        
        Args:
            file_path: 音頻文件路徑
            
        Returns:
            轉錄結果字典
        """
        try:
            # 在執行緒池中運行同步轉錄
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                self._transcribe_sync,
                file_path
            )
            return result
            
        except Exception as e:
            logger.error(f"異步本地Whisper轉錄失敗: {str(e)}")
            raise
    
    async def check_status(self) -> Dict[str, Any]:
        """檢查服務狀態"""
        try:
            # 檢查是否能載入模型
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self._executor, self._load_model)
            
            return {
                "available": True,
                "model": self.model_name,
                "language": self.language,
                "device": self.device,
                "provider": "local_whisper"
            }
            
        except Exception as e:
            return {
                "available": False,
                "error": str(e)
            }
    
    def __del__(self):
        """清理資源"""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False) 