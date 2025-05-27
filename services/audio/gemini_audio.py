import logging
import time
import os
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
from config import AppConfig
from models.base import APIError


class GeminiAudioService:
    """Gemini 音頻轉文字服務 - 專注於語音轉文字功能"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.genai_clients = [genai.Client(api_key=key) for key in config.google_api_keys]
        self.current_genai_index = 0
        self.model_name = "gemini-2.0-flash"  # 使用支持音頻的模型

    def transcribe_audio(self, audio_file_path: str) -> str:
        """使用 Gemini 直接轉錄音頻文件"""
        start_time = time.time()
        
        try:
            logging.info(f"開始使用 Gemini 轉錄音頻: {audio_file_path}")
            
            # 檢查音頻文件
            if not os.path.exists(audio_file_path):
                raise APIError(f"音頻文件不存在: {audio_file_path}")
            
            file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
            logging.info(f"音頻文件大小: {file_size_mb:.1f}MB")
            
            # 檢查文件大小限制（Gemini 支援最大 100MB）
            if file_size_mb > 100:
                raise APIError(f"音頻文件過大 ({file_size_mb:.1f}MB)，Gemini 最大支援 100MB")
            
            # 上傳音頻文件到 Gemini
            client = self.genai_clients[self.current_genai_index]
            
            # 檢測音頻格式
            mime_type = self._detect_audio_mime_type(audio_file_path)
            
            try:
                # 上傳文件
                myfile = client.files.upload(
                    file=audio_file_path,
                    config={
                        "mime_type": mime_type,
                        "display_name": os.path.basename(audio_file_path)
                    }
                )
                logging.info(f"文件上傳成功: {myfile.uri}")
                
                # 請求轉錄 - 優化的轉錄專用提示
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=[
                        "請提供這個音頻的完整逐字稿。要求：1) 準確轉錄所有語音內容 2) 保持原始表達和語序 3) 如有多個說話者請標注 4) 只返回轉錄文字，不要添加額外說明或分析",
                        myfile
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.1,  # 降低溫度確保準確性
                        max_output_tokens=30000,
                        top_p=0.8
                    )
                )
                
                processing_time = time.time() - start_time
                
                if response and response.candidates and response.text:
                    transcription = response.text.strip()
                    logging.info(f"Gemini 轉錄完成，耗時 {processing_time:.2f}秒，文字長度: {len(transcription)} 字符")
                    
                    # 清理上傳的文件
                    try:
                        client.files.delete(name=myfile.name)
                        logging.info("已清理上傳的臨時文件")
                    except Exception as e:
                        logging.warning(f"清理臨時文件失敗: {e}")
                    
                    return transcription
                else:
                    raise APIError("Gemini 無法生成轉錄結果")
                    
            except Exception as e:
                # 嘗試切換到下一個 API 金鑰
                self.current_genai_index = (self.current_genai_index + 1) % len(self.genai_clients)
                logging.warning(f"Gemini API 金鑰 {self.current_genai_index} 失敗，已切換: {e}")
                raise APIError(f"Gemini 轉錄失敗: {e}")
                
        except Exception as e:
            processing_time = time.time() - start_time
            logging.error(f"Gemini 音頻轉錄失敗 (耗時{processing_time:.2f}秒): {e}")
            raise

    def _transcribe_and_summarize_legacy_deprecated(self, audio_file_path: str) -> Dict[str, str]:
        """
        已棄用的方法：同時進行轉錄和摘要
        
        此方法違反了單一職責原則，已被棄用。
        請使用 transcribe_audio() 進行語音轉文字，
        然後使用 GeminiService.generate_summary() 進行摘要生成。
        """
        logging.warning("調用了已棄用的 _transcribe_and_summarize_legacy_deprecated 方法，請使用分離的轉錄和摘要服務")
        
        # 重定向到正確的分離流程
        raise APIError("此方法已棄用，請使用分離的轉錄和摘要服務")
        
        start_time = time.time()
        
        try:
            logging.info(f"開始使用 Gemini 進行音頻轉錄和摘要: {audio_file_path}")
            
            # 檢查音頻文件
            if not os.path.exists(audio_file_path):
                raise APIError(f"音頻文件不存在: {audio_file_path}")
            
            file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
            logging.info(f"音頻文件大小: {file_size_mb:.1f}MB")
            
            # 檢查文件大小限制
            if file_size_mb > 1000:
                raise APIError(f"音頻文件過大 ({file_size_mb:.1f}MB)，Gemini 最大支援 1000MB")
            
            # 上傳音頻文件到 Gemini
            client = self.genai_clients[self.current_genai_index]
            mime_type = self._detect_audio_mime_type(audio_file_path)
            
            try:
                # 上傳文件
                myfile = client.files.upload(
                    file=audio_file_path,
                    config={
                        "mime_type": mime_type,
                        "display_name": os.path.basename(audio_file_path)
                    }
                )
                logging.info(f"文件上傳成功: {myfile.uri}")
                
                # 計算音頻長度（估算）
                estimated_duration = self._estimate_audio_duration(file_size_mb)
                
                # 同時請求轉錄和摘要
                if estimated_duration <= 10:  # 短音頻
                    prompt = """請分析這個音頻文件，提供完整的逐字稿和重點摘要。

