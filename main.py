import os
import logging
import tempfile
import uuid
import subprocess
import time
import asyncio
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Optional, Union, Dict, Set
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
import markdown

from dotenv import load_dotenv
from flask import Flask, request, abort, jsonify, render_template_string
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, ReplyMessageRequest, \
    TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent, AudioMessageContent, FileMessageContent
import openai
from google import genai
from google.genai import types
import requests

# 載入環境變數
load_dotenv()


# 摘要存儲管理器
class SummaryStorage:
    """摘要存儲管理器"""
    
    def __init__(self):
        self.summaries: Dict[str, Dict] = {}
        self.lock = threading.Lock()
    
    def store_summary(self, user_id: str, transcribed_text: str, summary_text: str, 
                     processing_time: float, text_length: int) -> str:
        """存儲摘要並返回ID"""
        with self.lock:
            summary_id = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:12]
            
            self.summaries[summary_id] = {
                'user_id': user_id,
                'transcribed_text': transcribed_text,
                'summary_text': summary_text,
                'processing_time': processing_time,
                'text_length': text_length,
                'created_at': datetime.now(),
                'estimated_minutes': text_length / 180
            }
            
            return summary_id
    
    def get_summary(self, summary_id: str) -> Optional[Dict]:
        """獲取摘要"""
        with self.lock:
            return self.summaries.get(summary_id)
    
    def cleanup_old_summaries(self, hours: int = 24):
        """清理舊摘要"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            expired_ids = [
                sid for sid, info in self.summaries.items()
                if info['created_at'] < cutoff_time
            ]
            
            for sid in expired_ids:
                del self.summaries[sid]
            
            if expired_ids:
                logging.info(f"清理了 {len(expired_ids)} 個過期摘要")


# 處理狀態管理
class ProcessingStatus:
    """處理狀態管理器"""

    def __init__(self):
        self.processing_messages: Dict[str, Dict] = {}
        self.completed_messages: Set[str] = set()
        self.lock = threading.Lock()

    def is_processing(self, message_id: str) -> bool:
        """檢查訊息是否正在處理中"""
        with self.lock:
            return message_id in self.processing_messages

    def is_completed(self, message_id: str) -> bool:
        """檢查訊息是否已完成處理"""
        with self.lock:
            return message_id in self.completed_messages

    def start_processing(self, message_id: str, user_id: str) -> bool:
        """開始處理訊息，如果已在處理中則返回False"""
        with self.lock:
            if message_id in self.processing_messages or message_id in self.completed_messages:
                return False

            self.processing_messages[message_id] = {
                'user_id': user_id,
                'start_time': datetime.now(),
                'status': 'started'
            }
            return True

    def update_status(self, message_id: str, status: str):
        """更新處理狀態"""
        with self.lock:
            if message_id in self.processing_messages:
                self.processing_messages[message_id]['status'] = status
                self.processing_messages[message_id]['update_time'] = datetime.now()

    def complete_processing(self, message_id: str, success: bool = True):
        """完成處理"""
        with self.lock:
            if message_id in self.processing_messages:
                del self.processing_messages[message_id]
            self.completed_messages.add(message_id)

    def cleanup_old_records(self, hours: int = 24):
        """清理舊記錄"""
        with self.lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            # 清理超時的處理中訊息
            expired_processing = []
            for msg_id, info in self.processing_messages.items():
                if info['start_time'] < cutoff_time:
                    expired_processing.append(msg_id)

            for msg_id in expired_processing:
                del self.processing_messages[msg_id]

            # 保持completed_messages在合理大小內（最近1000條）
            if len(self.completed_messages) > 1000:
                # 簡單的FIFO清理，實際生產環境可能需要更精細的策略
                excess = len(self.completed_messages) - 800
                completed_list = list(self.completed_messages)
                for i in range(excess):
                    self.completed_messages.discard(completed_list[i])


@dataclass
class AppConfig:
    line_channel_access_token: str
    line_channel_secret: str
    openai_api_key: str
    google_api_keys: List[str]
    whisper_model: str = "whisper-1"
    gemini_model: str = "gemini-2.5-flash-preview-05-20"
    thinking_budget: int = 512
    max_retries: int = 3
    temp_dir: str = tempfile.gettempdir()
    max_workers: int = 4  # 線程池大小
    webhook_timeout: int = 25  # webhook 處理超時時間（秒）
    long_audio_threshold: int = 120  # 長音訊門檻值（秒）
    max_audio_size_mb: int = 100  # 最大音訊檔案大小（MB）
    segment_processing_delay: float = 0.5  # 分段處理間隔（秒）
    full_analysis: bool = True  # 是否進行完整分析（分析所有段落）
    max_segments_for_full_analysis: int = 50  # 完整分析時的最大段落數

    @classmethod
    def from_env(cls) -> 'AppConfig':
        """從環境變數創建配置"""
        required_vars = {
            'line_channel_access_token': os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
            'line_channel_secret': os.getenv("LINE_CHANNEL_SECRET"),
            'openai_api_key': os.getenv("OPENAI_API_KEY")
        }

        missing_vars = [k for k, v in required_vars.items() if not v]
        if missing_vars:
            raise ValueError(f"缺少必要的環境變數: {', '.join(missing_vars)}")

        google_api_keys = []
        for i in range(1, 11):
            key = os.getenv(f"GOOGLE_API_KEY_{i}")
            if key:
                google_api_keys.append(key)

        if not google_api_keys:
            single_key = os.getenv("GOOGLE_API_KEY")
            if single_key:
                google_api_keys.append(single_key)

        if not google_api_keys:
            raise ValueError("請設定至少一個 GOOGLE_API_KEY")

        return cls(
            line_channel_access_token=required_vars['line_channel_access_token'],
            line_channel_secret=required_vars['line_channel_secret'],
            openai_api_key=required_vars['openai_api_key'],
            google_api_keys=google_api_keys,
            whisper_model=os.getenv("WHISPER_MODEL_NAME", "whisper-1"),
            gemini_model=os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-preview-05-20"),
            thinking_budget=int(os.getenv("THINKING_BUDGET", "256")),  # 降低預設值
            max_retries=int(os.getenv("MAX_RETRIES", "2")),  # 降低重試次數
            max_workers=int(os.getenv("MAX_WORKERS", "4")),
            webhook_timeout=int(os.getenv("WEBHOOK_TIMEOUT", "25")),
            full_analysis=os.getenv("FULL_ANALYSIS", "true").lower() == "true",
            max_segments_for_full_analysis=int(os.getenv("MAX_SEGMENTS_FOR_FULL_ANALYSIS", "50"))
        )


class AudioProcessingError(Exception):
    pass


class APIError(Exception):
    pass


class TempFileManager:
    def __init__(self, temp_dir: str):
        self.temp_dir = temp_dir
        self.created_files: List[str] = []

    def create_temp_file(self, suffix: str = "") -> str:
        temp_file = os.path.join(self.temp_dir, f"{uuid.uuid4()}{suffix}")
        self.created_files.append(temp_file)
        return temp_file

    def cleanup(self):
        for file_path in self.created_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logging.warning(f"清理檔案失敗: {file_path}, 錯誤: {e}")
        self.created_files.clear()


class AudioService:
    @staticmethod
    def check_ffmpeg() -> bool:
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5  # 降低超時時間
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def convert_audio(input_file: str, output_file: str, max_duration_hours: int = 4) -> bool:
        try:
            # 檢查檔案大小
            file_size_mb = os.path.getsize(input_file) / (1024 * 1024)
            logging.info(f"音訊檔案大小: {file_size_mb:.1f}MB")
            
            # 根據檔案大小調整超時時間
            if file_size_mb > 50:
                timeout = 300  # 5分鐘
                logging.info("大檔案處理，延長轉換超時時間至5分鐘")
            elif file_size_mb > 20:
                timeout = 120  # 2分鐘
            else:
                timeout = 60   # 1分鐘
            
            # 優化音訊轉換：降低質量以減少檔案大小和處理時間
            cmd = [
                "ffmpeg", "-i", input_file,
                "-ar", "16000",  # 降低採樣率到16kHz（Whisper推薦）
                "-ac", "1",      # 轉換為單聲道
                "-ab", "64k",    # 降低位元率
                "-y", output_file,
                "-loglevel", "error"
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout
            )
            
            if result.returncode == 0:
                output_size_mb = os.path.getsize(output_file) / (1024 * 1024)
                logging.info(f"轉換完成，輸出檔案大小: {output_size_mb:.1f}MB")
                return True
            else:
                logging.error(f"FFmpeg 錯誤: {result.stderr.decode()}")
                return False
                
        except subprocess.TimeoutExpired:
            logging.error(f"音訊轉換超時（{timeout}秒）")
            return False
        except Exception as e:
            logging.error(f"轉換音訊時發生錯誤: {e}")
            return False


class AIService:
    def __init__(self, config: AppConfig):
        self.config = config
        self.openai_client = openai
        self.openai_client.api_key = config.openai_api_key
        self.genai_clients = [genai.Client(api_key=key) for key in config.google_api_keys]
        self.current_genai_index = 0

    def transcribe_audio(self, audio_file_path: str) -> str:
        """使用Whisper轉換語音為文字 - 優化版本"""
        try:
            start_time = time.time()
            
            # 檢查檔案大小，如果超過25MB則警告
            file_size = os.path.getsize(audio_file_path)
            if file_size > 25 * 1024 * 1024:  # 25MB
                logging.warning(f"音訊檔案較大: {file_size / (1024*1024):.1f}MB，處理時間可能較長")
            
            with open(audio_file_path, "rb") as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model=self.config.whisper_model,
                    file=audio_file,
                    language="zh",
                    response_format="text",  # 直接返回文字，減少處理時間
                    prompt="以下是中文語音內容，請準確轉錄："  # 添加提示提高準確性
                )

            processing_time = time.time() - start_time
            logging.info(f"Whisper 處理時間: {processing_time:.2f}秒")

            result = transcript.strip() if isinstance(transcript, str) else transcript.text.strip()
            logging.info(f"轉錄文字長度: {len(result)} 字符")
            
            return result
        except openai.APIError as e:
            if "insufficient_quota" in str(e):
                raise APIError("OpenAI API 配額不足")
            elif "rate_limit" in str(e):
                raise APIError("API 請求過於頻繁")
            else:
                raise APIError(f"OpenAI API 錯誤: {e}")

    def generate_summary(self, text: str) -> str:
        """生成文字摘要 - 超長錄音智能處理版本"""
        start_time = time.time()

        try:
            text_length = len(text)
            logging.info(f"開始處理文字摘要，長度: {text_length} 字符")

            # 估算錄音時長（粗略估算：每分鐘約150-200字）
            estimated_minutes = text_length / 180
            
            if text_length <= 1500:
                # 短錄音（<10分鐘）：完整摘要
                return self._generate_complete_summary(text)
            elif text_length <= 5000:
                # 中等錄音（10-30分鐘）：重點摘要
                return self._generate_focused_summary(text)
            elif text_length <= 15000:
                # 長錄音（30分鐘-1.5小時）：結構化摘要
                return self._generate_structured_summary(text)
            else:
                # 超長錄音（>1.5小時）：分段式摘要
                return self._generate_segmented_summary(text, estimated_minutes)

        except Exception as e:
            processing_time = time.time() - start_time
            logging.error(f"Gemini 處理失敗 (耗時{processing_time:.2f}秒): {e}")
            return "摘要功能暫時無法使用，但錄音轉文字成功。"

    def _generate_complete_summary(self, text: str) -> str:
        """完整摘要（短錄音）"""
        prompt = f"請將以下錄音內容整理成重點摘要：\n\n{text}"
        
        config = types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=60000,
            top_p=0.8,
            top_k=10
        )
        
        response = self._call_gemini_with_rotation(prompt, config)
        return self._extract_response_text(response, text)

    def _generate_focused_summary(self, text: str) -> str:
        """重點摘要（中等錄音）"""
        try:
            logging.info("使用重點摘要模式處理中等長度錄音")
            prompt = f"請將以下錄音內容整理成重點摘要，突出主要觀點和關鍵資訊：\n\n{text}"
            
            config = types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=60000,
                top_p=0.8,
                top_k=10
            )
            
            response = self._call_gemini_with_rotation(prompt, config)
            result = self._extract_response_text(response, text)
            
            logging.info(f"重點摘要生成成功，長度: {len(result)} 字符")
            return result
            
        except Exception as e:
            logging.error(f"重點摘要生成失敗: {e}")
            # 如果失敗，嘗試更簡單的處理方式
            return self._generate_simple_focused_summary(text)

    def _generate_structured_summary(self, text: str) -> str:
        """結構化摘要（長錄音）"""
        # 將文字分成3段進行分析
        length = len(text)
        segment1 = text[:length//3]
        segment2 = text[length//3:2*length//3]
        segment3 = text[2*length//3:]
        
        prompt = f"""請分析以下較長錄音的內容，提供結構化摘要：

