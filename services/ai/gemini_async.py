# -*- coding: utf-8 -*-
"""
異步 Google Gemini AI 服務模組。

此模組提供了 `AsyncGeminiService` 類別，用於與 Google Gemini AI 模型進行異步互動。
主要功能包括：
- 生成各種長度文本的摘要 (完整摘要、重點摘要、結構化摘要、分段摘要)。
- 處理 API 金鑰輪換和請求重試機制。
- 提取並標準化 Gemini API 的回應。
- (可選擴展) 文本情感分析、關鍵字提取等。

此服務設計為可配置的，允許透過 `AppConfig` 傳入 API 金鑰、模型名稱等參數。
"""

import logging
import asyncio # 用於異步操作，例如 await asyncio.sleep()
# 在檔案頂部，確保 time 被導入
import time
from typing import Dict, Any, Optional, List
import json
import random
from google import genai
from google.genai import types

from config import AppConfig

logger = logging.getLogger(__name__)


class AsyncGeminiService:
    """異步Google Gemini AI服務"""
    
    def __init__(self, config: AppConfig):
        self.config = config
import time # 導入 time 模組
from typing import Dict, Any, Optional, List
import json
import random # random 未在此檔案直接使用，但保留以備未來擴展
from google import genai
from google.generativeai import types as genai_types # 使用別名以避免與 typing.types 衝突，並更清晰

from config import AppConfig

logger = logging.getLogger(__name__)


