# -*- coding: utf-8 -*-
"""
異步本地 Whisper 語音識別服務模組。

此模組提供了 `AsyncLocalWhisperService` 類別，用於在本地環境中異步執行
基於 `faster-whisper` 函式庫的語音轉文字任務。它允許在一個單獨的線程池中
執行計算密集型的 Whisper 模型轉錄，以避免阻塞主異步事件循環。

主要功能：
-   延遲載入 `faster-whisper` 模型，僅在首次需要時載入。
-   使用線程池 (`concurrent.futures.ThreadPoolExecutor`) 執行同步的轉錄操作。
-   提供異步的 `transcribe` 方法供應用程式其他部分調用。
-   提供服務健康狀態檢查功能。
"""

import logging
import asyncio # 用於異步操作和事件循環
from typing import Dict, Any, Optional, List # 用於類型註解
from pathlib import Path # Path 未在此檔案直接使用，但其概念與檔案路徑相關
import concurrent.futures # 用於創建線程池以執行同步操作

from config import AppConfig # 導入應用程式組態

logger = logging.getLogger(__name__)


class AsyncLocalWhisperService:
    """
    異步本地 Whisper 語音識別服務類別。

    透過 `faster-whisper` 函式庫在本地執行語音轉文字。
    轉錄操作在一個線程池中異步執行。
    """
    
    def __init__(self, config: AppConfig):
        """
        初始化 AsyncLocalWhisperService。

        Args:
            config (AppConfig): 應用程式的組態設定物件。
                                需要包含本地 Whisper 相關的設定，例如：
                                `LOCAL_WHISPER_MODEL_SIZE`, `LOCAL_WHISPER_LANGUAGE`, 
                                `LOCAL_WHISPER_TASK`, `LOCAL_WHISPER_DEVICE`。
        """
        self.config = config
        # 從組態中獲取 Whisper 模型名稱/大小 (例如 "base", "small", "medium")
        self.model_name: str = config.LOCAL_WHISPER_MODEL_SIZE 
        # 目標語言，"auto" 表示自動偵測，或指定語言代碼 (例如 "zh", "en")
        self.language: Optional[str] = config.LOCAL_WHISPER_LANGUAGE if config.LOCAL_WHISPER_LANGUAGE != "auto" else None
        self.task: str = config.LOCAL_WHISPER_TASK # "transcribe" (轉錄) 或 "translate" (翻譯至英文)
        self.device: str = config.LOCAL_WHISPER_DEVICE # "cpu", "cuda", 或 "auto"
        self.model = None # Whisper 模型實例將延遲載入
        # 創建一個線程池執行器，用於執行同步的 Whisper 模型操作
        # max_workers 可以根據伺服器核心數和預期負載進行調整
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=getattr(config, "LOCAL_WHISPER_MAX_WORKERS", 2))
        
        logger.info(f"本地 Whisper 服務已初始化。模型: {self.model_name}, 語言: {self.language or '自動偵測'}, 任務: {self.task}, 設備: {self.device}。模型將在首次使用時載入。")
    
    def _load_model(self) -> None:
        """
        (同步執行) 載入 `faster-whisper` 模型。

        此方法為同步操作，應在線程池中執行。
        如果模型尚未載入，則會進行初始化。

        Raises:
            ImportError: 如果 `faster-whisper` 函式庫未安裝。
            Exception: 如果模型載入過程中發生其他錯誤。
        """
        if self.model is None: # 僅在模型未載入時執行
            try:
                from faster_whisper import WhisperModel # 延遲導入
                logger.info(f"準備載入本地 Whisper 模型: {self.model_name} (設備: {self.device})。此過程可能需要一些時間...")
                
                # 根據設備選擇計算類型，CUDA 可用 float16 以加速，CPU 通常用 int8
                compute_type = "float16" if "cuda" in self.device.lower() else "int8"
                logger.debug(f"Whisper 模型計算類型設定為: {compute_type}")

                self.model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=compute_type
                    # 可以考慮添加其他參數，例如 num_workers (如果模型支援且有益於效能)
                )
                logger.info(f"本地 Whisper 模型 '{self.model_name}' 載入成功。")
            except ImportError:
                logger.critical("套件 'faster-whisper' 未安裝。本地 Whisper 服務無法運作。請執行 'pip install faster-whisper'。")
                raise ImportError("本地 Whisper 服務需要 'faster-whisper' 套件。請安裝後重試。")
            except Exception as e:
                logger.error(f"載入本地 Whisper 模型 '{self.model_name}' 時發生錯誤: {str(e)}", exc_info=True)
                raise # 重新拋出例外，以便上層捕獲
    
    def _transcribe_sync(self, file_path: str) -> Dict[str, Any]:
        """
        (同步執行) 使用已載入的 Whisper 模型轉錄音訊檔案。

        此方法為同步操作，應在線程池中執行。

        Args:
            file_path (str): 要轉錄的音訊檔案的本地路徑。

        Returns:
            Dict[str, Any]: 包含轉錄結果的字典，結構如下：
                            {
                                'transcript': '完整文字稿',
                                'language': '偵測到的語言代碼',
                                'language_probability': 語言偵測的信心度,
                                'duration': 音訊時長 (秒),
                                'segments': [{'start': 開始時間, 'end': 結束時間, 'text': 片段文字}, ...],
                                'provider': 'local_whisper',
                                'model_used': '使用的模型名稱'
                            }

        Raises:
            Exception: 如果轉錄過程中發生錯誤或結果為空。
        """
        try:
            self._load_model() # 確保模型已載入
            if self.model is None: # 再次檢查，以防 _load_model 內部邏輯問題
                 logger.error("本地 Whisper 模型未能成功載入，無法執行轉錄。")
                 raise RuntimeError("本地 Whisper 模型未初始化。")

            logger.info(f"本地 Whisper 開始轉錄檔案: {file_path} (語言: {self.language or '自動'}, 任務: {self.task})")
            
            # 使用 faster-whisper 進行轉錄
            # 參數可以根據需求調整，例如 beam_size, temperature 等
            # 參考: https://github.com/guillaumekln/faster-whisper#usage
            segments_iterable, info = self.model.transcribe(
                audio=file_path,
                language=self.language, # 如果是 None，faster-whisper 會自動偵測
                task=self.task,
                beam_size=5,            # 控制搜索束的大小，影響準確性和速度
                best_of=5,              # (如果 beam_size > 1) 控制候選序列數量
                temperature=0.0,        # 溫度設為 0 以獲得更具確定性的輸出
                # word_timestamps=True, # 如果需要詞級別時間戳，設為 True (會增加處理時間)
                # condition_on_previous_text=True, # 利用前文提高一致性
            )
            
            logger.debug(f"Whisper 模型偵測到的語言: {info.language} (信心度: {info.language_probability:.2f}), 音訊時長: {info.duration:.2f}s")
            
            transcript_parts: List[str] = [] # 用於收集所有文字片段
            processed_segments: List[Dict[str, Any]] = [] # 用於收集包含時間戳的片段資訊
            
            # 迭代處理 segments (segments_iterable 是一個生成器)
            for segment in segments_iterable:
                transcript_parts.append(segment.text)
                processed_segments.append({
                    'start': round(segment.start, 3), # 保留3位小數
                    'end': round(segment.end, 3),
                    'text': segment.text.strip()
                })
            
            full_transcript = ' '.join(transcript_parts).strip() # 合併所有文字片段並去除頭尾空白
            
            if not full_transcript:
                logger.warning(f"本地 Whisper 轉錄結果為空 (檔案: {file_path})。可能是無語音內容或無法識別。")
                # 即使結果為空，也返回一個包含元數據的有效結構，讓呼叫者判斷
                # raise Exception("轉錄結果為空。") 

            logger.info(f"本地 Whisper 轉錄成功完成 (檔案: {file_path})。文字稿長度: {len(full_transcript)} 字元。")
            return {
                'transcript': full_transcript,
                'language_detected': info.language, # 偵測到的語言
                'language_probability': round(info.language_probability, 4), # 語言偵測信心度
                'duration_seconds': round(info.duration, 3), # 音訊總時長
                'segments': processed_segments, # 包含時間戳的片段列表
                'provider': 'local_whisper (faster-whisper)',
                'model_used': self.model_name # 使用的模型名稱/大小
            }
            
        except Exception as e: # 捕獲所有可能的轉錄錯誤
            logger.error(f"本地 Whisper 同步轉錄過程中發生錯誤 (檔案: {file_path}): {str(e)}", exc_info=True)
            raise # 重新拋出，讓異步方法捕獲並處理
    
    async def transcribe_audio_file_async(self, file_path: str) -> Dict[str, Any]: # 方法名與其他服務統一
        """
        異步轉錄指定的音訊檔案。

        此方法將同步的 `_transcribe_sync` 方法提交到線程池中執行，
        從而實現非阻塞的異步操作。

        Args:
            file_path (str): 要轉錄的音訊檔案的本地路徑。
            
        Returns:
            Dict[str, Any]: 包含轉錄結果的字典。詳見 `_transcribe_sync` 的回傳說明。
        
        Raises:
            Exception: 如果轉錄過程中發生任何錯誤。
        """
        logger.info(f"接收到異步本地 Whisper 轉錄請求，檔案: {file_path}")
        try:
            loop = asyncio.get_event_loop() # 獲取當前事件循環
            # 在線程池中異步執行同步的轉錄方法
            result = await loop.run_in_executor(
                self._executor,      # 使用類別實例的線程池
                self._transcribe_sync, # 要執行的同步函數
                file_path            # 傳遞給同步函數的參數
            )
            logger.info(f"異步本地 Whisper 轉錄任務完成，檔案: {file_path}")
            return result
            
        except Exception as e: # 捕獲在 run_in_executor 中可能發生的錯誤或 _transcribe_sync 拋出的錯誤
            logger.error(f"異步本地 Whisper 轉錄過程中發生錯誤 (檔案: {file_path}): {str(e)}", exc_info=True)
            # 根據錯誤處理策略，可以返回一個錯誤結構或重新拋出
            raise # 重新拋出，讓 API 層或其他呼叫者處理
    
    async def check_service_health_async(self) -> Dict[str, Any]: # 方法名與其他服務統一
        """
        檢查本地 Whisper 服務的健康狀態。

        主要透過嘗試載入模型來判斷服務是否配置正確且可用。

        Returns:
            Dict[str, Any]: 包含服務健康狀態的字典。
        """
        logger.info("開始檢查本地 Whisper 服務健康狀態...")
        try:
            # 嘗試在線程池中執行模型載入 (如果尚未載入)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self._executor, self._load_model)
            
            # 如果模型載入成功 (或已載入)，則認為服務可用
            if self.model is not None:
                logger.info("本地 Whisper 服務健康狀態良好，模型已成功載入或先前已載入。")
                return {
                    "available": True,
                    "status_message": "服務運作正常，模型已載入。",
                    "model_configured": self.model_name,
                    "language_configured": self.language or "自動偵測",
                    "device_configured": self.device,
                    "provider": "local_whisper (faster-whisper)"
                }
            else: # 理論上 _load_model 失敗會拋錯，但多一層防護
                logger.warning("本地 Whisper 健康檢查：模型未能載入，但 _load_model 未拋出例外。")
                return {"available": False, "status_message": "模型未能載入。", "provider": "local_whisper"}
            
        except Exception as e: # 捕獲模型載入等過程中可能發生的錯誤
            logger.error(f"本地 Whisper 服務健康檢查失敗: {str(e)}", exc_info=True)
            return {
                "available": False,
                "status_message": f"服務檢查失敗: {type(e).__name__} - {str(e)}",
                "provider": "local_whisper"
            }
    
    def __del__(self):
        """
        物件銷毀時的清理操作。

        確保線程池被正確關閉，釋放資源。
        """
        if hasattr(self, '_executor') and self._executor:
            logger.info("正在關閉本地 Whisper 服務的線程池執行器...")
            self._executor.shutdown(wait=True) # wait=True 確保所有待處理任務完成後再關閉
            logger.info("本地 Whisper 服務的線程池執行器已關閉。")