【前段內容】
{segment1[:2000]}

【中段內容】
{segment2[:2000]}

【後段內容】 
{segment3[:2000]}

請提供：
1. 主要主題
2. 重點內容
3. 關鍵結論
4. 重要細節"""

        config = types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=60000,
            top_p=0.8,
            top_k=10
        )
        
        response = self._call_gemini_with_rotation(prompt, config)
        result = self._extract_response_text(response, text, structured=True)
        
        return f"{result}\n\n📊 錄音時長：約 {len(text)/180:.0f} 分鐘"

    def _generate_segmented_summary(self, text: str, estimated_minutes: float) -> str:
        """分段式摘要（超長錄音）"""
        try:
            # 將文字分成多個段落，每段約3000字
            segments = []
            chunk_size = 3000
            for i in range(0, len(text), chunk_size):
                segment = text[i:i+chunk_size]
                segments.append(segment)
            
            logging.info(f"超長錄音分為 {len(segments)} 段處理")
            
            # 根據配置決定是否進行完整分析
            if self.config.full_analysis:
                # 完整分析所有段落
                if len(segments) <= self.config.max_segments_for_full_analysis:
                    key_segments = segments
                    analysis_note = f"（完整分析 {len(segments)} 段）"
                    logging.info(f"進行完整分析，處理 {len(segments)} 段")
                else:
                    # 如果段落數超過限制，進行警告但仍盡可能分析更多
                    key_segments = segments[:self.config.max_segments_for_full_analysis]
                    analysis_note = f"（因段落過多，已分析前 {len(key_segments)} 段，共 {len(segments)} 段）"
                    logging.warning(f"段落數 {len(segments)} 超過限制 {self.config.max_segments_for_full_analysis}，只分析前 {len(key_segments)} 段")
            else:
                # 智能選取關鍵段落（原有邏輯）
                if len(segments) > 10:
                    # 取開頭3段、中間2段、結尾3段
                    key_segments = segments[:3] + segments[len(segments)//2-1:len(segments)//2+1] + segments[-3:]
                    analysis_note = f"（智能選取：已從 {len(segments)} 段中選取 {len(key_segments)} 個關鍵段落分析）"
                else:
                    key_segments = segments[:6]  # 最多處理前6段
                    analysis_note = f"（共 {len(segments)} 段，已分析前 {len(key_segments)} 段）"
            
            # 生成分段摘要
            segment_summaries = []
            total_segments = len(key_segments)
            
            # 如果是完整分析且段落很多，發送進度通知
            if self.config.full_analysis and total_segments > 20:
                logging.info(f"開始完整分析 {total_segments} 段，預計需要 {total_segments * 0.5:.0f} 秒")
            
            for i, segment in enumerate(key_segments):
                try:
                    # 動態調整段落標記（如果是智能選取，使用原始段落號）
                    if self.config.full_analysis or len(segments) <= 10:
                        segment_label = f"第{i+1}段"
                    else:
                        # 智能選取模式，計算原始段落號
                        if i < 3:
                            segment_number = i + 1
                        elif i < 5:
                            segment_number = len(segments)//2 + (i - 3)
                        else:
                            segment_number = len(segments) - (7 - i)
                        segment_label = f"第{segment_number}段"
                    
                    prompt = f"請簡潔總結以下錄音片段的重點（{segment_label}）：\n\n{segment[:2000]}"
                    
                    config = types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=10000,
                        top_p=0.8,
                        top_k=5
                    )
                    
                    response = self._call_gemini_with_rotation(prompt, config)
                    if response and response.candidates:
                        summary = response.text.strip()
                        segment_summaries.append(f"【{segment_label}】{summary}")
                    
                    # 記錄處理進度
                    if (i + 1) % 10 == 0:
                        logging.info(f"已完成 {i + 1}/{total_segments} 段分析")
                    
                    time.sleep(self.config.segment_processing_delay)  # 使用配置的延遲時間
                    
                except Exception as e:
                    logging.warning(f"處理{segment_label}時出錯: {e}")
                    segment_summaries.append(f"【{segment_label}】處理失敗")
            
            # 生成總體摘要
            combined_summary = "\n\n".join(segment_summaries)
            
            final_prompt = f"""基於以下分段摘要，請提供整體重點總結：