class AsyncGeminiService:
    """
    異步 Google Gemini AI 服務類別。

    提供與 Google Gemini 模型互動的方法，主要用於生成文本摘要。
    支持基於文本長度的不同摘要策略，並包含 API 金鑰輪換和重試機制。
    """
    
    def __init__(self, config: AppConfig):
        """
        初始化 AsyncGeminiService。

        Args:
            config (AppConfig): 應用程式的組態設定物件，包含 Google API 金鑰、
                                Gemini 模型名稱、重試次數和延遲等參數。
        
        Raises:
            ValueError: 如果組態中未提供 Google API 金鑰。
        """
        self.config = config
        self.api_keys: List[str] = config.GOOGLE_API_KEYS # 從 AppConfig 獲取 Google API 金鑰列表
        self.model_name: str = config.AI_MODEL_NAME # 從 AppConfig 獲取要使用的 Gemini 模型名稱
        self.max_retries: int = config.AI_MAX_RETRIES # 從 AppConfig 獲取最大重試次數
        self.retry_delay: int = config.AI_RETRY_DELAY_SECONDS # 從 AppConfig 獲取重試延遲秒數
        
        if not self.api_keys:
            logger.error("Google API 金鑰 (GOOGLE_API_KEYS) 未在組態中設定。")
            raise ValueError("Google API 金鑰未設定，無法初始化 AsyncGeminiService。")
        
        # API 金鑰輪換相關初始化
        self.current_api_key_index: int = 0 # 用於 API 金鑰輪換的索引
        # 注意：Google Gemini SDK 通常透過 `genai.configure(api_key="YOUR_API_KEY")` 設定全域金鑰。
        # 為了實現輪換，我們會在 `_call_gemini_with_rotation` 方法中動態設定當前使用的金鑰。
        logger.info(f"AsyncGeminiService 初始化完成，使用模型: {self.model_name}，共 {len(self.api_keys)} 個 API 金鑰。")

    async def generate_summary_async(self, transcript: str) -> str:
        """
        異步生成文字摘要，並根據文本長度智能選擇不同的處理策略。

        Args:
            transcript (str): 需要摘要的原始轉錄文字。

        Returns:
            str: 生成的摘要文字。如果處理失敗，則返回一條對使用者友好的錯誤或提示訊息。
        
        Raises:
            ValueError: 如果輸入的轉錄文字為空。
        """
        start_time = time.time() # 記錄開始時間以計算處理耗時

        try:
            logger.info(f"🤖 開始為 ID 未知的錄音生成 AI 摘要 (文字長度: {len(transcript)})")
            
            if not transcript or not transcript.strip(): # 檢查文字稿是否為空或僅包含空白
                logger.warning("生成摘要請求失敗：提供的轉錄文字為空。")
                raise ValueError("轉錄文字為空，無法生成摘要。")
            
            text_length = len(transcript)
            logger.info(f"開始處理文字摘要，長度: {text_length} 字元。")

            # 根據文本長度選擇不同的摘要策略
            # TODO: 將長度閾值 (例如 3000, 7500, 20000) 移至 AppConfig 中作為可配置參數
            estimated_minutes = text_length / 180 # 粗略估算每分鐘字數 (可調整，例如 150-250)

            if text_length <= 3000:  # 約 15-20 分鐘內的短錄音
                logger.info("採用「完整摘要」策略處理短錄音。")
                summary = await self._generate_complete_summary(transcript)
            elif text_length <= 7500: # 約 20-40 分鐘的中等錄音
                logger.info("採用「重點摘要」策略處理中等長度錄音。")
                summary = await self._generate_focused_summary(transcript)
            elif text_length <= 20000: # 約 40-110 分鐘的長錄音
                logger.info("採用「結構化摘要」策略處理長錄音。")
                summary = await self._generate_structured_summary(transcript)
            else: # 超過約 110 分鐘的超長錄音
                logger.info("採用「分段式摘要」策略處理超長錄音。")
                summary = await self._generate_segmented_summary(transcript, estimated_minutes)
            
            if not summary: # 確保摘要結果非空
                logger.error("AI 摘要生成後返回結果為空。")
                # 即使 _extract_response_text 應處理此情況，多一層防護
                raise Exception("摘要生成失敗，返回結果為空。") 
            
            processing_time = time.time() - start_time
            logger.info(f"✨ AI 摘要生成成功完成，耗時: {processing_time:.2f} 秒。摘要長度: {len(summary)} 字元。")
            return summary
            
        except ValueError as ve: # 捕獲特定的 ValueError (例如空的 transcript)
            logger.error(f"生成摘要時發生數值錯誤: {str(ve)}", exc_info=True)
            return f"摘要生成失敗：輸入內容不正確 ({str(ve)})"
        except Exception as e: # 捕獲所有其他在摘要流程中發生的例外
            processing_time = time.time() - start_time # 計算錯誤時的處理時間
            logger.error(f"❌ 生成 AI 摘要過程中發生未預期錯誤 (耗時 {processing_time:.2f} 秒): {str(e)}", exc_info=True)
            return "抱歉，AI 摘要功能暫時遇到問題。您的文字稿應已保存，請稍後再試或聯繫技術支援。"

    async def _generate_complete_summary(self, text: str) -> str:
        """
        為短文本 (通常 <= 3000 字元) 生成較為完整的摘要。

        Args:
            text (str): 需要摘要的文本。

        Returns:
            str: 生成的完整摘要。
        """
        logger.debug(f"執行「完整摘要」針對長度為 {len(text)} 的文本。")
        prompt = self._build_summary_prompt(text, summary_type="完整摘要")
        
        generation_config = genai_types.GenerationConfig( # 使用 genai_types.GenerationConfig
            temperature=0.2, # 稍微提高一點溫度以獲得更多樣性，但仍保持事實性
            max_output_tokens=8192, # 確保有足夠空間輸出完整摘要 (Gemini Flash 最大到 8192)
            top_p=0.9, # top_p 控制多樣性
            top_k=20  # top_k 控制多樣性
        )
        
        response = await self._call_gemini_with_rotation(prompt, generation_config)
        return self._extract_response_text(response, original_text=text, summary_type_for_log="完整摘要")
    
    async def _generate_focused_summary(self, text: str) -> str:
        """
        為中等長度文本 (通常 > 3000 且 <= 7500 字元) 生成重點摘要。
        如果標準方法失敗，會嘗試使用簡化版本。

        Args:
            text (str): 需要摘要的文本。

        Returns:
            str: 生成的重點摘要。
        """
        try:
            logger.info(f"執行「重點摘要」針對長度為 {len(text)} 的文本。")
            prompt = self._build_summary_prompt(text, summary_type="重點摘要")
            
            generation_config = genai_types.GenerationConfig(
                temperature=0.25, # 中等長度，可以稍微更有彈性
                max_output_tokens=8192,
                top_p=0.85,
                top_k=30
            )
            
            response = await self._call_gemini_with_rotation(prompt, generation_config)
            result = self._extract_response_text(response, original_text=text, summary_type_for_log="重點摘要")
            
            logger.info(f"「重點摘要」生成成功，摘要長度: {len(result)} 字元。")
            return result
            
        except Exception as e:
            logger.error(f"「重點摘要」初步嘗試失敗: {str(e)}。嘗試使用簡化版重點摘要。", exc_info=True)
            return await self._generate_simple_focused_summary(text) # 備用方案
    
    async def _generate_structured_summary(self, text: str) -> str:
        """
        為長文本 (通常 > 7500 且 <= 20000 字元) 生成結構化摘要。
        將文本分成三部分預覽，並要求 AI 提供包含主要議題、重點內容、結論和關鍵字的結構化輸出。

        Args:
            text (str): 需要摘要的文本。

        Returns:
            str: 生成的結構化摘要，包含錄音時長估算。
        """
        logger.info(f"執行「結構化摘要」針對長度為 {len(text)} 的文本。")
        # 預覽文本的前、中、後部分，每部分最多2000字元，以符合 Gemini API 的上下文長度限制和成本效益
        preview_length = 2000 
        length = len(text)
        segment1_preview = text[:preview_length]
        segment2_preview = text[length//2 - preview_length//2 : length//2 + preview_length//2] if length > preview_length * 2 else ""
        segment3_preview = text[-preview_length:] if length > preview_length else "" # 如果文本本身小於 preview_length，則 segment3_preview 會是重複的

        prompt = f"""請分析以下較長錄音的內容，並提供一個詳細且結構化的摘要。
錄音內容預覽如下（可能僅為部分）：

【錄音開頭片段】
{segment1_preview}
...
【錄音中間片段】
{segment2_preview if segment2_preview else "(中間片段省略或與開頭/結尾重疊)"}
...
【錄音結尾片段】
{segment3_preview if segment3_preview else "(結尾片段省略或與開頭重疊)"}

**您的任務是基於對【完整錄音文本】（儘管此處僅展示片段）的理解，來完成以下結構化摘要。**

請嚴格按照以下格式提供詳細的摘要：

## 📝 會議/對話摘要報告

### 🎯 主要議題與目的 (請條列3-5個核心討論點或會議目的，每個議題後需有2-3句的詳細闡述，說明其重要性或背景)
- [議題一：詳細闡述...]
- [議題二：詳細闡述...]

### 📋 詳細內容與討論要點 (請深入說明討論中的重要觀點、論據、數據支持、案例分析或關鍵決策過程，至少5-8個關鍵點，每點需有足夠上下文和細節支撐)
- [內容點一：詳細說明與細節...]
- [內容點二：詳細說明與細節...]

### ✅ 行動項目與決策 (如有，請列出明確的待辦事項、已達成的決策、負責人及預計完成時間或後續步驟)
- [行動項/決策一：(負責人：XXX) (預計完成/狀態：YYYY-MM-DD 或 已完成) 說明...]

### 💡 關鍵洞察與結論 (請總結至少3-5個從討論中獲得的最重要見解、深層結論或反思，並簡述其推導依據或對未來的影響)
- [洞察一：(推導依據或影響：...) 結論說明...]

### 🔑 核心關鍵字 (請提取至少10-15個與內容高度相關的核心關鍵字或關鍵短語，用逗號分隔)
[關鍵字1, 關鍵字2, 關鍵字3, ...]

請務必使用【繁體中文】回應。內容必須詳細、精確且具有良好的組織性。請確保摘要能夠充分反映原始錄音的複雜性和深度。
"""

        generation_config = genai_types.GenerationConfig(
            temperature=0.3, # 結構化輸出，溫度可以稍高一點以獲得更自然的語言
            max_output_tokens=8192,
            top_p=0.85,
            top_k=35
        )
        
        response = await self._call_gemini_with_rotation(prompt, generation_config)
        result = self._extract_response_text(response, original_text=text, is_structured_summary=True, summary_type_for_log="結構化摘要")
        
        estimated_minutes_display = len(text) / 180 
        logger.info(f"「結構化摘要」生成成功，摘要長度: {len(result)} 字元。")
        return f"{result}\n\n📊 錄音時長估算：約 {estimated_minutes_display:.0f} 分鐘"
    
    async def _generate_segmented_summary(self, text: str, estimated_minutes: float) -> str:
        """
        為超長文本 (通常 > 20000 字元) 生成分段式摘要。
        此方法會將文本分割成多個段落，對選取的關鍵段落分別生成摘要，然後再對這些分段摘要進行總結。

        Args:
            text (str): 需要摘要的超長文本。
            estimated_minutes (float): 預估的錄音時長 (分鐘)，用於日誌和最終輸出。

        Returns:
            str: 生成的分段式摘要，包含整體摘要、分段重點、時長估算和分析說明。
        """
        logger.info(f"執行「分段式摘要」針對長度為 {len(text)} 的文本 (預估 {estimated_minutes:.0f} 分鐘)。")
        try:
            segments = [] # 存儲文本片段
            # 考慮到 Gemini API 的上下文視窗和成本效益，每段約 2500-3000 字元較為合適
            chunk_size = getattr(self.config, 'SEGMENT_CHUNK_SIZE', 2800) 
            for i in range(0, len(text), chunk_size):
                segment = text[i:i+chunk_size]
                segments.append(segment)
            
            logger.info(f"超長錄音已分割為 {len(segments)} 段進行處理。")
            
            # 根據組態決定分析哪些段落以及多少段落
            full_analysis = getattr(self.config, 'FULL_ANALYSIS_SEGMENTED', False) # 是否對所有選定段落進行完整分析
            max_segments_to_analyze = getattr(self.config, 'MAX_SEGMENTS_FOR_SEGMENTED_SUMMARY', 7) # 預設最多處理7個選取段落
            
            if full_analysis and len(segments) > max_segments_to_analyze * 1.5 : # 如果段落數遠超限制，即使是完整分析模式也提示
                 logger.warning(f"即使在完整分析模式下，段落數 ({len(segments)}) 也遠超建議處理上限 ({max_segments_to_analyze})，可能導致處理時間過長或成本較高。")

            # 智能選取或限制段落數量
            if len(segments) <= max_segments_to_analyze: # 如果總段落數在限制內，則全部處理
                key_segments_indices = list(range(len(segments)))
                analysis_note = f"（已分析全部 {len(segments)} 段）"
            elif not full_analysis: # 非完整分析模式下的智能選取
                # 策略：選取開頭、中間、結尾的段落，確保覆蓋性
                num_start = min(3, len(segments)) # 開頭最多3段
                num_end = min(3, len(segments) - num_start) # 結尾最多3段
                num_middle = max(0, max_segments_to_analyze - num_start - num_end) # 中間段落填補剩餘名額

                key_segments_indices = list(range(num_start)) # 開頭段落索引
                
                if num_middle > 0 and len(segments) > num_start + num_end: # 確保有足夠段落選取中間部分
                    middle_step = (len(segments) - num_start - num_end) // (num_middle + 1)
                    for i in range(num_middle):
                        key_segments_indices.append(num_start + (i + 1) * middle_step)
                
                if num_end > 0 : # 結尾段落索引
                     key_segments_indices.extend(list(range(len(segments) - num_end, len(segments))))
                
                key_segments_indices = sorted(list(set(key_segments_indices))) # 去重並排序
                analysis_note = f"（智能選取：從 {len(segments)} 段中選取 {len(key_segments_indices)} 個關鍵段落進行分析）"
            else: # 完整分析模式，但超出最大限制
                key_segments_indices = list(range(max_segments_to_analyze))
                analysis_note = f"（因段落過多，已分析前 {max_segments_to_analyze} 段，總共 {len(segments)} 段）"

            key_segments = [segments[i] for i in key_segments_indices]
            logger.info(f"將對 {len(key_segments)} 個選定段落進行摘要。分析說明: {analysis_note}")

            segment_summaries = []
            total_selected_segments = len(key_segments)
            segment_processing_delay = getattr(self.config, 'SEGMENT_PROCESSING_DELAY', 0.6) # 獲取或設定段落處理延遲

            if total_selected_segments > 10: # 如果選定段落較多，提示預期時間
                 logger.info(f"開始分析 {total_selected_segments} 個選定段落，預計需要約 {total_selected_segments * segment_processing_delay * 2:.0f} 秒 (包含API調用和延遲)。")
            
            for i, segment_text in enumerate(key_segments):
                original_segment_index = key_segments_indices[i] # 獲取此片段在原始 segments 列表中的索引
                segment_label = f"原始第 {original_segment_index + 1} 段" # 使用原始段落編號
                
                try:
                    # 提示詞要求對單個片段進行簡潔總結
                    prompt = f"請針對以下【錄音片段】({segment_label})，用繁體中文提煉出其核心要點和關鍵資訊（約100-200字）：\n\n---\n{segment_text[:3000]}\n---\n\n核心要點與關鍵資訊：" # 限制預覽長度
                    
                    generation_config_segment = genai_types.GenerationConfig(
                        temperature=0.15, # 稍高溫度以獲取更自然的片段摘要
                        max_output_tokens=2048, # 足夠片段摘要
                        top_p=0.8,
                        top_k=15
                    )
                    
                    response = await self._call_gemini_with_rotation(prompt, generation_config_segment)
                    # 假設 _extract_response_text 已被更新以處理 is_structured_summary 和 summary_type_for_log
                    summary_text = self._extract_response_text(response, original_text=segment_text, summary_type_for_log=f"片段 {segment_label}")
                    if summary_text: # 確保提取到文本
                        segment_summaries.append(f"【{segment_label}總結】\n{summary_text}")
                    else:
                        segment_summaries.append(f"【{segment_label}總結】\n(此片段未能生成有效摘要)")
                        logger.warning(f"錄音片段 {segment_label} 未能生成有效摘要文本。")

                    if (i + 1) % 5 == 0 or (i + 1) == total_selected_segments: # 每5段或最後一段時記錄進度
                        logger.info(f"分段摘要進度：已完成 {i + 1}/{total_selected_segments} 個選定段落的分析。")
                    
                    if i < total_selected_segments - 1: # 不是最後一個片段時才延遲
                        await asyncio.sleep(segment_processing_delay) 
                    
                except Exception as e_segment:
                    logger.warning(f"處理錄音片段 {segment_label} 時發生錯誤: {str(e_segment)}", exc_info=True)
                    segment_summaries.append(f"【{segment_label}總結】\n(處理此片段時發生錯誤，已跳過)")
            
            combined_segment_summaries = "\n\n---\n\n".join(segment_summaries) # 使用分隔符組合各片段摘要
            
            # 基於所有片段摘要，生成最終的整體摘要
            final_summary_prompt = f"""以下是從一份長篇錄音中提取並分別總結的【多個片段摘要】。請基於這些片段摘要，整合並生成一份連貫、全面的【整體摘要報告】。

【各片段摘要彙總】:
{combined_segment_summaries}

**您的任務是完成以下【整體摘要報告】的各個部分，確保內容的準確性、完整性和邏輯性：**

## 📝 整體摘要報告

### 🎯 主要議題與核心目的 (請綜合所有片段，提煉出3-5個貫穿全文的核心議題或對話的主要目的，並簡述其重要性)
- [核心議題一：重要性簡述...]
- [核心議題二：重要性簡述...]

### 📋 關鍵內容與重要細節 (請整合各片段的關鍵資訊，按主題或邏輯順序歸納，提供至少5-8個重要內容點，並補充必要的上下文或細節)
- [重要內容點一：詳細說明...]
- [重要內容點二：詳細說明...]

### ✅ 主要決策與行動項目 (如有，請明確列出討論中達成的關鍵決策或需要採取的具體行動，包括可能的負責人和時程)
- [決策/行動一：(負責人/時程：...) 說明...]

### 💡 綜合見解與深層結論 (請基於所有片段的分析，提出至少3個具有洞察力的綜合見解或深層結論，並說明其推斷依據或潛在影響)
- [綜合見解一：(依據/影響：...) 結論說明...]

### 🔑 全文核心關鍵字 (請提取10-15個能夠代表整個錄音內容的核心關鍵字或短語，用逗號分隔)
[關鍵字1, 關鍵字2, ...]

請務必使用【繁體中文】進行回應。報告應結構清晰、內容詳實，能夠讓讀者快速掌握長篇錄音的整體情況和核心價值。
"""

            final_generation_config = genai_types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=8192,
                top_p=0.85,
                top_k=40
            )
            
            final_response = await self._call_gemini_with_rotation(final_summary_prompt, final_generation_config)
            final_overall_summary = self._extract_response_text(final_response, original_text=combined_segment_summaries, is_structured_summary=True, summary_type_for_log="分段後整體摘要")
            
            # 組合最終結果
            result = f"✨ **整體摘要報告** ✨\n{final_overall_summary}\n\n---\n\n🔍 **各片段重點回顧** 🔍\n{combined_segment_summaries}\n\n---\n"
            result += f"⏱️ **錄音資訊**：總時長約 {estimated_minutes:.0f} 分鐘 (原始文本約 {len(text)} 字)。\n"
            result += f"📊 **分析方式**：{analysis_note}"
            
            logger.info(f"「分段式摘要」生成成功，整體摘要長度: {len(final_overall_summary)}，分段重點總長度: {len(combined_segment_summaries)}。")
            return result
            
        except Exception as e:
            logger.error(f"「分段式摘要」處理過程中發生嚴重錯誤: {str(e)}。嘗試使用備用摘要方法。", exc_info=True)
            return await self._generate_fallback_summary(text, estimated_minutes) # 備用方案
    
    async def _generate_fallback_summary(self, text: str, estimated_minutes: float) -> str:
        """
        備用摘要生成方法 (當主要的分段處理失敗時調用)。
        此方法僅處理文本的開頭和結尾部分以生成一個非常簡略的摘要。

        Args:
            text (str): 原始文本。
            estimated_minutes (float): 預估的錄音時長。

        Returns:
            str: 生成的備用摘要或進一步的錯誤提示。
        """
        logger.info(f"執行「備用摘要」針對長度為 {len(text)} 的文本 (預估 {estimated_minutes:.0f} 分鐘)。")
        # 只取開頭和結尾進行摘要，預覽長度可調整
        preview_length_fallback = 2000 
        start_text_preview = text[:preview_length_fallback]
        end_text_preview = text[-preview_length_fallback:] if len(text) > preview_length_fallback * 2 else ""
        
        summary_input_text = f"錄音開頭片段：\n{start_text_preview}"
        if end_text_preview:
            summary_input_text += f"\n\n錄音結尾片段：\n{end_text_preview}"
        
        prompt = f"這是一份長約 {estimated_minutes:.0f} 分鐘的錄音，由於內容過長或處理複雜，目前僅能提供基於其開頭和結尾片段的【精簡摘要】。請根據以下提供的片段內容，用繁體中文總結出最重要的核心資訊：\n\n{summary_input_text}"
        
        try:
            generation_config = genai_types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=4096, # 限制輸出以符合備用性質
                top_p=0.8,
                top_k=20
            )
            
            response = await self._call_gemini_with_rotation(prompt, generation_config)
            result_text = self._extract_response_text(response, original_text=summary_input_text, summary_type_for_log="備用摘要")
            
            logger.info(f"「備用摘要」生成成功，摘要長度: {len(result_text)}。")
            return f"## ⚠️ 精簡摘要 (備用方案)\n\n{result_text}\n\n**請注意**：由於原始錄音內容過長或先前處理遇到困難，此為基於部分內容生成的精簡摘要。\n\n⏱️ 錄音總時長約 {estimated_minutes:.0f} 分鐘。"
            
        except Exception as e_fallback:
            logger.error(f"「備用摘要」生成也失敗: {str(e_fallback)}", exc_info=True)
            # 在所有摘要方法都失敗時，返回一個包含原始信息的通用訊息
            return (f"✅ 錄音轉文字已完成。\n"
                    f"⏱️ 錄音總時長約 {estimated_minutes:.0f} 分鐘 (文本長度 {len(text)} 字)。\n"
                    f"📝 抱歉，由於內容過長或技術限制，目前無法自動生成摘要。建議您直接查閱完整的逐字稿內容。")
    
    async def _generate_simple_focused_summary(self, text: str) -> str:
        """
        簡化版的重點摘要方法 (作為中等長度錄音處理的備用方案)。
        將文本分塊，對前面幾塊分別生成簡短摘要後合併。

        Args:
            text (str): 需要摘要的文本。

        Returns:
            str: 生成的簡化版重點摘要，或在失敗時嘗試更短的摘要。
        """
        try:
            logger.info(f"執行「簡化版重點摘要」針對長度為 {len(text)} 的文本。")
            chunk_size_simple = 2000 # 每塊大小
            num_chunks_to_process = 3 # 最多處理的塊數
            chunks = [text[i:i+chunk_size_simple] for i in range(0, len(text), chunk_size_simple)]
            
            summaries = []
            # 僅處理前面幾塊，或直到達到處理上限
            for i, chunk in enumerate(chunks[:num_chunks_to_process]): 
                try:
                    prompt = f"請用繁體中文，簡潔地總結以下內容片段的核心要點 (約 50-100 字)：\n\n---\n{chunk}\n---\n\n核心要點："
                    
                    generation_config_simple = genai_types.GenerationConfig(
                        temperature=0.15,
                        max_output_tokens=1024, # 每段摘要限制輸出
                        top_p=0.8,
                        top_k=10
                    )
                    
                    response = await self._call_gemini_with_rotation(prompt, generation_config_simple)
                    # 假設 _extract_response_text 已被更新
                    chunk_summary = self._extract_response_text(response, original_text=chunk, summary_type_for_log=f"簡化片段 {i+1}")
                    if chunk_summary:
                        summaries.append(f"【片段 {i+1} 要點】\n{chunk_summary}")
                    
                    if i < num_chunks_to_process - 1: # 不是最後一塊時才延遲
                         await asyncio.sleep(self.retry_delay / 2 if self.retry_delay > 0.5 else 0.3) # 短暫延遲

                except Exception as e_chunk:
                    logger.warning(f"處理簡化摘要的第 {i+1} 片段時失敗: {str(e_chunk)}", exc_info=True)
                    continue # 跳過失敗的片段
            
            if summaries:
                result = "\n\n---\n\n".join(summaries)
                if len(chunks) > num_chunks_to_process:
                    result += f"\n\n💡 **提示**：以上為基於文本前 {num_chunks_to_process * chunk_size_simple} 字元（約 {num_chunks_to_process} 個片段）生成的重點摘要。全文共約 {len(chunks)} 個片段。"
                logger.info(f"「簡化版重點摘要」生成成功，合併摘要長度: {len(result)}。")
                return result
            else:
                logger.warning("「簡化版重點摘要」未能從任何片段中生成有效摘要，嘗試最終備用方案 (極簡摘要)。")
                return await self._generate_short_summary(text[:1500]) # 取文本前1500字進行最簡摘要
                
        except Exception as e:
            logger.error(f"「簡化版重點摘要」過程中發生錯誤: {str(e)}。嘗試最終備用方案 (極簡摘要)。", exc_info=True)
            return await self._generate_short_summary(text[:1500]) # 出錯也嘗試極簡摘要

    async def _generate_short_summary(self, text: str) -> str:
        """
        生成非常簡短的摘要 (作為最終的備用方案)。
        主要用於處理前面所有摘要方法都失敗的情況，或文本極短。

        Args:
            text (str): 需要摘要的文本 (通常是原始文本的前一部分，例如前1000-1500字)。

        Returns:
            str: 生成的極簡摘要，或一條提示訊息。
        """
        try:
            logger.info(f"執行「極簡摘要」針對長度為 {len(text)} 的文本。")
            prompt = f"請用繁體中文，以最精簡的方式總結以下內容的核心主題（嚴格限制在 100 字元以內）：\n\n---\n{text[:1500]}\n---\n\n核心主題：" # 限制輸入文本長度
            
            generation_config_short = genai_types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=512, # 限制輸出長度
                top_p=0.7,
                top_k=5
            )

            response = await self._call_gemini_with_rotation(prompt, generation_config_short)
            short_summary_text = self._extract_response_text(response, original_text=text[:1500], summary_type_for_log="極簡摘要")
            
            if short_summary_text:
                 logger.info(f"「極簡摘要」生成成功: {short_summary_text}")
                 return f"## 📝 極簡摘要\n\n{short_summary_text}\n\n**提示**：由於先前處理限制或錯誤，此為基於部分內容生成的極簡摘要。"
            else: # 如果連極簡摘要都失敗
                logger.warning("「極簡摘要」也未能生成有效文本。")
                return ("✅ 錄音轉文字已完成。\n"
                        "📝 抱歉，AI 摘要功能目前無法為此內容生成摘要，建議您直接查閱完整的逐字稿。")
                
        except Exception as e:
            logger.error(f"「極簡摘要」生成也失敗: {str(e)}", exc_info=True)
            return ("✅ 錄音轉文字已完成。\n"
                    "📝 抱歉，AI 摘要功能因技術問題暫時無法使用，請查看完整的逐字稿。")
    
    def _build_summary_prompt(self, transcript: str, summary_type: str = "通用") -> str:
        """
        根據提供的文字稿和摘要類型，構建一個結構化的摘要提示詞 (Prompt)。

        Args:
            transcript (str): 錄音轉錄的完整文字內容。
            summary_type (str, optional): 期望的摘要類型 (例如 "完整摘要", "重點摘要")，
                                          用於微調提示詞內容。預設為 "通用"。

        Returns:
            str: 構建完成的、準備發送給 Gemini API 的提示詞字串。
        """
        logger.debug(f"開始為「{summary_type}」構建摘要提示詞，文字稿長度: {len(transcript)}。")
        # 基礎提示詞結構，強調結構化和詳盡性
        # 針對 Gemini Pro 1.5 Flash 的特性進行優化，它能處理較長的上下文
        # 提示詞中明確要求使用繁體中文
        return f"""
**任務：** 請為以下【{summary_type}】的錄音轉錄內容生成一份詳細、結構化且精確的摘要報告。

**原始轉錄內容：**
---
{transcript}
---

**摘要報告格式要求：**

請嚴格遵循以下 Markdown 格式輸出您的摘要報告，並確保每個部分都得到充分闡述。使用【繁體中文】進行回應。

## 📝 會議/對話摘要報告

### 🎯 核心議題與主要目的 (Core Issues & Main Objectives)
*   **議題/目的 1：** [對第一個核心議題或會議目的進行至少2-3句的詳細描述，解釋其背景和重要性。]
*   **議題/目的 2：** [對第二個核心議題或會議目的進行至少2-3句的詳細描述，解釋其背景和重要性。]
*   **(依此類推，列出3-5個)**

### 📋 詳細內容與關鍵討論點 (Detailed Content & Key Discussion Points)
*   **討論點 1 - [主題]：** [針對此主題，詳細說明討論中的重要觀點、提出的論據、相關數據或案例分析。內容應具體且有深度。]
*   **討論點 2 - [主題]：** [同上，確保每個討論點都有充分的闡述，至少涵蓋5-8個整體關鍵點。]
*   **(依此類推)**

### ✅ 重要決策與行動項目 (Key Decisions & Action Items)
*   **決策/行動 1：** [明確列出已達成的決策或需要採取的具體行動。]
    *   **負責人：** [指定負責人，如適用]
    *   **截止日期/狀態：** [預計完成日期或目前狀態，如 '進行中', '已完成']
    *   **相關細節：** [補充必要的執行細節或上下文]
*   **(依此類推，列出所有重要決策和行動項目)**

### 💡 綜合見解與深層結論 (Overall Insights & In-depth Conclusions)
*   **見解/結論 1：** [基於整體討論，總結一個重要的見解或深層結論。]
    *   **推斷依據/潛在影響：** [簡述此見解/結論的推斷過程、依據的資訊，或它可能帶來的潛在影響。]
*   **(依此類推，至少3-5個)**

### 🔑 全文核心關鍵字 (Core Keywords)
[請從全文中提取至少10-15個能夠高度概括核心內容的關鍵字或關鍵短語，使用逗號分隔。例如：市場分析, 產品策略, 預算規劃, 客戶回饋, 競爭對手動態, ...]

**重要指示：**
- **語言：** 請務必使用【繁體中文】。
- **詳盡性：** 摘要的詳細程度應與原文長度成正比。對於較長的文本，摘要應包含更豐富的細節和更深入的分析。
- **準確性：** 確保摘要內容準確反映原文的意涵，避免主觀臆斷或資訊遺漏。
- **結構化：** 嚴格遵循上述 Markdown 格式，確保報告的易讀性和專業性。
- **避免過簡：** 對於信息量大的文本，摘要應有足夠的字數來涵蓋關鍵信息。例如，對於超過一萬字的文本，摘要字數期望在1000字以上。
"""
    
    async def _call_gemini_with_rotation(self, prompt: str, generation_config: genai_types.GenerationConfig) -> Optional[genai_types.GenerateContentResponse]:
        """
        異步調用 Google Gemini API 生成內容，並實現 API 金鑰輪換和重試機制。

        此方法會依序嘗試使用 `self.api_keys` 列表中的 API 金鑰。
        如果一次調用失敗 (例如因配額限制、暫時性錯誤等)，它會自動切換到下一個金鑰並重試。
        重試之間會有指數退避延遲。

        Args:
            prompt (str): 要發送給 Gemini API 的提示詞。
            generation_config (genai_types.GenerationConfig): Gemini API 的生成配置。

        Returns:
            Optional[genai_types.GenerateContentResponse]: Gemini API 的成功回應，如果所有重試均失敗則返回 None 或拋出最後一個錯誤。

        Raises:
            Exception: 如果所有 API 金鑰和重試嘗試均失敗，則拋出最後一次遇到的例外。
        """
        last_error: Optional[Exception] = None # 用於記錄最後一次發生的錯誤
        
        # 外層循環：遍歷所有 API 金鑰
        for i in range(len(self.api_keys)): 
            current_key_index = (self.current_api_key_index + i) % len(self.api_keys)
            current_api_key = self.api_keys[current_key_index]
            logger.info(f"嘗試使用 API 金鑰索引 {current_key_index} (金鑰尾號: ...{current_api_key[-4:] if len(current_api_key) > 4 else '****'}) 進行 Gemini API 調用。")
            
            # 設定當前 genai SDK 使用的 API 金鑰
            genai.configure(api_key=current_api_key)

            try:
                # 內層循環：針對當前 API 金鑰進行重試
                for attempt in range(self.max_retries + 1): # +1 是因為第一次嘗試（attempt=0）不算重試
                    try:
                        # 創建模型實例
                        model = genai.GenerativeModel(self.model_name)
                        
                        # 使用 asyncio.to_thread 執行同步的 SDK 調用，使其在異步上下文中不阻塞事件循環
                        response = await asyncio.to_thread( 
                            model.generate_content,
                            contents=prompt,
                            generation_config=generation_config,
                            # request_options={"timeout": 60} # 可選：設定請求超時 (秒)
                        )
                        
                        logger.info(f"Gemini API 調用成功 (使用金鑰索引 {current_key_index}，第 {attempt + 1} 次嘗試)。")
                        self.current_api_key_index = current_key_index # 更新當前成功的金鑰索引，下次優先使用此金鑰
                        return response # 成功則返回回應
                    
                    except Exception as e_attempt: # 捕獲當前嘗試的錯誤
                        last_error = e_attempt
                        logger.warning(f"⚠️ Gemini API 調用嘗試 {attempt + 1} 失敗 (使用金鑰索引 {current_key_index}): {type(e_attempt).__name__} - {str(e_attempt)}")
                        
                        # 如果是特定的、可重試的錯誤類型 (例如資源耗盡、暫時性伺服器錯誤)，則進行重試
                        # TODO: 更精細地區分錯誤類型以決定是否重試
                        # 例如: if isinstance(e_attempt, (types.ResourceExhausted, types.ServiceUnavailable)):
                        if attempt < self.max_retries:
                            delay = self.retry_delay * (2 ** attempt) # 指數退避策略
                            logger.info(f"將在 {delay:.2f} 秒後使用相同金鑰重試...")
                            await asyncio.sleep(delay)
                        else: # 當前金鑰的所有重試已用盡
                            logger.error(f"API 金鑰索引 {current_key_index} 的所有重試嘗試均失敗。")
                            break # 跳出內層重試循環，準備嘗試下一個 API 金鑰
                
                # 如果內層循環是因為 break 跳出的 (即當前金鑰的所有重試均失敗)，則繼續外層循環嘗試下一個金鑰
                # 檢查 last_error 是否是由於最後一次嘗試失敗而設定的
                if last_error and attempt == self.max_retries: 
                    # 只有在確實是因為重試次數耗盡才繼續嘗試下一個金鑰
                    if i < len(self.api_keys) - 1: # 如果還有其他金鑰
                        logger.info(f"準備嘗試下一個 API 金鑰...")
                        await asyncio.sleep(self.retry_delay) # 切換金鑰前稍作延遲
                    continue # 嘗試下一個 API 金鑰
                # 如果不是因為重試耗盡 (例如，是一個不可重試的錯誤直接跳出)，則不應繼續
                # 但目前的邏輯是，只要內層循環結束（無論是 break 還是正常完成），如果沒有 return response，就會到這裡
                # 需要確保只有在明確知道可以嘗試下一個金鑰時才 continue
                
            except Exception as e_key_config: # 捕獲與金鑰配置或客戶端初始化相關的更嚴重錯誤
                last_error = e_key_config
                logger.error(f"配置或使用 API 金鑰索引 {current_key_index} 時發生嚴重錯誤: {type(e_key_config).__name__} - {str(e_key_config)}", exc_info=True)
                # 如果是金鑰無效等錯誤，直接嘗試下一個金鑰
                # TODO: 根據實際的 Google API 錯誤類型來判斷是否為金鑰無效錯誤
                if "API_KEY_INVALID" in str(e_key_config).upper() or \
                   "API_KEY_NOT_AUTHORIZED" in str(e_key_config).upper() or \
                   "PERMISSION_DENIED" in str(e_key_config).upper():
                    logger.warning(f"API 金鑰索引 {current_key_index} 可能無效或權限不足，嘗試下一個金鑰。")
                    if i < len(self.api_keys) - 1: # 如果還有其他金鑰
                         await asyncio.sleep(self.retry_delay) 
                    continue # 嘗試下一個 API 金鑰
                else: # 如果是其他類型的嚴重錯誤，可能無需再試其他金鑰，直接跳出外層循環
                    break 
        
        # 如果遍歷所有 API 金鑰和所有重試嘗試後仍然失敗
        logger.critical(f"所有 API 金鑰 ({len(self.api_keys)} 個) 和重試嘗試 ({self.max_retries} 次/每個金鑰) 均告失敗。")
        if last_error:
            raise last_error # 拋出最後一次遇到的錯誤
        else:
            # 這種情況理論上不應發生，因為至少會有一個 last_error 被記錄
            raise Exception("Gemini API 調用徹底失敗，且未記錄特定的最終錯誤。")

    def _extract_response_text(self, response: Optional[genai_types.GenerateContentResponse], original_text: str, 
                               is_structured_summary: bool = False, summary_type_for_log: str = "通用") -> str:
        """
        從 Gemini API 的回應中提取文本內容，並處理各種可能的完成狀態。

        Args:
            response (Optional[genai_types.GenerateContentResponse]): 從 Gemini API 收到的回應物件。
            original_text (str): 原始輸入文本，主要用於日誌記錄長度等元信息，不直接參與提取。
            is_structured_summary (bool, optional): 指示是否期望結構化摘要。
                                                  如果為 True 且因長度限制導致摘要不完整，會嘗試返回部分結果。
                                                  預設為 False。
            summary_type_for_log (str, optional): 用於日誌記錄的摘要類型。預設為 "通用"。

        Returns:
            str: 提取到的文本摘要。

        Raises:
            Exception: 如果無法從回應中提取有效的文本摘要 (例如 API 回應格式錯誤、安全阻擋等)。
        """
        if not response or not hasattr(response, 'candidates') or not response.candidates:
            logger.warning(f"Gemini API 回應無效或無候選內容 ({summary_type_for_log})。")
            raise Exception(f"無法生成「{summary_type_for_log}」：API 回應中無候選內容或回應格式不正確。")
        
        candidate = response.candidates[0] # 通常取第一個候選結果
        
        # 處理 finish_reason
        finish_reason_enum = candidate.finish_reason
        finish_reason_str = genai_types.FinishReason(finish_reason_enum).name if finish_reason_enum else "UNKNOWN"
        
        logger.info(f"Gemini API 回應的完成原因 ({summary_type_for_log})：「{finish_reason_str}」。")
        
        # 檢查是否有安全評級導致內容被阻擋
        if candidate.safety_ratings:
            for rating in candidate.safety_ratings:
                # 假設嚴重等級高於 HARM_PROBABILITY_NEGLIGIBLE 都視為潛在問題
                # HARM_PROBABILITY_LOW, HARM_PROBABILITY_MEDIUM, HARM_PROBABILITY_HIGH
                if rating.probability > genai_types.HarmProbability.NEGLIGIBLE: # 實際枚舉值可能不同，需查閱SDK
                    logger.warning(f"Gemini API 回應包含潛在不安全內容 ({summary_type_for_log})：類別 {rating.category.name}, 機率 {rating.probability.name}。")
                    # 如果 finish_reason 不是 SAFETY，但 safety_rating 指出問題，也應謹慎處理
                    if finish_reason_enum != genai_types.FinishReason.SAFETY:
                         # 即使不是因安全停止，但檢測到風險，也返回安全提示
                         return f"⚠️ AI偵測到回應中可能包含不適宜內容 (類別: {rating.category.name})，因此無法完整提供摘要。"
        
        # 根據 finish_reason 決定如何處理
        if finish_reason_enum == genai_types.FinishReason.STOP: # 正常完成
            if hasattr(response, 'text') and response.text and response.text.strip():
                result = response.text.strip()
                logger.info(f"「{summary_type_for_log}」成功生成，摘要長度: {len(result)} 字元。")
                return result
            else:
                logger.warning(f"Gemini API 正常停止，但未返回有效文本內容 ({summary_type_for_log})。")
                raise Exception(f"「{summary_type_for_log}」生成異常：AI 正常停止但未提供文本。")
        elif finish_reason_enum == genai_types.FinishReason.SAFETY: # 因安全設定停止
            logger.warning(f"Gemini API 因安全性原因停止生成 ({summary_type_for_log})。原始文本長度: {len(original_text)}。")
            return "⚠️ 抱歉，由於內容可能涉及敏感資訊或違反使用政策，AI 無法完成本次摘要。請檢查您的文本內容並重試。"
        elif finish_reason_enum == genai_types.FinishReason.MAX_TOKENS: # 達到最大 Token 限制
            logger.warning(f"Gemini API 因達到最大 Token 限制而停止 ({summary_type_for_log})。")
            if hasattr(response, 'text') and response.text and response.text.strip(): # 即使達到限制，有時也會返回部分內容
                logger.info(f"返回「{summary_type_for_log}」的部分結果，因達到最大 Token 限制。")
                return f"{response.text.strip()}\n\n⚠️ **注意：摘要可能因已達內容長度上限而未完整生成。**"
            else: # 如果沒有部分內容，則認為是個問題
                raise Exception(f"「{summary_type_for_log}」生成失敗：已達內容長度上限且無部分結果返回。")
        elif finish_reason_enum == genai_types.FinishReason.RECITATION: # 內容過多引用來源材料
             logger.warning(f"Gemini API 因偵測到過多引用而停止生成 ({summary_type_for_log})。")
             return "⚠️ AI 偵測到生成內容可能過多直接引用來源資料，為避免版權疑慮，已停止本次摘要。建議調整提示或文本內容。"
        else: # 其他未知或未明確處理的完成原因 (例如 LENGTH, UNKNOWN, UNSPECIFIED)
            logger.warning(f"Gemini API 返回未明確處理的完成原因 ({summary_type_for_log})：「{finish_reason_str}」。")
            if hasattr(response, 'text') and response.text and response.text.strip(): # 嘗試返回任何可用文本
                logger.info(f"返回「{summary_type_for_log}」的部分結果，完成原因：「{finish_reason_str}」。")
                return f"{response.text.strip()}\n\n⚠️ **注意：摘要可能因「{finish_reason_str}」原因而未完整生成。**"
            else:
                raise Exception(f"「{summary_type_for_log}」生成異常，完成原因：「{finish_reason_str}」，且無有效文本返回。")
    
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        (實驗性功能) 使用 Gemini 分析輸入文字的情感傾向。

        Args:
            text (str): 需要分析情感的文字。

        Returns:
            Dict[str, Any]: 包含情感分析結果的字典，
                            例如 `{"overall_sentiment": "positive", "confidence": 0.85, ...}`。
                            如果分析失敗，可能返回包含錯誤訊息的字典或拋出例外。
        
        Raises:
            Exception: 如果情感分析過程中發生嚴重錯誤。
        """
        logger.info(f"開始對長度為 {len(text)} 的文本進行情感分析。")
        try:
            # 提示詞指導模型返回 JSON 格式的情感分析結果
            prompt = f"""
