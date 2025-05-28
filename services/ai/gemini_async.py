"""
異步Google Gemini AI摘要服務
"""

import logging
import asyncio
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
        self.api_keys = config.google_api_keys
        self.model = config.gemini_model
        self.thinking_budget = config.thinking_budget
        self.max_retries = config.max_retries
        
        if not self.api_keys:
            raise ValueError("Google API密鑰未設置")
        
        # 初始化每個API金鑰的客戶端
        self.genai_clients = [genai.Client(api_key=key) for key in self.api_keys]
        self.current_genai_index = 0
    
    async def generate_summary(self, transcript: str) -> str:
        """
        生成文字摘要 - 支援不同長度文本的智能處理
        
        Args:
            transcript: 轉錄的文字
            
        Returns:
            摘要文字
        """
        start_time = time.time()

        try:
            logger.info("🤖 開始生成AI摘要")
            
            if not transcript or not transcript.strip():
                raise ValueError("轉錄文字為空")
            
            text_length = len(transcript)
            logger.info(f"開始處理文字摘要，長度: {text_length} 字符")

            # 估算錄音時長（粗略估算：每分鐘約150-200字）
            estimated_minutes = text_length / 180
            
            # 根據文本長度選擇不同的處理策略
            if text_length <= 3000:
                # 短錄音（<10分鐘）：完整摘要
                summary = await self._generate_complete_summary(transcript)
            elif text_length <= 6000:
                # 中等錄音（10-30分鐘）：重點摘要
                summary = await self._generate_focused_summary(transcript)
            elif text_length <= 18000:
                # 長錄音（30分鐘-1.5小時）：結構化摘要
                summary = await self._generate_structured_summary(transcript)
            else:
                # 超長錄音（>1.5小時）：分段式摘要
                summary = await self._generate_segmented_summary(transcript, estimated_minutes)
            
            if not summary:
                raise Exception("摘要生成失敗，返回結果為空")
            
            processing_time = time.time() - start_time
            logger.info(f"✨ AI摘要生成完成，耗時: {processing_time:.2f}秒")
            return summary
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ 生成摘要失敗 (耗時{processing_time:.2f}秒): {str(e)}")
            return "摘要功能暫時無法使用，但錄音轉文字成功。"
    
    async def _generate_complete_summary(self, text: str) -> str:
        """完整摘要（短錄音）"""
        prompt = self._build_summary_prompt(text)
        
        config = types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=60000,
            top_p=0.8,
            top_k=10
        )
        
        response = await self._call_gemini_with_rotation(prompt, config)
        return self._extract_response_text(response, text)
    
    async def _generate_focused_summary(self, text: str) -> str:
        """重點摘要（中等錄音）"""
        try:
            logger.info("使用重點摘要模式處理中等長度錄音")
            prompt = self._build_summary_prompt(text)
            
            config = types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=60000,
                top_p=0.8,
                top_k=10
            )
            
            response = await self._call_gemini_with_rotation(prompt, config)
            result = self._extract_response_text(response, text)
            
            logger.info(f"重點摘要生成成功，長度: {len(result)} 字符")
            return result
            
        except Exception as e:
            logger.error(f"重點摘要生成失敗: {e}")
            # 如果失敗，嘗試更簡單的處理方式
            return await self._generate_simple_focused_summary(text)
    
    async def _generate_structured_summary(self, text: str) -> str:
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
4. 重要細節

請按照以下格式提供詳細的摘要：

## 📝 會議/對話摘要

### 🎯 主要議題
- [列出3-5個主要討論點，每點至少包含2-3句詳細描述]

### 📋 重要內容
- [詳細說明重要討論內容，至少包含5-8個關鍵點，每點需要有足夠的上下文和細節]

### ✅ 行動項目
- [如果有的話，列出需要執行的事項，包含負責人和時間線]

### 💡 關鍵洞察
- [總結重要的見解或結論，至少3-5點，每點包含具體依據]

### 🔑 關鍵字
[相關關鍵字用逗號分隔，至少10-15個關鍵詞]

