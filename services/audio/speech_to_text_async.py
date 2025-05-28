# -*- coding: utf-8 -*-
"""
異步語音轉文字 (Speech-to-Text) 服務聚合器模組。

此模組定義了 `AsyncSpeechToTextService` 類別，它作為一個統一的介面，
可以根據應用程式的組態設定，選擇並調用不同的後端語音識別服務。
支援的後端服務可能包括 OpenAI Whisper API、Deepgram、本地 Whisper (faster-whisper)
以及 Google Gemini 的音訊處理功能。

主要功能：
-   根據組態動態初始化並選擇語音識別服務提供者。
-   提供統一的 `transcribe_audio_data` (處理 bytes) 和 `transcribe_audio_file_async` (處理檔案路徑) 方法。
-   實現服務備援 (fallback) 機制：如果主要服務提供者失敗，會嘗試使用備用的服務提供者。
-   計算音訊時長 (需要 `PyAV` 函式庫)。
-   提供檢查各後端服務健康狀態的功能。
"""

import logging
import asyncio # 用於異步操作
import aiofiles # 用於異步檔案操作
from typing import Dict, Any, Optional, List # 用於類型註解
from pathlib import Path # 用於路徑操作
import os # 用於檔案系統操作，例如檢查檔案是否存在、獲取檔案大小
import base64 # base64 未在此檔案直接使用，但保留以備考慮原始音訊數據傳輸
import tempfile # 用於創建臨時檔案

# 嘗試導入 PyAV 函式庫，用於音訊時長計算
try:
    import av # PyAV 函式庫
    HAS_AV = True
    logger_av = logging.getLogger('libav') # 獲取 libav (PyAV 底層) 的日誌記錄器
    logger_av.setLevel(logging.ERROR) # 設定 libav 的日誌級別為 ERROR，以減少不必要的輸出
except ImportError:
    HAS_AV = False
    logging.warning("⚠️ PyAV 套件未安裝。音訊時長計算功能將不可用。請執行 'pip install av' 來安裝。")

from config import AppConfig # 導入應用程式組態
# 導入各個具體的 STT 服務實現
from .whisper_async import AsyncWhisperService
from .deepgram_async import AsyncDeepgramService
from .local_whisper_async import AsyncLocalWhisperService
from .gemini_audio_async import AsyncGeminiAudioService # 假設 Gemini 音訊服務已在此檔案中

logger = logging.getLogger(__name__)


