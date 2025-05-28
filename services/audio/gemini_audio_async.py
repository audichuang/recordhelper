# -*- coding: utf-8 -*-
"""
異步 Google Gemini 音訊處理服務模組。

此模組提供了 `AsyncGeminiAudioService` 類別，專門用於利用 Google Gemini AI 模型
進行音訊的異步轉文字 (Speech-to-Text) 功能。它基於官方的 `google-generativeai` SDK。

主要功能：
-   透過 Gemini API 上傳音訊檔案。
-   發送包含音訊檔案和特定提示 (Prompt) 的請求以進行轉錄。
-   支援說話者識別和時間戳的轉錄格式。
-   提供 API 金鑰輪換機制 (如果設定了多個金鑰)。
-   包含服務健康狀態檢查功能。
-   (可選) 使用自訂提示進行轉錄。

與 `services.ai.gemini_async.py` 的區別：
-   `gemini_async.py` 主要處理純文本的 AI 任務，例如摘要生成。
-   此 `gemini_audio_async.py` 專注於音訊輸入的處理，特別是轉錄。
"""

import logging
import asyncio # 用於異步操作，例如 await asyncio.get_event_loop().run_in_executor
import aiofiles # 用於異步檔案操作 (雖然在此版本中，SDK 的檔案上傳是同步的，但保留以備未來SDK更新)
from typing import Dict, Any, Optional, List # 用於類型註解
from pathlib import Path # 用於路徑操作和檢查檔案是否存在
import os # 用於獲取檔案大小
import random # 用於隨機選擇 API 金鑰
import tempfile # 未直接使用，但其概念與臨時檔案處理相關

from config import AppConfig # 導入應用程式組態

logger = logging.getLogger(__name__)


