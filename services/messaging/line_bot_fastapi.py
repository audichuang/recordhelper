# -*- coding: utf-8 -*-
"""
LINE Bot Webhook 處理器 (FastAPI 版本)。

此模組定義了 `LineWebhookHandler` 類別，用於接收和處理來自 LINE Platform 的 Webhook 事件。
它整合了 LINE Bot SDK (`line-bot-sdk-python`)，並與應用程式內部的其他服務
(例如語音轉文字、AI 摘要服務) 進行互動，以回應使用者的訊息。

主要功能：
- 驗證 Webhook 請求的簽名以確保安全性。
- 解析 Webhook 事件。
- 根據事件類型 (例如文字訊息、音訊訊息) 執行相應的處理邏輯。
- 下載音訊檔案、調用語音轉文字服務、調用 AI 摘要服務。
- 向使用者回覆處理結果或錯誤訊息。
"""

import logging
import json # json 未在此檔案直接使用，但保留以備未來擴展
import hashlib
import hmac
import base64
from typing import Dict, Any
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, AudioMessage, TextMessage, TextSendMessage

from config import AppConfig
# 假設 AsyncSpeechToTextService 和 AsyncGeminiService 位於正確的路徑且可導入
from services.audio.speech_to_text_async import AsyncSpeechToTextService
from services.ai.gemini_async import AsyncGeminiService # 確保此服務有 generate_summary 方法或相應的異步方法

logger = logging.getLogger(__name__)

