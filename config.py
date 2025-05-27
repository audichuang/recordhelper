import os
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv
from datetime import timedelta

# 載入環境變數
load_dotenv()


@dataclass
class AppConfig:
    # LINE Bot 配置
    line_channel_access_token: str
    line_channel_secret: str
    
    # API 金鑰
    openai_api_key: str
    google_api_keys: List[str]
    
    # 數據庫配置
    database_url: str
    database_host: str
    database_port: int
    database_name: str
    database_user: str
    database_password: str
    
    # JWT 配置
    jwt_secret_key: str
    jwt_access_token_expires: timedelta
    jwt_refresh_token_expires: timedelta
    
    # 文件上傳配置
    upload_folder: str
    max_file_size: int  # bytes
    allowed_extensions: List[str]
    
    # 語音轉文字服務配置
    speech_to_text_provider: str = "openai"
    whisper_model: str = "whisper-1"
    deepgram_api_keys: List[str] = None
    deepgram_model: str = "nova-2"
    deepgram_language: str = "zh-TW"
    
    # 本地 Whisper 配置
    local_whisper_model: str = "turbo"
    local_whisper_language: str = "zh"
    local_whisper_task: str = "transcribe"
    local_whisper_device: str = "auto"
    
    # AI 摘要配置
    gemini_model: str = "gemini-2.5-flash-preview-05-20"
    thinking_budget: int = 512
    max_retries: int = 3
    temp_dir: str = "/tmp"
    max_workers: int = 4
    webhook_timeout: int = 25
    long_audio_threshold: int = 120
    max_audio_size_mb: int = 100
    segment_processing_delay: float = 0.5
    full_analysis: bool = True
    max_segments_for_full_analysis: int = 50
    
    # Redis 配置
    redis_url: str = "redis://localhost:6379/0"
    
    # Celery 配置
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    @classmethod
    def from_env(cls) -> 'AppConfig':
        """從環境變數創建配置"""
        # LINE Bot 配置（可選）
        line_channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
        line_channel_secret = os.getenv("LINE_CHANNEL_SECRET", "")
        
        # 數據庫配置
        db_host = os.getenv("DB_HOST", "192.168.31.247")
        db_port = int(os.getenv("DB_PORT", "5444"))
        db_name = os.getenv("DB_NAME", "record")
        db_user = os.getenv("DB_USER", "root")
        db_password = os.getenv("DB_PASSWORD", "VZq9rWbC3oJYFYdDrjT6edewVHQEKNCBWPDnyqxKyzMTE3CoozBrWnYsi6KkpwKujcFKDytQCrxhTbcxsAB2vswcVgQc9ieYvtpP")
        
        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        
        # JWT 配置
        jwt_secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
        
        # 語音轉文字服務配置
        speech_provider = os.getenv("SPEECH_TO_TEXT_PROVIDER", "openai").lower()
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        
        # Deepgram API 金鑰
        deepgram_api_keys = []
        for i in range(1, 11):
            key = os.getenv(f"DEEPGRAM_API_KEY_{i}")
            if key:
                deepgram_api_keys.append(key)
        
        if not deepgram_api_keys:
            single_key = os.getenv("DEEPGRAM_API_KEY")
            if single_key:
                deepgram_api_keys.append(single_key)
        
        # Google API 金鑰
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

        # 文件上傳配置
        upload_folder = os.getenv("UPLOAD_FOLDER", "uploads")
        max_file_size = int(os.getenv("MAX_FILE_SIZE", str(100 * 1024 * 1024)))  # 100MB
        
        return cls(
            line_channel_access_token=line_channel_access_token,
            line_channel_secret=line_channel_secret,
            openai_api_key=openai_api_key,
            google_api_keys=google_api_keys,
            
            # 數據庫配置
            database_url=database_url,
            database_host=db_host,
            database_port=db_port,
            database_name=db_name,
            database_user=db_user,
            database_password=db_password,
            
            # JWT 配置
            jwt_secret_key=jwt_secret_key,
            jwt_access_token_expires=timedelta(hours=1),
            jwt_refresh_token_expires=timedelta(days=30),
            
            # 文件上傳配置
            upload_folder=upload_folder,
            max_file_size=max_file_size,
            allowed_extensions=['mp3', 'wav', 'm4a', 'aac', 'flac', 'ogg'],
            
            # 其他現有配置
            speech_to_text_provider=speech_provider,
            whisper_model=os.getenv("WHISPER_MODEL_NAME", "whisper-1"),
            deepgram_api_keys=deepgram_api_keys,
            deepgram_model=os.getenv("DEEPGRAM_MODEL", "nova-2"),
            deepgram_language=os.getenv("DEEPGRAM_LANGUAGE", "zh-TW"),
            local_whisper_model=os.getenv("LOCAL_WHISPER_MODEL", "turbo"),
            local_whisper_language=os.getenv("LOCAL_WHISPER_LANGUAGE", "zh"),
            local_whisper_task=os.getenv("LOCAL_WHISPER_TASK", "transcribe"),
            local_whisper_device=os.getenv("LOCAL_WHISPER_DEVICE", "auto"),
            gemini_model=os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-preview-05-20"),
            thinking_budget=int(os.getenv("THINKING_BUDGET", "256")),
            max_retries=int(os.getenv("MAX_RETRIES", "2")),
            max_workers=int(os.getenv("MAX_WORKERS", "4")),
            webhook_timeout=int(os.getenv("WEBHOOK_TIMEOUT", "25")),
            full_analysis=os.getenv("FULL_ANALYSIS", "true").lower() == "true",
            max_segments_for_full_analysis=int(os.getenv("MAX_SEGMENTS_FOR_FULL_ANALYSIS", "50")),
            
            # Redis 和 Celery
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            celery_broker_url=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
            celery_result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
        ) 