class AsyncSpeechToTextService:
    """
    異步語音轉文字服務聚合器。

    根據組態選擇並調用不同的後端 STT 服務，並提供備援機制。
    """
    
    def __init__(self, config: AppConfig):
        """
        初始化 AsyncSpeechToTextService。

        Args:
            config (AppConfig): 應用程式的組態設定物件。
        """
        self.config = config
        # 將設定的提供者名稱轉換為小寫，以便進行不區分大小寫的比較
        self.primary_provider: str = config.SPEECH_TO_TEXT_PROVIDER.lower()
        
        # 初始化所有可能的後端 STT 服務實例
        # 這些服務在其實現內部應處理自身的 API 金鑰和設定載入
        self.whisper_service = AsyncWhisperService(config)
        self.deepgram_service = AsyncDeepgramService(config)
        self.local_whisper_service = AsyncLocalWhisperService(config)
        self.gemini_audio_service = AsyncGeminiAudioService(config) # 假設 Gemini 音訊服務也需要 config
        
        logger.info(f"🔧 異步語音轉文字服務 (AsyncSpeechToTextService) 初始化完成。主要提供者設定為: '{self.primary_provider}'")
    
    async def get_audio_duration_from_data(self, audio_data: bytes, source_description: str = "記憶體中的音訊數據") -> Optional[float]:
        """
        從提供的音訊二進制數據中計算音訊時長。

        需要 `PyAV` 函式庫支援。如果未安裝，將無法計算並返回 None。

        Args:
            audio_data (bytes): 音訊檔案的原始二進制數據。
            source_description (str, optional): 音訊來源的描述，用於日誌記錄。預設為 "記憶體中的音訊數據"。

        Returns:
            Optional[float]: 音訊時長 (秒)。如果無法計算 (例如 PyAV 未安裝或檔案損毀)，則返回 None。
        """
        if not HAS_AV: # 檢查 PyAV 是否可用
            logger.warning(f"⚠️ 無法計算音訊時長 ({source_description})：PyAV 套件未安裝。")
            return None
        
        try:
            import io # 用於將 bytes 數據包裝為類似檔案的物件
            
            # 使用 io.BytesIO 將 bytes 數據創建為一個記憶體中的二進制流
            audio_buffer = io.BytesIO(audio_data)
            
            # 使用 PyAV 開啟記憶體中的音訊流並獲取時長
            # `av.open` 可以接受類檔案物件
            with av.open(audio_buffer, mode='r') as container: # mode='r' 指示讀取模式
                if container.streams.audio: # 檢查是否存在音訊流
                    # 音訊時長通常以 stream.duration * stream.time_base 計算
                    # container.duration 直接給出以 AV_TIME_BASE 為單位的總時長
                    duration_seconds = float(container.duration) / av.time_base if container.duration is not None else None
                    if duration_seconds is not None:
                        logger.info(f"🕒 計算得到音訊 ({source_description}) 時長: {duration_seconds:.2f} 秒。")
                        return duration_seconds
                    else:
                        logger.warning(f"⚠️ 無法從音訊流 ({source_description}) 中獲取有效的 duration 屬性。")
                else:
                    logger.warning(f"⚠️ 音訊檔案 ({source_description}) 中未找到音訊流。")
            return None # 如果沒有音訊流或 duration
            
        except Exception as e: # 捕獲所有可能的例外 (例如 av.AVError, TypeError 等)
            logger.error(f"❌ 計算音訊時長 ({source_description}) 時發生錯誤: {str(e)}", exc_info=True)
            return None

    async def get_audio_duration_from_file(self, audio_path: str) -> Optional[float]: # 方法名更清晰
        """
        計算本地音訊檔案的時長。

        需要 `PyAV` 函式庫支援。如果未安裝，將無法計算並返回 None。
        
        Args:
            audio_path (str): 音訊檔案的本地路徑。
            
        Returns:
            Optional[float]: 音訊時長 (秒)。如果無法計算，則返回 None。
        """
        if not HAS_AV:
            logger.warning(f"⚠️ 無法計算音訊時長 (檔案: {audio_path})：PyAV 套件未安裝。")
            return None
        
        if not os.path.exists(audio_path): # 檢查檔案是否存在
            logger.error(f"❌ 計算音訊時長失敗：音訊檔案 '{audio_path}' 不存在。")
            return None
            
        try:
            # 使用 PyAV 開啟音訊檔案並獲取時長
            with av.open(audio_path) as container:
                if container.streams.audio:
                    duration_seconds = float(container.duration) / av.time_base if container.duration is not None else None
                    if duration_seconds is not None:
                        logger.info(f"🕒 計算得到音訊檔案 '{audio_path}' 時長: {duration_seconds:.2f} 秒。")
                        return duration_seconds
                    else:
                        logger.warning(f"⚠️ 無法從音訊檔案 '{audio_path}' 中獲取有效的 duration 屬性。")
                else:
                    logger.warning(f"⚠️ 音訊檔案 '{audio_path}' 中未找到音訊流。")
            return None
            
        except Exception as e:
            logger.error(f"❌ 計算音訊檔案 '{audio_path}' 時長時發生錯誤: {str(e)}", exc_info=True)
            return None
    
    async def transcribe_audio_data(self, audio_data: bytes, original_filename: Optional[str] = "uploaded_audio") -> Dict[str, Any]: # 簡化參數
        """
        使用組態中設定的主要服務提供者轉錄提供的音訊二進制數據，並實現自動備援機制。

        此方法會先將音訊數據保存到一個臨時檔案，然後調用 `_transcribe_with_fallback` 進行處理。
        
        Args:
            audio_data (bytes): 音訊檔案的原始二進制數據。
            original_filename (Optional[str]): 原始檔案名稱，用於生成臨時檔案的後綴以保留格式。預設為 "uploaded_audio"。
            
        Returns:
            Dict[str, Any]: 包含轉錄結果和相關元數據的字典。
                            如果所有服務均轉錄失敗，則會拋出例外。
        
        Raises:
            Exception: 如果所有 STT 服務提供者均轉錄失敗。
        """
        logger.info(f"🎙️ 開始轉錄提供的音訊數據 (大小: {len(audio_data) / (1024):.2f} KB)。原始檔名提示: {original_filename}")
        
        # 從原始檔名推斷檔案後綴 (格式)
        file_suffix = ".tmp" # 預設後綴
        if original_filename:
            try:
                ext = Path(original_filename).suffix.lower()
                if ext: # 確保有擴展名
                    file_suffix = ext
            except Exception: # 防範 Path 解析錯誤
                logger.warning(f"無法從 '{original_filename}' 解析檔案後綴，將使用預設後綴 '{file_suffix}'。")

        temp_file_path: Optional[str] = None # 初始化為 None
        try:
            # 創建一個帶有適當後綴的臨時檔案來保存音訊數據
            # delete=False 允許我們在 finally 區塊中手動刪除，或在某些情況下保留以供除錯
            with tempfile.NamedTemporaryFile(suffix=file_suffix, delete=False) as temp_file:
                await asyncio.get_event_loop().run_in_executor(None, temp_file.write, audio_data) # 在線程中執行寫入
                temp_file_path = temp_file.name # 獲取臨時檔案的路徑
            logger.debug(f"音訊數據已寫入臨時檔案: {temp_file_path}")

            # 計算音訊時長 (從臨時檔案)
            audio_duration = await self.get_audio_duration_from_file(temp_file_path)
            
            # 使用備援機制進行轉錄
            result = await self._transcribe_with_fallback(temp_file_path)
            
            # 在結果中補充或更新音訊時長資訊
            if 'duration_seconds' not in result or result['duration_seconds'] is None:
                if audio_duration is not None:
                    result['duration_seconds'] = audio_duration
                    logger.info(f"📊 使用從臨時檔案計算得到的音訊時長更新結果: {audio_duration:.2f} 秒。")
                else:
                    logger.warning("⚠️ 無法獲取音訊時長資訊以更新轉錄結果。")
            
            logger.info(f"✅ 音訊數據轉錄成功完成。轉錄文本長度: {len(result.get('transcript', ''))} 字元。")
            return result
                
        except Exception as e: # 捕獲所有可能的錯誤，包括檔案操作或轉錄錯誤
            logger.error(f"❌ 音訊數據轉錄過程中發生嚴重錯誤: {str(e)}", exc_info=True)
            raise # 重新拋出例外，讓上層處理
        finally:
            # 無論成功或失敗，都嘗試清理臨時檔案
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path) # 刪除臨時檔案
                    logger.debug(f"臨時檔案 '{temp_file_path}' 已成功刪除。")
                except Exception as e_cleanup:
                    logger.warning(f"⚠️ 清理臨時檔案 '{temp_file_path}' 時發生錯誤: {e_cleanup}", exc_info=True)
                    
    async def transcribe_audio_file_async(self, audio_path: str) -> Dict[str, Any]: # 方法名與其他服務統一
        """
        使用組態中設定的主要服務提供者轉錄指定的音訊檔案，並實現自動備援機制。
        
        Args:
            audio_path (str): 音訊檔案的本地路徑。
            
        Returns:
            Dict[str, Any]: 包含轉錄結果和相關元數據的字典。
                            如果所有服務均轉錄失敗，則會拋出例外。
        
        Raises:
            FileNotFoundError: 如果指定的 `audio_path` 不存在。
            Exception: 如果所有 STT 服務提供者均轉錄失敗。
        """
        if not os.path.exists(audio_path): # 檢查檔案是否存在
            logger.error(f"❌ 轉錄請求失敗：找不到音訊檔案於 '{audio_path}'。")
            raise FileNotFoundError(f"找不到音訊檔案: {audio_path}")
            
        logger.info(f"🎙️ 開始轉錄音訊檔案: {audio_path}")
        
        # 計算音訊時長
        audio_duration = await self.get_audio_duration_from_file(audio_path)
        
        try:
            # 使用備援機制進行轉錄
            result = await self._transcribe_with_fallback(audio_path)
            
            # 在結果中補充或更新音訊時長資訊
            if 'duration_seconds' not in result or result['duration_seconds'] is None:
                if audio_duration is not None:
                    result['duration_seconds'] = audio_duration
                    logger.info(f"📊 使用計算得到的音訊時長更新結果: {audio_duration:.2f} 秒。")
                else:
                    logger.warning("⚠️ 無法獲取音訊時長資訊以更新轉錄結果。")
            
            logger.info(f"✅ 音訊檔案 '{audio_path}' 轉錄成功完成。")
            return result
            
        except Exception as e: # 捕獲所有可能的轉錄錯誤
            logger.error(f"❌ 音訊檔案 '{audio_path}' 轉錄過程中發生嚴重錯誤: {str(e)}", exc_info=True)
            raise # 重新拋出，讓上層處理
    
    async def check_service_health_async(self) -> Dict[str, Any]: # 方法名與其他服務統一
        """
        檢查所有已配置的後端語音轉文字服務的健康狀態。

        Returns:
            Dict[str, Any]: 包含各服務健康狀態的字典。
                            結構為：
                            {
                                "primary_provider": "設定的主要提供者",
                                "overall_status": "healthy/degraded/unhealthy",
                                "services": {
                                    "openai_whisper_api": {"available": True/False, ...},
                                    "deepgram": {"available": True/False, ...},
                                    "local_whisper": {"available": True/False, ...},
                                    "gemini_audio": {"available": True/False, ...}
                                }
                            }
        """
        logger.info("開始檢查所有語音轉文字服務的健康狀態...")
        status_report = {
            "primary_provider": self.primary_provider,
            "overall_status": "unknown", # 初始狀態未知
            "services": {}
        }
        all_services_available = True
        primary_service_available = False

        service_checks = {
            "openai_whisper_api": self.whisper_service.check_service_health_async,
            "deepgram": self.deepgram_service.check_service_health_async,
            "local_whisper": self.local_whisper_service.check_service_health_async,
            "gemini_audio": self.gemini_audio_service.check_service_health_async,
        }

        for service_name, check_func in service_checks.items():
            try:
                service_status = await check_func()
                status_report["services"][service_name] = service_status
                if not service_status.get("available", False):
                    all_services_available = False
                    if service_name == self.primary_provider:
                        primary_service_available = False
                elif service_name == self.primary_provider:
                    primary_service_available = True

            except Exception as e_check:
                logger.error(f"檢查服務 '{service_name}' 狀態時發生錯誤: {str(e_check)}", exc_info=True)
                status_report["services"][service_name] = {"available": False, "error": f"檢查時發生錯誤: {type(e_check).__name__}"}
                all_services_available = False
                if service_name == self.primary_provider:
                    primary_service_available = False
        
        # 判斷總體狀態
        if primary_service_available:
            status_report["overall_status"] = "healthy" if all_services_available else "degraded"
        else:
            status_report["overall_status"] = "unhealthy"
            
        logger.info(f"🔍 語音轉文字服務狀態檢查完成。主要提供者 ('{self.primary_provider}') 狀態: {'可用' if primary_service_available else '不可用'}。總體狀態: {status_report['overall_status']}。")
        return status_report
    
    async def _transcribe_with_fallback(self, file_path: str) -> Dict[str, Any]:
        """
        使用智能備援方案轉錄音訊。

        備援順序 (可根據實際需求和服務可靠性調整)：
        1.  主要服務 (根據組態 `SPEECH_TO_TEXT_PROVIDER` 設定)。
        2.  如果主要服務是 Gemini Audio 且失敗，嘗試使用其內建的 API 金鑰輪換機制 (如果已實現)。
        3.  Deepgram (如果已組態且不是主要服務)。
        4.  OpenAI Whisper API (如果已組態且不是主要服務)。
        5.  Google Gemini Audio (如果已組態且不是主要服務，且尚未作為主要服務嘗試過)。
        6.  本地 Whisper (faster-whisper) (作為最後的備援選項)。
        
        Args:
            file_path (str): 音訊檔案的本地路徑。
            
        Returns:
            Dict[str, Any]: 包含轉錄結果的字典。

        Raises:
            Exception: 如果所有轉錄服務均失敗。
        """
        last_error: Optional[Exception] = None # 用於記錄最後一個發生的錯誤
        
        # 定義嘗試的服務列表和順序，主要提供者優先
        # TODO: 此順序和條件可以進一步優化或透過組態設定
        provider_try_order: List[str] = []
        if self.primary_provider:
            provider_try_order.append(self.primary_provider)
        
        # 添加其他備用服務，確保不重複且存在
        # 順序可以根據偏好和可靠性調整
        # for provider_key in ["gemini_audio", "deepgram", "openai", "local_whisper"]: # 示例順序
        for provider_key in ["gemini_audio", "deepgram", "openai", "local_whisper"]: # 更改備用順序
            if provider_key != self.primary_provider and provider_key not in provider_try_order:
                # 檢查服務是否真的已配置 (例如有API金鑰)
                if provider_key == "gemini_audio" and self.gemini_audio_service.api_keys:
                    provider_try_order.append(provider_key)
                elif provider_key == "deepgram" and self.deepgram_service.api_keys:
                    provider_try_order.append(provider_key)
                elif provider_key == "openai" and self.whisper_service.api_key:
                    provider_try_order.append(provider_key)
                elif provider_key == "local_whisper": # 本地服務通常假設可用，除非模型載入失敗
                    provider_try_order.append(provider_key)
        
        logger.info(f"開始嘗試轉錄，服務嘗試順序: {provider_try_order}")

        for provider_name in provider_try_order:
            try:
                logger.info(f"🔄 正在嘗試使用服務提供者 '{provider_name}' 進行轉錄 (檔案: {file_path})...")
                result: Optional[Dict[str, Any]] = None
                
                if provider_name == "openai":
                    result = await self.whisper_service.transcribe_audio_file_async(file_path)
                elif provider_name == "local_whisper":
                    result = await self.local_whisper_service.transcribe_audio_file_async(file_path)
                elif provider_name == "deepgram":
                    result = await self.deepgram_service.transcribe_audio_data(await aiofiles.open(file_path, 'rb').read(), mime_type="audio/wav") # Deepgram可能需要MIME
                elif provider_name == "gemini_audio":
                    # Gemini Audio 服務的 transcribe_audio_file_async 已包含內部邏輯 (例如輪換金鑰)
                    result = await self.gemini_audio_service.transcribe_audio_file_async(file_path)
                else:
                    logger.warning(f"未知的服務提供者 '{provider_name}' 在備援邏輯中被跳過。")
                    continue # 跳過未知的提供者

                if result and (result.get('transcript') or result.get('text')): # 確保有轉錄內容
                    logger.info(f"✅ 使用服務 '{provider_name}' 轉錄成功。")
                    if provider_name != self.primary_provider:
                        result['backup_provider_used'] = provider_name # 標記使用了備用服務
                    return result
                else:
                    # 即使沒有拋出例外，但如果結果無效或為空，也視為一次失敗的嘗試
                    logger.warning(f"服務 '{provider_name}' 返回的結果無效或為空文本。")
                    last_error = Exception(f"服務 '{provider_name}' 返回無效結果。") # 更新 last_error
                
            except Exception as e_provider: # 捕獲特定提供者轉錄時的錯誤
                last_error = e_provider # 記錄錯誤
                logger.warning(f"⚠️ 使用服務 '{provider_name}' 轉錄失敗: {type(e_provider).__name__} - {str(e_provider)}", exc_info=False) # 簡化日誌，避免過多堆疊追蹤
        
        # 如果遍歷所有服務後仍未成功
        logger.error(f"所有語音轉文字服務提供者均轉錄失敗。最後記錄的錯誤: {type(last_error).__name__} - {str(last_error)}", exc_info=True if last_error else False)
        raise Exception(f"所有轉錄服務均失敗。最後錯誤: {str(last_error)}") from last_error
    
    # 以下私有方法是 _transcribe_with_fallback 的早期版本，現已整合，保留註解以供參考
    # async def _transcribe_with_gemini_no_fallback(self, file_path: str) -> Dict[str, Any]:
    #     """使用 Gemini Audio SDK 轉錄，但不自動嘗試本地備用"""
    #     return await self.gemini_audio_service.transcribe_audio_file_async(file_path)
    
    # async def _transcribe_with_gemini_key_rotation(self, file_path: str) -> Dict[str, Any]:
    #     """嘗試輪換 Gemini API keys"""
    #     # 假設 AsyncGeminiAudioService 內部處理輪換或提供特定方法
    #     # 如果 AsyncGeminiAudioService 沒有此方法，則需要在此處實現輪換邏輯
    #     if hasattr(self.gemini_audio_service, 'transcribe_with_key_rotation'):
    #         return await self.gemini_audio_service.transcribe_with_key_rotation(file_path)
    #     else:
    #         logger.warning("Gemini Audio 服務不支援 'transcribe_with_key_rotation' 方法，將使用標準轉錄。")
    #         return await self.gemini_audio_service.transcribe_audio_file_async(file_path)

    # 以下方法已整合到 _transcribe_with_fallback 的迴圈中
    # async def _transcribe_with_openai(self, file_path: str) -> Dict[str, Any]:
    #     """使用OpenAI Whisper轉錄"""
    #     return await self.whisper_service.transcribe_audio_file_async(file_path)
    
    # async def _transcribe_with_deepgram(self, file_path: str) -> Dict[str, Any]:
    #     """使用Deepgram轉錄"""
    #     # Deepgram SDK/API 可能需要 bytes，或處理檔案路徑
    #     async with aiofiles.open(file_path, 'rb') as afp:
    #         audio_data = await afp.read()
    #     # 假設 Deepgram 服務的 transcribe 方法接受 audio_data 和 mime_type
    #     # mime_type 需要根據 file_path 的擴展名判斷，或作為參數傳入
    #     # 簡化示例，假設為 'audio/wav'
    #     return await self.deepgram_service.transcribe_audio_data(audio_data, mime_type="audio/wav") 
    
    # async def _transcribe_with_local_whisper(self, file_path: str) -> Dict[str, Any]:
    #     """使用本地Whisper轉錄"""
    #     return await self.local_whisper_service.transcribe_audio_file_async(file_path)
    
    # async def _transcribe_with_gemini_audio(self, file_path: str) -> Dict[str, Any]:
    #     """使用Gemini Audio轉錄"""
    #     return await self.gemini_audio_service.transcribe_audio_file_async(file_path)
    
    # get_service_status 方法已更名為 check_service_health_async 並移至上方