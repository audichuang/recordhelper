import os
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent, AudioMessageContent, FileMessageContent
import openai
from google import genai
from google.genai import types
import requests
import uuid
import subprocess

# 載入環境變數
load_dotenv()

# Flask App 初始化
app = Flask(__name__)

# LINE Bot 設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not all([LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, OPENAI_API_KEY, GOOGLE_API_KEY]):
    print("錯誤：請設定必要的環境變數 (LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, OPENAI_API_KEY, GOOGLE_API_KEY)")
    exit()

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

# 建立 Gemini 客戶端
genai_client = genai.Client(api_key=GOOGLE_API_KEY)

# Whisper 模型設定
WHISPER_MODEL = os.getenv("WHISPER_MODEL_NAME", "whisper-1")

# Gemini 模型設定
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-preview-05-20")
DEFAULT_GEMINI_PROMPT = "請將以下會議記錄或談話內容整理成條列式的重點摘要，並確保語氣專業、內容精煉且易於理解：\n\n{text}"
GEMINI_PROMPT_TEMPLATE = os.getenv("GEMINI_PROMPT_TEMPLATE", DEFAULT_GEMINI_PROMPT)

# 思考預算設定（0 = 關閉思考，1024 = 適中，24576 = 最大）
THINKING_BUDGET = int(os.getenv("THINKING_BUDGET", "512"))  # 預設使用適中的思考預算


# 檢查 ffmpeg 是否可用
def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        print("錯誤：找不到 ffmpeg。請確保已安裝 ffmpeg 並將其加入系統 PATH。")
        return False