class LineWebhookHandler:
    """
    LINE Bot Webhook 事件處理器類別。

    負責初始化 LINE Bot API 客戶端、Webhook 解析器以及其他所需服務 (如語音轉文字、AI服務)。
    提供 `handle_webhook` 方法來處理傳入的 Webhook 請求，包括簽名驗證和事件分派。
    """
    
    def __init__(self, config: AppConfig):
        """
        初始化 LineWebhookHandler。

        Args:
            config (AppConfig): 應用程式的組態設定物件，包含 LINE Bot 的 Channel Access Token 和 Channel Secret，
                                以及其他服務所需的 API 金鑰等。
        """
        self.config = config
        # 初始化 LINE Bot API 客戶端，用於主動發送訊息或獲取內容
        self.line_bot_api = LineBotApi(config.LINE_CHANNEL_ACCESS_TOKEN)
        # 初始化 Webhook 解析器，用於解析 Webhook 事件主體
        self.parser = WebhookParser(config.LINE_CHANNEL_SECRET)
        # 初始化語音轉文字服務
        self.speech_service = AsyncSpeechToTextService(config) # 假設 STT 服務也需要 config
        # 初始化 AI 摘要服務 (假設 AsyncGeminiService 的建構函式接受整個 config 或僅 api_key)
        self.ai_service = AsyncGeminiService(api_key=config.GEMINI_API_KEY) # 或 self.ai_service = AsyncGeminiService(config)
        logger.info("LineWebhookHandler 初始化完成，LINE Bot API 和相關服務已設定。")
    
    async def handle_webhook(self, body: bytes, signature: str) -> None:
        """
        處理傳入的 LINE Webhook 請求。

        此方法會驗證請求簽名的有效性，然後解析 Webhook 事件，
        並將每個事件分派給相應的處理函數。

        Args:
            body (bytes): Webhook 請求的原始主體 (bytes)。
            signature (str): 從 'X-Line-Signature' 請求標頭中獲取的簽名。

        Raises:
            InvalidSignatureError: 如果請求簽名驗證失敗。
            Exception: 如果在事件處理過程中發生其他未預期的錯誤。
        """
        logger.debug(f"接收到 LINE Webhook 請求，簽名: {signature}，主體長度: {len(body)} bytes。")
        try:
            # 步驟 1：驗證簽名 (使用 LINE SDK 內建的 parser 或自訂的 _verify_signature)
            # WebhookParser.parse() 方法內部已包含簽名驗證邏輯，如果簽名無效會拋出 InvalidSignatureError。
            # 因此，如果使用 parser.parse，通常不需要再手動調用 _verify_signature。
            # if not self._verify_signature(body, signature):
            #     logger.error("LINE Webhook 簽名驗證失敗。")
            #     raise InvalidSignatureError('無效的簽名，請求可能來自未授權的來源。')
            # logger.debug("LINE Webhook 簽名驗證成功。")
            
            # 步驟 2：解析 Webhook 事件
            # 注意：body 需要解碼為 UTF-8 字串才能被 parser 使用
            events = self.parser.parse(body.decode('utf-8'), signature)
            logger.info(f"成功解析 {len(events)} 個 LINE Webhook 事件。")
            
            # 步驟 3：非同步處理每個事件
            for event in events:
                logger.debug(f"開始處理事件：類型 {type(event).__name__}, 來源 {event.source}")
                await self._handle_event(event)
                
        except InvalidSignatureError: # 特地捕獲簽名錯誤以記錄並重新拋出
            logger.error("LINE Webhook 簽名驗證失敗。請求可能未經授權。", exc_info=True)
            raise # 讓 FastAPI 的錯誤處理機制處理此 HTTP 相關錯誤
        except Exception as e:
            logger.error(f"處理 LINE Webhook 時發生未預期錯誤: {str(e)}", exc_info=True)
            # 根據錯誤處理策略，可以選擇是否要向上拋出，或者僅記錄錯誤
            raise # 向上拋出，以便 FastAPI 可以返回適當的 HTTP 錯誤回應
    
    def _verify_signature(self, body: bytes, signature: str) -> bool:
        """
        (備用) 手動驗證 LINE Webhook 請求簽名。

        注意：`WebhookParser.parse()` 方法已內建簽名驗證。此方法主要用於理解簽名過程或在不使用 `parse` 的情況下進行驗證。

        Args:
            body (bytes): Webhook 請求的原始主體。
            signature (str): 從 'X-Line-Signature' 請求標頭中獲取的簽名。

        Returns:
            bool: 如果簽名有效則返回 True，否則返回 False。
        """
        # 使用 HMAC-SHA256 演算法計算雜湊值
        hash_value = hmac.new(
            self.config.LINE_CHANNEL_SECRET.encode('utf-8'), # 使用 Channel Secret 作為金鑰
            body, # 直接使用原始 bytes 主體
            hashlib.sha256
        ).digest()
        
        # 將計算出的雜湊值進行 Base64 編碼，得到預期的簽名
        expected_signature = base64.b64encode(hash_value).decode('utf-8')
        
        # 使用安全的方式比較兩個簽名是否一致 (防止時序攻擊)
        return hmac.compare_digest(signature, expected_signature)
    
    async def _handle_event(self, event: Any) -> None:
        """
        根據事件類型分派並處理單個 LINE Webhook 事件。

        Args:
            event (Any): 從 LINE Platform 接收到的已解析事件物件 (例如 MessageEvent, FollowEvent 等)。
        """
        try:
            # 目前主要處理訊息事件 (MessageEvent)
            if isinstance(event, MessageEvent):
                # 根據訊息類型進一步分派
                if isinstance(event.message, AudioMessage):
                    # 如果是音訊訊息，交給 _handle_audio_message 處理
                    await self._handle_audio_message(event)
                elif isinstance(event.message, TextMessage):
                    # 如果是文字訊息，交給 _handle_text_message 處理
                    await self._handle_text_message(event)
                else:
                    logger.info(f"收到未處理的訊息類型: {type(event.message).__name__}，訊息 ID: {event.message.id}")
            # TODO: 可以根據需要在此處添加對其他事件類型 (例如 FollowEvent, UnfollowEvent, PostbackEvent 等) 的處理邏輯
            # elif isinstance(event, FollowEvent):
            #     logger.info(f"使用者 {event.source.user_id} 加入好友。")
            #     # 可以發送歡迎訊息等
            else:
                logger.info(f"收到未處理的事件類型: {type(event).__name__}")
                    
        except Exception as e:
            logger.error(f"處理 LINE 事件 (類型: {type(event).__name__}, 來源: {event.source}) 時發生錯誤: {str(e)}", exc_info=True)
            # 嘗試向使用者發送錯誤通知訊息 (如果事件有 reply_token)
            if hasattr(event, 'reply_token') and event.reply_token:
                try:
                    self.line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="抱歉，處理您的請求時發生了一些內部問題，我們將盡快修復。")
                    )
                    logger.info(f"已向使用者 {event.source.user_id} 發送錯誤通知。")
                except LineBotApiError as api_error:
                    logger.error(f"向使用者 {event.source.user_id} 發送錯誤通知失敗: {api_error.status_code} {api_error.error.message}", exc_info=True)
            elif hasattr(event, 'source') and hasattr(event.source, 'user_id'):
                 # 如果沒有 reply_token，但有 user_id，可以考慮使用 push_message
                try:
                    self.line_bot_api.push_message(
                        event.source.user_id,
                        TextSendMessage(text="抱歉，處理您的請求時發生了一些內部問題，我們將盡快修復。")
                    )
                    logger.info(f"已向使用者 {event.source.user_id} 推播錯誤通知。")
                except LineBotApiError as api_error:
                    logger.error(f"向使用者 {event.source.user_id} 推播錯誤通知失敗: {api_error.status_code} {api_error.error.message}", exc_info=True)


    async def _handle_audio_message(self, event: MessageEvent) -> None:
        """
        處理接收到的音訊訊息。

        包括下載音訊、語音轉文字、生成 AI 摘要，並將結果回覆給使用者。

        Args:
            event (MessageEvent): 包含音訊訊息的 LINE MessageEvent 物件。
        """
        audio_message_id = event.message.id
        user_id = event.source.user_id
        reply_token = event.reply_token # 獲取 reply_token 以便回覆初始訊息

        logger.info(f"開始處理來自使用者 {user_id} 的音訊訊息 ID: {audio_message_id}")
        
        try:
            # 步驟 1：立即回覆一個「處理中」的訊息，避免使用者等待過久導致 LINE Platform 認為超時
            # 注意：reply_message 只能使用一次。後續更新應使用 push_message。
            self.line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="🎵 收到您的語音訊息，助手正在努力處理中，請稍候片刻...")
            )
            logger.debug(f"已向使用者 {user_id} 回覆「處理中」訊息 (音訊 ID: {audio_message_id})。")
            
            # 步驟 2：下載音訊檔案內容
            logger.debug(f"開始下載音訊內容 (音訊 ID: {audio_message_id})。")
            message_content = self.line_bot_api.get_message_content(audio_message_id)
            audio_data = b''
            for chunk in message_content.iter_content(): # 以 chunk 方式讀取以處理大檔案
                audio_data += chunk
            logger.info(f"音訊內容下載完成 (音訊 ID: {audio_message_id})，大小: {len(audio_data)} bytes。")
            
            # 步驟 3：將音訊數據傳遞給語音轉文字服務
            # 假設 AsyncSpeechToTextService 的 transcribe_audio_data 方法可以直接處理 bytes 數據
            # 並返回一個包含 'transcript' 和 'duration' (可選) 的字典
            # 注意：LINE Bot 音訊通常是 m4a 格式。需確認 STT 服務是否支援或需要轉換。
            # 這裡的 format_str 和 mime_type 需要根據實際情況或 STT 服務要求設定。
            # LINE AudioMessage 不直接提供這些資訊，可能需要預設或偵測。
            # 暫時假設 STT 服務能自動處理或接受通用格式。
            logger.info(f"開始對音訊 ID {audio_message_id} 進行語音轉文字...")
            # TODO: 確認 STT 服務所需的音訊格式和 MIME 類型，此處的 'm4a' 和 'audio/mp4' 為常見預設
            stt_result = await self.speech_service.transcribe_audio_data(
                audio_data=audio_data, 
                format_str="m4a", # LINE Bot 音訊通常為 m4a
                mime_type="audio/mp4" # M4A 的 MIME 類型
            )
            transcript = stt_result.get('text', '') # 從結果中獲取文字稿
            # duration = stt_result.get('duration') # 如果 STT 服務返回時長
            
            if not transcript:
                logger.warning(f"音訊 ID {audio_message_id} 語音轉文字結果為空。")
                self.line_bot_api.push_message( # 使用 push_message 進行後續回覆
                    user_id,
                    TextSendMessage(text="抱歉，我無法識別您語音中的內容，請嘗試用更清晰的語音再說一次，或檢查您的麥克風設定。")
                )
                return
            logger.info(f"音訊 ID {audio_message_id} 語音轉文字成功，文字稿長度: {len(transcript)}。")
            
            # 步驟 4：使用轉錄後的文字生成 AI 摘要
            logger.info(f"開始為音訊 ID {audio_message_id} 的文字稿生成 AI 摘要...")
            summary = await self.ai_service.generate_summary_async(transcript) # 假設 AI 服務有 generate_summary_async
            
            if not summary:
                logger.warning(f"音訊 ID {audio_message_id} AI 摘要結果為空。將僅發送文字稿。")
                summary = "（AI 摘要生成失敗或無內容）" # 提供一個預設的摘要失敗訊息
            else:
                logger.info(f"音訊 ID {audio_message_id} AI 摘要生成成功，摘要長度: {len(summary)}。")

            # 步驟 5：構建並發送包含結果的回覆訊息 (使用 push_message)
            reply_text = f"📝 您的語音轉文字結果：\n「{transcript}」\n\n"
            reply_text += f"🤖 AI 智能摘要：\n「{summary}」"
            
            self.line_bot_api.push_message(
                user_id,
                TextSendMessage(text=reply_text)
            )
            logger.info(f"已向使用者 {user_id} 發送音訊 ID {audio_message_id} 的處理結果。")
            
            # 注意：臨時檔案的保存和清理邏輯已移除，因為音訊數據直接從記憶體傳遞。
            # 如果 STT 服務需要檔案路徑，則需要重新實現臨時檔案的保存和清理。
                
        except LineBotApiError as lbe: # 捕獲 LINE Bot API 相關錯誤
            logger.error(f"處理音訊訊息 (ID: {audio_message_id}) 時發生 LINE Bot API 錯誤: {lbe.status_code} {lbe.error.message}", exc_info=True)
            # 根據錯誤類型決定是否以及如何通知使用者
            if reply_token and not reply_token_used(reply_token, locals()): # 檢查 reply_token 是否已用
                 self.line_bot_api.reply_message(reply_token, TextSendMessage(text="處理您的語音時與 LINE 伺服器通訊發生問題，請稍後再試。"))
            elif user_id:
                 self.line_bot_api.push_message(user_id, TextSendMessage(text="處理您的語音時與 LINE 伺服器通訊發生問題，請稍後再試。"))
        except Exception as e:
            logger.error(f"處理音訊訊息 (ID: {audio_message_id}) 時發生未預期錯誤: {str(e)}", exc_info=True)
            # 通用錯誤回覆 (如果 reply_token 尚未使用)
            if reply_token and not reply_token_used(reply_token, locals()):
                 self.line_bot_api.reply_message(reply_token, TextSendMessage(text="哎呀，處理您的語音訊息時遇到一點小麻煩，工程師已收到通知！"))
            elif user_id: # 否則嘗試用 push_message
                 self.line_bot_api.push_message(user_id, TextSendMessage(text="哎呀，處理您的語音訊息時遇到一點小麻煩，工程師已收到通知！"))

    async def _handle_text_message(self, event: MessageEvent) -> None:
        """
        處理接收到的文字訊息。

        可以實現簡單的指令回應 (例如 "幫助", "狀態") 或對較長文字進行 AI 摘要。

        Args:
            event (MessageEvent): 包含文字訊息的 LINE MessageEvent 物件。
        """
        user_text = event.message.text.strip() # 獲取並清理使用者輸入的文字
        user_id = event.source.user_id
        reply_token = event.reply_token
        logger.info(f"收到來自使用者 {user_id} 的文字訊息: 「{user_text}」")
        
        try:
            # 指令處理：檢查使用者是否輸入了特定指令
            if user_text.lower() in ['幫助', 'help', '說明', '/help']:
                help_text = (
                    "👋 您好！我是您的錄音助手。\n\n"
                    "您可以這樣使用我：\n"
                    "1️⃣ 直接傳送【語音訊息】：我會將其轉換為文字，並提供 AI 生成的摘要。\n"
                    "2️⃣ 傳送【較長的文字訊息】：我會嘗試為您生成 AI 摘要 (長度需大於20字)。\n"
                    "3️⃣ 輸入【幫助】或【說明】：再次顯示此使用說明。\n"
                    "4️⃣ 輸入【狀態】：檢查我的目前服務狀態。\n\n"
                    "💡 提示：語音訊息請盡量在安靜環境錄製，以獲得最佳辨識效果。"
                )
                self.line_bot_api.reply_message(reply_token, TextSendMessage(text=help_text))
                logger.info(f"已向使用者 {user_id} 回覆幫助說明。")
                return # 指令已處理，結束函數
            
            if user_text.lower() in ['狀態', 'status', '/status']:
                # TODO: 未來可以擴展此處以檢查依賴服務的實際狀態
                status_text = "✅ 錄音助手目前服務正常運作中！\n🎵 語音辨識功能：就緒\n🤖 AI 摘要功能：就緒"
                self.line_bot_api.reply_message(reply_token, TextSendMessage(text=status_text))
                logger.info(f"已向使用者 {user_id} 回覆服務狀態。")
                return # 指令已處理
            
            # 對於一般文字訊息，如果長度足夠，則嘗試生成摘要
            # TODO: "20" 這個長度閾值可以考慮移到 AppConfig 中作為可設定參數
            if len(user_text) > self.config.TEXT_SUMMARY_MIN_LENGTH: # 假設 AppConfig 有 TEXT_SUMMARY_MIN_LENGTH
                logger.info(f"使用者 {user_id} 的文字訊息長度 ({len(user_text)}) 超過閾值，準備進行 AI 摘要。")
                # 先回覆一個處理中訊息，因為 AI 摘要可能需要時間
                self.line_bot_api.reply_message(
                    reply_token,
                    TextSendMessage(text="📝 收到您的文字，正在為您生成 AI 智能摘要，請稍候...")
                )
                
                summary = await self.ai_service.generate_summary_async(user_text) # 使用異步方法
                reply_text = f"🤖 AI 為您總結的文字摘要如下：\n\n「{summary}」" if summary else "抱歉，目前無法為這段文字生成摘要。"
                
                self.line_bot_api.push_message(user_id, TextSendMessage(text=reply_text)) # 使用 push_message 發送結果
                logger.info(f"已向使用者 {user_id} 推播文字訊息的 AI 摘要結果。")
            else:
                # 對於較短的文字或未匹配任何指令的文字，提供一般性回覆
                logger.info(f"使用者 {user_id} 的文字訊息 「{user_text}」 未觸發特定操作，發送一般回覆。")
                self.line_bot_api.reply_message(
                    reply_token,
                    TextSendMessage(text="您好！您可以傳送語音訊息給我，我會幫您轉成文字並做摘要。輸入「幫助」可以查看更多功能喔！")
                )
                
        except LineBotApiError as lbe:
            logger.error(f"處理文字訊息 (來自 {user_id}) 時發生 LINE Bot API 錯誤: {lbe.status_code} {lbe.error.message}", exc_info=True)
            if reply_token and not reply_token_used(reply_token, locals()):
                 self.line_bot_api.reply_message(reply_token, TextSendMessage(text="與 LINE 伺服器溝通時發生問題，請稍後再試一次。"))
        except Exception as e:
            logger.error(f"處理文字訊息 (來自 {user_id}，內容: 「{user_text[:50]}...」) 時發生未預期錯誤: {str(e)}", exc_info=True)
            if reply_token and not reply_token_used(reply_token, locals()):
                 self.line_bot_api.reply_message(reply_token, TextSendMessage(text="哎呀，處理您的文字訊息時出現了未預期的狀況！"))

def reply_token_used(token: str, local_vars: Dict) -> bool:
    """
    輔助函數，用於檢查 reply_token 是否可能已被使用。
    這是一個簡化的檢查，實際情況下 reply_token 的使用狀態由 LINE Platform 管理。
    此函數主要用於避免在同一個錯誤處理流程中重複嘗試使用 reply_token。
    """
    # 這裡可以根據實際情況擴展，例如檢查日誌或特定的狀態標記
    # 但最簡單的方式是假設如果在 try 區塊中已成功 reply，則不應在 except 中再次 reply
    # 不過，由於 reply_message 拋出例外時，reply_token 可能仍有效，此檢查幫助不大。
    # 更可靠的方式是，如果 reply_message 失敗，則後續應使用 push_message。
    # 此函數目前僅作為一個概念性輔助，實際應用中可能需要更複雜的邏輯或直接避免重複 reply。
    return False # 預設返回 False，讓呼叫者自行決定是否嘗試 reply