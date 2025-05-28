# -*- coding: utf-8 -*-
"""
異步 OpenAI Whisper 語音識別服務模組。

此模組提供了 `AsyncWhisperService` 類別，用於與 OpenAI Whisper API 進行異步互動，
以實現語音轉文字功能。它處理 API 金鑰配置、檔案上傳以及 API 回應的解析。
"""

import logging
import aiohttp # 用於異步 HTTP 請求
import aiofiles # 用於異步檔案操作
from typing import Dict, Any, Optional, List # 用於類型註解
from pathlib import Path # 用於處理檔案路徑

from config import AppConfig # 導入應用程式組態

logger = logging.getLogger(__name__)


class AsyncWhisperService:
    """
    異步 OpenAI Whisper API 語音轉文字服務類別。

    封裝了與 OpenAI Whisper API 互動的邏輯，包括：
    - 初始化設定 (API 金鑰、模型名稱)。
    - 異步轉錄音訊檔案。
    - 檢查 OpenAI Whisper 服務的健康狀態 (透過列出模型)。
    """
    
    def __init__(self, config: AppConfig):
        """
        初始化 AsyncWhisperService。

        Args:
            config (AppConfig): 應用程式的組態設定物件。
                                需要包含 OpenAI API 金鑰 (`OPENAI_API_KEY`) 
                                和 Whisper 模型名稱 (`WHISPER_MODEL`)。
        
        Raises:
            ValueError: 如果組態中未提供 OpenAI API 金鑰。
        """
        self.config = config
        self.api_key: Optional[str] = config.OPENAI_API_KEY # 從組態獲取 OpenAI API 金鑰
        self.model: str = config.WHISPER_MODEL # 使用的 Whisper 模型 (例如 "whisper-1")
        self.base_url: str = "https://api.openai.com/v1" # OpenAI API 的基礎 URL
        
        if not self.api_key:
            logger.error("OpenAI API 金鑰 (OPENAI_API_KEY) 未在組態中設定。Whisper API 服務將不可用。")
            # 考慮是否應在此處拋出 ValueError，或允許服務在無金鑰的情況下初始化但無法運作。
            # 為了保持一致性和早期失敗原則，拋出錯誤通常更好。
            raise ValueError("OpenAI API 金鑰未設定，無法初始化 AsyncWhisperService。")
        logger.info(f"AsyncWhisperService 初始化完成，使用模型: {self.model}。")
    
    async def transcribe_audio_file_async(self, file_path: str) -> Dict[str, Any]: # 方法名與其他服務統一
        """
        使用 OpenAI Whisper API 異步轉錄指定的音訊檔案。

        Args:
            file_path (str): 本地音訊檔案的路徑。支援的格式請參考 OpenAI API 文件。

        Returns:
            Dict[str, Any]: 包含轉錄結果的字典，結構如下：
                            {
                                'transcript': '完整文字稿',
                                'language': '偵測到的語言代碼',
                                'duration_seconds': 音訊時長 (秒),
                                'segments': [{'start': 開始時間, 'end': 結束時間, 'text': 片段文字, ...}],
                                'provider': 'openai_whisper_api',
                                'model_used': '使用的模型名稱'
                            }
                            如果轉錄失敗，則拋出例外。
        
        Raises:
            FileNotFoundError: 如果提供的 `file_path` 不存在。
            ValueError: 如果 API 金鑰未設定 (理論上應在初始化時捕獲)。
            aiohttp.ClientError: 如果 API 請求過程中發生網路或客戶端錯誤。
            Exception: 如果 API 返回非預期狀態碼或回應格式錯誤，或發生其他未預期錯誤。
        """
        if not self.api_key: # 再次檢查以防萬一
            logger.error("OpenAI Whisper API 轉錄請求失敗：API 金鑰未設定。")
            raise ValueError("OpenAI API 金鑰未設定。")

        if not Path(file_path).exists(): # 檢查檔案是否存在
            logger.error(f"OpenAI Whisper 轉錄請求失敗：音訊檔案 '{file_path}' 不存在。")
            raise FileNotFoundError(f"音訊檔案不存在: {file_path}")

        logger.info(f"開始使用 OpenAI Whisper API 轉錄檔案: {file_path} (模型: {self.model})")
        
        try:
            # 異步讀取音訊檔案內容
            async with aiofiles.open(file_path, 'rb') as audio_file_handle:
                audio_data = await audio_file_handle.read()
            logger.debug(f"音訊檔案 '{Path(file_path).name}' (大小: {len(audio_data)} bytes) 讀取完成。")
            
            # 準備 multipart/form-data 請求數據
            # OpenAI API 要求檔案以 'file' 欄位上傳
            form_data = aiohttp.FormData()
            form_data.add_field(
                'file', 
                audio_data, 
                filename=Path(file_path).name, # 提供檔案名稱
                # OpenAI API 會自動偵測內容類型，但明確指定有助於某些情況
                # content_type='audio/mpeg' # 例如，如果是 MP3 檔案
                # content_type='audio/wav'  # 例如，如果是 WAV 檔案
                # 也可以不指定，讓 aiohttp 或 API 自行判斷
            )
            form_data.add_field('model', self.model) # 指定使用的 Whisper 模型
            form_data.add_field('language', 'zh')  # 明確指定語言為中文 (繁體/簡體由模型判斷)
            form_data.add_field('response_format', 'verbose_json') # 要求詳細的 JSON 回應，包含時間戳等
            # 其他可選參數: prompt, temperature, timestamp_granularities
            # form_data.add_field('prompt', '這是一段關於台灣美食的談話。') # 提供提示以引導模型
            # form_data.add_field('timestamp_granularities[]', 'segment') # 要求片段級時間戳
            # form_data.add_field('timestamp_granularities[]', 'word')    # 要求詞級時間戳 (如果需要)

            # 準備請求標頭，包含 API 金鑰
            headers = {'Authorization': f'Bearer {self.api_key}'}
            
            request_url = f"{self.base_url}/audio/transcriptions" # OpenAI 轉錄 API 端點
            logger.debug(f"向 OpenAI Whisper API ({request_url}) 發送轉錄請求...")

            # 使用 aiohttp 異步發送 POST 請求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    request_url,
                    data=form_data, # 使用 FormData
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=600)  # 設定總超時為 10 分鐘 (處理較長音訊)
                ) as response:
                    response_status = response.status
                    response_content = await response.text() # 獲取回應內容 (可能是 JSON 或錯誤訊息)

                    if response_status != 200: # 檢查 HTTP 狀態碼
                        logger.error(f"OpenAI Whisper API 請求失敗。狀態碼: {response_status}，回應: {response_content[:500]}...")
                        # 嘗試解析 JSON 錯誤訊息 (OpenAI API 通常會返回 JSON 格式的錯誤)
                        try:
                            error_details = json.loads(response_content)
                            error_message = error_details.get("error", {}).get("message", response_content)
                        except json.JSONDecodeError:
                            error_message = response_content
                        raise Exception(f"OpenAI API 錯誤 {response_status}: {error_message}")
                    
                    logger.info(f"OpenAI Whisper API 請求成功 (狀態碼: {response_status})。開始解析回應...")
                    result = json.loads(response_content) # 解析 JSON 回應
            
            # 從 `verbose_json` 回應中提取所需資訊
            # 參考 OpenAI API 文件: https://platform.openai.com/docs/api-reference/audio/createTranscription#audio/createTranscription-response_format
            transcript_text = result.get('text', '').strip()
            
            if not transcript_text and not result.get('segments'): # 如果完全沒有文本且沒有片段，可能是有問題
                 logger.warning(f"OpenAI Whisper API 返回的轉錄文字稿和片段均為空 (檔案: {file_path})。")
                 # 可以選擇拋出例外或返回帶有空 transcript 的結果
                 # raise Exception("OpenAI Whisper API 返回的轉錄結果為空。")

            # 格式化並返回包含詳細資訊的結果字典
            formatted_result = {
                'transcript': transcript_text, # 完整文字稿
                'language_detected': result.get('language', 'zh'), # 偵測到的語言
                'duration_seconds': result.get('duration'), # 音訊時長 (秒)
                'segments': result.get('segments', []), # 包含時間戳和各片段文字的列表
                # 'words': result.get('words', []), # 如果請求了詞級時間戳 (注意：verbose_json 預設不含此欄位，需明確要求)
                'provider': 'openai_whisper_api', # 標識服務提供者
                'model_used': self.model # 使用的模型
            }
            logger.info(f"✅ OpenAI Whisper 轉錄成功完成 (檔案: {file_path})。文字稿長度: {len(transcript_text)} 字元。")
            return formatted_result
            
        except FileNotFoundError: # 由 Path(file_path).exists() 或 aiofiles.open 引發
            raise # 直接重新拋出 FileNotFoundError
        except aiohttp.ClientError as net_err: # 捕獲網路相關錯誤
            logger.error(f"OpenAI Whisper 轉錄時發生網路錯誤 (檔案: {file_path}): {str(net_err)}", exc_info=True)
            raise # 重新拋出
        except ValueError as val_err: # 捕獲 API 金鑰未設定等錯誤
            logger.error(f"OpenAI Whisper 轉錄時發生組態或數值錯誤 (檔案: {file_path}): {str(val_err)}", exc_info=True)
            raise
        except Exception as e: # 捕獲所有其他未預期錯誤
            logger.error(f"OpenAI Whisper 轉錄過程中發生未預期錯誤 (檔案: {file_path}): {str(e)}", exc_info=True)
            raise Exception(f"OpenAI Whisper 轉錄失敗：{type(e).__name__} - {str(e)}") from e # 重新拋出，包含原始錯誤類型和訊息
    
    async def check_service_health_async(self) -> Dict[str, Any]: # 方法名與其他服務統一
        """
        檢查 OpenAI Whisper API 服務的健康狀態。

        透過嘗試列出 OpenAI 模型 (一個需要有效 API 金鑰的輕量級請求) 來判斷服務是否可用。

        Returns:
            Dict[str, Any]: 包含服務健康狀態的字典。
        """
        logger.info("開始檢查 OpenAI Whisper API 服務健康狀態...")
        if not self.api_key:
            logger.warning("OpenAI Whisper API 健康檢查：API 金鑰未設定。")
            return {"available": False, "status_message": "API 金鑰未設定", "provider": "openai_whisper_api"}

        headers = {'Authorization': f'Bearer {self.api_key}'}
        check_url = f"{self.base_url}/models" # 列出模型的端點
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    check_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10) # 設定較短的超時 (10秒)
                ) as response:
                    if response.status == 200:
                        # models_data = await response.json() # 可以選擇性地檢查模型列表是否包含 self.model
                        logger.info(f"OpenAI Whisper API 服務健康狀態良好。")
                        return {
                            "available": True,
                            "status_message": "服務運作正常，API 金鑰有效。",
                            "model_configured": self.model,
                            "provider": "openai_whisper_api"
                        }
                    else:
                        error_detail = await response.text()
                        logger.warning(f"OpenAI Whisper API 健康檢查失敗。狀態碼: {response.status}，回應: {error_detail[:200]}...")
                        return {
                            "available": False,
                            "status_message": f"API 請求失敗，狀態碼: {response.status}",
                            "provider": "openai_whisper_api",
                            "error_detail": error_detail[:200]
                        }
                        
        except aiohttp.ClientError as net_err:
            logger.error(f"OpenAI Whisper API 健康檢查時發生網路錯誤: {str(net_err)}", exc_info=True)
            return {"available": False, "status_message": f"網路連線錯誤: {type(net_err).__name__}", "provider": "openai_whisper_api"}
        except Exception as e:
            logger.error(f"OpenAI Whisper API 健康檢查時發生未預期錯誤: {str(e)}", exc_info=True)
            return {"available": False, "status_message": f"未預期錯誤: {type(e).__name__}", "provider": "openai_whisper_api"}