請用繁體中文回應，內容必須詳細且有組織性。"""

        config = types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=60000,
            top_p=0.8,
            top_k=10
        )
        
        response = await self._call_gemini_with_rotation(prompt, config)
        result = self._extract_response_text(response, text, structured=True)
        
        return f"{result}\n\n📊 錄音時長：約 {len(text)/180:.0f} 分鐘"
    
    async def _generate_segmented_summary(self, text: str, estimated_minutes: float) -> str:
        """分段式摘要（超長錄音）"""
        try:
            # 將文字分成多個段落，每段約3000字
            segments = []
            chunk_size = 3000
            for i in range(0, len(text), chunk_size):
                segment = text[i:i+chunk_size]
                segments.append(segment)
            
            logger.info(f"超長錄音分為 {len(segments)} 段處理")
            
            # 根據配置決定分析多少段落
            full_analysis = getattr(self.config, 'full_analysis', False)
            max_segments = getattr(self.config, 'max_segments_for_full_analysis', 10)
            
            if full_analysis:
                # 完整分析所有段落
                if len(segments) <= max_segments:
                    key_segments = segments
                    analysis_note = f"（完整分析 {len(segments)} 段）"
                    logger.info(f"進行完整分析，處理 {len(segments)} 段")
                else:
                    # 如果段落數超過限制，進行警告但仍盡可能分析更多
                    key_segments = segments[:max_segments]
                    analysis_note = f"（因段落過多，已分析前 {len(key_segments)} 段，共 {len(segments)} 段）"
                    logger.warning(f"段落數 {len(segments)} 超過限制 {max_segments}，只分析前 {len(key_segments)} 段")
            else:
                # 智能選取關鍵段落
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
            if full_analysis and total_segments > 20:
                logger.info(f"開始完整分析 {total_segments} 段，預計需要 {total_segments * 0.5:.0f} 秒")
            
            for i, segment in enumerate(key_segments):
                try:
                    # 動態調整段落標記（如果是智能選取，使用原始段落號）
                    if full_analysis or len(segments) <= 10:
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
                    
                    response = await self._call_gemini_with_rotation(prompt, config)
                    if response and hasattr(response, 'candidates') and response.candidates:
                        summary = response.text.strip()
                        segment_summaries.append(f"【{segment_label}】{summary}")
                    
                    # 記錄處理進度
                    if (i + 1) % 10 == 0:
                        logger.info(f"已完成 {i + 1}/{total_segments} 段分析")
                    
                    delay = getattr(self.config, 'segment_processing_delay', 0.5)
                    await asyncio.sleep(delay)  # 使用配置的延遲時間
                    
                except Exception as e:
                    logger.warning(f"處理{segment_label}時出錯: {e}")
                    segment_summaries.append(f"【{segment_label}】處理失敗")
            
            # 生成總體摘要
            combined_summary = "\n\n".join(segment_summaries)
            
            final_prompt = f"""基於以下分段摘要，請提供整體重點總結：

{combined_summary}

請提供：
1. 主要議題和主題
2. 核心觀點和結論
3. 重要決定或行動項目

請按照以下格式提供摘要：

## 📝 會議/對話摘要

### 🎯 主要議題
- [列出3-5個主要討論點，每點包含詳細描述]

### 📋 重要內容
- [詳細說明重要討論內容]

### ✅ 行動項目
- [如果有的話，列出需要執行的事項]

### 💡 關鍵洞察
- [總結重要的見解或結論]

