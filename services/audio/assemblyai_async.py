"""
異步 AssemblyAI 語音識別服務
"""

import os
import logging
import asyncio
import aiohttp
import aiofiles
import subprocess
from typing import Dict, Any, Optional, List
from pathlib import Path
import uuid
import tempfile

from config import AppConfig
from .srt_formatter import SRTFormatter

logger = logging.getLogger(__name__)

# 檔案大小限制 (5GB)
MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024


class AsyncAssemblyAIService:
    """異步 AssemblyAI 服務"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.api_keys = config.assemblyai_api_keys if hasattr(config, 'assemblyai_api_keys') else []
        
        # 如果沒有列表，嘗試獲取單一金鑰
        if not self.api_keys and hasattr(config, 'assemblyai_api_key'):
            self.api_keys = [config.assemblyai_api_key]
        
        if not self.api_keys:
            logger.warning("⚠️ AssemblyAI API 金鑰未設置")
            self.api_keys = []  # 設為空列表而不是拋出異常
        else:
            logger.info(f"✅ AssemblyAI 服務初始化成功，已載入 {len(self.api_keys)} 個 API 金鑰")
        
        self.current_key_index = 0
        self.base_url = "https://api.assemblyai.com/v2"
        
        # 模型配置
        self.speech_model = config.assemblyai_model if hasattr(config, 'assemblyai_model') else "best"
        self.language = config.assemblyai_language if hasattr(config, 'assemblyai_language') else "zh"
    
    def _get_next_api_key(self) -> str:
        """獲取下一個可用的 API 金鑰（輪詢）"""
        if not self.api_keys:
            raise ValueError("沒有可用的 AssemblyAI API 金鑰")
        
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key
    
    async def _check_file_size(self, file_path: str) -> int:
        """檢查檔案大小"""
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / 1024 / 1024
        logger.info(f"檔案大小: {file_size_mb:.2f} MB")
        return file_size
    
    async def _compress_audio_to_mp3(self, input_file: str) -> str:
        """
        使用 ffmpeg 壓縮音檔為 MP3 格式
        
        Args:
            input_file: 輸入音檔路徑
            
        Returns:
            壓縮後的檔案路徑
        """
        output_file = None
        try:
            # 創建臨時檔案
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                output_file = tmp.name
            
            logger.info(f"正在壓縮音檔為 MP3: {input_file}")
            
            cmd = [
                'ffmpeg', '-i', input_file,
                '-acodec', 'libmp3lame',
                '-b:a', '64k',    # 64kbps 位元率
                '-ar', '22050',   # 22.05kHz 取樣率
                '-ac', '1',       # 單聲道
                '-y',             # 覆蓋輸出檔案
                output_file
            ]
            
            # 使用 asyncio 執行 subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"音檔壓縮失敗: {stderr.decode()}")
            
            # 顯示壓縮結果
            original_size = os.path.getsize(input_file)
            compressed_size = os.path.getsize(output_file)
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            logger.info(f"壓縮完成:")
            logger.info(f"  原始大小: {original_size / 1024 / 1024:.2f} MB")
            logger.info(f"  壓縮後: {compressed_size / 1024 / 1024:.2f} MB")
            logger.info(f"  壓縮率: {compression_ratio:.1f}%")
            
            return output_file
            
        except Exception as e:
            # 如果壓縮失敗，清理臨時檔案
            if output_file and os.path.exists(output_file):
                os.remove(output_file)
            logger.error(f"壓縮音檔時發生錯誤: {e}")
            raise
    
    async def _upload_file(self, file_path: str, api_key: str) -> str:
        """
        上傳檔案到 AssemblyAI
        
        Args:
            file_path: 檔案路徑
            api_key: API 金鑰
            
        Returns:
            上傳後的檔案 URL
        """
        headers = {
            'authorization': api_key
        }
        
        async with aiofiles.open(file_path, 'rb') as f:
            file_data = await f.read()
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/upload",
                headers=headers,
                data=file_data,
                timeout=aiohttp.ClientTimeout(total=600)  # 10分鐘超時
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"檔案上傳失敗 {response.status}: {error_text}")
                
                result = await response.json()
                upload_url = result.get('upload_url')
                
                if not upload_url:
                    raise Exception("上傳失敗：未獲得檔案 URL")
                
                logger.info(f"檔案上傳成功: {upload_url}")
                return upload_url
    
    async def _create_transcript(self, audio_url: str, api_key: str) -> str:
        """
        創建轉錄任務
        
        Args:
            audio_url: 音檔 URL
            api_key: API 金鑰
            
        Returns:
            轉錄任務 ID
        """
        headers = {
            'authorization': api_key,
            'content-type': 'application/json'
        }
        
        # 配置轉錄選項
        data = {
            'audio_url': audio_url,
            'language_code': self.language if self.language != 'auto' else None,
            'speech_model': self.speech_model,
            'speaker_labels': True,  # 啟用說話者識別
            'punctuate': True,       # 自動加標點符號
            'format_text': True,     # 格式化文字
            'language_detection': self.language == 'auto',
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/transcript",
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"創建轉錄任務失敗 {response.status}: {error_text}")
                
                result = await response.json()
                transcript_id = result.get('id')
                
                if not transcript_id:
                    raise Exception("創建轉錄任務失敗：未獲得任務 ID")
                
                logger.info(f"轉錄任務已創建: {transcript_id}")
                return transcript_id
    
    async def _poll_transcript(self, transcript_id: str, api_key: str) -> Dict[str, Any]:
        """
        輪詢轉錄結果
        
        Args:
            transcript_id: 轉錄任務 ID
            api_key: API 金鑰
            
        Returns:
            轉錄結果
        """
        headers = {
            'authorization': api_key
        }
        
        max_attempts = 300  # 最多等待 5 分鐘（每秒一次）
        attempt = 0
        
        async with aiohttp.ClientSession() as session:
            while attempt < max_attempts:
                async with session.get(
                    f"{self.base_url}/transcript/{transcript_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"獲取轉錄結果失敗 {response.status}: {error_text}")
                    
                    result = await response.json()
                    status = result.get('status')
                    
                    if status == 'completed':
                        logger.info("轉錄完成")
                        return result
                    elif status == 'error':
                        error_msg = result.get('error', '未知錯誤')
                        raise Exception(f"轉錄失敗: {error_msg}")
                    else:
                        # 處理中，等待
                        logger.debug(f"轉錄狀態: {status}, 等待中...")
                        await asyncio.sleep(1)
                        attempt += 1
        
        raise Exception("轉錄超時：處理時間過長")
    
    async def transcribe(self, file_path: str, compress_if_needed: bool = True) -> Dict[str, Any]:
        """
        轉錄音頻文件
        
        Args:
            file_path: 音頻文件路徑
            compress_if_needed: 是否在需要時壓縮檔案
            
        Returns:
            轉錄結果字典
        """
        temp_files = []  # 追蹤需要清理的暫存檔案
        
        try:
            logger.info(f"AssemblyAI 開始轉錄: {file_path}")
            
            # 檢查檔案大小
            file_size = await self._check_file_size(file_path)
            
            # 如果檔案太大，進行壓縮
            if file_size > MAX_FILE_SIZE:
                if compress_if_needed:
                    logger.info(f"檔案大小超過限制 ({MAX_FILE_SIZE / 1024 / 1024 / 1024:.1f} GB)，正在壓縮...")
                    compressed_file = await self._compress_audio_to_mp3(file_path)
                    temp_files.append(compressed_file)
                    file_path = compressed_file
                else:
                    raise Exception(f"檔案大小超過限制 ({MAX_FILE_SIZE / 1024 / 1024 / 1024:.1f} GB)")
            
            # 嘗試使用不同的 API 金鑰
            last_error = None
            for attempt in range(len(self.api_keys)):
                api_key = self._get_next_api_key()
                
                try:
                    # 1. 上傳檔案
                    logger.info("正在上傳音檔...")
                    audio_url = await self._upload_file(file_path, api_key)
                    
                    # 2. 創建轉錄任務
                    logger.info("正在創建轉錄任務...")
                    transcript_id = await self._create_transcript(audio_url, api_key)
                    
                    # 3. 輪詢結果
                    logger.info("正在等待轉錄結果...")
                    result = await self._poll_transcript(transcript_id, api_key)
                    
                    # 處理結果
                    transcript = result.get('text', '').strip()
                    if not transcript:
                        raise Exception("轉錄結果為空")
                    
                    # 計算音頻時長（毫秒轉秒）
                    duration_ms = result.get('audio_duration', 0)
                    duration = duration_ms / 1000 if duration_ms else None
                    
                    # 調試信息
                    logger.info(f"🔍 AssemblyAI 原始時長數據: audio_duration={duration_ms}ms, 轉換後={duration}s")
                    
                    # 處理單詞時間戳
                    words = []
                    if result.get('words'):
                        for word_info in result['words']:
                            words.append({
                                'text': word_info.get('text', ''),
                                'start': word_info.get('start', 0) / 1000,  # 毫秒轉秒
                                'end': word_info.get('end', 0) / 1000,
                                'confidence': word_info.get('confidence', 0),
                                'speaker': word_info.get('speaker')
                            })
                    
                    # 生成 SRT 格式字幕
                    srt_content = ''
                    if words:
                        srt_content = SRTFormatter.generate_srt_from_words(words, sentence_level=True)
                    
                    # 格式化返回結果
                    return {
                        'transcript': transcript,
                        'language': result.get('language_code', self.language),
                        'duration': duration,
                        'words': words,
                        'confidence': result.get('confidence'),
                        'speakers': result.get('speakers'),
                        'provider': 'assemblyai',
                        'model': self.speech_model,
                        'api_key_index': self.api_keys.index(api_key),
                        'srt': srt_content,
                        'has_srt': bool(srt_content)
                    }
                    
                except Exception as e:
                    last_error = e
                    logger.warning(f"AssemblyAI API 金鑰 {attempt + 1} 失敗: {str(e)}")
                    
                    # 如果是最後一個金鑰，拋出錯誤
                    if attempt == len(self.api_keys) - 1:
                        raise last_error
                    
                    # 否則繼續嘗試下一個金鑰
                    await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"AssemblyAI 轉錄失敗: {str(e)}")
            raise
            
        finally:
            # 清理暫存檔案
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.debug(f"已清理暫存檔案: {temp_file}")
                except Exception as cleanup_error:
                    logger.warning(f"清理檔案時發生錯誤 {temp_file}: {cleanup_error}")
    
    async def check_status(self) -> Dict[str, Any]:
        """檢查服務狀態"""
        try:
            # 使用第一個 API 金鑰測試
            if not self.api_keys:
                return {
                    "available": False,
                    "error": "沒有配置 API 金鑰"
                }
            
            api_key = self.api_keys[0]
            headers = {
                'authorization': api_key
            }
            
            # 測試 API 連接
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status in [200, 404]:  # 404 是預期的，因為根路徑可能不存在
                        return {
                            "available": True,
                            "model": self.speech_model,
                            "language": self.language,
                            "provider": "assemblyai",
                            "api_keys_count": len(self.api_keys)
                        }
                    else:
                        return {
                            "available": False,
                            "error": f"API 響應錯誤: {response.status}"
                        }
                        
        except Exception as e:
            return {
                "available": False,
                "error": str(e)
            }