# 使用 ffmpeg 轉換音訊格式
def convert_audio(input_file, output_file):
    try:
        subprocess.run(
            ["ffmpeg", "-i", input_file, "-y", output_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return True
    except Exception as e:
        app.logger.error(f"轉換音訊時發生錯誤: {e}")
        return False


@app.route("/", methods=['GET'])
def home():
    """首頁，顯示可用的測試端點"""
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>LINE Bot 錄音助手</title>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; }}
            .status {{ padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .success {{ background-color: #e8f5e8; color: #2e7d32; }}
            .error {{ background-color: #ffebee; color: #c62828; }}
            .info {{ background-color: #e3f2fd; color: #1565c0; }}
            a {{ display: inline-block; background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 5px; }}
            a:hover {{ background-color: #45a049; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎙️ LINE Bot 錄音助手</h1>

            <div class="info">
                <h3>📊 系統狀態</h3>
                <p><strong>Flask 服務：</strong> ✅ 運行中</p>
                <p><strong>OpenAI API：</strong> {'✅ 已設定' if OPENAI_API_KEY else '❌ 未設定'}</p>
                <p><strong>Google API：</strong> {'✅ 已設定' if GOOGLE_API_KEY else '❌ 未設定'}</p>
                <p><strong>LINE Bot：</strong> {'✅ 已設定' if LINE_CHANNEL_ACCESS_TOKEN else '❌ 未設定'}</p>
                <p><strong>FFmpeg：</strong> {'✅ 可用' if check_ffmpeg() else '❌ 不可用'}</p>
            </div>

            <div class="info">
                <h3>🔧 測試工具</h3>
                <p>在部署到 LINE Bot 之前，建議先測試各個 API 是否正常工作：</p>
                <a href="/test-gemini">🧪 測試 Gemini API</a>
                <br><br>
                <p><strong>目前設定：</strong></p>
                <ul>
                    <li>Gemini 模型：{GEMINI_MODEL_NAME}</li>
                    <li>思考預算：{THINKING_BUDGET} tokens</li>
                    <li>Whisper 模型：{WHISPER_MODEL}</li>
                </ul>
            </div>

            <div class="info">
                <h3>📱 LINE Bot 使用方式</h3>
                <p>1. 確保所有 API 測試通過</p>
                <p>2. 設定 LINE Bot Webhook URL 為：<code>https://your-domain.com/callback</code></p>
                <p>3. 在 LINE 中發送錄音訊息進行測試</p>
            </div>
        </div>
    </body>
    </html>
    '''


@app.route("/test-gemini", methods=['GET', 'POST'])
def test_gemini():
    """測試 Gemini API 的端點"""
    if request.method == 'GET':
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Gemini API 測試</title>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 800px; margin: 0 auto; }
                textarea { width: 100%; height: 150px; margin: 10px 0; }
                button { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; cursor: pointer; }
                .result { margin-top: 20px; padding: 20px; background-color: #f9f9f9; border-radius: 5px; }
                .error { background-color: #ffebee; color: #c62828; }
                .success { background-color: #e8f5e8; color: #2e7d32; }
                .config { background-color: #e3f2fd; padding: 15px; margin: 10px 0; border-radius: 5px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🧪 Gemini API 測試工具</h1>

                <div class="config">
                    <h3>目前設定</h3>
                    <p><strong>模型：</strong> ''' + GEMINI_MODEL_NAME + '''</p>
                    <p><strong>思考預算：</strong> ''' + str(THINKING_BUDGET) + ''' tokens</p>
                    <p><strong>API Key：</strong> ''' + ('✅ 已設定' if GOOGLE_API_KEY else '❌ 未設定') + '''</p>
                </div>

                <form method="POST">
                    <h3>測試文字：</h3>
                    <textarea name="test_text" placeholder="輸入要測試的文字...">這是一個測試。請用一句話總結這段文字。</textarea>

                    <h3>思考預算 (0-1024)：</h3>
                    <input type="number" name="thinking_budget" value="0" min="0" max="1024" style="width: 100px;">
                    <small>0 = 關閉思考，1024 = 最大思考</small>

                    <br><br>
                    <button type="submit">🚀 測試 Gemini API</button>
                </form>
            </div>
        </body>
        </html>
        '''

    elif request.method == 'POST':
        try:
            test_text = request.form.get('test_text', '測試文字')
            thinking_budget = int(request.form.get('thinking_budget', 0))

            app.logger.info(f"測試 Gemini API - 文字: {test_text[:50]}...")
            app.logger.info(f"測試設定 - thinking_budget: {thinking_budget}")

            # 建立測試設定
            config = types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=200,
                top_p=0.8,
                top_k=10,
                thinking_config=types.ThinkingConfig(
                    thinking_budget=thinking_budget
                )
            )

            # 發送請求
            response = genai_client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=f"請簡要回應：{test_text}",
                config=config
            )

            # 檢查回應
            if not response or not response.candidates:
                return f'''
                <div class="container">
                    <div class="result error">
                        <h3>❌ 測試失敗</h3>
                        <p>API 返回空回應</p>
                        <a href="/test-gemini">← 返回測試</a>
                    </div>
                </div>
                '''

            candidate = response.candidates[0]
            finish_reason = str(candidate.finish_reason)

            result_html = f'''
            <div class="container">
                <div class="result success">
                    <h3>✅ 測試成功！</h3>
                    <p><strong>回應：</strong></p>
                    <div style="background-color: white; padding: 15px; border-radius: 5px; margin: 10px 0;">
                        {response.text if response.text else '(空回應)'}
                    </div>
                    <p><strong>完成原因：</strong> {finish_reason}</p>
                    <p><strong>使用的設定：</strong></p>
                    <ul>
                        <li>模型：{GEMINI_MODEL_NAME}</li>
                        <li>思考預算：{thinking_budget} tokens</li>
                        <li>最大輸出：200 tokens</li>
                    </ul>
                </div>
                <a href="/test-gemini">← 繼續測試</a>
            </div>
            '''

            return result_html

        except Exception as e:
            app.logger.error(f"Gemini 測試錯誤: {e}")
            return f'''
            <div class="container">
                <div class="result error">
                    <h3>❌ 測試失敗</h3>
                    <p><strong>錯誤訊息：</strong> {str(e)}</p>
                    <p><strong>建議檢查：</strong></p>
                    <ul>
                        <li>Google API Key 是否正確</li>
                        <li>API 配額是否足夠</li>
                        <li>網路連線是否正常</li>
                        <li>模型名稱是否正確</li>
                    </ul>
                    <a href="/test-gemini">← 返回測試</a>
                </div>
            </div>
            '''


@app.route("/callback", methods=['POST'])
def callback():
    # 取得 X-Line-Signature 標頭值
    signature = request.headers['X-Line-Signature']

    # 以文字形式取得請求主體
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # 處理 webhook 主體
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    except Exception as e:
        app.logger.error(f"Error handling webhook: {e}")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=AudioMessageContent)
def handle_audio_message(event):
    line_api = MessagingApi(ApiClient(configuration))
    message_id = event.message.id
    user_id = event.source.user_id
    app.logger.info(f"接收到來自使用者 {user_id} 的錄音訊息 ID: {message_id}")

    # 檢查是否為重複傳送
    webhook_event_id = getattr(event, 'webhook_event_id', None)
    is_redelivery = hasattr(event, 'delivery_context') and getattr(event.delivery_context, 'is_redelivery', False)

    if is_redelivery:
        app.logger.warning(f"跳過重複傳送的訊息: {message_id} (webhook_event_id: {webhook_event_id})")
        return

    # 初始化檔案路徑變數
    temp_file_path = None
    mp3_file_path = None

    try:
        # 1. 下載錄音檔案
        app.logger.info(f"開始下載錄音檔案: {message_id}")

        headers = {
            'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
        }

        response = requests.get(
            f'https://api-data.line.me/v2/bot/message/{message_id}/content',
            headers=headers,
            timeout=30
        )

        if response.status_code != 200:
            raise Exception(f"下載檔案失敗，狀態碼: {response.status_code}")

        temp_file_path = f"/tmp/{uuid.uuid4()}.m4a"
        with open(temp_file_path, 'wb') as fd:
            fd.write(response.content)

        # 轉換 m4a 到 mp3
        mp3_file_path = f"/tmp/{uuid.uuid4()}.mp3"
        if not convert_audio(temp_file_path, mp3_file_path):
            raise Exception("音訊轉換失敗")
        app.logger.info(f"錄音檔案已轉換為 MP3: {mp3_file_path}")

        # 2. 使用 OpenAI Whisper 將錄音轉為逐字稿
        app.logger.info(f"開始使用 Whisper ({WHISPER_MODEL}) 進行語音轉文字...")
        with open(mp3_file_path, "rb") as audio_file:
            transcript = openai.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=audio_file,
                language="zh"  # 指定中文提高準確度
            )
        transcribed_text = transcript.text
        app.logger.info(f"逐字稿 ({WHISPER_MODEL}): {transcribed_text}")

        if not transcribed_text.strip():
            raise Exception("無法辨識語音內容，請嘗試重新錄音")

        # 3. 使用 Gemini 2.5 Flash 將逐字稿轉為重點摘要
        summary_text = generate_summary_with_retry(transcribed_text)

        # 4. 將結果傳回給使用者
        reply_text = f"🎙️ 錄音轉文字：\n{transcribed_text}\n\n📝 重點摘要：\n{summary_text}"

        # 檢查內容長度，避免超過 LINE 訊息限制
        if len(reply_text) > 5000:
            safe_reply_message(line_api, event.reply_token, [
                TextMessage(text=f"🎙️ 錄音轉文字：\n{transcribed_text}"),
                TextMessage(text=f"📝 重點摘要：\n{summary_text}")
            ])
        else:
            safe_reply_message(line_api, event.reply_token, [TextMessage(text=reply_text)])

    except openai.APIError as e:
        app.logger.error(f"OpenAI API 錯誤: {e}")
        error_message = "語音轉文字服務暫時出現問題"

        if "insufficient_quota" in str(e):
            error_message = "⚠️ OpenAI API 配額不足，請檢查帳戶餘額"
        elif "rate_limit" in str(e):
            error_message = "⚠️ API 請求過於頻繁，請稍後再試"

        safe_reply_message(line_api, event.reply_token, [
            TextMessage(text=f"抱歉，{error_message}")
        ])

    except Exception as e:
        app.logger.error(f"處理錄音訊息時發生未預期錯誤: {e}", exc_info=True)

        # 如果有逐字稿但摘要失敗，至少回傳逐字稿
        error_message = "處理您的錄音時發生錯誤"
        if 'transcribed_text' in locals() and transcribed_text.strip():
            error_message = f"摘要功能暫時無法使用，但這是您的錄音內容：\n\n🎙️ {transcribed_text}"

        safe_reply_message(line_api, event.reply_token, [
            TextMessage(text=error_message)
        ])

    finally:
        # 清理暫存檔案
        for file_path in [temp_file_path, mp3_file_path]:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    app.logger.warning(f"清理檔案失敗: {file_path}, 錯誤: {e}")


def generate_summary_with_retry(transcribed_text, max_retries=3):
    """使用重試機制生成摘要（新版 SDK）"""
    import time

    for attempt in range(max_retries):
        try:
            app.logger.info(f"開始使用 Gemini ({GEMINI_MODEL_NAME}) 產生重點摘要... (嘗試 {attempt + 1}/{max_retries})")

            prompt = GEMINI_PROMPT_TEMPLATE.format(text=transcribed_text)

            # 根據重試次數調整輸入長度，避免 MAX_TOKENS 錯誤
            max_input_length = 15000 - (attempt * 5000)  # 逐步縮短輸入
            if len(prompt) > max_input_length:
                shortened_text = transcribed_text[:max_input_length // 2] + "..."
                prompt = GEMINI_PROMPT_TEMPLATE.format(text=shortened_text)
                app.logger.info(f"嘗試 {attempt + 1}: 縮短輸入到 {len(prompt)} 字符")

            # 根據重試次數調整輸出長度
            max_output = max(200, 600 - (attempt * 200))  # 逐步減少輸出長度

            # 使用新版 SDK 的設定方式，加入 thinking_config 控制思考 tokens
            thinking_budget = max(0, min(THINKING_BUDGET, max_output))  # 根據輸出長度調整思考預算

            # 現在可以安全地記錄這些變數
            app.logger.info(f"使用 thinking_budget: {thinking_budget}, max_output_tokens: {max_output}")

            config = types.GenerateContentConfig(
                temperature=0.2,  # 降低溫度提高穩定性
                max_output_tokens=max_output,
                top_p=0.7,
                top_k=10,
                thinking_config=types.ThinkingConfig(
                    thinking_budget=thinking_budget
                )
            )

            response = genai_client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt,
                config=config
            )

            # 檢查回應是否有效
            if not response or not response.candidates:
                raise Exception("API 返回空的回應")

            candidate = response.candidates[0]

            # 新版 SDK 使用枚舉值，需要轉換為字符串比較
            finish_reason_str = str(candidate.finish_reason)
            app.logger.info(f"finish_reason: {finish_reason_str}")

            if "STOP" in finish_reason_str:  # 正常完成
                summary_text = response.text
                app.logger.info(f"重點摘要 ({GEMINI_MODEL_NAME}): {summary_text}")
                return summary_text
            elif "MAX_TOKENS" in finish_reason_str:  # MAX_TOKENS
                if attempt < max_retries - 1:
                    app.logger.info(f"達到 token 限制，將在下次重試中縮短內容")
                    raise Exception("達到最大 token 限制，嘗試縮短內容")
                else:
                    # 最後一次嘗試失敗，返回簡化版本
                    simple_prompt = f"請用一句話總結：{transcribed_text[:500]}"
                    simple_config = types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=100,
                        top_p=0.5,
                        thinking_config=types.ThinkingConfig(
                            thinking_budget=0  # 關閉思考功能，節省 tokens
                        )
                    )
                    try:
                        app.logger.info("嘗試生成簡化版摘要...")
                        simple_response = genai_client.models.generate_content(
                            model=GEMINI_MODEL_NAME,
                            contents=simple_prompt,
                            config=simple_config
                        )
                        if simple_response and simple_response.text:
                            app.logger.info(f"簡化版摘要成功: {simple_response.text}")
                            return f"簡要摘要：{simple_response.text}"
                    except Exception as simple_e:
                        app.logger.error(f"簡化版摘要也失敗: {simple_e}")
                        pass
                    return f"內容較長，無法完整摘要。主要內容：\n{transcribed_text[:200]}..."
            elif "SAFETY" in finish_reason_str:  # SAFETY
                return "⚠️ 內容可能包含敏感資訊，無法產生摘要。"
            elif "RECITATION" in finish_reason_str:  # RECITATION
                return "⚠️ 內容可能涉及版權問題，無法產生摘要。"
            else:
                raise Exception(f"未知的 finish_reason: {finish_reason_str}")

        except Exception as e:
            app.logger.error(f"Gemini API 錯誤 (嘗試 {attempt + 1}/{max_retries}): {e}")

            if "quota" in str(e).lower() or "resource_exhausted" in str(e).lower():
                return f"⚠️ Gemini API 配額不足，無法產生摘要。\n\n原始內容：\n{transcribed_text}"
            elif "blocked" in str(e).lower() or "safety" in str(e).lower():
                return "⚠️ 內容可能包含敏感資訊，無法產生摘要。"
            elif "MAX_TOKENS" in str(e) or "達到最大 token 限制" in str(e):
                if attempt < max_retries - 1:
                    wait_time = 2  # 縮短等待時間
                    app.logger.info(f"等待 {wait_time} 秒後以更短內容重試...")
                    time.sleep(wait_time)
                    continue
                else:
                    return f"內容過長，無法生成完整摘要。\n\n錄音內容：\n{transcribed_text[:300]}..."
            elif attempt < max_retries - 1:
                wait_time = (attempt + 1) * 3
                app.logger.info(f"等待 {wait_time} 秒後重試...")
                time.sleep(wait_time)
                continue
            else:
                return f"摘要功能暫時無法使用，這是您的錄音內容：\n{transcribed_text}"

    return f"摘要功能暫時無法使用，這是您的錄音內容：\n{transcribed_text}"


def safe_reply_message(line_api, reply_token, messages):
    """安全的回覆訊息函數，處理 reply token 過期問題"""
    try:
        line_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )
        app.logger.info("訊息回覆成功")

    except Exception as e:
        app.logger.error(f"回覆訊息失敗: {e}")
        if "Invalid reply token" in str(e) or "invalid reply token" in str(e).lower():
            app.logger.warning("Reply token 已過期或無效，無法回覆訊息")
        else:
            # 如果不是 reply token 問題，記錄詳細錯誤
            app.logger.error(f"非 reply token 錯誤: {e}")


@handler.add(MessageEvent, message=FileMessageContent)
def handle_file_message(event):
    """處理檔案訊息（包含音訊檔案）"""
    # 直接呼叫音訊處理函數
    handle_audio_message(event)


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    line_api = MessagingApi(ApiClient(configuration))
    user_text = event.message.text

    if user_text.startswith("測試"):
        try:
            summary = generate_summary_with_retry(
                "這是一個測試文字，用來檢查 Gemini 2.5 Flash 是否正常運作。大家在討論工作分配的問題，有人提到時間管理很重要。")
            safe_reply_message(line_api, event.reply_token, [
                TextMessage(text=f"✅ 測試成功！\n\n📝 摘要結果：\n{summary}")
            ])
        except Exception as e:
            safe_reply_message(line_api, event.reply_token, [
                TextMessage(text=f"❌ 測試失敗：{e}")
            ])
    else:
        safe_reply_message(line_api, event.reply_token, [
            TextMessage(
                text="🎙️ 請傳送一段錄音，我會為您轉換成逐字稿並整理重點。\n\n💡 或輸入「測試」來檢查摘要功能是否正常。")
        ])


if __name__ == "__main__":
    # 檢查 ffmpeg 是否可用
    if not check_ffmpeg():
        print("警告：找不到 ffmpeg，音訊轉換功能可能無法正常運作。")
        print("請安裝 ffmpeg 並確保它在系統 PATH 中。")
        print("在 macOS 上，您可以使用 'brew install ffmpeg' 來安裝。")

    # 建立 /tmp 資料夾 (如果不存在)
    if not os.path.exists("/tmp"):
        os.makedirs("/tmp")
    app.run(host="0.0.0.0", port=5001, debug=True)