### 🔑 關鍵字
[相關關鍵字用逗號分隔]"""

            config = types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=60000,
                top_p=0.8,
                top_k=10
            )
            
            final_response = await self._call_gemini_with_rotation(final_prompt, config)
            final_summary = self._extract_response_text(final_response, text, structured=True)
            
            # 組合最終結果
            result = f"🎯 【整體摘要】\n{final_summary}\n\n📝 【分段重點】\n{combined_summary}\n\n"
            result += f"⏱️ 錄音時長：約 {estimated_minutes:.0f} 分鐘 ({len(text)} 字)\n"
            result += f"📊 分析說明：{analysis_note}"
            
            return result
            
        except Exception as e:
            logger.error(f"分段摘要處理失敗: {e}")
            return await self._generate_fallback_summary(text, estimated_minutes)
    
    async def _generate_fallback_summary(self, text: str, estimated_minutes: float) -> str:
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
            
            response = await self._call_gemini_with_rotation(prompt, config)
            result = self._extract_response_text(response, text)
            
            return f"{result}\n\n⚠️ 因錄音過長，此為簡化摘要\n⏱️ 錄音時長：約 {estimated_minutes:.0f} 分鐘"
            
        except Exception as e:
            logger.error(f"備用摘要也失敗: {e}")
            return f"✅ 錄音轉文字成功\n⏱️ 錄音時長：約 {estimated_minutes:.0f} 分鐘 ({len(text)} 字)\n📝 因內容過長，摘要功能暫時無法使用，請查看完整逐字稿"
    
    async def _generate_simple_focused_summary(self, text: str) -> str:
        """簡化版重點摘要（中等錄音備用方案）"""
        try:
            logger.info("使用簡化版重點摘要")
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
                    
                    response = await self._call_gemini_with_rotation(prompt, config)
                    if (response and hasattr(response, 'candidates') and response.candidates and 
                        "STOP" in str(response.candidates[0].finish_reason)):
                        summaries.append(response.text.strip())
                    
                    await asyncio.sleep(0.3)  # 短暫延遲
                    
                except Exception as e:
                    logger.warning(f"處理第{i+1}段簡化摘要失敗: {e}")
                    continue
            
            if summaries:
                result = "\n\n".join(summaries)
                if len(chunks) > 3:
                    result += f"\n\n💡 註：已摘要前3段內容，總共{len(chunks)}段"
                return result
            else:
                return await self._generate_short_summary(text[:1000])
                
        except Exception as e:
            logger.error(f"簡化版重點摘要失敗: {e}")
            return await self._generate_short_summary(text[:1000])
    
    async def _generate_short_summary(self, text: str) -> str:
        """生成簡短摘要（備用方案）"""
        try:
            logger.info("使用簡短摘要模式")
            prompt = f"請用最簡潔的方式總結以下內容的主要重點（限100字內）：\n\n{text[:1000]}"
            
            config = types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=20000,
                top_p=0.8,
                top_k=5
            )

            response = await self._call_gemini_with_rotation(prompt, config)
            
            if (response and hasattr(response, 'candidates') and response.candidates and 
                "STOP" in str(response.candidates[0].finish_reason)):
                return f"{response.text.strip()}\n\n⚠️ 因處理限制，此為簡化摘要"
            else:
                return "✅ 錄音轉文字成功\n📝 內容較長，建議查看完整逐字稿"
                
        except Exception as e:
            logger.error(f"簡短摘要也失敗: {e}")
            return "✅ 錄音轉文字成功\n📝 摘要功能暫時無法使用，請查看完整逐字稿"
    
    def _build_summary_prompt(self, transcript: str) -> str:
        """構建摘要提示詞"""
        return f"""
請為以下錄音轉錄內容生成一個詳細且結構化的摘要。摘要長度應該與原文長度成比例，確保包含所有重要信息。

轉錄內容：
{transcript}

請按照以下格式生成詳細的摘要：

## 📝 會議/對話摘要

### 🎯 主要議題
- [列出3-5個主要討論點，每點至少包含2-3句詳細描述]

### 📋 重要內容
- [詳細說明重要討論內容，至少包含5-8個關鍵點，每點需要有足夠的上下文和細節]

### ✅ 行動項目
- [如果有的話，列出需要執行的事項，包含負責人和時間線]

### 💡 關鍵洞察
- [總結重要的見解或結論，至少3-5點，每點包含具體依據]

### 🔑 關鍵字
[相關關鍵字用逗號分隔，至少10-15個關鍵詞]

