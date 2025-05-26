import time
import logging
from google import genai
from google.genai import types
from config import AppConfig
from models import APIError


class GeminiService:
    def __init__(self, config: AppConfig):
        self.config = config
        self.genai_clients = [genai.Client(api_key=key) for key in config.google_api_keys]
        self.current_genai_index = 0

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