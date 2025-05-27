import logging
import markdown
import os
from datetime import datetime
from flask import Flask, request, abort, jsonify, render_template_string, send_from_directory
from linebot.v3.exceptions import InvalidSignatureError

from config import AppConfig
from services.messaging.line_bot import AsyncLineBotService
from services.audio.base import AudioService


def create_web_routes(app: Flask, config: AppConfig, linebot_service: AsyncLineBotService):
    """創建 Flask 路由"""

    @app.route('/favicon.ico')
    def favicon():
        """提供 favicon 圖標"""
        try:
            # 檢查 favicon.png 是否存在
            if os.path.exists('favicon.png'):
                return send_from_directory('.', 'favicon.png', mimetype='image/png')
            else:
                # 如果沒有 favicon 文件，返回一個簡單的透明圖標
                return '', 204
        except Exception as e:
            logging.warning(f"提供 favicon 時出錯: {e}")
            return '', 404

    @app.route("/", methods=['GET'])
    def home():
        """首頁"""
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>異步LINE Bot 錄音助手</title>
            <meta charset="UTF-8">
            <link rel="icon" type="image/png" href="/favicon.ico">
            <link rel="shortcut icon" type="image/png" href="/favicon.ico">
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
                    <p><strong>語音轉文字：</strong> {linebot_service.speech_to_text_service.get_provider_name()}</p>
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

        # 獲取語音轉文字服務資訊
        stt_info = linebot_service.speech_to_text_service.get_usage_info()
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "processing_messages": processing_count,
            "completed_messages": completed_count,
            "max_workers": config.max_workers,
            "ffmpeg_available": AudioService.check_ffmpeg(),
            "speech_to_text_service": stt_info
        })

    @app.route("/test-gemini", methods=['GET'])
    def test_gemini():
        """測試Gemini API功能"""
        try:
            # 測試AI服務
            test_text = "這是一個測試文字，用來檢查Gemini API是否正常運作。"
            summary = linebot_service.gemini_service.generate_summary(test_text)
            
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

    @app.route("/test-gemini-audio", methods=['GET'])
    def test_gemini_audio():
        """測試 Gemini 音頻服務功能"""
        try:
            # 檢查是否使用 Gemini 音頻服務
            if config.speech_to_text_provider != "gemini_audio":
                return jsonify({
                    "status": "info",
                    "timestamp": datetime.now().isoformat(),
                    "message": f"當前使用的語音轉文字服務是 '{config.speech_to_text_provider}'，非 Gemini 音頻服務",
                    "current_provider": linebot_service.speech_to_text_service.get_provider_name(),
                    "to_enable": "請在 .env 文件中設定 SPEECH_TO_TEXT_PROVIDER=gemini_audio"
                })
            
            # 獲取 Gemini 音頻服務資訊
            usage_info = linebot_service.speech_to_text_service.service.get_usage_info()
            
            return jsonify({
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "service_info": usage_info,
                "provider": linebot_service.speech_to_text_service.get_provider_name(),
                "api_keys_count": len(config.google_api_keys)
            })
            
        except Exception as e:
            return jsonify({
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "provider": config.speech_to_text_provider
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
                <link rel="icon" type="image/png" href="/favicon.ico">
                <link rel="shortcut icon" type="image/png" href="/favicon.ico">
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
            <link rel="icon" type="image/png" href="/favicon.ico">
            <link rel="shortcut icon" type="image/png" href="/favicon.ico">
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
            <link rel="icon" type="image/png" href="/favicon.ico">
            <link rel="shortcut icon" type="image/png" href="/favicon.ico">
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