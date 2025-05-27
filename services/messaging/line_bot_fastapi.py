"""
FastAPI版本的LINE Bot webhook處理器
"""

import logging
import json
import hashlib
import hmac
import base64
from typing import Dict, Any
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, AudioMessage, TextMessage, TextSendMessage

from config import AppConfig
from services.audio.speech_to_text_async import AsyncSpeechToTextService
from services.ai.gemini_async import AsyncGeminiService

logger = logging.getLogger(__name__)


class LineWebhookHandler:
    """LINE Bot webhook處理器"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.line_bot_api = LineBotApi(config.line_channel_access_token)
        self.parser = WebhookParser(config.line_channel_secret)
        self.speech_service = AsyncSpeechToTextService(config)
        self.ai_service = AsyncGeminiService(config)
    
    async def handle_webhook(self, body: bytes, signature: str):
        """處理LINE webhook"""
        try:
            # 驗證簽名
            if not self._verify_signature(body, signature):
                raise InvalidSignatureError('Invalid signature')
            
            # 解析事件
            events = self.parser.parse(body.decode('utf-8'), signature)
            
            # 處理每個事件
            for event in events:
                await self._handle_event(event)
                
        except Exception as e:
            logger.error(f"處理LINE webhook錯誤: {str(e)}")
            raise
    
    def _verify_signature(self, body: bytes, signature: str) -> bool:
        """驗證LINE webhook簽名"""
        hash_value = hmac.new(
            self.config.line_channel_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).digest()
        
        expected_signature = base64.b64encode(hash_value).decode()
        return hmac.compare_digest(signature, expected_signature)
    
    async def _handle_event(self, event):
        """處理單個事件"""
        try:
            if isinstance(event, MessageEvent):
                if isinstance(event.message, AudioMessage):
                    await self._handle_audio_message(event)
                elif isinstance(event.message, TextMessage):
                    await self._handle_text_message(event)
                    
        except Exception as e:
            logger.error(f"處理事件錯誤: {str(e)}")
            # 發送錯誤訊息給用戶
            try:
                self.line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="抱歉，處理您的訊息時發生錯誤，請稍後再試。")
                )
            except LineBotApiError as api_error:
                logger.error(f"發送錯誤訊息失敗: {api_error}")
    
    async def _handle_audio_message(self, event):
        """處理音頻訊息"""
        try:
            logger.info(f"收到音頻訊息: {event.message.id}")
            
            # 發送處理中訊息
            self.line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="🎵 收到您的語音訊息，正在處理中，請稍候...")
            )
            
            # 下載音頻文件
            message_content = self.line_bot_api.get_message_content(event.message.id)
            audio_data = b''
            for chunk in message_content.iter_content():
                audio_data += chunk
            
            # 保存音頻文件
            import os
            import tempfile
            audio_dir = "temp_audio"
            os.makedirs(audio_dir, exist_ok=True)
            
            audio_file_path = os.path.join(audio_dir, f"{event.message.id}.m4a")
            with open(audio_file_path, 'wb') as f:
                f.write(audio_data)
            
            # 語音轉文字
            logger.info("開始語音轉文字處理")
            transcript_result = await self.speech_service.transcribe_audio(audio_file_path)
            transcript = transcript_result.get('transcript', '')
            
            if not transcript:
                self.line_bot_api.push_message(
                    event.source.user_id,
                    TextSendMessage(text="抱歉，無法識別您的語音內容，請再試一次。")
                )
                return
            
            # 生成AI摘要
            logger.info("開始生成AI摘要")
            summary = await self.ai_service.generate_summary(transcript)
            
            # 構建回覆訊息
            reply_text = f"📝 語音轉文字結果：\n\n{transcript}\n\n"
            reply_text += f"🤖 AI智能摘要：\n\n{summary}"
            
            # 發送結果
            self.line_bot_api.push_message(
                event.source.user_id,
                TextSendMessage(text=reply_text)
            )
            
            # 清理臨時文件
            try:
                os.remove(audio_file_path)
            except:
                pass
                
            logger.info(f"音頻訊息處理完成: {event.message.id}")
            
        except Exception as e:
            logger.error(f"處理音頻訊息錯誤: {str(e)}")
            self.line_bot_api.push_message(
                event.source.user_id,
                TextSendMessage(text="抱歉，處理您的語音時發生錯誤，請稍後再試。")
            )
    
    async def _handle_text_message(self, event):
        """處理文字訊息"""
        try:
            user_text = event.message.text.strip()
            logger.info(f"收到文字訊息: {user_text}")
            
            # 基本指令處理
            if user_text in ['幫助', 'help', '說明']:
                help_text = (
                    "🎙️ 錄音助手使用說明：\n\n"
                    "📱 發送語音訊息 - 自動轉換為文字並生成AI摘要\n"
                    "💬 發送文字 - 直接使用AI分析和摘要\n"
                    "❓ 發送「幫助」- 查看此說明\n"
                    "📊 發送「狀態」- 查看服務狀態"
                )
                self.line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=help_text)
                )
                return
            
            if user_text in ['狀態', 'status']:
                status_text = "✅ 服務運行正常\n🎵 語音識別：可用\n🤖 AI摘要：可用"
                self.line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=status_text)
                )
                return
            
            # 對於普通文字，也可以生成摘要
            if len(user_text) > 20:  # 只對較長的文字生成摘要
                self.line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="📝 正在分析您的文字內容...")
                )
                
                summary = await self.ai_service.generate_summary(user_text)
                reply_text = f"🤖 AI分析結果：\n\n{summary}"
                
                self.line_bot_api.push_message(
                    event.source.user_id,
                    TextSendMessage(text=reply_text)
                )
            else:
                # 簡單回覆
                self.line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="您好！請發送語音訊息，我會幫您轉換為文字並生成摘要。")
                )
                
        except Exception as e:
            logger.error(f"處理文字訊息錯誤: {str(e)}")
            self.line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="抱歉，處理您的訊息時發生錯誤。")
            ) 