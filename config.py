import os
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()


@dataclass
class AppConfig:
    line_channel_access_token: str
    line_channel_secret: str
    openai_api_key: str
    google_api_keys: List[str]
    # 語音轉文字服務配置
    speech_to_text_provider: str = "openai"  # "openai" 或 "deepgram"
    whisper_model: str = "whisper-1"
    deepgram_api_keys: List[str] = None  # 支援多個 Deepgram API Key
    deepgram_model: str = "nova-2"
    deepgram_language: str = "zh-TW"  # 中文繁體
    # AI 摘要配置
    gemini_model: str = "gemini-2.5-flash-preview-05-20"
    thinking_budget: int = 512
    max_retries: int = 3
    temp_dir: str = "/tmp"
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
        # 基本必要變數
        line_channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        line_channel_secret = os.getenv("LINE_CHANNEL_SECRET")
        
        if not line_channel_access_token or not line_channel_secret:
            raise ValueError("缺少必要的環境變數: LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET")

        # 語音轉文字服務配置
        speech_provider = os.getenv("SPEECH_TO_TEXT_PROVIDER", "openai").lower()
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        
        # Deepgram API 金鑰（支援多個）
        deepgram_api_keys = []
        for i in range(1, 11):  # 支援 DEEPGRAM_API_KEY_1 到 DEEPGRAM_API_KEY_10
            key = os.getenv(f"DEEPGRAM_API_KEY_{i}")
            if key:
                deepgram_api_keys.append(key)
        
        # 如果沒有找到編號的金鑰，檢查單一金鑰
        if not deepgram_api_keys:
            single_key = os.getenv("DEEPGRAM_API_KEY")
            if single_key:
                deepgram_api_keys.append(single_key)
        
        # 根據選擇的服務檢查必要的 API 金鑰
        if speech_provider == "openai" and not openai_api_key:
            raise ValueError("使用 OpenAI Whisper 需要設定 OPENAI_API_KEY")
        elif speech_provider == "deepgram" and not deepgram_api_keys:
            raise ValueError("使用 Deepgram 需要設定至少一個 DEEPGRAM_API_KEY")
        elif speech_provider not in ["openai", "deepgram"]:
            raise ValueError(f"不支援的語音轉文字服務: {speech_provider}，請選擇 'openai' 或 'deepgram'")

        # Google API 金鑰（Gemini 摘要服務）
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
            line_channel_access_token=line_channel_access_token,
            line_channel_secret=line_channel_secret,
            openai_api_key=openai_api_key,
            google_api_keys=google_api_keys,
            # 語音轉文字服務配置
            speech_to_text_provider=speech_provider,
            whisper_model=os.getenv("WHISPER_MODEL_NAME", "whisper-1"),
            deepgram_api_keys=deepgram_api_keys,
            deepgram_model=os.getenv("DEEPGRAM_MODEL", "nova-2"),
            deepgram_language=os.getenv("DEEPGRAM_LANGUAGE", "zh-TW"),
            # AI 摘要配置
            gemini_model=os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-preview-05-20"),
            thinking_budget=int(os.getenv("THINKING_BUDGET", "256")),  # 降低預設值
            max_retries=int(os.getenv("MAX_RETRIES", "2")),  # 降低重試次數
            max_workers=int(os.getenv("MAX_WORKERS", "4")),
            webhook_timeout=int(os.getenv("WEBHOOK_TIMEOUT", "25")),
            full_analysis=os.getenv("FULL_ANALYSIS", "true").lower() == "true",
            max_segments_for_full_analysis=int(os.getenv("MAX_SEGMENTS_FOR_FULL_ANALYSIS", "50"))
        ) 