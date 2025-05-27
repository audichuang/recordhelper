"""
異步Google Gemini AI摘要服務
"""

import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List
import json
import random

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
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
    
    def _get_api_key(self) -> str:
        """隨機選擇一個API密鑰"""
        return random.choice(self.api_keys)
    
    async def generate_summary(self, transcript: str) -> str:
        """
        生成文字摘要
        
        Args:
            transcript: 轉錄的文字
            
        Returns:
            摘要文字
        """
        try:
            logger.info("開始生成AI摘要")
            
            if not transcript or not transcript.strip():
                raise ValueError("轉錄文字為空")
            
            # 構建提示詞
            prompt = self._build_summary_prompt(transcript)
            
            # 調用Gemini API
            summary = await self._call_gemini_api(prompt)
            
            if not summary:
                raise Exception("摘要生成失敗，返回結果為空")
            
            logger.info("AI摘要生成完成")
            return summary
            
        except Exception as e:
            logger.error(f"生成摘要失敗: {str(e)}")
            raise
    
    def _build_summary_prompt(self, transcript: str) -> str:
        """構建摘要提示詞"""
        return f"""
請為以下錄音轉錄內容生成一個詳細且結構化的摘要。

轉錄內容：
{transcript}

請按照以下格式生成摘要：

## 📝 會議/對話摘要

### 🎯 主要議題
- [列出3-5個主要討論點]

### 📋 重要內容
- [詳細說明重要討論內容]

### ✅ 行動項目
- [如果有的話，列出需要執行的事項]

### 💡 關鍵洞察
- [總結重要的見解或結論]

### 🔑 關鍵字
[相關關鍵字用逗號分隔]

請用繁體中文回應，內容要詳細且有組織性。
"""
    
    async def _call_gemini_api(self, prompt: str) -> str:
        """調用Gemini API"""
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                api_key = self._get_api_key()
                
                # 構建請求數據
                request_data = {
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt}
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.7,
                        "topK": 40,
                        "topP": 0.95,
                        "maxOutputTokens": 2048,
                        "responseMimeType": "text/plain"
                    },
                    "systemInstruction": {
                        "parts": [
                            {
                                "text": "你是一個專業的會議記錄和內容摘要助手。請生成結構化、詳細且有用的摘要。"
                            }
                        ]
                    }
                }
                
                # 添加思考預算（如果支持的話）
                if self.thinking_budget > 0:
                    request_data["generationConfig"]["thinkingBudget"] = self.thinking_budget
                
                url = f"{self.base_url}/models/{self.model}:generateContent"
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json=request_data,
                        params={"key": api_key},
                        headers={"Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        
                        if response.status != 200:
                            error_text = await response.text()
                            error_msg = f"Gemini API錯誤 {response.status}: {error_text}"
                            logger.warning(f"嘗試 {attempt + 1} 失敗: {error_msg}")
                            last_error = Exception(error_msg)
                            
                            if attempt < self.max_retries:
                                await asyncio.sleep(2 ** attempt)  # 指數退避
                                continue
                            else:
                                raise last_error
                        
                        result = await response.json()
                
                # 解析回應
                if 'candidates' not in result or not result['candidates']:
                    raise Exception("Gemini API返回空的候選回應")
                
                candidate = result['candidates'][0]
                if 'content' not in candidate or 'parts' not in candidate['content']:
                    raise Exception("Gemini API回應格式錯誤")
                
                parts = candidate['content']['parts']
                if not parts or 'text' not in parts[0]:
                    raise Exception("Gemini API回應中沒有文字內容")
                
                summary = parts[0]['text'].strip()
                
                if not summary:
                    raise Exception("生成的摘要為空")
                
                return summary
                
            except Exception as e:
                last_error = e
                logger.warning(f"Gemini API調用嘗試 {attempt + 1} 失敗: {str(e)}")
                
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)  # 指數退避
                    continue
                else:
                    break
        
        raise last_error or Exception("所有重試都失敗了")
    
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
            
            result = await self._call_gemini_api(prompt)
            
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
從以下文字中提取最重要的關鍵字，每行一個關鍵字，最多10個：

{text}

關鍵字：
"""
            
            result = await self._call_gemini_api(prompt)
            
            # 解析關鍵字
            keywords = []
            for line in result.split('\n'):
                keyword = line.strip('- ').strip()
                if keyword and len(keyword) > 1:
                    keywords.append(keyword)
            
            return keywords[:10]  # 最多返回10個關鍵字
            
        except Exception as e:
            logger.error(f"關鍵字提取失敗: {str(e)}")
            return []
    
    async def check_status(self) -> Dict[str, Any]:
        """檢查服務狀態"""
        try:
            api_key = self._get_api_key()
            url = f"{self.base_url}/models"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params={"key": api_key},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        return {
                            "available": True,
                            "model": self.model,
                            "provider": "google_gemini",
                            "api_keys_count": len(self.api_keys)
                        }
                    else:
                        return {
                            "available": False,
                            "error": f"API響應錯誤: {response.status}"
                        }
                        
        except Exception as e:
            return {
                "available": False,
                "error": str(e)
            } 