{combined_summary}

請提供：
1. 主要議題和主題
2. 核心觀點和結論
3. 重要決定或行動項目"""

            config = types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=60000,
                top_p=0.8,
                top_k=10
            )
            
            final_response = self._call_gemini_with_rotation(final_prompt, config)
            final_summary = self._extract_response_text(final_response, text, structured=True)
            
            # 組合最終結果
            result = f"🎯 【整體摘要】\n{final_summary}\n\n📝 【分段重點】\n{combined_summary}\n\n"
            result += f"⏱️ 錄音時長：約 {estimated_minutes:.0f} 分鐘 ({len(text)} 字)\n"
            result += f"📊 分析說明：{analysis_note}"
            
            return result
            
        except Exception as e:
            logging.error(f"分段摘要處理失敗: {e}")
            return self._generate_fallback_summary(text, estimated_minutes)

    def _generate_fallback_summary(self, text: str, estimated_minutes: float) -> str:
        """備用摘要（當分段處理失敗時）"""
        # 只取開頭和結尾進行摘要
        start_text = text[:2000]
        end_text = text[-2000:] if len(text) > 4000 else ""
        
        summary_text = f"開頭：{start_text}"
        if end_text:
            summary_text += f"\n\n結尾：{end_text}"
        
        prompt = f"這是一個約 {estimated_minutes:.0f} 分鐘的長錄音的開頭和結尾部分，請提供基本摘要：\n\n{summary_text}"
        
        try:
            config = types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=30000,
                top_p=0.8,
                top_k=5
            )
            
            response = self._call_gemini_with_rotation(prompt, config)
            result = self._extract_response_text(response, text)
            
            return f"{result}\n\n⚠️ 因錄音過長，此為簡化摘要\n⏱️ 錄音時長：約 {estimated_minutes:.0f} 分鐘"
            
        except Exception as e:
            logging.error(f"備用摘要也失敗: {e}")
            return f"✅ 錄音轉文字成功\n⏱️ 錄音時長：約 {estimated_minutes:.0f} 分鐘 ({len(text)} 字)\n📝 因內容過長，摘要功能暫時無法使用，請查看完整逐字稿"

    def _extract_response_text(self, response, original_text: str, structured: bool = False) -> str:
        """提取回應文字並處理各種狀況"""
        if not response or not response.candidates:
            logging.warning("Gemini 回應無內容或無候選項")
            raise APIError("無法生成摘要回應")
        
        candidate = response.candidates[0]
        finish_reason = str(candidate.finish_reason)
        
        logging.info(f"Gemini 回應狀態: {finish_reason}")
        
        if "STOP" in finish_reason:
            result = response.text.strip()
            logging.info(f"摘要生成成功，長度: {len(result)} 字符")
            return result
        elif "SAFETY" in finish_reason:
            return "⚠️ 內容可能包含敏感資訊，無法產生摘要"
        elif "MAX_TOKEN" in finish_reason or "LENGTH" in finish_reason:
            logging.warning(f"Token 限制觸發: {finish_reason}")
            # 如果是結構化處理，嘗試返回部分結果
            if structured and response.text:
                return f"{response.text.strip()}\n\n⚠️ 摘要因長度限制可能不完整"
            else:
                # 對於中等長度錄音，嘗試簡化處理
                raise APIError(f"內容過長需要簡化處理: {finish_reason}")
        else:
            logging.warning(f"未知的完成狀態: {finish_reason}")
            if response.text and len(response.text.strip()) > 0:
                return f"{response.text.strip()}\n\n⚠️ 摘要可能不完整（{finish_reason}）"
            else:
                raise APIError(f"摘要生成異常: {finish_reason}")

    def _generate_simple_focused_summary(self, text: str) -> str:
        """簡化版重點摘要（中等錄音備用方案）"""
        try:
            logging.info("使用簡化版重點摘要")
            # 分段處理，每段2000字符
            chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
            
            summaries = []
            for i, chunk in enumerate(chunks[:3]):  # 最多處理前3段
                try:
                    prompt = f"請簡潔總結以下內容的重點：\n\n{chunk}"
                    
                    config = types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=20000,
                        top_p=0.8,
                        top_k=5
                    )
                    
                    response = self._call_gemini_with_rotation(prompt, config)
                    if response and response.candidates and "STOP" in str(response.candidates[0].finish_reason):
                        summaries.append(response.text.strip())
                    
                    time.sleep(0.3)  # 短暫延遲
                    
                except Exception as e:
                    logging.warning(f"處理第{i+1}段簡化摘要失敗: {e}")
                    continue
            
            if summaries:
                result = "\n\n".join(summaries)
                if len(chunks) > 3:
                    result += f"\n\n💡 註：已摘要前3段內容，總共{len(chunks)}段"
                return result
            else:
                return self._generate_short_summary(text[:1000])
                
        except Exception as e:
            logging.error(f"簡化版重點摘要失敗: {e}")
            return self._generate_short_summary(text[:1000])

    def _generate_short_summary(self, text: str) -> str:
        """生成簡短摘要（備用方案）"""
        try:
            logging.info("使用簡短摘要模式")
            prompt = f"請用最簡潔的方式總結以下內容的主要重點（限100字內）：\n\n{text[:1000]}"
            
            config = types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=20000,
                top_p=0.8,
                top_k=5
            )

            response = self._call_gemini_with_rotation(prompt, config)
            
            if response and response.candidates and "STOP" in str(response.candidates[0].finish_reason):
                return f"{response.text.strip()}\n\n⚠️ 因處理限制，此為簡化摘要"
            else:
                return "✅ 錄音轉文字成功\n📝 內容較長，建議查看完整逐字稿"
                
        except Exception as e:
            logging.error(f"簡短摘要也失敗: {e}")
            return "✅ 錄音轉文字成功\n📝 摘要功能暫時無法使用，請查看完整逐字稿"

    def _call_gemini_with_rotation(self, prompt: str, config: types.GenerateContentConfig):
        """快速輪詢API金鑰，只嘗試一次"""
        client = self.genai_clients[self.current_genai_index]
        try:
            response = client.models.generate_content(
                model=self.config.gemini_model,
                contents=prompt,
                config=config
            )
            return response
        except Exception as e:
            logging.warning(f"Gemini API 金鑰 {self.current_genai_index + 1} 失敗: {e}")
            # 切換到下一個金鑰供下次使用
            self.current_genai_index = (self.current_genai_index + 1) % len(self.genai_clients)
            raise APIError(f"Gemini API 調用失敗: {e}")


class AsyncLineBotService:
    """異步處理的LINE Bot服務"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.configuration = Configuration(access_token=config.line_channel_access_token)
        self.handler = WebhookHandler(config.line_channel_secret)
        self.ai_service = AIService(config)
        self.audio_service = AudioService()
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

            # 3. 語音轉文字
            self.processing_status.update_status(message_id, "transcribing")
            transcribed_text = self.ai_service.transcribe_audio(mp3_file)

            if not transcribed_text:
                raise AudioProcessingError("無法辨識語音內容")

            # 4. 生成摘要（非阻塞，失敗也不影響主要功能）
            self.processing_status.update_status(message_id, "summarizing")
            try:
                summary_text = self.ai_service.generate_summary(transcribed_text)
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
        """發送最終結果"""
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
                # 假設部署在 localhost:5001，實際使用時應該用真實域名
                html_link = f"\n\n🌐 美化顯示：https://chatbot.audiweb.uk/summary/{summary_id}"
                logging.info(f"生成摘要頁面: {summary_id}")
            except Exception as e:
                logging.error(f"生成摘要頁面失敗: {e}")
        
        if is_summary_failed:
            # 摘要失敗時，確保提供完整轉錄文字
            reply_text = f"🎙️ 錄音轉文字：\n{transcribed_text}\n\n📝 摘要狀態：\n{summary_text}{length_info}{time_info}"
        else:
            reply_text = f"🎙️ 錄音轉文字：\n{transcribed_text}\n\n📝 重點摘要：\n{summary_text}{length_info}{time_info}{html_link}"

        # 分割長訊息（更智能的分割）
        if len(reply_text) > 4500:
            # 第一條：轉錄文字
            messages = [f"🎙️ 錄音轉文字：\n{transcribed_text}"]
            
            # 第二條：摘要和統計
            if is_summary_failed:
                messages.append(f"📝 摘要狀態：\n{summary_text}{length_info}{time_info}")
            else:
                messages.append(f"📝 重點摘要：\n{summary_text}{length_info}{time_info}{html_link}")
        else:
            messages = [reply_text]

        # 發送訊息
        for i, msg in enumerate(messages):
            try:
                self._send_push_message(line_api, user_id, msg)
                if i < len(messages) - 1:  # 不是最後一條訊息
                    time.sleep(0.2)  # 訊息間間隔
            except Exception as e:
                logging.error(f"發送第{i+1}條訊息失敗: {e}")
                # 即使某條訊息失敗，也繼續發送其他訊息

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
                summary = self.ai_service.generate_summary("這是一個測試文字")
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


