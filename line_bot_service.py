import time
import threading
import logging
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import List

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent, AudioMessageContent, FileMessageContent

from config import AppConfig
from models import ProcessingStatus, SummaryStorage, AudioProcessingError, APIError
from audio_service import AudioService, TempFileManager
from speech_to_text_service import SpeechToTextService
from gemini_service import GeminiService


class AsyncLineBotService:
    """異步處理的LINE Bot服務"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.configuration = Configuration(access_token=config.line_channel_access_token)
        self.handler = WebhookHandler(config.line_channel_secret)
        
        # 初始化各種服務
        self.audio_service = AudioService()
        self.speech_to_text_service = SpeechToTextService(config)
        self.gemini_service = GeminiService(config)
        self.processing_status = ProcessingStatus()
        self.summary_storage = SummaryStorage()

        # 線程池用於異步處理
        self.executor = ThreadPoolExecutor(max_workers=config.max_workers)

        # 定期清理任務
        self._start_cleanup_task()

        self._register_handlers()

    def _start_cleanup_task(self):
        """啟動定期清理任務"""

        def cleanup_worker():
            while True:
                try:
                    time.sleep(3600)  # 每小時執行一次
                    self.processing_status.cleanup_old_records()
                    self.summary_storage.cleanup_old_summaries()
                    logging.info("完成定期清理任務")
                except Exception as e:
                    logging.error(f"清理任務錯誤: {e}")

        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()

    def _register_handlers(self):
        """註冊LINE Bot事件處理器"""

        @self.handler.add(MessageEvent, message=AudioMessageContent)
        def handle_audio_message(event):
            self._handle_audio_message_async(event)

        @self.handler.add(MessageEvent, message=FileMessageContent)
        def handle_file_message(event):
            self._handle_audio_message_async(event)

        @self.handler.add(MessageEvent, message=TextMessageContent)
        def handle_text_message(event):
            self._handle_text_message(event)

    def _handle_audio_message_async(self, event):
        """異步處理音訊訊息"""
        message_id = event.message.id
        user_id = event.source.user_id
        reply_token = event.reply_token

        # 檢查是否已處理或正在處理
        if self.processing_status.is_completed(message_id):
            logging.info(f"訊息 {message_id} 已處理完成，跳過")
            return

        if not self.processing_status.start_processing(message_id, user_id):
            logging.info(f"訊息 {message_id} 正在處理中或已完成，跳過")
            return

        # 立即回覆確認訊息，避免LINE重發
        line_api = MessagingApi(ApiClient(self.configuration))
        try:
            self._safe_reply(line_api, reply_token, [
                TextMessage(text="🎙️ 收到您的錄音，正在處理中，請稍候...")
            ])
            logging.info(f"已發送確認訊息給用戶 {user_id}")
        except Exception as e:
            logging.error(f"發送確認訊息失敗: {e}")

        # 提交到線程池異步處理
        future = self.executor.submit(
            self._process_audio_background,
            message_id, user_id, line_api
        )

        # 設定多階段超時處理
        def timeout_handler():
            # 第一次通知：25秒後
            time.sleep(self.config.webhook_timeout)
            if not self.processing_status.is_completed(message_id):
                logging.warning(f"訊息 {message_id} 處理超時 - 第一次通知")
                self.processing_status.update_status(message_id, "timeout_notified_1")
                try:
                    self._send_push_message(line_api, user_id,
                                            "⏰ 處理時間較長，請稍候。我們會盡快為您完成錄音分析。")
                except Exception as e:
                    logging.error(f"發送第一次超時訊息失敗: {e}")
            
            # 第二次通知：2分鐘後
            time.sleep(95)  # 總共120秒
            if not self.processing_status.is_completed(message_id):
                logging.warning(f"訊息 {message_id} 處理超時 - 第二次通知")
                self.processing_status.update_status(message_id, "timeout_notified_2")
                try:
                    self._send_push_message(line_api, user_id,
                                            "🎯 正在處理較長的錄音，預計還需要幾分鐘時間。\n\n💡 長錄音處理流程：\n1️⃣ 音訊轉換\n2️⃣ 語音識別\n3️⃣ 分段摘要\n\n請耐心等候...")
                except Exception as e:
                    logging.error(f"發送第二次超時訊息失敗: {e}")
            
            # 第三次通知：5分鐘後
            time.sleep(180)  # 總共300秒
            if not self.processing_status.is_completed(message_id):
                logging.warning(f"訊息 {message_id} 處理超時 - 第三次通知")
                self.processing_status.update_status(message_id, "timeout_notified_3")
                try:
                    self._send_push_message(line_api, user_id,
                                            "⏳ 您的錄音正在最後處理階段，即將完成！\n\n📊 對於2-3小時的長錄音，我們的處理流程包括：\n• 智能分段分析\n• 結構化摘要生成\n• 重點內容提取\n\n感謝您的耐心等候 🙏")
                except Exception as e:
                    logging.error(f"發送第三次超時訊息失敗: {e}")

        timeout_thread = threading.Thread(target=timeout_handler, daemon=True)
        timeout_thread.start()

    def _process_audio_background(self, message_id: str, user_id: str, line_api: MessagingApi):
        """背景處理音訊"""
        file_manager = TempFileManager(self.config.temp_dir)
        start_time = time.time()

        try:
            logging.info(f"開始背景處理音訊 {message_id}")
            self.processing_status.update_status(message_id, "downloading")

            # 1. 下載音訊
            audio_content = self._download_audio(message_id)

            # 2. 轉換格式
            self.processing_status.update_status(message_id, "converting")
            original_file = file_manager.create_temp_file(".m4a")
            mp3_file = file_manager.create_temp_file(".mp3")

            with open(original_file, 'wb') as f:
                f.write(audio_content)

            if not self.audio_service.convert_audio(original_file, mp3_file):
                raise AudioProcessingError("音訊轉換失敗")

            # 3. 語音轉文字與摘要處理
            self.processing_status.update_status(message_id, "transcribing")
            
            # 檢查是否使用 Gemini 音頻服務
            if self.config.speech_to_text_provider == "gemini_audio":
                # Gemini 音頻服務可以同時處理轉錄和摘要
                logging.info("使用 Gemini 音頻服務進行直接處理")
                try:
                    # 嘗試使用組合功能（轉錄+摘要）
                    result = self.speech_to_text_service.service.transcribe_and_summarize(mp3_file)
                    transcribed_text = result["transcription"]
                    summary_text = result["summary"]
                    
                    if not transcribed_text:
                        raise AudioProcessingError("Gemini 無法辨識語音內容")
                    
                    logging.info(f"Gemini 直接處理完成，轉錄: {len(transcribed_text)}字, 摘要: {len(summary_text)}字")
                    
                except Exception as e:
                    # 如果組合功能失敗，退回到基本轉錄
                    logging.warning(f"Gemini 組合功能失敗，使用基本轉錄: {e}")
                    transcribed_text = self.speech_to_text_service.transcribe_audio(mp3_file)
                    
                    if not transcribed_text:
                        raise AudioProcessingError("無法辨識語音內容")
                    
                    # 4. 使用傳統 Gemini 文字摘要
                    self.processing_status.update_status(message_id, "summarizing")
                    try:
                        summary_text = self.gemini_service.generate_summary(transcribed_text)
                    except Exception as e2:
                        logging.warning(f"摘要生成失敗: {e2}")
                        summary_text = "摘要功能暫時無法使用"
            else:
                # 其他語音轉文字服務的傳統處理流程
                transcribed_text = self.speech_to_text_service.transcribe_audio(mp3_file)

                if not transcribed_text:
                    raise AudioProcessingError("無法辨識語音內容")

                # 4. 生成摘要（非阻塞，失敗也不影響主要功能）
                self.processing_status.update_status(message_id, "summarizing")
                try:
                    summary_text = self.gemini_service.generate_summary(transcribed_text)
                except Exception as e:
                    logging.warning(f"摘要生成失敗: {e}")
                    summary_text = "摘要功能暫時無法使用"

            # 5. 發送結果
            self.processing_status.update_status(message_id, "sending")
            processing_time = time.time() - start_time

            self._send_final_result(line_api, user_id, transcribed_text, summary_text, processing_time)

            self.processing_status.complete_processing(message_id, True)
            logging.info(f"音訊處理完成 {message_id}，總耗時 {processing_time:.2f}秒")

        except Exception as e:
            processing_time = time.time() - start_time
            logging.error(f"背景處理音訊失敗 {message_id} (耗時{processing_time:.2f}秒): {e}")

            try:
                error_msg = "處理您的錄音時發生錯誤，請稍後再試"
                if isinstance(e, AudioProcessingError):
                    error_msg = str(e)
                elif isinstance(e, APIError):
                    error_msg = str(e)

                self._send_push_message(line_api, user_id, f"抱歉，{error_msg}")
            except Exception as send_error:
                logging.error(f"發送錯誤訊息失敗: {send_error}")

            self.processing_status.complete_processing(message_id, False)
        finally:
            file_manager.cleanup()

    def _download_audio(self, message_id: str) -> bytes:
        """下載音訊檔案"""
        headers = {'Authorization': f'Bearer {self.config.line_channel_access_token}'}
        url = f'https://api-data.line.me/v2/bot/message/{message_id}/content'

        response = requests.get(url, headers=headers, timeout=20)  # 降低超時時間
        if response.status_code != 200:
            raise AudioProcessingError(f"下載檔案失敗，狀態碼: {response.status_code}")

        return response.content

    def _send_final_result(self, line_api: MessagingApi, user_id: str,
                           transcribed_text: str, summary_text: str, processing_time: float):
        """發送最終結果 - 智能分割確保符合 LINE 5000 字符限制"""
        # 統計資訊
        text_length = len(transcribed_text)
        estimated_minutes = text_length / 180
        time_info = f"\n\n⏱️ 處理時間: {processing_time:.1f}秒"
        length_info = f"\n📊 錄音長度: 約{estimated_minutes:.1f}分鐘 ({text_length}字)"
        
        # 檢查摘要是否成功
        is_summary_failed = ("摘要功能暫時無法使用" in summary_text or 
                           "建議查看完整逐字稿" in summary_text)
        
        # 生成 HTML 摘要頁面
        summary_id = None
        html_link = ""
        if not is_summary_failed:
            try:
                summary_id = self.summary_storage.store_summary(
                    user_id, transcribed_text, summary_text, processing_time, text_length
                )
                html_link = f"\n\n🌐 美化顯示：https://chatbot.audiweb.uk/summary/{summary_id}"
                logging.info(f"生成摘要頁面: {summary_id}")
            except Exception as e:
                logging.error(f"生成摘要頁面失敗: {e}")
        
        # 準備訊息組件
        transcribed_header = "🎙️ 錄音轉文字："
        summary_header = "📝 重點摘要：" if not is_summary_failed else "📝 摘要狀態："
        stats_info = f"{length_info}{time_info}{html_link}"
        
        # 智能分割訊息，確保每條都在 4800 字符內（留有緩衝）
        messages = []
        
        # 第一條：轉錄文字
        transcribed_msg = f"{transcribed_header}\n{transcribed_text}"
        if len(transcribed_msg) <= 4800:
            messages.append(transcribed_msg)
        else:
            # 轉錄文字太長，需要分割
            max_text_length = 4800 - len(transcribed_header) - 50  # 留緩衝和分頁標記
            chunks = self._split_text_by_sentences(transcribed_text, max_text_length)
            
            for i, chunk in enumerate(chunks):
                if len(chunks) > 1:
                    header = f"{transcribed_header} ({i+1}/{len(chunks)})"
                else:
                    header = transcribed_header
                messages.append(f"{header}\n{chunk}")
        
        # 第二條：摘要
        summary_msg = f"{summary_header}\n{summary_text}"
        if len(summary_msg) <= 4800:
            messages.append(summary_msg)
        else:
            # 摘要太長，需要分割
            max_summary_length = 4800 - len(summary_header) - 50
            summary_chunks = self._split_text_by_sentences(summary_text, max_summary_length)
            
            for i, chunk in enumerate(summary_chunks):
                if len(summary_chunks) > 1:
                    header = f"{summary_header} ({i+1}/{len(summary_chunks)})"
                else:
                    header = summary_header
                messages.append(f"{header}\n{chunk}")
        
        # 第三條：統計資訊
        if stats_info.strip():
            stat_msg = f"📊 處理統計{stats_info}"
            if len(stat_msg) <= 4800:
                messages.append(stat_msg)
            else:
                # 統計資訊太長（理論上不會發生，但保險起見）
                messages.append(f"📊 處理統計{length_info}{time_info}")
                if html_link:
                    messages.append(f"🌐 美化顯示{html_link}")

        # 發送訊息，加強錯誤處理
        successful_sends = 0
        for i, msg in enumerate(messages):
            try:
                # 最終檢查：確保訊息長度不超過 5000
                if len(msg) > 5000:
                    logging.warning(f"訊息 {i+1} 長度 {len(msg)} 超過限制，截斷處理")
                    msg = msg[:4950] + "...\n\n📋 完整內容請查看美化顯示頁面"
                
                self._send_push_message(line_api, user_id, msg)
                successful_sends += 1
                logging.info(f"成功發送第 {i+1}/{len(messages)} 條訊息 (長度: {len(msg)})")
                
                if i < len(messages) - 1:  # 不是最後一條訊息
                    time.sleep(0.3)  # 訊息間間隔
                    
            except Exception as e:
                logging.error(f"發送第{i+1}條訊息失敗 (長度: {len(msg)}): {e}")
                
                # 如果是長度問題，嘗試發送簡化版本
                if "Length must be between" in str(e) and len(msg) > 3000:
                    try:
                        simple_msg = f"🎙️ 錄音已處理完成！\n\n📊 文字長度: {text_length} 字\n⏱️ 處理時間: {processing_time:.1f}秒"
                        if html_link:
                            simple_msg += f"{html_link}"
                        
                        self._send_push_message(line_api, user_id, simple_msg)
                        logging.info(f"發送簡化版本成功")
                        successful_sends += 1
                        break  # 發送成功後跳出
                    except Exception as e2:
                        logging.error(f"發送簡化版本也失敗: {e2}")
        
        if successful_sends == 0:
            # 所有訊息都失敗，發送最基本的通知
            try:
                basic_msg = f"🎙️ 錄音處理完成\n📊 {text_length}字 / {processing_time:.1f}秒"
                self._send_push_message(line_api, user_id, basic_msg)
                logging.info("發送基本通知成功")
            except Exception as e:
                logging.error(f"連基本通知都失敗: {e}")
        
        logging.info(f"訊息發送完成：{successful_sends}/{len(messages)} 條成功")

    def _split_text_by_sentences(self, text: str, max_length: int) -> list:
        """按句子分割文字，盡量保持完整性"""
        if len(text) <= max_length:
            return [text]
        
        # 按句號、問號、驚嘆號分割
        sentences = []
        current = ""
        
        for char in text:
            current += char
            if char in "。！？\n" and len(current) > 50:  # 避免過短的句子
                sentences.append(current.strip())
                current = ""
        
        if current.strip():
            sentences.append(current.strip())
        
        # 組合句子到合適的長度
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= max_length:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text[:max_length]]

    def _send_push_message(self, line_api: MessagingApi, user_id: str, text: str):
        """發送推送訊息"""
        try:
            line_api.push_message(PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=text)]
            ))
        except Exception as e:
            logging.error(f"推送訊息失敗: {e}")
            raise

    def _handle_text_message(self, event):
        """處理文字訊息"""
        line_api = MessagingApi(ApiClient(self.configuration))
        user_text = event.message.text

        if user_text.startswith("測試"):
            try:
                summary = self.gemini_service.generate_summary("這是一個測試文字")
                self._safe_reply(line_api, event.reply_token, [
                    TextMessage(text=f"✅ 測試成功！摘要：{summary}")
                ])
            except Exception as e:
                self._safe_reply(line_api, event.reply_token, [
                    TextMessage(text=f"❌ 測試失敗：{e}")
                ])
        elif user_text.startswith("狀態"):
            # 系統狀態查詢
            status_info = self._get_system_status()
            self._safe_reply(line_api, event.reply_token, [
                TextMessage(text=status_info)
            ])
        else:
            help_text = ("🎙️ 請傳送錄音，我會轉換成逐字稿並整理重點。\n\n"
                         "💡 指令：\n• 「測試」- 測試AI功能\n• 「狀態」- 查看系統狀態")
            self._safe_reply(line_api, event.reply_token, [TextMessage(text=help_text)])

    def _get_system_status(self) -> str:
        """獲取系統狀態"""
        with self.processing_status.lock:
            processing_count = len(self.processing_status.processing_messages)
            completed_count = len(self.processing_status.completed_messages)
        
        with self.summary_storage.lock:
            summary_count = len(self.summary_storage.summaries)

        return (f"📊 系統狀態\n"
                f"• 處理中訊息: {processing_count}\n"
                f"• 已完成訊息: {completed_count}\n"
                f"• 已存儲摘要: {summary_count}\n"
                f"• 線程池大小: {self.config.max_workers}\n"
                f"• FFmpeg: {'✅' if self.audio_service.check_ffmpeg() else '❌'}\n"
                f"• API金鑰數量: {len(self.config.google_api_keys)}\n"
                f"• 完整分析: {'✅ 啟用' if self.config.full_analysis else '❌ 智能選取'}\n"
                f"• 最大分析段數: {self.config.max_segments_for_full_analysis}\n"
                f"• HTML美化顯示: ✅ 已啟用")

    def _safe_reply(self, line_api: MessagingApi, reply_token: str, messages: List[TextMessage]):
        """安全回覆"""
        try:
            line_api.reply_message(ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            ))
        except Exception as e:
            logging.error(f"回覆訊息失敗: {e}")
            # 如果reply token失效，記錄詳細錯誤但不拋出異常
            if "Invalid reply token" in str(e):
                logging.warning(f"Reply token 已失效或過期: {reply_token}")
            else:
                logging.error(f"其他回覆錯誤: {e}") 