**請嚴格按照以下格式回覆，不要遺漏任何標記：**

【逐字稿】
[請在此處提供完整的音頻逐字轉錄內容，包括所有對話和說話內容]

【重點摘要】
[請在此處提供3-5個重點的結構化摘要，包括主要議題、關鍵觀點和重要結論]

請確保：
1. 逐字稿部分包含所有音頻中的語音內容
2. 摘要部分至少包含100字以上的詳細總結
3. 使用指定的【】標記格式"""
                elif estimated_duration <= 30:  # 中等音頻
                    prompt = """請分析這個音頻文件，提供完整的逐字稿和結構化摘要。

**請嚴格按照以下格式回覆，不要遺漏任何標記：**

【逐字稿】
[請在此處提供完整的音頻逐字轉錄內容，包括所有對話和說話內容]

【結構化摘要】
主要主題：[音頻討論的核心主題]
重點內容：[關鍵內容和重要觀點，至少3-5點]
關鍵結論：[最終結論和行動項目]

請確保：
1. 逐字稿部分包含所有音頻中的語音內容
2. 結構化摘要每個部分都要有詳細內容，總字數至少150字
3. 使用指定的【】標記格式"""
                else:  # 長音頻
                    prompt = """請分析這個音頻文件，提供完整的逐字稿和詳細的分段摘要。

**請嚴格按照以下格式回覆，不要遺漏任何標記：**

【逐字稿】
[請在此處提供完整的音頻逐字轉錄內容，包括所有對話和說話內容]

【分段摘要】
[請按時間順序或主題提供詳細的分段摘要，包括：
- 主要議題和討論重點
- 核心觀點和不同立場
- 重要決定或行動項目
- 關鍵數據或事實
總字數至少200字以上]

請確保：
1. 逐字稿部分包含所有音頻中的語音內容
2. 分段摘要要詳細且結構化，總字數至少200字
3. 使用指定的【】標記格式"""
                
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt, myfile],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=60000,
                        top_p=0.8,
                        top_k=10
                    )
                )
                
                processing_time = time.time() - start_time
                
                if response and response.candidates and response.text:
                    result_text = response.text.strip()
                    
                    # 解析回應，分離轉錄和摘要
                    transcription, summary = self._parse_combined_response(result_text)
                    
                    logging.info(f"Gemini 音頻處理完成，耗時 {processing_time:.2f}秒")
                    logging.info(f"轉錄長度: {len(transcription)} 字符，摘要長度: {len(summary)} 字符")
                    
                    # 清理上傳的文件
                    try:
                        client.files.delete(name=myfile.name)
                        logging.info("已清理上傳的臨時文件")
                    except Exception as e:
                        logging.warning(f"清理臨時文件失敗: {e}")
                    
                    return {
                        "transcription": transcription,
                        "summary": summary,
                        "processing_time": processing_time,
                        "estimated_duration": estimated_duration
                    }
                else:
                    raise APIError("Gemini 無法生成處理結果")
                    
            except Exception as e:
                # 嘗試切換到下一個 API 金鑰
                self.current_genai_index = (self.current_genai_index + 1) % len(self.genai_clients)
                logging.warning(f"Gemini API 金鑰 {self.current_genai_index} 失敗，已切換: {e}")
                raise APIError(f"Gemini 音頻處理失敗: {e}")
                
        except Exception as e:
            processing_time = time.time() - start_time
            logging.error(f"Gemini 音頻處理失敗 (耗時{processing_time:.2f}秒): {e}")
            raise

    def analyze_audio_content(self, audio_file_path: str, custom_prompt: str = None) -> str:
        """自定義音頻內容分析"""
        start_time = time.time()
        
        try:
            logging.info(f"開始使用 Gemini 進行自定義音頻分析: {audio_file_path}")
            
            if not os.path.exists(audio_file_path):
                raise APIError(f"音頻文件不存在: {audio_file_path}")
            
            file_size_mb = os.path.getsize(audio_file_path) / (1024 * 1024)
            
            if file_size_mb > 100:
                raise APIError(f"音頻文件過大 ({file_size_mb:.1f}MB)，Gemini 最大支援 100MB")
            
            client = self.genai_clients[self.current_genai_index]
            mime_type = self._detect_audio_mime_type(audio_file_path)
            
            try:
                # 上傳文件
                myfile = client.files.upload(
                    file=audio_file_path,
                    config={
                        "mime_type": mime_type,
                        "display_name": os.path.basename(audio_file_path)
                    }
                )
                
                # 使用自定義提示或預設分析提示
                if custom_prompt:
                    prompt = custom_prompt
                else:
                    prompt = """請分析這個音頻文件，包括：