請仔細分析以下提供的文字內容，並判斷其整體情感傾向。
您的分析結果需要以【JSON格式】返回，包含以下鍵值：
- "overall_sentiment": 字串，表示整體情感（例如 "positive", "negative", "neutral", "mixed"）。
- "confidence_score": 浮點數 (0.0 至 1.0)，表示您對整體情感判斷的信心程度。
- "detected_emotions": 字串列表，列出文本中可能包含的具體情感標籤（例如 ["喜悅", "期待", "擔憂", "不滿"]，若無明顯特定情感則為空列表）。
- "key_phrases_contributing_sentiment": 字串列表，列出文本中最能體現上述情感傾向的關鍵短語或句子。

文字內容如下：
---
{text[:5000]} 
---

請嚴格按照上述 JSON 結構輸出您的分析結果。
"""
            # 限制輸入文本長度以優化效能和成本
            
            generation_config = genai_types.GenerationConfig(
                temperature=0.1, # 低溫以獲得更一致和結構化的 JSON 輸出
                max_output_tokens=1024, # 足夠 JSON 輸出
                top_p=0.8, # 保持一定的確定性
                top_k=10
            )
            
            response = await self._call_gemini_with_rotation(prompt, generation_config)
            result_text = self._extract_response_text(response, original_text=text[:5000], summary_type_for_log="情感分析")
            
            # 嘗試將模型回應解析為 JSON 物件
            try:
                sentiment_data = json.loads(result_text)
                # 基本的結構驗證
                if not all(key in sentiment_data for key in ["overall_sentiment", "confidence_score", "detected_emotions", "key_phrases_contributing_sentiment"]):
                    logger.warning(f"情感分析的 Gemini 回應 JSON 格式不完整：{result_text}")
                    raise json.JSONDecodeError("缺少必要的鍵", result_text, 0)
                
                logger.info(f"情感分析成功，整體情感: {sentiment_data.get('overall_sentiment')} (信心度: {sentiment_data.get('confidence_score')})")
                return sentiment_data
            except json.JSONDecodeError as json_err:
                logger.warning(f"情感分析的 Gemini 回應不是有效的 JSON 格式：{result_text}。錯誤：{json_err}")
                # 如果不是有效 JSON，返回包含原始回應和錯誤訊息的字典
                return {
                    "overall_sentiment": "unknown", # 情感未知
                    "confidence_score": 0.0,
                    "detected_emotions": [],
                    "key_phrases_contributing_sentiment": [],
                    "error_message": "AI 回應格式非預期 JSON，無法完整解析情感。",
                    "raw_response": result_text # 包含原始回應以供除錯
                }
                
        except Exception as e:
            logger.error(f"情感分析過程中發生錯誤: {str(e)}", exc_info=True)
            # 向上拋出例外，讓呼叫者處理或記錄更高級別的錯誤
            raise Exception(f"情感分析服務失敗：{str(e)}")
    
    async def extract_keywords(self, text: str) -> List[str]:
        """
        (實驗性功能) 使用 Gemini 從輸入文字中提取關鍵字。

        Args:
            text (str): 需要提取關鍵字的文字。

        Returns:
            List[str]: 提取到的關鍵字列表。如果提取失敗，則返回空列表。
        """
        logger.info(f"開始對長度為 {len(text)} 的文本進行關鍵字提取。")
        try:
            # 提示詞指導模型提取關鍵字，並指定格式
            prompt = f"""
