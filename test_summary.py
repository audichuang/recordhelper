import os
import logging
import time
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template_string
from google import genai
from google.genai import types

# 載入環境變數
load_dotenv()

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class GeminiTester:
    def __init__(self):
        # 載入 Google API 金鑰
        self.api_keys = []
        for i in range(1, 11):
            key = os.getenv(f"GOOGLE_API_KEY_{i}")
            if key:
                self.api_keys.append(key)
        
        if not self.api_keys:
            single_key = os.getenv("GOOGLE_API_KEY")
            if single_key:
                self.api_keys.append(single_key)
        
        if not self.api_keys:
            raise ValueError("請設定至少一個 GOOGLE_API_KEY")
        
        self.clients = [genai.Client(api_key=key) for key in self.api_keys]
        self.current_client_index = 0
        self.model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-preview-05-20")
        
        logging.info(f"初始化完成，載入 {len(self.api_keys)} 個 API 金鑰")

    def generate_summary(self, text: str, summary_type: str = "auto", max_tokens: int = None) -> dict:
        """生成摘要"""
        start_time = time.time()
        text_length = len(text)
        
        try:
            logging.info(f"開始生成摘要，文字長度: {text_length} 字符，類型: {summary_type}")
            
            # 根據類型選擇不同的處理方式
            if summary_type == "short":
                result = self._generate_short_summary(text, max_tokens)
            elif summary_type == "focused":
                result = self._generate_focused_summary(text, max_tokens)
            elif summary_type == "structured":
                result = self._generate_structured_summary(text, max_tokens)
            elif summary_type == "segmented":
                result = self._generate_segmented_summary(text, max_tokens)
            else:  # auto
                result = self._auto_generate_summary(text, max_tokens)
            
            processing_time = time.time() - start_time
            
            return {
                "success": True,
                "summary": result,
                "processing_time": processing_time,
                "text_length": text_length,
                "estimated_minutes": text_length / 180,
                "summary_type": summary_type,
                "max_tokens_used": max_tokens
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logging.error(f"摘要生成失敗: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "processing_time": processing_time,
                "text_length": text_length,
                "summary_type": summary_type
            }

    def _auto_generate_summary(self, text: str, max_tokens: int = None) -> str:
        """自動選擇摘要類型"""
        text_length = len(text)
        
        if text_length <= 1500:
            return self._generate_short_summary(text, max_tokens)
        elif text_length <= 5000:
            return self._generate_focused_summary(text, max_tokens)
        elif text_length <= 15000:
            return self._generate_structured_summary(text, max_tokens)
        else:
            return self._generate_segmented_summary(text, max_tokens)

    def _generate_short_summary(self, text: str, max_tokens: int = None) -> str:
        """簡短摘要"""
        if max_tokens:
            token_limits = [max_tokens, max_tokens//2, max_tokens//3]
        else:
            token_limits = [4000, 2000, 1000, 500]
        
        for i, max_tokens in enumerate(token_limits):
            try:
                if i > 0:
                    logging.info(f"重試簡短摘要，使用 {max_tokens} tokens")
                
                prompt = f"請將以下錄音內容整理成重點摘要：\n\n{text}"
                
                config = types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=max_tokens,
                    top_p=0.8,
                    top_k=10
                )
                
                response = self._call_gemini(prompt, config)
                result = self._extract_text(response)
                
                if i > 0:
                    result += f"\n\n💡 使用簡化模式生成（{max_tokens} tokens）"
                
                return result
                
            except Exception as e:
                if "TOKEN_LIMIT_RETRY" in str(e) and i < len(token_limits) - 1:
                    continue
                elif i == len(token_limits) - 1:
                    return self._generate_emergency_summary(text)
                else:
                    raise

    def _generate_focused_summary(self, text: str, max_tokens: int = None) -> str:
        """重點摘要"""
        # 嘗試不同的 token 限制
        if max_tokens:
            token_limits = [max_tokens, max_tokens//2, max_tokens//3]
        else:
            token_limits = [8000, 4000, 2000, 1000]
        
        for i, max_tokens in enumerate(token_limits):
            try:
                if i > 0:
                    logging.info(f"重試重點摘要，使用 {max_tokens} tokens")
                
                prompt = f"請將以下錄音內容整理成重點摘要，突出主要觀點和關鍵資訊：\n\n{text}"
                
                config = types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=max_tokens,
                    top_p=0.8,
                    top_k=10
                )
                
                response = self._call_gemini(prompt, config)
                result = self._extract_text(response)
                
                if i > 0:
                    result += f"\n\n💡 使用簡化模式生成（{max_tokens} tokens）"
                
                return result
                
            except Exception as e:
                if "TOKEN_LIMIT_RETRY" in str(e) and i < len(token_limits) - 1:
                    continue
                elif i == len(token_limits) - 1:
                    # 最後一次嘗試失敗，返回簡化處理
                    return self._generate_emergency_summary(text)
                else:
                    raise

    def _generate_structured_summary(self, text: str, max_tokens: int = None) -> str:
        """結構化摘要"""
        # 分段處理
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
            max_output_tokens=max_tokens if max_tokens else 10000,
            top_p=0.8,
            top_k=10
        )
        
        response = self._call_gemini(prompt, config)
        return self._extract_text(response)

    def _generate_segmented_summary(self, text: str, max_tokens: int = None) -> str:
        """分段式摘要"""
        # 分割成多個段落
        segments = [text[i:i+3000] for i in range(0, len(text), 3000)]
        
        logging.info(f"分段處理，共 {len(segments)} 段")
        
        # 處理前5段
        segment_summaries = []
        for i, segment in enumerate(segments[:5]):
            try:
                prompt = f"請簡潔總結以下錄音片段的重點（第{i+1}段）：\n\n{segment}"
                
                config = types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=1000,
                    top_p=0.8,
                    top_k=5
                )
                
                response = self._call_gemini(prompt, config)
                summary = self._extract_text(response)
                segment_summaries.append(f"【第{i+1}段】{summary}")
                
                time.sleep(0.5)  # 避免API過於頻繁
                
            except Exception as e:
                logging.warning(f"處理第{i+1}段失敗: {e}")
                segment_summaries.append(f"【第{i+1}段】處理失敗")
        
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
            max_output_tokens=15000,
            top_p=0.8,
            top_k=10
        )
        
        final_response = self._call_gemini(final_prompt, config)
        final_summary = self._extract_text(final_response)
        
        result = f"🎯 【整體摘要】\n{final_summary}\n\n📝 【分段重點】\n{combined_summary}\n\n"
        if len(segments) > 5:
            result += f"💡 註：已分析前5段，總共{len(segments)}段"
        
        return result

    def _generate_emergency_summary(self, text: str) -> str:
        """緊急摘要（當所有正常方法都失敗時）"""
        try:
            logging.info("使用緊急摘要模式")
            # 只取前500字符進行摘要
            short_text = text[:500]
            prompt = f"請用50字以內簡潔總結以下內容的主要重點：\n\n{short_text}"
            
            config = types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=1000,
                top_p=0.9,
                top_k=5
            )
            
            response = self._call_gemini(prompt, config)
            result = self._extract_text(response)
            
            return f"{result}\n\n⚠️ 因長度限制，僅分析了前500字符"
            
        except Exception as e:
            logging.error(f"緊急摘要也失敗: {e}")
            return f"⚠️ 摘要生成失敗\n📄 文字長度: {len(text)} 字符\n💡 建議：嘗試縮短文字或使用分段摘要模式"

    def _call_gemini(self, prompt: str, config: types.GenerateContentConfig):
        """調用 Gemini API"""
        client = self.clients[self.current_client_index]
        
        try:
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return response
        except Exception as e:
            # 切換到下一個 API 金鑰
            self.current_client_index = (self.current_client_index + 1) % len(self.clients)
            logging.warning(f"API 金鑰 {self.current_client_index} 失敗，已切換: {e}")
            raise

    def _extract_text(self, response) -> str:
        """提取回應文字"""
        if not response or not response.candidates:
            raise Exception("無回應內容")
        
        candidate = response.candidates[0]
        finish_reason = str(candidate.finish_reason)
        
        logging.info(f"Gemini 回應狀態: {finish_reason}")
        
        if "STOP" in finish_reason:
            return response.text.strip()
        elif "SAFETY" in finish_reason:
            return "⚠️ 內容可能包含敏感資訊，無法產生摘要"
        elif "MAX_TOKEN" in finish_reason or "LENGTH" in finish_reason:
            if response.text and response.text.strip():
                return f"{response.text.strip()}\n\n⚠️ 摘要因長度限制可能不完整"
            else:
                # 嘗試使用更少的 tokens 重新生成
                logging.warning(f"遇到 token 限制，嘗試簡化處理: {finish_reason}")
                raise Exception("TOKEN_LIMIT_RETRY")
        else:
            if response.text and response.text.strip():
                return f"{response.text.strip()}\n\n⚠️ 摘要可能不完整（{finish_reason}）"
            else:
                raise Exception(f"生成異常：{finish_reason}")