1. 內容主題和重點
2. 說話者的情緒和語調
3. 關鍵訊息和結論
4. 任何特殊的音頻特徵（背景音、音質等）"""
                
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt, myfile],
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=30000,
                        top_p=0.9,
                        top_k=10
                    )
                )
                
                processing_time = time.time() - start_time
                
                if response and response.candidates and response.text:
                    result = response.text.strip()
                    logging.info(f"Gemini 音頻分析完成，耗時 {processing_time:.2f}秒")
                    
                    # 清理上傳的文件
                    try:
                        client.files.delete(name=myfile.name)
                    except Exception as e:
                        logging.warning(f"清理臨時文件失敗: {e}")
                    
                    return result
                else:
                    raise APIError("Gemini 無法生成分析結果")
                    
            except Exception as e:
                self.current_genai_index = (self.current_genai_index + 1) % len(self.genai_clients)
                logging.warning(f"Gemini API 金鑰 {self.current_genai_index} 失敗，已切換: {e}")
                raise APIError(f"Gemini 音頻分析失敗: {e}")
                
        except Exception as e:
            processing_time = time.time() - start_time
            logging.error(f"Gemini 音頻分析失敗 (耗時{processing_time:.2f}秒): {e}")
            raise

    def get_usage_info(self) -> Dict[str, Any]:
        """獲取使用資訊"""
        return {
            "service": "Gemini Audio Transcription",
            "provider": "gemini_audio",
            "model": self.model_name,
            "api_keys_count": len(self.genai_clients),
            "current_key_index": self.current_genai_index,
            "supported_formats": ["MP3", "WAV", "AIFF", "AAC", "OGG", "FLAC"],
            "max_file_size_mb": 100,
            "max_duration_hours": 9.5,
            "features": ["高質量語音轉文字", "多語言支持", "說話者區分"],
            "status": "ready"
        }

    def _detect_audio_mime_type(self, audio_file_path: str) -> str:
        """檢測音頻文件的 MIME 類型"""
        extension = os.path.splitext(audio_file_path.lower())[1]
        
        mime_types = {
            '.mp3': 'audio/mp3',
            '.wav': 'audio/wav',
            '.aiff': 'audio/aiff',
            '.aac': 'audio/aac',
            '.ogg': 'audio/ogg',
            '.flac': 'audio/flac',
            '.m4a': 'audio/aac',
            '.opus': 'audio/ogg'
        }
        
        return mime_types.get(extension, 'audio/mp3')  # 預設為 mp3

    def _estimate_audio_duration(self, file_size_mb: float) -> float:
        """根據文件大小估算音頻時長（分鐘）"""
        # 粗略估算：MP3 128kbps 約 1MB/分鐘
        # 這只是估算，實際時長可能有差異
        return file_size_mb

    def _parse_combined_response(self, response_text: str) -> tuple[str, str]:
        """解析包含轉錄和摘要的回應"""
        try:
            logging.info(f"開始解析Gemini回應，總長度: {len(response_text)} 字符")
            
            # 尋找標記（包括中英文括號）
            transcription_markers = ["【逐字稿】", "【轉錄】", "【完整逐字稿】", "[逐字稿]", "[轉錄]", "逐字稿：", "轉錄：", "Transcription:", "Full Transcription:"]
            summary_markers = ["【重點摘要】", "【摘要】", "【結構化摘要】", "【分段摘要】", "[重點摘要]", "[摘要]", "摘要：", "重點摘要：", "Summary:", "主要主題：", "重點內容："]
            
            transcription = ""
            summary = ""
            
            # 先記錄原始回應的一部分用於調試
            preview = response_text[:500] + "..." if len(response_text) > 500 else response_text
            logging.info(f"回應預覽: {preview}")
            
            # 找到轉錄部分
            transcription_found = False
            for marker in transcription_markers:
                if marker in response_text:
                    logging.info(f"找到轉錄標記: {marker}")
                    parts = response_text.split(marker, 1)
                    if len(parts) > 1:
                        remaining_text = parts[1]
                        
                        # 找到摘要標記的位置
                        summary_start = -1
                        found_summary_marker = ""
                        for sum_marker in summary_markers:
                            pos = remaining_text.find(sum_marker)
                            if pos != -1:
                                summary_start = pos
                                found_summary_marker = sum_marker
                                break
                        
                        if summary_start != -1:
                            transcription = remaining_text[:summary_start].strip()
                            summary_part = remaining_text[summary_start:].strip()
                            
                            # 移除摘要標記
                            if summary_part.startswith(found_summary_marker):
                                summary = summary_part[len(found_summary_marker):].strip()
                            else:
                                summary = summary_part
                            
                            logging.info(f"找到摘要標記: {found_summary_marker}")
                        else:
                            transcription = remaining_text.strip()
                            logging.info("未找到摘要標記，將生成預設摘要")
                        
                        transcription_found = True
                        break
            
            # 如果沒有找到轉錄標記，嘗試基於內容結構解析
            if not transcription_found:
                logging.info("未找到轉錄標記，嘗試其他解析方法")
                
                # 檢查是否有明顯的分段
                lines = response_text.strip().split('\n')
                if len(lines) > 10:  # 如果有多行，可能是轉錄內容
                    # 嘗試找到摘要關鍵詞
                    summary_line_idx = -1
                    for i, line in enumerate(lines):
                        if any(marker.replace("【", "").replace("】", "").replace("[", "").replace("]", "") in line for marker in summary_markers):
                            summary_line_idx = i
                            break
                    
                    if summary_line_idx > 0:
                        transcription = '\n'.join(lines[:summary_line_idx]).strip()
                        summary = '\n'.join(lines[summary_line_idx:]).strip()
                        logging.info(f"基於行結構解析，分割點在第 {summary_line_idx} 行")
                    else:
                        # 按比例分割：前80%作為轉錄，後20%作為摘要
                        split_point = int(len(response_text) * 0.8)
                        transcription = response_text[:split_point].strip()
                        summary = response_text[split_point:].strip()
                        logging.info("按80/20比例分割內容")
                else:
                    # 短內容直接作為轉錄
                    transcription = response_text.strip()
                    logging.info("內容較短，整體作為轉錄")
            
            # 確保有摘要內容
            if not summary and transcription:
                if len(transcription) > 300:
                    # 從轉錄中生成摘要（取前300字作為摘要基礎）
                    summary = f"主要內容摘要：{transcription[:300]}..."
                else:
                    summary = f"完整內容：{transcription}"
                logging.info("生成了預設摘要")
            
            # 清理內容
            transcription = transcription.strip()
            summary = summary.strip()
            
            logging.info(f"解析完成 - 轉錄: {len(transcription)} 字符, 摘要: {len(summary)} 字符")
            
            return transcription, summary
            
        except Exception as e:
            logging.error(f"解析回應失敗: {e}")
            # 發生錯誤時，將回應分為兩部分
            if len(response_text) > 500:
                return response_text[:len(response_text)//2], response_text[len(response_text)//2:]
            else:
                return response_text, "自動摘要：音頻轉錄完成，請查看完整內容"

    def count_tokens(self, audio_file_path: str) -> int:
        """計算音頻文件的 token 數量"""
        try:
            if not os.path.exists(audio_file_path):
                raise APIError(f"音頻文件不存在: {audio_file_path}")
            
            client = self.genai_clients[self.current_genai_index]
            mime_type = self._detect_audio_mime_type(audio_file_path)
            
            # 上傳文件
            myfile = client.files.upload(
                file=audio_file_path,
                config={
                    "mime_type": mime_type,
                    "display_name": os.path.basename(audio_file_path)
                }
            )
            
            # 計算 tokens
            response = client.models.count_tokens(
                model=self.model_name,
                contents=[myfile]
            )
            
            # 清理文件
            try:
                client.files.delete(name=myfile.name)
            except Exception as e:
                logging.warning(f"清理臨時文件失敗: {e}")
            
            return response.total_tokens
            
        except Exception as e:
            logging.error(f"計算 token 數量失敗: {e}")
            return 0 