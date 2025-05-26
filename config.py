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
    whisper_model: str = "whisper-1"
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
        required_vars = {
            'line_channel_access_token': os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
            'line_channel_secret': os.getenv("LINE_CHANNEL_SECRET"),
            'openai_api_key': os.getenv("OPENAI_API_KEY")
        }

        missing_vars = [k for k, v in required_vars.items() if not v]
        if missing_vars:
            raise ValueError(f"缺少必要的環境變數: {', '.join(missing_vars)}")

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
            line_channel_access_token=required_vars['line_channel_access_token'],
            line_channel_secret=required_vars['line_channel_secret'],
            openai_api_key=required_vars['openai_api_key'],
            google_api_keys=google_api_keys,
            whisper_model=os.getenv("WHISPER_MODEL_NAME", "whisper-1"),
            gemini_model=os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-preview-05-20"),
            thinking_budget=int(os.getenv("THINKING_BUDGET", "256")),  # 降低預設值
            max_retries=int(os.getenv("MAX_RETRIES", "2")),  # 降低重試次數
            max_workers=int(os.getenv("MAX_WORKERS", "4")),
            webhook_timeout=int(os.getenv("WEBHOOK_TIMEOUT", "25")),
            full_analysis=os.getenv("FULL_ANALYSIS", "true").lower() == "true",
            max_segments_for_full_analysis=int(os.getenv("MAX_SEGMENTS_FOR_FULL_ANALYSIS", "50"))
        ) 