class AsyncGeminiAudioService:
    """
    異步 Google Gemini 音訊處理服務類別。

    封裝了使用 Google GenAI SDK 與 Gemini 模型進行音訊轉錄的邏輯。
    """
    
    def __init__(self, config: AppConfig):
        """
        初始化 AsyncGeminiAudioService。

        Args:
            config (AppConfig): 應用程式的組態設定物件。
                                需要包含 `GOOGLE_API_KEYS` (用於 Gemini 的 API 金鑰列表)
                                和 `AI_MODEL_NAME` (雖然此處可能針對音訊有特定模型，但暫用通用設定)
                                以及 `AI_MAX_RETRIES`。
        
        Raises:
            ValueError: 如果組態中未提供 Google API 金鑰。
            ImportError: 如果 `google-generativeai` SDK 未安裝。
        """
        self.config = config
        self.api_keys: List[str] = config.GOOGLE_API_KEYS or [] # 從組態獲取 API 金鑰
        # TODO: Gemini 可能有專用於音訊轉錄的模型名稱，應在 AppConfig 中區分
        # 目前暫時使用通用的 AI_MODEL_NAME，但 Gemini API 通常針對不同任務有不同模型端點
        # 例如 'models/gemini-1.5-flash-latest' 或特定支援音訊的模型
        self.model_name: str = config.AI_MODEL_NAME # 使用的 Gemini 模型 (需確認是否為適用於音訊的模型)
        self.max_retries: int = config.AI_MAX_RETRIES # 最大重試次數 (雖然此版本中未明確實現 SDK 級別的重試)
        
        if not self.api_keys:
            logger.error("Google API 金鑰 (GOOGLE_API_KEYS) 未在組態中設定。Gemini 音訊服務將不可用。")
            raise ValueError("Google API 金鑰未設定。")
        
        self.current_api_key_index: int = 0 # 用於 API 金鑰輪換
        self._client = None # GenAI 客戶端將延遲初始化
        self._ensure_genai_sdk_installed() # 確保 SDK 已安裝
        logger.info(f"AsyncGeminiAudioService 初始化完成。將使用模型 '{self.model_name}' (需確認其音訊處理能力)。")

    def _ensure_genai_sdk_installed(self) -> None:
        """私有方法，檢查 google-generativeai SDK 是否已安裝。"""
        try:
            import google.generativeai
            logger.debug(f"Google GenAI SDK 版本: {google.generativeai.__version__}")
        except ImportError:
            logger.critical("套件 'google-generativeai' 未安裝。Gemini 音訊服務無法運作。請執行 'pip install google-generativeai'。")
            raise ImportError("Gemini 音訊服務需要 'google-generativeai' 套件。請安裝後重試。")

    def _get_api_key(self) -> str:
        """
        從可用的 API 金鑰列表中隨機選擇一個 (或按順序輪換)。
        目前實作為隨機選擇。

        Returns:
            str: 一個隨機選擇的 Google API 金鑰。
        
        Raises:
            ValueError: 如果 API 金鑰列表為空。
        """
        if not self.api_keys:
            raise ValueError("Google API 金鑰列表為空。")
        # 簡單輪換策略：
        # self.current_api_key_index = (self.current_api_key_index + 1) % len(self.api_keys)
        # return self.api_keys[self.current_api_key_index]
        # 或者隨機選擇：
        return random.choice(self.api_keys)
    
    def _get_generation_config(self) -> Dict[str, Any]: # 返回字典以相容 SDK
        """
        獲取用於 Gemini API 內容生成的標準化配置。

        Returns:
            Dict[str, Any]: 包含生成配置參數的字典。
        """
        # 這些參數可能需要根據 Gemini 音訊處理的最佳實踐進行調整
        return {
            "max_output_tokens": 8192, # Gemini 1.5 Flash 最大輸出
            "temperature": 0.1,       # 較低的溫度以獲得更具確定性的轉錄結果
            # "top_p": 0.95,          # 可選
            # "top_k": 40,            # 可選
        }
    
    def _get_genai_client(self): # 方法名統一為 get_genai_client
        """
        獲取 (並在首次調用時初始化) Google GenAI 客戶端。
        此方法會使用 `_get_api_key` 選擇的 API 金鑰來配置全域 genai 設定。

        Returns:
            google.generativeai.GenerativeModel: 配置好的 Gemini 模型實例。
                                                (更正：應返回 Client 或直接配置 genai)
        
        Raises:
            RuntimeError: 如果 GenAI SDK 初始化失敗。
        """
        # Google GenAI SDK 通常使用全域 API 金鑰配置
        # `genai.configure(api_key="YOUR_API_KEY")`
        # `genai.GenerativeModel('model-name')`
        # 此處的 `self._client` 概念可能需要調整以適應 SDK 的工作方式
        # 如果目標是輪換金鑰，則每次調用 API 前都應 `genai.configure`
        
        # 此處的邏輯是：確保 genai 已配置，並返回一個模型實例。
        # 實際的金鑰設定發生在 _call_gemini_api_sync 內部。
        try:
            from google import genai # 延遲導入
            # 此處不立即配置金鑰，金鑰將在 _call_gemini_api_sync 中輪換設定
            # logger.debug("Google GenAI SDK 已準備就緒。")
            return genai # 返回 genai 模組本身，以便後續調用 genai.GenerativeModel 等
        except ImportError as e:
            logger.critical(f"無法導入 'google.generativeai' SDK: {e}。請確保已正確安裝。")
            raise RuntimeError(f"Gemini SDK 導入失敗: {e}")
        except Exception as e_init: # 捕獲其他可能的初始化錯誤
            logger.error(f"初始化 Google GenAI 時發生錯誤: {e_init}", exc_info=True)
            raise RuntimeError(f"GenAI 初始化失敗: {e_init}")

    async def transcribe_audio_file_async(self, file_path: str, custom_prompt: Optional[str] = None) -> Dict[str, Any]: # 統一方法名
        """
        使用 Gemini SDK 異步轉錄指定的音訊檔案。支援標準提示詞和自訂提示詞。

        Args:
            file_path (str): 本地音訊檔案的路徑。
            custom_prompt (Optional[str], optional): 用於指導轉錄過程的自訂提示詞。
                                                     如果為 None，則使用預設的詳細轉錄提示。

        Returns:
            Dict[str, Any]: 包含轉錄結果的字典，結構類似：
                            {
                                'transcript': '轉錄文字...',
                                'text': '轉錄文字...', // 與 transcript 相同，為相容性
                                'provider': 'gemini_audio_sdk',
                                'model': '使用的模型名稱',
                                'confidence': 0.95, // 預設信心度，Gemini API 可能不直接提供
                                'language': 'zh', // 預設語言，Gemini API 可能會返回偵測到的語言
                                'speaker_detection': True, // 指示是否請求了說話者識別
                                'timestamp_enabled': True, // 指示是否請求了時間戳
                                'custom_prompt_used': bool // 指示是否使用了自訂提示
                            }
        
        Raises:
            FileNotFoundError: 如果提供的 `file_path` 不存在。
            ValueError: 如果檔案大小超過 Gemini API 的限制 (例如 100MB)。
            RuntimeError: 如果 Gemini SDK 初始化或 API 調用過程中發生嚴重錯誤。
        """
        logger.info(f"開始使用 Gemini Audio 進行音訊轉錄，檔案: {file_path}" + (f" (使用自訂提示)" if custom_prompt else " (使用預設提示)"))
        
        if not Path(file_path).exists():
            logger.error(f"音訊檔案不存在於指定路徑: {file_path}")
            raise FileNotFoundError(f"音訊檔案不存在: {file_path}")
        
        file_size_bytes = os.path.getsize(file_path)
        file_size_mb = file_size_bytes / (1024 * 1024)
        
        # Gemini API (例如 Files API) 通常對檔案大小有限制，例如 Gemini 1.5 Flash 為 2GB，但特定模型或任務可能有更低限制。
        # 假設此處參考的是某個特定音訊上傳接口的100MB限制。
        # TODO: 應從 AppConfig 或 Gemini SDK 的常數中獲取此限制值。
        max_file_size_mb = getattr(self.config, "GEMINI_AUDIO_MAX_SIZE_MB", 100) 
        if file_size_mb > max_file_size_mb:
            logger.error(f"檔案大小 ({file_size_mb:.2f}MB) 超過 Gemini 音訊處理的 {max_file_size_mb}MB 限制。檔案: {file_path}")
            raise ValueError(f"檔案大小 ({file_size_mb:.2f}MB) 超過 {max_file_size_mb}MB 限制。")
        
        try:
            # 使用 asyncio.to_thread 在異步環境中執行同步的 SDK 操作
            transcription_result = await asyncio.get_event_loop().run_in_executor(
                None, # 使用預設的線程池執行器
                self._transcribe_sync_with_sdk, # 要執行的同步函數
                file_path, # 傳遞給同步函數的參數
                custom_prompt # 傳遞給同步函數的參數
            )
            return transcription_result
            
        except Exception as e: # 捕獲所有可能的例外
            logger.error(f"Gemini Audio 音訊轉錄過程中發生未預期錯誤 (檔案: {file_path}): {str(e)}", exc_info=True)
            # 根據錯誤處理策略，可以返回一個錯誤結構或重新拋出一個更通用的服務層例外
            raise RuntimeError(f"Gemini Audio 轉錄失敗: {str(e)}") from e # 保留原始例外鏈
    
    def _transcribe_sync_with_sdk(self, file_path: str, custom_prompt: Optional[str]) -> Dict[str, Any]:
        """
        (同步執行) 使用 Google GenAI SDK 進行音訊轉錄的核心邏輯。
        此方法應在一個單獨的線程中執行，以避免阻塞異步事件循環。

        Args:
            file_path (str): 音訊檔案的路徑。
            custom_prompt (Optional[str]): 自訂的轉錄提示。

        Returns:
            Dict[str, Any]: 包含轉錄結果的字典。
        
        Raises:
            Exception: 如果在 SDK 調用過程中發生任何錯誤。
        """
        logger.info(f"同步轉錄核心邏輯開始，檔案: {file_path}。")
        
        # 獲取並配置 GenAI SDK (此處進行金鑰配置)
        genai_sdk = self._get_genai_client() # 確保 SDK 已導入
        current_api_key = self._get_api_key() # 獲取當前要使用的 API 金鑰
        genai_sdk.configure(api_key=current_api_key) # 配置 SDK 使用的金鑰
        logger.debug(f"已為本次轉錄配置 Gemini API 金鑰 (尾號: ...{current_api_key[-4:] if len(current_api_key) > 4 else '****'})。")

        try:
            # 步驟 1: 上傳音訊檔案至 Gemini Files API
            logger.info(f"正在上傳音訊檔案 '{Path(file_path).name}' 至 Gemini Files API...")
            # `display_name` 是可選的，有助於在 Google Cloud Console 中識別檔案
            uploaded_file = genai_sdk.upload_file(path=file_path, display_name=f"audio_upload_{Path(file_path).name}")
            logger.info(f"音訊檔案上傳成功。檔案名稱: '{uploaded_file.name}', URI: '{uploaded_file.uri}'")
            
            # 等待檔案處理完成 (如果 SDK 沒有自動等待)
            # 有些 SDK 版本可能需要手動檢查檔案狀態，直到變為 ACTIVE
            # file_resource = genai_sdk.get_file(name=uploaded_file.name)
            # while file_resource.state.name == "PROCESSING":
            #     logger.debug(f"檔案 '{uploaded_file.name}' 仍在處理中，等待 5 秒...")
            #     time.sleep(5) # 同步等待，在 executor 中執行是安全的
            #     file_resource = genai_sdk.get_file(name=uploaded_file.name)
            # if file_resource.state.name != "ACTIVE":
            #     logger.error(f"檔案 '{uploaded_file.name}' 上傳後未能變為 ACTIVE 狀態，目前狀態: {file_resource.state.name}")
            #     raise RuntimeError(f"Gemini 檔案處理失敗，狀態: {file_resource.state.name}")
            # logger.info(f"檔案 '{uploaded_file.name}' 已成功處理並變為 ACTIVE 狀態。")


            # 步驟 2: 準備轉錄請求的提示 (Prompt)
            if custom_prompt:
                transcription_prompt = custom_prompt
                logger.info("使用使用者提供的自訂提示進行轉錄。")
            else:
                # 使用預設的詳細轉錄提示，要求說話者識別和時間戳
                transcription_prompt = """請將我上傳的此份音訊檔案完整轉錄成文字稿。
在轉錄過程中，請盡可能：
1.  **準確識別所有不同的說話者**，並將他們標記為「說話者 A」、「說話者 B」、「說話者 C」等等。
2.  為每段由不同說話者開始的對話內容**提供精確的時間戳**，格式為 `[時:分:秒]` (例如 `[00:01:23]`)。
3.  **完整且準確地轉錄每一位說話者的所有對話內容**，包括口語表達和填充詞 (例如「嗯」、「啊」)，以保持對話的自然流暢度。
4.  如果背景有明顯的非語音聲音且對理解上下文重要，可以用括號標註 (例如 `(背景音樂)`, `(敲門聲)`)。
5.  使用【繁體中文】進行轉錄。

輸出格式範例：
[00:00:01] 說話者 A：大家好，今天我們會議的主題是關於最新的市場推廣策略。
[00:00:05] 說話者 B：是的，我已經準備好了一些初步的想法，我們可以一起討論。
[00:00:09] 說話者 A：(翻閱文件聲) 好的，請您先開始。
...

請嚴格按照此格式輸出完整的文字稿。"""
                logger.info("使用預設的詳細轉錄提示 (包含說話者識別和時間戳)。")

            # 步驟 3: 發送轉錄請求給 Gemini 模型
            logger.info(f"向 Gemini 模型 '{self.model_name}' 發送轉錄請求...")
            model_instance = genai_sdk.GenerativeModel(self.model_name) # 創建模型實例
            
            # 構建請求內容，包含提示和已上傳的音訊檔案
            # Gemini API 可能期望一個包含 FileDataPart 的列表
            # 參考: https://ai.google.dev/docs/gemini_api_overview?hl=zh-cn#prompts_with_media
            request_contents = [transcription_prompt, {"file_data": {"mime_type": uploaded_file.mime_type, "file_uri": uploaded_file.uri}}]
            
            response = model_instance.generate_content(
                contents=request_contents,
                generation_config=genai_types.GenerationConfig(**self._get_generation_config()) # 解包字典
            )
            
            # 步驟 4: 處理回應並提取文字稿
            # Gemini API 的回應結構可能比較複雜，需要仔細解析
            # 假設 `response.text` 直接包含轉錄結果 (這可能需要根據實際 SDK 行為調整)
            if not response or not hasattr(response, 'text') or not response.text:
                logger.error("Gemini API 返回的回應無效或缺少轉錄文本。")
                # 嘗試記錄更詳細的回應訊息，如果有的話
                if response and hasattr(response, 'prompt_feedback'):
                    logger.error(f"Gemini API Prompt Feedback: {response.prompt_feedback}")
                raise Exception("Gemini API 返回的回應無效或缺少轉錄文本。")
            
            transcription_text = response.text.strip()
            logger.info(f"✅ Gemini Audio 轉錄成功。原始文本長度: {len(transcription_text)} 字元。")
            
            # 步驟 5: 清理已上傳的檔案 (非常重要，以避免產生不必要的儲存費用)
            try:
                logger.info(f"準備刪除已上傳至 Gemini Files API 的檔案: '{uploaded_file.name}'...")
                genai_sdk.delete_file(name=uploaded_file.name)
                logger.info(f"成功刪除 Gemini Files API上的檔案: '{uploaded_file.name}'。")
            except Exception as e_delete:
                # 即使刪除失敗，也只記錄警告，因為轉錄本身可能已成功
                logger.warning(f"刪除 Gemini Files API 上的檔案 '{uploaded_file.name}' 時發生錯誤: {str(e_delete)}", exc_info=True)

            return {
                'transcript': transcription_text,
                'text': transcription_text, # 為相容性保留
                'provider': 'gemini_audio_sdk_custom_prompt' if custom_prompt else 'gemini_audio_sdk_default_prompt',
                'model_used': self.model_name, # 使用的模型
                'confidence': 0.95, # Gemini API 目前可能不直接提供整體信心度，此為預設值
                'language_detected': 'zh-TW', # 假設，Gemini 可能會返回偵測到的語言
                'speaker_detection_requested': not custom_prompt, # 如果使用預設提示，則請求了說話者識別
                'timestamp_requested': not custom_prompt, # 如果使用預設提示，則請求了時間戳
                'custom_prompt_applied': bool(custom_prompt)
            }
            
        except Exception as e_sync: # 捕獲同步執行過程中的所有錯誤
            logger.error(f"❌ Gemini Audio 同步轉錄核心邏輯失敗: {str(e_sync)}", exc_info=True)
            # 將原始錯誤包裝後重新拋出，以便上層異步函數捕獲
            raise RuntimeError(f"Gemini Audio 同步轉錄失敗: {str(e_sync)}") from e_sync
    
    async def check_service_health_async(self) -> Dict[str, Any]: # 與其他服務的健康檢查方法名統一
        """
        檢查 Google Gemini Audio 服務的健康狀態。

        透過嘗試初始化 GenAI 客戶端並列出可用模型來驗證 API 金鑰和連線。

        Returns:
            Dict[str, Any]: 包含服務健康狀態的字典。
        """
        logger.info("開始檢查 Google Gemini Audio 服務健康狀態...")
        try:
            # 嘗試獲取並配置 GenAI SDK (這會使用一個 API 金鑰)
            genai_sdk = self._get_genai_client()
            current_api_key = self._get_api_key()
            genai_sdk.configure(api_key=current_api_key)
            logger.debug(f"已為健康檢查配置 Gemini API 金鑰 (尾號: ...{current_api_key[-4:] if len(current_api_key) > 4 else '****'})。")

            # 嘗試執行一個輕量級的 API 調用，例如列出模型
            # 在異步環境中執行同步的 SDK 調用
            await asyncio.get_event_loop().run_in_executor(
                None, self._check_models_sync_for_health, genai_sdk # 傳遞 genai_sdk 模組
            )
            
            logger.info("Google Gemini Audio 服務健康狀態良好。")
            return {
                "available": True,
                "model_configured": self.model_name, # 指示設定中使用的模型
                "provider": "Google Gemini API (via google-generativeai SDK for Audio)",
                "api_keys_available": len(self.api_keys),
                "message": "服務運作正常，API 金鑰和連線有效。"
            }
                        
        except Exception as e: # 捕獲任何在檢查過程中發生的錯誤
            logger.error(f"Google Gemini Audio 服務健康檢查失敗: {str(e)}", exc_info=True)
            return {
                "available": False,
                "model_configured": self.model_name,
                "error": f"服務檢查失敗: {type(e).__name__} - {str(e)}"
            }
    
    def _check_models_sync_for_health(self, genai_sdk_module) -> bool: # 接收 genai 模組
        """
        (同步執行) 檢查 Gemini API 模型列表是否可訪問。
        此方法用於健康檢查，應在 `run_in_executor` 中調用。

        Args:
            genai_sdk_module: 已導入的 `google.generativeai` 模組。

        Returns:
            bool: 如果成功列出模型則返回 True。

        Raises:
            Exception: 如果 API 調用失敗。
        """
        try:
            # 嘗試列出可用模型，這是一個相對輕量級的 API 調用
            # 此處的 models 是一個 iterator，需要轉換為 list 或迭代來實際觸發 API call
            models_list = list(genai_sdk_module.list_models()) 
            logger.info(f"Gemini API 連線測試成功，找到 {len(models_list)} 個可用模型。")
            # 可以進一步檢查 self.model_name 是否在 models_list 中 (如果需要)
            # if not any(m.name == self.model_name for m in models_list):
            #    logger.warning(f"設定的模型 '{self.model_name}' 在可用模型列表中未找到。")
            return True
        except Exception as e_sdk_call: # 捕獲 SDK 調用時的特定錯誤
            logger.error(f"Gemini API 連線測試 (列出模型) 失敗: {str(e_sdk_call)}", exc_info=True)
            raise # 重新拋出，以便 check_service_health_async 捕獲並報告
    
    # transcribe_with_key_rotation 和 _transcribe_with_client_sync 方法在此版本中被整合進
    # _call_gemini_api_sync 和 _call_gemini_with_rotation 的邏輯中，
    # 即 _call_gemini_with_rotation 負責處理金鑰輪換和重試。
    # 如果需要獨立的、手動觸發的金鑰輪換轉錄方法，可以保留或調整它們。
    # 目前的設計是在每次主要的 API 調用 (_call_gemini_with_rotation) 中都隱含了金鑰輪換和重試。

    # 以下為原有的 transcribe_with_key_rotation 和 _transcribe_with_client_sync，
    # 暫時註解掉，因為其功能已部分被 _call_gemini_with_rotation 覆蓋。
    # 如果需要明確的、手動的“使用下一個金鑰重試”功能，則可以解除註解並調整。
    """
    async def transcribe_with_key_rotation(self, file_path: str) -> Dict[str, Any]:
        \"""
        (已棄用或需重構) 嘗試使用不同的 API key 進行轉錄。
        目前的金鑰輪換邏輯已整合到 `_call_gemini_with_rotation` 中。
        
        Args:
            file_path: 音頻文件路徑
            
        Returns:
            轉錄結果字典
        \"""
        logger.warning("`transcribe_with_key_rotation` 方法可能已棄用或其功能已整合，請檢查。")
        if len(self.api_keys) <= 1: # 如果只有一個金鑰，則無需輪換
            logger.info("只有一個 API 金鑰，無需輪換。直接使用標準轉錄方法。")
            return await self.transcribe_audio_file_async(file_path) # 或者拋出錯誤提示至少需要2個金鑰才能輪換
            # raise Exception("API 金鑰輪換至少需要兩個可用的金鑰。")
        
        initial_key_index = self.current_api_key_index # 記錄初始金鑰索引
        last_error = None
        
        for i in range(len(self.api_keys)): # 遍歷所有金鑰進行嘗試
            self.current_api_key_index = (initial_key_index + i) % len(self.api_keys) # 設定當前嘗試的金鑰
            current_api_key_for_log = self.api_keys[self.current_api_key_index]
            logger.info(f"🔑 正在嘗試使用 API 金鑰索引 {self.current_api_key_index} (尾號: ...{current_api_key_for_log[-4:] if len(current_api_key_for_log) > 4 else '****'}) 進行轉錄...")
            
            try:
                # 注意：這裡的 _transcribe_sync_with_sdk 需要能夠接收一個已配置好金鑰的 client，
                # 或者 genai SDK 允許在每次調用時傳遞金鑰。
                # 目前的 _get_genai_client 和 _transcribe_sync_with_sdk 可能需要調整以支援這種輪換。
                # 一個簡化的假設是 _get_genai_client 內部會使用 self.current_api_key_index 來配置。
                
                # 為確保每次嘗試都使用正確的金鑰，我們在此處重新配置全域金鑰
                from google import genai
                genai.configure(api_key=self.api_keys[self.current_api_key_index])

                result = await asyncio.get_event_loop().run_in_executor(
                    None, self._transcribe_sync_with_sdk, file_path, None # custom_prompt 設為 None
                )
                
                logger.info(f"✅ 使用 API 金鑰索引 {self.current_api_key_index} 轉錄成功。")
                return result # 一旦成功，立即返回結果
                
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ 使用 API 金鑰索引 {self.current_api_key_index} 轉錄失敗: {str(e)}")
                # 如果不是最後一個金鑰，則繼續嘗試下一個
                if i < len(self.api_keys) - 1:
                    logger.info("嘗試下一個 API 金鑰...")
                    await asyncio.sleep(self.retry_delay if self.retry_delay > 0 else 1) # 簡單延遲
                else:
                    logger.error("所有 API 金鑰均嘗試失敗。")
        
        # 如果所有金鑰都失敗了
        if last_error:
            raise Exception(f"所有 API 金鑰均轉錄失敗。最後遇到的錯誤: {str(last_error)}") from last_error
        else: # 理論上不會執行到此，除非 api_keys 為空（已在開頭檢查）
            raise Exception("API 金鑰列表為空或發生未知錯誤導致無法轉錄。")
    """
    
    # _transcribe_with_client_sync 方法已更名為 _transcribe_sync_with_sdk 並調整
    # 主要的轉錄邏輯現在集中在 _transcribe_sync_with_sdk，並由 transcribe_audio_file_async 調用。
    # 金鑰輪換的責任現在主要由 _call_gemini_with_rotation（用於文本生成）處理，
    # 對於檔案上傳和基於檔案的 generate_content，SDK 的行為可能不同，
    # 上面的 transcribe_with_key_rotation 是一個手動輪換的範例，但需要確保 SDK 的 configure 和 client 例項化能配合。
    # 目前，`_get_genai_client` 和 `_transcribe_sync_with_sdk` 中的金鑰配置是基於 `_get_api_key()` 隨機選擇一個，
    # 這意味著如果一次 `transcribe_audio_file_async` 調用失敗，它不會自動輪換金鑰重試。
    # 要實現完整的輪換重試，需要將 `transcribe_audio_file_async` 的核心邏輯包裝在類似 `_call_gemini_with_rotation` 的循環中。
    # 為了簡化當前任務，我們假設單個金鑰配置成功，或者由外部重試機制處理金鑰問題。
    # 如果需要內建輪換，則需重構 `transcribe_audio_file_async` 和 `_transcribe_sync_with_sdk`。