請用繁體中文回應，內容必須詳細且有組織性。摘要的字數應該合理反映原始文本的信息量，避免過於簡短。對於一萬字以上的文本，摘要至少應有1000字以上。
"""
    
    async def _call_gemini_with_rotation(self, prompt: str, config: types.GenerateContentConfig):
        """異步調用Gemini API，並在失敗時輪換API金鑰"""
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                client = self.genai_clients[self.current_genai_index]
                
                # 使用官方SDK調用API
                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config
                )
                
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ Gemini API調用嘗試 {attempt + 1} 失敗 (使用金鑰 {self.current_genai_index + 1}): {str(e)}")
                
                # 切換到下一個API金鑰
                self.current_genai_index = (self.current_genai_index + 1) % len(self.genai_clients)
                
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)  # 指數退避
                    continue
                else:
                    break
        
        raise last_error or Exception("所有重試都失敗了")
    
    def _extract_response_text(self, response, original_text: str, structured: bool = False) -> str:
        """提取回應文字並處理各種狀況"""
        if not response or not hasattr(response, 'candidates') or not response.candidates:
            logger.warning("Gemini 回應無內容或無候選項")
            raise Exception("無法生成摘要回應")
        
        candidate = response.candidates[0]
        finish_reason = str(candidate.finish_reason) if hasattr(candidate, 'finish_reason') else "UNKNOWN"
        
        logger.info(f"Gemini 回應狀態: {finish_reason}")
        
        if "STOP" in finish_reason:
            result = response.text.strip()
            logger.info(f"摘要生成成功，長度: {len(result)} 字符")
            return result
        elif "SAFETY" in finish_reason:
            return "⚠️ 內容可能包含敏感資訊，無法產生摘要"
        elif "MAX_TOKEN" in finish_reason or "LENGTH" in finish_reason:
            logger.warning(f"Token 限制觸發: {finish_reason}")
            # 如果是結構化處理，嘗試返回部分結果
            if structured and response.text:
                return f"{response.text.strip()}\n\n⚠️ 摘要因長度限制可能不完整"
            else:
                # 對於中等長度錄音，嘗試簡化處理
                raise Exception(f"內容過長需要簡化處理: {finish_reason}")
        else:
            logger.warning(f"未知的完成狀態: {finish_reason}")
            if response.text and len(response.text.strip()) > 0:
                return f"{response.text.strip()}\n\n⚠️ 摘要可能不完整（{finish_reason}）"
            else:
                raise Exception(f"摘要生成異常: {finish_reason}")
    
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """分析文字情感"""
        try:
            prompt = f"""
分析以下文字的情感傾向，請返回JSON格式：

文字內容：
{text}

請分析並返回：
{{
    "overall_sentiment": "positive/negative/neutral",
    "confidence": 0.0-1.0,
    "emotions": ["具體情感標籤"],
    "key_phrases": ["關鍵短語"]
}}
"""
            
            config = types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=20000,
                top_p=0.8,
                top_k=5
            )
            
            response = await self._call_gemini_with_rotation(prompt, config)
            result = response.text.strip()
            
            # 嘗試解析為JSON
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                # 如果不是有效JSON，返回基本格式
                return {
                    "overall_sentiment": "neutral",
                    "confidence": 0.5,
                    "emotions": [],
                    "key_phrases": [],
                    "raw_response": result
                }
                
        except Exception as e:
            logger.error(f"情感分析失敗: {str(e)}")
            raise
    
    async def extract_keywords(self, text: str) -> List[str]:
        """提取關鍵字"""
        try:
            prompt = f"""
從以下文字中提取最重要的關鍵字，每行一個關鍵字，最多15個：

{text}

關鍵字：
"""
            
            config = types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=20000,
                top_p=0.8,
                top_k=5
            )
            
            response = await self._call_gemini_with_rotation(prompt, config)
            result = response.text.strip()
            
            # 解析關鍵字
            keywords = []
            for line in result.split('\n'):
                keyword = line.strip('- ').strip()
                if keyword and len(keyword) > 1:
                    keywords.append(keyword)
            
            return keywords[:15]  # 最多返回15個關鍵字
            
        except Exception as e:
            logger.error(f"關鍵字提取失敗: {str(e)}")
            return []
    
    async def check_status(self) -> Dict[str, Any]:
        """檢查服務狀態"""
        try:
            client = self.genai_clients[self.current_genai_index]
            
            # 使用一個簡單的提示詞測試服務是否可用
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents="測試",
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=10,
                    )
                )
                
                if response and hasattr(response, 'candidates') and response.candidates:
                    return {
                        "available": True,
                        "model": self.model,
                        "provider": "google_gemini",
                        "api_keys_count": len(self.api_keys),
                        "using_sdk": True
                    }
                else:
                    return {
                        "available": False,
                        "error": "API響應無內容"
                    }
            except Exception as e:
                return {
                    "available": False,
                    "error": str(e)
                }
                
        except Exception as e:
            return {
                "available": False,
                "error": str(e)
            } 