# 創建 Flask 應用
app = Flask(__name__)
gemini_tester = GeminiTester()

# HTML 模板
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gemini 摘要測試工具</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            color: #333;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #555;
        }
        textarea {
            width: 100%;
            min-height: 200px;
            padding: 15px;
            border: 2px solid #e1e5e9;
            border-radius: 8px;
            font-size: 14px;
            line-height: 1.5;
            resize: vertical;
            box-sizing: border-box;
        }
        textarea:focus {
            outline: none;
            border-color: #4285f4;
        }
        select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e1e5e9;
            border-radius: 8px;
            font-size: 14px;
            background-color: white;
            box-sizing: border-box;
        }
        select:focus {
            outline: none;
            border-color: #4285f4;
        }
        .options {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .option {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .option input[type="radio"] {
            margin: 0;
        }
        .button-group {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .btn-primary {
            background-color: #4285f4;
            color: white;
        }
        .btn-primary:hover:not(:disabled) {
            background-color: #3367d6;
        }
        .btn-secondary {
            background-color: #f8f9fa;
            color: #333;
            border: 1px solid #e1e5e9;
        }
        .btn-secondary:hover {
            background-color: #e8f0fe;
        }
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .result {
            margin-top: 20px;
            padding: 20px;
            border-radius: 8px;
            white-space: pre-wrap;
            line-height: 1.6;
        }
        .result.success {
            background-color: #e8f5e8;
            border: 1px solid #c3e6c3;
            color: #2e7d32;
        }
        .result.error {
            background-color: #ffe8e8;
            border: 1px solid #ffb3b3;
            color: #d32f2f;
        }
        .stats {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            margin-top: 15px;
            font-size: 14px;
            color: #666;
        }
        .loading {
            display: none;
            text-align: center;
            margin: 20px 0;
            color: #4285f4;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #4285f4;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Gemini 摘要測試工具</h1>
            <p>貼入轉錄文字，測試不同的摘要模式</p>
        </div>

        <form id="summaryForm">
            <div class="form-group">
                <label for="inputText">輸入文字（語音轉錄文字）：</label>
                <textarea id="inputText" name="text" placeholder="請貼入您要測試的錄音轉錄文字...&#10;&#10;例如：今天的會議主要討論了三個重點..."></textarea>
            </div>

            <div class="form-group">
                <label>摘要類型：</label>
                <div class="options">
                    <div class="option">
                        <input type="radio" id="auto" name="summaryType" value="auto" checked>
                        <label for="auto">自動選擇</label>
                    </div>
                    <div class="option">
                        <input type="radio" id="short" name="summaryType" value="short">
                        <label for="short">簡短摘要 (&lt;1500字)</label>
                    </div>
                    <div class="option">
                        <input type="radio" id="focused" name="summaryType" value="focused">
                        <label for="focused">重點摘要 (1500-5000字)</label>
                    </div>
                    <div class="option">
                        <input type="radio" id="structured" name="summaryType" value="structured">
                        <label for="structured">結構化摘要 (5000-15000字)</label>
                    </div>
                    <div class="option">
                        <input type="radio" id="segmented" name="summaryType" value="segmented">
                        <label for="segmented">分段摘要 (&gt;15000字)</label>
                    </div>
                </div>
            </div>

            <div class="form-group">
                <label for="maxTokens">輸出長度限制（可選）：</label>
                <select id="maxTokens" name="maxTokens">
                    <option value="">自動選擇</option>
                    <option value="2000">簡短 (2,000 tokens)</option>
                    <option value="5000">中等 (5,000 tokens)</option>
                    <option value="10000">較長 (10,000 tokens)</option>
                    <option value="20000">很長 (20,000 tokens)</option>
                    <option value="40000">超長 (40,000 tokens)</option>
                    <option value="65000">最大 (65,000 tokens)</option>
                </select>
            </div>

            <div class="button-group">
                <button type="submit" class="btn-primary">生成摘要</button>
                <button type="button" class="btn-secondary" onclick="clearAll()">清除內容</button>
            </div>
        </form>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <div>正在生成摘要...</div>
        </div>

        <div id="result"></div>
    </div>

    <script>
        document.getElementById('summaryForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(e.target);
            const text = formData.get('text').trim();
            const summaryType = formData.get('summaryType');
            const maxTokens = formData.get('maxTokens');
            
            if (!text) {
                alert('請輸入要摘要的文字');
                return;
            }
            
            // 顯示載入狀態
            document.getElementById('loading').style.display = 'block';
            document.getElementById('result').innerHTML = '';
            e.target.querySelector('button[type="submit"]').disabled = true;
            
            try {
                const response = await fetch('/api/summary', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        text: text,
                        summary_type: summaryType,
                        max_tokens: maxTokens ? parseInt(maxTokens) : null
                    })
                });
                
                const data = await response.json();
                displayResult(data);
                
            } catch (error) {
                displayResult({
                    success: false,
                    error: '網路錯誤：' + error.message
                });
            } finally {
                document.getElementById('loading').style.display = 'none';
                e.target.querySelector('button[type="submit"]').disabled = false;
            }
        });
        
        function displayResult(data) {
            const resultDiv = document.getElementById('result');
            
            if (data.success) {
                resultDiv.innerHTML = `
                    <div class="result success">
                        <strong>📝 摘要結果：</strong><br><br>
                        ${data.summary}
                    </div>
                    <div class="stats">
                        <strong>📊 統計資訊：</strong><br>
                        • 處理時間：${data.processing_time.toFixed(2)} 秒<br>
                        • 文字長度：${data.text_length} 字符<br>
                        • 預估錄音時長：${data.estimated_minutes.toFixed(1)} 分鐘<br>
                        • 使用模式：${getSummaryTypeName(data.summary_type)}<br>
                        ${data.max_tokens_used ? `• 輸出限制：${data.max_tokens_used} tokens` : ''}
                    </div>
                `;
            } else {
                resultDiv.innerHTML = `
                    <div class="result error">
                        <strong>❌ 錯誤：</strong><br><br>
                        ${data.error}
                    </div>
                    <div class="stats">
                        <strong>📊 統計資訊：</strong><br>
                        • 處理時間：${data.processing_time ? data.processing_time.toFixed(2) : 'N/A'} 秒<br>
                        • 文字長度：${data.text_length || 'N/A'} 字符
                    </div>
                `;
            }
        }
        
        function getSummaryTypeName(type) {
            const names = {
                'auto': '自動選擇',
                'short': '簡短摘要',
                'focused': '重點摘要',
                'structured': '結構化摘要',
                'segmented': '分段摘要'
            };
            return names[type] || type;
        }
        
        function clearAll() {
            document.getElementById('inputText').value = '';
            document.getElementById('result').innerHTML = '';
            document.querySelector('input[name="summaryType"][value="auto"]').checked = true;
            document.getElementById('maxTokens').value = '';
        }
        
        // 自動調整文字區域高度
        document.getElementById('inputText').addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.max(200, this.scrollHeight) + 'px';
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/summary', methods=['POST'])
def api_summary():
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({
                "success": False,
                "error": "請提供要摘要的文字"
            }), 400
        
        text = data['text'].strip()
        summary_type = data.get('summary_type', 'auto')
        max_tokens = data.get('max_tokens', None)
        
        if not text:
            return jsonify({
                "success": False,
                "error": "文字內容不能為空"
            }), 400
        
        result = gemini_tester.generate_summary(text, summary_type, max_tokens)
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"API 錯誤: {e}")
        return jsonify({
            "success": False,
            "error": f"伺服器錯誤：{str(e)}"
        }), 500

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "api_keys_count": len(gemini_tester.api_keys),
        "model": gemini_tester.model_name
    })

if __name__ == '__main__':
    print("🚀 Gemini 摘要測試工具啟動中...")
    print(f"📊 載入 {len(gemini_tester.api_keys)} 個 API 金鑰")
    print(f"🤖 使用模型: {gemini_tester.model_name}")
    print("🌐 請訪問: http://127.0.0.1:5002")
    
    app.run(host='0.0.0.0', port=5002, debug=True) 