def create_app() -> Flask:
    """創建Flask應用"""
    try:
        config = AppConfig.from_env()
    except ValueError as e:
        logging.error(f"配置錯誤: {e}")
        exit(1)

    app = Flask(__name__)

    # 設定日誌
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 創建異步LINE Bot服務
    linebot_service = AsyncLineBotService(config)

    @app.route("/", methods=['GET'])
    def home():
        """首頁"""
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>異步LINE Bot 錄音助手</title>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; }}
                .status {{ padding: 15px; margin: 10px 0; border-radius: 5px; background-color: #e3f2fd; color: #1565c0; }}
                .improvement {{ padding: 15px; margin: 10px 0; border-radius: 5px; background-color: #e8f5e8; color: #2e7d32; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 異步LINE Bot 錄音助手</h1>

                <div class="improvement">
                    <h3>🚀 超高性能優化</h3>
                    <ul>
                        <li>💪 極限輸出：60,000 tokens 最大摘要長度</li>
                        <li>🌐 HTML美化：markdown 格式完美顯示</li>
                        <li>🔄 異步處理：避免重複訊息問題</li>
                        <li>⚡ 快速回應：立即確認收到錄音</li>
                        <li>📊 狀態管理：智能處理重複請求</li>
                        <li>⏱️ 超時保護：25秒內必定有回應</li>
                        <li>🧵 多線程：支援同時處理多個請求</li>
                        <li>📝 詳盡摘要：支援超長錄音完整分析</li>
                        <li>🎨 美化頁面：專業級摘要展示體驗</li>
                    </ul>
                </div>

                <div class="status">
                    <h3>📊 系統設定</h3>
                    <p><strong>服務時間：</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                    <p><strong>最大工作線程：</strong> {config.max_workers}</p>
                    <p><strong>Webhook超時：</strong> {config.webhook_timeout}秒</p>
                    <p><strong>思考預算：</strong> {config.thinking_budget} tokens</p>
                    <p><strong>最大重試：</strong> {config.max_retries} 次</p>
                    <p><strong>API金鑰數量：</strong> {len(config.google_api_keys)}</p>
                    <p><strong>完整分析：</strong> {'✅ 啟用' if config.full_analysis else '❌ 智能選取'}</p>
                    <p><strong>最大分析段數：</strong> {config.max_segments_for_full_analysis}</p>
                    
                    <div style="margin-top: 20px; text-align: center;">
                        <a href="/summaries" style="
                            display: inline-block;
                            background: #667eea;
                            color: white;
                            text-decoration: none;
                            padding: 12px 24px;
                            border-radius: 25px;
                            font-weight: bold;
                            transition: background 0.3s;
                        " onmouseover="this.style.background='#5a6fd8'" onmouseout="this.style.background='#667eea'">
                            📚 查看摘要管理
                        </a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        '''

    @app.route("/callback", methods=['POST'])
    def callback():
        """LINE Bot webhook - 優化版本"""
        signature = request.headers['X-Line-Signature']
        body = request.get_data(as_text=True)

        try:
            linebot_service.handler.handle(body, signature)
        except InvalidSignatureError:
            logging.error("Invalid signature")
            abort(400)
        except Exception as e:
            logging.error(f"Webhook處理錯誤: {e}")
            # 即使出錯也要返回200，避免LINE重發

        return 'OK'

    @app.route("/health", methods=['GET'])
    def health_check():
        """健康檢查"""
        with linebot_service.processing_status.lock:
            processing_count = len(linebot_service.processing_status.processing_messages)
            completed_count = len(linebot_service.processing_status.completed_messages)

        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "processing_messages": processing_count,
            "completed_messages": completed_count,
            "max_workers": config.max_workers,
            "ffmpeg_available": AudioService.check_ffmpeg()
        })

    @app.route("/test-gemini", methods=['GET'])
    def test_gemini():
        """測試Gemini API功能"""
        try:
            # 測試AI服務
            test_text = "這是一個測試文字，用來檢查Gemini API是否正常運作。"
            summary = linebot_service.ai_service.generate_summary(test_text)
            
            return jsonify({
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "test_input": test_text,
                "gemini_response": summary,
                "api_keys_count": len(config.google_api_keys)
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "api_keys_count": len(config.google_api_keys)
            }), 500

    @app.route("/summary/<summary_id>", methods=['GET'])
    def view_summary(summary_id):
        """查看美化後的摘要頁面"""
        summary_data = linebot_service.summary_storage.get_summary(summary_id)
        
        if not summary_data:
            return '''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>摘要不存在</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; text-align: center; }
                    .error { color: #d32f2f; }
                </style>
            </head>
            <body>
                <h1 class="error">❌ 摘要不存在或已過期</h1>
                <p>請確認鏈接是否正確，或聯繫管理員。</p>
            </body>
            </html>
            ''', 404
        
        # 將 markdown 轉換為 HTML
        try:
            summary_html = markdown.markdown(
                summary_data['summary_text'],
                extensions=['extra', 'codehilite', 'toc']
            )
        except:
            # 如果 markdown 解析失敗，直接使用原文但處理換行
            summary_html = summary_data['summary_text'].replace('\n', '<br>')
        
        # 同樣處理轉錄文字
        transcribed_html = summary_data['transcribed_text'].replace('\n', '<br>')
        
        # 生成美化的 HTML 頁面
        html_template = '''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>錄音摘要 - {{ created_at }}</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 0;
                    background-color: #f8fafc;
                    color: #2d3748;
                }
                .container {
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }
                .header {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 15px;
                    margin-bottom: 30px;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.1);
                }
                .header h1 {
                    margin: 0;
                    font-size: 2.2em;
                    text-align: center;
                }
                .stats {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                    gap: 15px;
                    margin-top: 20px;
                }
                .stat-item {
                    background: rgba(255,255,255,0.2);
                    padding: 15px;
                    border-radius: 10px;
                    text-align: center;
                }
                .stat-value {
                    font-size: 1.5em;
                    font-weight: bold;
                    display: block;
                }
                .section {
                    background: white;
                    padding: 30px;
                    margin-bottom: 25px;
                    border-radius: 15px;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.08);
                    border-left: 5px solid #667eea;
                }
                .section h2 {
                    color: #667eea;
                    margin-top: 0;
                    font-size: 1.5em;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }
                .transcribed-text {
                    max-height: 300px;
                    overflow-y: auto;
                    background-color: #f7fafc;
                    padding: 20px;
                    border-radius: 10px;
                    border: 1px solid #e2e8f0;
                    font-family: 'Courier New', monospace;
                    line-height: 1.8;
                }
                .summary-content {
                    font-size: 1.1em;
                    line-height: 1.8;
                }
                .summary-content h1, .summary-content h2, .summary-content h3 {
                    color: #4a5568;
                    margin-top: 25px;
                    margin-bottom: 15px;
                }
                .summary-content h1 { font-size: 1.8em; }
                .summary-content h2 { font-size: 1.5em; }
                .summary-content h3 { font-size: 1.3em; }
                .summary-content strong {
                    color: #2d3748;
                    font-weight: 600;
                }
                .summary-content ul, .summary-content ol {
                    padding-left: 25px;
                }
                .summary-content li {
                    margin-bottom: 8px;
                }
                .summary-content blockquote {
                    border-left: 4px solid #667eea;
                    padding-left: 20px;
                    margin: 20px 0;
                    background-color: #f7fafc;
                    padding: 15px 20px;
                    border-radius: 0 8px 8px 0;
                }
                .footer {
                    text-align: center;
                    padding: 30px;
                    color: #718096;
                    font-size: 0.9em;
                }
                .toggle-btn {
                    background: #667eea;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 25px;
                    cursor: pointer;
                    font-size: 0.9em;
                    margin-bottom: 15px;
                    transition: background 0.3s;
                }
                .toggle-btn:hover {
                    background: #5a6fd8;
                }
                @media (max-width: 600px) {
                    .container { padding: 10px; }
                    .header { padding: 20px; }
                    .section { padding: 20px; }
                    .header h1 { font-size: 1.8em; }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎙️ 錄音摘要報告</h1>
                    <div class="stats">
                        <div class="stat-item">
                            <span class="stat-value">{{ estimated_minutes }}</span>
                            <span>分鐘</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-value">{{ text_length }}</span>
                            <span>字數</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-value">{{ processing_time }}</span>
                            <span>處理時間</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-value">{{ created_date }}</span>
                            <span>創建時間</span>
                        </div>
                    </div>
                </div>

                <div class="section">
                    <h2>📝 智能摘要</h2>
                    <div class="summary-content">
                        {{ summary_html|safe }}
                    </div>
                </div>

                <div class="section">
                    <h2>📄 完整逐字稿</h2>
                    <button class="toggle-btn" onclick="toggleTranscript()">
                        <span id="toggle-text">顯示完整逐字稿</span>
                    </button>
                    <div id="transcript" class="transcribed-text" style="display: none;">
                        {{ transcribed_html|safe }}
                    </div>
                </div>

                <div class="footer">
                    <p>💡 此摘要由 AI 自動生成，保存時間為24小時</p>
                    <p>🤖 powered by Gemini AI & Whisper</p>
                </div>
            </div>

            <script>
                function toggleTranscript() {
                    const transcript = document.getElementById('transcript');
                    const toggleText = document.getElementById('toggle-text');
                    
                    if (transcript.style.display === 'none') {
                        transcript.style.display = 'block';
                        toggleText.textContent = '隱藏完整逐字稿';
                    } else {
                        transcript.style.display = 'none';
                        toggleText.textContent = '顯示完整逐字稿';
                    }
                }
            </script>
        </body>
        </html>
        '''
        
        return render_template_string(
            html_template,
            summary_html=summary_html,
            transcribed_html=transcribed_html,
            estimated_minutes=f"{summary_data['estimated_minutes']:.1f}",
            text_length=summary_data['text_length'],
            processing_time=f"{summary_data['processing_time']:.1f}s",
            created_date=summary_data['created_at'].strftime('%m/%d'),
            created_at=summary_data['created_at'].strftime('%Y-%m-%d %H:%M')
        )

    @app.route("/summaries", methods=['GET'])
    def list_summaries():
        """摘要列表頁面"""
        with linebot_service.summary_storage.lock:
            summaries = list(linebot_service.summary_storage.summaries.items())
        
        # 按時間倒序排列
        summaries.sort(key=lambda x: x[1]['created_at'], reverse=True)
        
        html_template = '''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>摘要管理 - LINE Bot 錄音助手</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                    background-color: #f8fafc;
                }
                .container {
                    max-width: 1000px;
                    margin: 0 auto;
                    padding: 20px;
                }
                .header {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 15px;
                    margin-bottom: 30px;
                    text-align: center;
                }
                .summary-card {
                    background: white;
                    padding: 20px;
                    margin-bottom: 15px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    border-left: 4px solid #667eea;
                }
                .summary-meta {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 10px;
                    flex-wrap: wrap;
                    gap: 10px;
                }
                .summary-stats {
                    display: flex;
                    gap: 15px;
                    font-size: 0.9em;
                    color: #666;
                }
                .summary-preview {
                    color: #444;
                    line-height: 1.5;
                    margin: 10px 0;
                }
                .view-btn {
                    background: #667eea;
                    color: white;
                    text-decoration: none;
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-size: 0.9em;
                    transition: background 0.3s;
                }
                .view-btn:hover {
                    background: #5a6fd8;
                }
                .empty-state {
                    text-align: center;
                    padding: 60px 20px;
                    color: #666;
                }
                @media (max-width: 600px) {
                    .summary-meta { flex-direction: column; align-items: flex-start; }
                    .summary-stats { flex-wrap: wrap; }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📚 摘要管理中心</h1>
                    <p>查看和管理所有的錄音摘要</p>
                </div>

                {% if summaries %}
                    {% for summary_id, data in summaries %}
                    <div class="summary-card">
                        <div class="summary-meta">
                            <div class="summary-stats">
                                <span>📅 {{ data.created_at.strftime('%m/%d %H:%M') }}</span>
                                <span>⏱️ {{ "%.1f"|format(data.estimated_minutes) }}分鐘</span>
                                <span>📝 {{ data.text_length }}字</span>
                                <span>⚡ {{ "%.1f"|format(data.processing_time) }}秒</span>
                            </div>
                            <a href="/summary/{{ summary_id }}" class="view-btn">查看詳情</a>
                        </div>
                        <div class="summary-preview">
                            {{ data.summary_text[:200] }}{% if data.summary_text|length > 200 %}...{% endif %}
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="empty-state">
                        <h2>📭 暫無摘要</h2>
                        <p>向 LINE Bot 發送錄音後，摘要會出現在這裡</p>
                    </div>
                {% endif %}
            </div>
        </body>
        </html>
        '''
        
        return render_template_string(html_template, summaries=summaries)

    return app


if __name__ == "__main__":
    app = create_app()

    if not AudioService.check_ffmpeg():
        logging.warning("FFmpeg 不可用")

    # 生產環境設定
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)