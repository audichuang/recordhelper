import os
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent, AudioMessageContent
import openai
import google.generativeai as genai
import requests
from pydub import AudioSegment
import uuid

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
genai.configure(api_key=GOOGLE_API_KEY)

# Whisper 模型設定
WHISPER_MODEL = os.getenv("WHISPER_MODEL_NAME", "whisper-1")

# Gemini 模型設定
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-pro-latest")
DEFAULT_GEMINI_PROMPT = "請將以下會議記錄或談話內容整理成條列式的重點摘要，並確保語氣專業、內容精煉且易於理解：\n\n{text}"
GEMINI_PROMPT_TEMPLATE = os.getenv("GEMINI_PROMPT_TEMPLATE", DEFAULT_GEMINI_PROMPT)

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
    app.logger.info(f"接收到來自使用者 {event.source.user_id} 的錄音訊息 ID: {message_id}")
    
    try:
        # 1. 下載錄音檔案
        app.logger.info(f"開始下載錄音檔案: {message_id}")
        message_content = line_api.get_message_content(message_id=message_id)
        temp_file_path = f"/tmp/{uuid.uuid4()}.m4a" # LINE 的錄音是 m4a 格式
        with open(temp_file_path, 'wb') as fd:
            for chunk in message_content.iter_content():
                fd.write(chunk)

        # 轉換 m4a 到 mp3 (Whisper 支援 mp3)
        audio = AudioSegment.from_file(temp_file_path, format="m4a")
        mp3_file_path = f"/tmp/{uuid.uuid4()}.mp3"
        audio.export(mp3_file_path, format="mp3")
        app.logger.info(f"錄音檔案已轉換為 MP3: {mp3_file_path}")

        # 2. 使用 OpenAI Whisper 將錄音轉為逐字稿
        app.logger.info(f"開始使用 Whisper ({WHISPER_MODEL}) 進行語音轉文字...")
        with open(mp3_file_path, "rb") as audio_file:
            transcript = openai.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=audio_file
            )
        transcribed_text = transcript.text
        app.logger.info(f"逐字稿 ({WHISPER_MODEL}): {transcribed_text}")

        # 3. 使用 Gemini API 將逐字稿轉為重點摘要
        app.logger.info(f"開始使用 Gemini ({GEMINI_MODEL_NAME}) 產生重點摘要...")
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        prompt = GEMINI_PROMPT_TEMPLATE.format(text=transcribed_text)
        app.logger.info(f"Gemini Prompt: {prompt}")
        response = model.generate_content(prompt)
        summary_text = response.text
        app.logger.info(f"重點摘要 ({GEMINI_MODEL_NAME}): {summary_text}")

        # 4. 將重點摘要傳回給使用者
        line_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"錄音重點摘要：\n{summary_text}")]
            )
        )

    except openai.APIError as e:
        app.logger.error(f"OpenAI API 錯誤: {e}")
        line_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="抱歉，語音轉文字服務暫時出現問題，請稍後再試。")]
            )
        )
    except genai.types.generation_types.BlockedPromptException as e:
        app.logger.error(f"Gemini API 內容被阻擋錯誤: {e}")
        line_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="抱歉，生成的摘要內容可能違反了使用政策，無法提供。")]
            )
        )
    except Exception as e:
        app.logger.error(f"處理錄音訊息時發生未預期錯誤: {e}", exc_info=True)
        line_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="處理您的錄音時發生錯誤，請稍後再試。")]
            )
        )
    finally:
        # 清理暫存檔案
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if os.path.exists(mp3_file_path):
            os.remove(mp3_file_path)

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    line_api = MessagingApi(ApiClient(configuration))
    line_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="請傳送一段錄音，我會為您轉換成逐字稿並整理重點。")]
        )
    )

if __name__ == "__main__":
    # 建立 /tmp 資料夾 (如果不存在)
    if not os.path.exists("/tmp"):
        os.makedirs("/tmp")
    app.run(port=5001, debug=True) # 您可以更改埠號 