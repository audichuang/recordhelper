# -*- coding: utf-8 -*-
"""
異步 Deepgram 語音識別服務模組。

此模組提供了 `AsyncDeepgramService` 類別，用於與 Deepgram 的語音轉文字 API 進行異步互動。
它支援使用多個 API 金鑰進行輪換，並處理 API 請求和回應。
"""

import logging
import aiohttp # 用於異步 HTTP 請求
import aiofiles # 用於異步檔案操作
from typing import Dict, Any, Optional, List # 用於類型註解
from pathlib import Path # Path 未在此檔案直接使用，但保留以備未來擴展
import random # 用於隨機選擇 API 金鑰

from config import AppConfig # 導入應用程式組態

logger = logging.getLogger(__name__)


class AsyncDeepgramService:
    """
    異步 Deepgram 語音識別服務類別。

    封裝了與 Deepgram API 互動的邏輯，包括：
    - 初始化設定 (API 金鑰、模型、語言等)。
    - API 金鑰的隨機輪換。
    - 異步轉錄音訊檔案。
    - 檢查 Deepgram 服務的健康狀態。
    """
    
    def __init__(self, config: AppConfig):
        """
        初始化 AsyncDeepgramService。

        Args:
            config (AppConfig): 應用程式的組態設定物件，其中應包含 Deepgram 相關的設定，
                                例如 `DEEPGRAM_API_KEYS`, `DEEPGRAM_MODEL`, `DEEPGRAM_LANGUAGE`。
        """
        self.config = config
        self.api_keys: List[str] = config.DEEPGRAM_API_KEYS or [] # 從組態獲取 API 金鑰列表，若無則為空列表
        self.model: str = config.DEEPGRAM_MODEL # 使用的 Deepgram 模型
        self.language: str = config.DEEPGRAM_LANGUAGE # 目標語言
        self.base_url: str = "https://api.deepgram.com/v1" # Deepgram API 的基礎 URL
        
        if not self.api_keys:
            logger.warning("Deepgram API 金鑰 (DEEPGRAM_API_KEYS) 未在組態中設定。服務可能無法使用。")
        else:
            logger.info(f"AsyncDeepgramService 初始化完成，使用模型: {self.model}，語言: {self.language}，共 {len(self.api_keys)} 個 API 金鑰。")

    def _get_api_key(self) -> str:
        """
        從可用的 API 金鑰列表中隨機選擇一個。

        Returns:
            str: 一個隨機選擇的 Deepgram API 金鑰。

        Raises:
            ValueError: 如果組態中未設定任何 Deepgram API 金鑰。
        """
        if not self.api_keys:
            # 此錯誤應在初始化時或更早前被捕獲，但再次檢查以確保安全
            logger.error("無法獲取 Deepgram API 金鑰：金鑰列表為空。")
            raise ValueError("Deepgram API 金鑰未設定，無法執行操作。")
        selected_key = random.choice(self.api_keys) # 從列表中隨機選取一個金鑰
        logger.debug(f"已選擇 Deepgram API 金鑰 (尾號: ...{selected_key[-4:] if len(selected_key) > 4 else '****'})。")
        return selected_key
    
    async def transcribe_audio_data(self, audio_data: bytes, mime_type: str = "audio/wav") -> Dict[str, Any]: # 修改為接收 bytes
        """
        異步轉錄提供的音訊數據。

        Args:
            audio_data (bytes): 要轉錄的原始音訊數據 (bytes)。
            mime_type (str, optional): 音訊數據的 MIME 類型。預設為 "audio/wav"。
                                       Deepgram 支援多種格式，請參考其官方文件。

        Returns:
            Dict[str, Any]: 包含轉錄結果的字典，格式如下：
                            {
                                'transcript': '轉錄後的文字',
                                'language': '使用的語言模型',
                                'confidence': 信心度分數 (0.0-1.0),
                                'words': [{'word': '詞彙', 'start': 開始時間, 'end': 結束時間, 'confidence': 詞彙信心度}, ...],
                                'provider': 'deepgram',
                                'model': '使用的模型名稱'
                            }
                            如果轉錄失敗或無結果，則可能拋出例外或返回包含錯誤訊息的字典 (取決於錯誤處理策略)。
        
        Raises:
            ValueError: 如果未設定 API 金鑰。
            aiohttp.ClientError: 如果 API 請求過程中發生網路或客戶端錯誤。
            Exception: 如果 API 返回非預期狀態碼或回應格式錯誤，或發生其他未預期錯誤。
        """
        if not self.api_keys: # 再次檢查 API 金鑰是否存在
            logger.error("Deepgram 轉錄請求失敗：API 金鑰未設定。")
            raise ValueError("Deepgram API 金鑰未設定，無法進行轉錄。")

        # 準備請求參數 (features)
        # 參考 Deepgram API 文件以獲取所有可用參數：https://developers.deepgram.com/reference/listen-file
        params = {
            'model': self.model,            # 指定模型
            'language': self.language,      # 指定語言
            'punctuate': 'true',            # 自動添加標點符號
            'utterances': 'true',           # 返回話語分段資訊 (utterances)
            'diarize': 'true',              # 啟用說話人分離 (diarization)
            'smart_format': 'true',         # 啟用智能格式化 (例如日期、數字)
            # 'numerals': 'true',           # 將數字詞轉換為數字 (如果 smart_format 不夠用)
            # 'profanity_filter': 'true',   # (可選) 不雅詞過濾
        }
        
        # 準備請求標頭
        api_key = self._get_api_key() # 獲取一個 API 金鑰
        headers = {
            'Authorization': f'Token {api_key}', # 使用 Token 授權
            'Content-Type': mime_type # 指定音訊內容的 MIME 類型
        }
        
        request_url = f"{self.base_url}/listen" # Deepgram Listen API 端點
        logger.info(f"開始向 Deepgram API ({request_url}) 發送音訊數據進行轉錄。模型: {self.model}, 語言: {self.language}, MIME: {mime_type}。")
        
        try:
            # 使用 aiohttp 異步發送 POST 請求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    request_url,
                    data=audio_data, # 直接傳遞 bytes 數據
                    headers=headers,
                    params=params, # 將 features 作為查詢參數發送
                    timeout=aiohttp.ClientTimeout(total=300)  # 設定總超時為 5 分鐘
                ) as response:
                    
                    response_status = response.status
                    response_text = await response.text() # 獲取回應內容以供日誌或錯誤處理
                    
                    if response_status != 200: # 檢查 HTTP 狀態碼
                        logger.error(f"Deepgram API 請求失敗。狀態碼: {response_status}，回應: {response_text[:500]}...") # 記錄部分回應
                        raise Exception(f"Deepgram API 錯誤 {response_status}: {response_text}")
                    
                    logger.info(f"Deepgram API 請求成功 (狀態碼: {response_status})。開始解析回應...")
                    result = json.loads(response_text) # 解析 JSON 回應
            
            # 詳細處理和驗證 Deepgram API 的回應結構
            if not result or 'results' not in result or not result['results']:
                logger.warning("Deepgram API 返回的結果中缺少 'results' 欄位或 'results' 為空。")
                raise Exception("Deepgram API 返回無效或空的結果結構。")
            
            # 通常我們關心第一個 channel 和第一個 alternative
            channels = result['results'].get('channels')
            if not channels or not isinstance(channels, list) or len(channels) == 0:
                logger.warning("Deepgram API 返回的 'channels' 欄位無效或為空。")
                raise Exception("Deepgram API 未返回有效的頻道資訊。")
            
            channel = channels[0]
            alternatives = channel.get('alternatives')
            if not alternatives or not isinstance(alternatives, list) or len(alternatives) == 0:
                logger.warning("Deepgram API 返回的 'alternatives' 欄位無效或為空。")
                raise Exception("Deepgram API 未返回任何轉錄候選項。")
            
            alternative = alternatives[0] # 取第一個 (通常是信心度最高的) 候選項
            transcript = alternative.get('transcript', '').strip() # 提取文字稿並去除頭尾空白
            
            if not transcript: # 如果文字稿為空字串
                logger.warning("Deepgram API 返回的轉錄文字稿為空。")
                # 根據業務邏輯，空文字稿可能視為一種失敗或特殊情況
                # 此處暫時作為一種可能的 "無語音" 或 "無法識別" 的情況處理
                # raise Exception("轉錄結果為空字串。") 
                # 或者返回帶有空 transcript 的結果，讓呼叫者處理

            # 格式化並返回包含詳細資訊的結果字典
            # TODO: 根據需要，可以從 result 中提取更多資訊，例如 'utterances', 'diarize' (如果啟用)
            formatted_result = {
                'transcript': transcript,
                'language_detected': result['results'].get('metadata', {}).get('language', self.language), # 嘗試獲取偵測到的語言
                'confidence': alternative.get('confidence', 0.0), # 整體信心度
                'words': alternative.get('words', []), # 每個詞的資訊 (包含時間戳、信心度)
                'utterances': result['results'].get('utterances', []), # 話語分段資訊
                'provider': 'Deepgram',
                'model_used': self.model, # 使用的模型
                'raw_response': result # 保留原始回應以供未來可能的詳細分析
            }
            logger.info(f"Deepgram 轉錄成功。文字稿長度: {len(transcript)}，信心度: {formatted_result['confidence']:.4f}")
            return formatted_result
            
        except aiohttp.ClientError as net_err: # 捕獲網路相關錯誤
            logger.error(f"Deepgram 轉錄時發生網路錯誤: {str(net_err)}", exc_info=True)
            raise # 重新拋出，讓上層處理或記錄
        except ValueError as val_err: # 捕獲前面手動拋出的 ValueError
            logger.error(f"Deepgram 轉錄時發生數值或組態錯誤: {str(val_err)}", exc_info=True)
            raise
        except Exception as e: # 捕獲所有其他未預期錯誤
            logger.error(f"Deepgram 轉錄過程中發生未預期錯誤: {str(e)}", exc_info=True)
            # 可以考慮將原始錯誤包裝後再拋出，或返回一個標準化的錯誤回應
            raise Exception(f"Deepgram 轉錄失敗：{type(e).__name__} - {str(e)}") # 重新拋出，包含錯誤類型和訊息
    
    async def check_service_health_async(self) -> Dict[str, Any]: # 方法名與其他服務一致
        """
        檢查 Deepgram 服務的健康狀態。

        透過嘗試列出專案 (一個需要有效 API 金鑰的輕量級請求) 來判斷服務是否可用。

        Returns:
            Dict[str, Any]: 包含服務健康狀態的字典。
                            例如 `{"available": True, "message": "服務運作正常"}` 或
                            `{"available": False, "error": "錯誤訊息"}`。
        """
        logger.info("開始檢查 Deepgram 服務健康狀態...")
        if not self.api_keys:
            logger.warning("Deepgram 健康檢查：API 金鑰未設定。")
            return {"available": False, "status_message": "API 金鑰未設定", "provider": "Deepgram"}
        
        api_key_to_test = self._get_api_key() # 獲取一個 API 金鑰進行測試
        headers = {'Authorization': f'Token {api_key_to_test}'}
        check_url = f"{self.base_url}/projects" # 列出專案的端點
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    check_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10) # 設定較短的超時 (10秒)
                ) as response:
                    if response.status == 200:
                        # projects_data = await response.json() # 可以選擇性地解析回應內容
                        logger.info(f"Deepgram 服務健康狀態良好 (API 金鑰尾號: ...{api_key_to_test[-4:] if len(api_key_to_test) > 4 else '****'})。")
                        return {
                            "available": True,
                            "status_message": "服務運作正常，API 金鑰有效。",
                            "model_configured": self.model,
                            "language_configured": self.language,
                            "provider": "Deepgram",
                            "api_keys_available": len(self.api_keys)
                        }
                    else:
                        error_detail = await response.text()
                        logger.warning(f"Deepgram 健康檢查失敗 (API 金鑰尾號: ...{api_key_to_test[-4:] if len(api_key_to_test) > 4 else '****'})。狀態碼: {response.status}，回應: {error_detail[:200]}")
                        return {
                            "available": False,
                            "status_message": f"API 請求失敗，狀態碼: {response.status}",
                            "provider": "Deepgram",
                            "error_detail": error_detail[:200] # 返回部分錯誤細節
                        }
                        
        except aiohttp.ClientError as net_err: # 網路錯誤
            logger.error(f"Deepgram 健康檢查時發生網路錯誤: {str(net_err)}", exc_info=True)
            return {"available": False, "status_message": f"網路連線錯誤: {type(net_err).__name__}", "provider": "Deepgram"}
        except Exception as e: # 其他未預期錯誤
            logger.error(f"Deepgram 健康檢查時發生未預期錯誤: {str(e)}", exc_info=True)
            return {"available": False, "status_message": f"未預期錯誤: {type(e).__name__}", "provider": "Deepgram"}