請仔細閱讀以下提供的文字內容，並從中提取出最重要的核心關鍵字或關鍵短語。
請返回一個列表，每個元素是一個關鍵字/短語。
最多提取 15 個最相關的關鍵字/短語。
請確保提取的關鍵字具有代表性，能夠概括文本的主要內容。

文字內容如下：
---
{text[:5000]}
---

請將提取到的關鍵字/短語以 Python 列表的字串表示形式輸出，例如：
["關鍵字1", "關鍵短語2", "核心概念3"]
"""
            # 限制輸入文本長度
            
            generation_config = genai_types.GenerationConfig(
                temperature=0.05, # 非常低的溫度以獲取精確和相關的關鍵字
                max_output_tokens=512, # 足夠關鍵字列表輸出
                top_p=0.7,
                top_k=5
            )
            
            response = await self._call_gemini_with_rotation(prompt, generation_config)
            result_text = self._extract_response_text(response, original_text=text[:5000], summary_type_for_log="關鍵字提取")
            
            # 嘗試將模型回應 (應為列表的字串表示) 解析為 Python 列表
            try:
                # 使用 json.loads 或 ast.literal_eval 更安全地解析列表字串
                # 此處假設模型能穩定輸出 Python 風格的列表字串
                # 例如： '["關鍵字1", "關鍵字2"]'
                # 移除可能存在於字串前後的非列表字元 (例如模型可能添加的說明文字)
                if '[' in result_text and ']' in result_text:
                    list_str_part = result_text[result_text.find('['):result_text.rfind(']')+1]
                    keywords = json.loads(list_str_part) 
                    if isinstance(keywords, list) and all(isinstance(kw, str) for kw in keywords):
                        logger.info(f"關鍵字提取成功，共提取 {len(keywords)} 個關鍵字 (最多返回15個)。")
                        return keywords[:15]  # 最多返回15個
                
                logger.warning(f"關鍵字提取的 Gemini 回應格式非預期列表字串：{result_text}")
                # 如果解析失敗，嘗試從換行符分割 (作為備用)
                keywords_fallback = [kw.strip('- ').strip().replace('"', '').replace("'", "") for kw in result_text.split('\n') if kw.strip()]
                if keywords_fallback:
                    logger.info(f"關鍵字提取 (備用解析) 成功，共提取 {len(keywords_fallback)} 個。")
                    return keywords_fallback[:15]
                return [] # 若都失敗則返回空列表

            except (json.JSONDecodeError, SyntaxError) as parse_err:
                logger.warning(f"解析關鍵字列表時發生錯誤: {parse_err}。原始回應: {result_text}")
                # 如果解析失敗，嘗試簡單的換行分割
                keywords_fallback_simple = [line.strip('- ').strip().replace('"',"").replace("'","") for line in result_text.split('\n') if line.strip() and len(line.strip()) > 1]
                if keywords_fallback_simple:
                     logger.info(f"關鍵字提取 (JSON解析失敗後，換行分割備用) 成功，共提取 {len(keywords_fallback_simple)} 個。")
                     return keywords_fallback_simple[:15]
                return []
            
        except Exception as e:
            logger.error(f"關鍵字提取過程中發生錯誤: {str(e)}", exc_info=True)
            return [] # 發生錯誤時返回空列表
    
    async def check_service_health_async(self) -> Dict[str, Any]: # 方法名與其他服務一致
        """
        檢查 Google Gemini AI 服務的健康狀態。

        透過發送一個簡單的測試請求來判斷服務是否可用及其配置。

        Returns:
            Dict[str, Any]: 包含服務健康狀態的字典，
                            例如 `{"available": True, "model_configured": "gemini-pro", ...}` 或 `{"available": False, "error": "錯誤訊息"}`。
        """
        logger.info("開始檢查 Google Gemini AI 服務健康狀態...")
        try:
            # 使用一個簡單的測試提示詞和配置
            test_prompt = "請簡短回覆 '測試成功' 以確認服務可用性。"
            test_generation_config = genai_types.GenerationConfig(
                temperature=0.0, # 要求確定性回覆
                max_output_tokens=50 # 限制輸出長度以節省資源
            )
            
            # _call_gemini_with_rotation 內部會處理 API 金鑰的設定和輪換
            response = await self._call_gemini_with_rotation(test_prompt, test_generation_config)
            
            # 驗證回應是否符合預期 (這裡的檢查比較寬鬆，主要確認能通訊成功)
            # _extract_response_text 會在回應無效時拋出例外
            extracted_text = self._extract_response_text(response, original_text=test_prompt, summary_type_for_log="健康檢查")
            
            if extracted_text: # 只要有成功提取到文本就認為基本可用
                logger.info(f"Google Gemini AI 服務健康狀態良好。測試回應: '{extracted_text[:30]}...'")
                return {
                    "available": True,
                    "model_configured": self.model_name, # 返回設定中使用的模型名稱
                    "provider": "Google Gemini API via google-generativeai SDK",
                    "api_keys_available": len(self.api_keys), # 返回設定的 API 金鑰數量
                    "message": "服務運作正常，已成功透過 API 測試請求。"
                }
            else: # 理論上 _extract_response_text 會拋錯，但多一層防護
                logger.warning("Google Gemini AI 服務健康檢查失敗：API 回應有效但提取文本為空。")
                return {
                    "available": False,
                    "model_configured": self.model_name,
                    "error": "API 回應有效但未能提取到測試文本，服務可能部分不可用。"
                }
                
        except Exception as e:
            logger.error(f"Google Gemini AI 服務健康檢查時發生嚴重錯誤: {str(e)}", exc_info=True)
            return {
                "available": False,
                "model_configured": self.model_name,
                "error": f"服務檢查時發生例外: {type(e).__name__} - {str(e)}"
            }