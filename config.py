# -*- coding: utf-8 -*-
"""
應用程式組態設定模組。

此模組定義了應用程式所需的所有配置參數，並提供從環境變數載入這些設定的功能。
使用 `dataclasses` 來定義強型別的配置類別 `AppConfig`，確保配置的清晰度和可維護性。
透過 `.env` 檔案或直接設定環境變數來管理不同的部署環境（例如開發、測試、生產）。
"""

import os
from dataclasses import dataclass, field # 導入 field 以更好處理預設列表
from typing import List, Optional # Optional 用於可選的列表
from dotenv import load_dotenv
from datetime import timedelta

# 載入 .env 檔案中的環境變數，使其可用於 os.getenv
# 這行應該在所有 os.getenv 調用之前執行
load_dotenv()

@dataclass
class AppConfig:
    """
    應用程式配置類別。

    使用 dataclass 自動生成建構函式、__repr__ 等方法。
    所有應用程式的配置參數都在此定義，並透過 `from_env` 類別方法從環境變數載入。
    """
    # --- 專案基本設定 ---
    PROJECT_NAME: str = "FastAPI 錄音助手"
    PROJECT_VERSION: str = "2.1.0"
    PROJECT_DESCRIPTION: str = "支援語音轉文字、AI摘要、LINE Bot等功能的 FastAPI 應用程式"
    API_PREFIX: str = "/api/v1" # API 路由前綴
    ENVIRONMENT: str = "development" # 運行環境 (development, staging, production)
    DEBUG: bool = False # 是否啟用除錯模式
    RELOAD: bool = False # Uvicorn 是否啟用熱重載
    HOST: str = "0.0.0.0" # Uvicorn 監聽主機
    PORT: int = 8000 # Uvicorn 監聽埠號
    WORKERS: int = 1 # Uvicorn worker 數量

    # --- 日誌設定 ---
    LOG_LEVEL: str = "INFO" # 日誌級別 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    LOG_DIR: str = "logs" # 日誌檔案存放目錄
    LOG_FILENAME: str = "app.log" # 日誌檔名

    # --- LINE Bot 配置 (可選) ---
    LINE_CHANNEL_ACCESS_TOKEN: Optional[str] = None # LINE Channel Access Token
    LINE_CHANNEL_SECRET: Optional[str] = None # LINE Channel Secret

    # --- API 金鑰 ---
    OPENAI_API_KEY: Optional[str] = None # OpenAI API 金鑰 (用於 Whisper STT 或其他 OpenAI 服務)
    GEMINI_API_KEY: Optional[str] = None # Gemini API 金鑰 (用於 AI 摘要)
    # DEEPGRAM_API_KEYS: List[str] = field(default_factory=list) # Deepgram API 金鑰列表 (用於 Deepgram STT)
    # GOOGLE_API_KEYS: List[str] = field(default_factory=list) # Google API 金鑰列表 (例如用於 Google STT - 雖然目前未使用)
    # 注意：dataclasses 對於可變預設值 (如 list) 需要使用 default_factory=list

    # --- 資料庫配置 ---
    DATABASE_URL: str # 主要資料庫連接字串 (例如 "postgresql+asyncpg://user:pass@host:port/db")
    DB_ECHO: bool = False # 是否在日誌中輸出 SQLAlchemy 執行的 SQL 語句 (除錯用)
    # 以下為構成 DATABASE_URL 的部分，如果 DATABASE_URL 未直接提供，可用於構建
    DATABASE_HOST: Optional[str] = None
    DATABASE_PORT: Optional[int] = None
    DATABASE_NAME: Optional[str] = None
    DATABASE_USER: Optional[str] = None
    DATABASE_PASSWORD: Optional[str] = None
    
    # --- JWT 認證配置 ---
    SECRET_KEY: str # 用於簽署 JWT 的密鑰，應為一個隨機且保密的字串
    ALGORITHM: str = "HS256" # JWT 簽名演算法
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 # Access Token 過期時間 (分鐘)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7 # Refresh Token 過期時間 (天)

    # --- 檔案上傳配置 ---
    UPLOAD_DIR: str = "uploads" # 上傳檔案的儲存目錄
    MAX_FILE_SIZE_MB: int = 100  # 最大允許上傳的檔案大小 (MB)
    ALLOWED_AUDIO_EXTENSIONS: List[str] = field(default_factory=lambda: ['mp3', 'wav', 'm4a', 'aac', 'flac', 'ogg']) # 允許的音訊檔案擴展名

    # --- 語音轉文字 (STT) 服務配置 ---
    SPEECH_TO_TEXT_PROVIDER: str = "openai" # 使用的 STT 服務提供者 (例如 "openai", "google", "deepgram", "local_whisper")
    # OpenAI Whisper 配置
    WHISPER_MODEL: str = "whisper-1" # OpenAI Whisper 模型名稱
    # Deepgram 配置
    DEEPGRAM_API_KEY: Optional[str] = None # Deepgram API 金鑰 (如果使用多個，考慮改為列表並在 from_env 中處理)
    DEEPGRAM_MODEL: str = "nova-2" # Deepgram 模型名稱
    DEEPGRAM_LANGUAGE: str = "zh-TW" # Deepgram 語言設定
    # 本地 Whisper (Faster Whisper) 配置
    LOCAL_WHISPER_MODEL_SIZE: str = "base" # 本地 Whisper 模型大小 (例如 "tiny", "base", "small", "medium", "large-v2")
    LOCAL_WHISPER_COMPUTE_TYPE: str = "default" # 計算類型 (例如 "default", "int8", "float16")
    LOCAL_WHISPER_DEVICE: str = "auto" # 運行設備 ("auto", "cpu", "cuda")

    # --- AI 模型 (例如 Gemini) 配置 ---
    AI_MODEL_NAME: str = "gemini-1.5-flash-latest" # 使用的 AI 模型名稱 (例如 Gemini)
    AI_MAX_RETRIES: int = 2 # AI API 呼叫最大重試次數
    AI_RETRY_DELAY_SECONDS: int = 5 # AI API 重試間隔秒數

    # --- 背景任務與處理配置 ---
    MAX_CONCURRENT_JOBS: int = 4 # 最大同時處理的背景任務數量 (例如錄音處理)
    JOB_TIMEOUT_SECONDS: int = 1800 # 單個背景任務的超時時間 (秒)

    # --- CORS (跨來源資源共享) 設定 ---
    ALLOWED_ORIGINS: List[str] = field(default_factory=list) # 允許跨域請求的來源列表 (例如 ["http://localhost:3000"])
    # --- Trusted Hosts 設定 ---
    ALLOWED_HOSTS: List[str] = field(default_factory=lambda: ["*"]) # 允許的請求主機名列表

    # --- Redis 配置 (可選，用於快取、Celery Broker/Backend) ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URL: Optional[str] = None # 可以直接提供 Redis 連接 URL

    # --- Celery 配置 (可選，如果使用 Celery 進行背景任務) ---
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    @classmethod
    def from_env(cls) -> 'AppConfig':
        """
        從環境變數載入並創建 AppConfig 實例。

        此方法會讀取預定義的環境變數，並用它們來填充 AppConfig 的各個欄位。
        對於某些配置，如果環境變數未設定，會使用合理的預設值。
        對於敏感資訊 (例如 API 金鑰、資料庫密碼)，強烈建議透過環境變數設定，
        而不是硬編碼在程式碼中。

        Returns:
            AppConfig: 已填充配置值的 AppConfig 實例。

        Raises:
            ValueError: 如果必要的環境變數缺失 (例如 GEMINI_API_KEY)。
        """
        # --- 專案基本設定 ---
        environment = os.getenv("ENVIRONMENT", "development").lower()
        debug_mode = os.getenv("DEBUG", "False").lower() == "true"
        reload_mode = os.getenv("RELOAD", "False").lower() == "true" if environment == "development" else False

        # --- 日誌設定 ---
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        log_dir = os.getenv("LOG_DIR", "logs")
        log_filename = os.getenv("LOG_FILENAME", "app.log")

        # --- LINE Bot 配置 (可選) ---
        line_channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        line_channel_secret = os.getenv("LINE_CHANNEL_SECRET")
        
        # --- API 金鑰 ---
        openai_api_key = os.getenv("OPENAI_API_KEY")
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key: # Gemini API 金鑰為必要項
            raise ValueError("環境變數 GEMINI_API_KEY 未設定，此為必要配置。")

        # --- 資料庫配置 ---
        # 優先使用完整的 DATABASE_URL 環境變數
        database_url = os.getenv("DATABASE_URL")
        db_host = os.getenv("DB_HOST", "localhost") # 預設為本地 PostgreSQL
        db_port = int(os.getenv("DB_PORT", "5432"))
        db_name = os.getenv("DB_NAME", "recordhelper_dev") # 預設資料庫名
        db_user = os.getenv("DB_USER", "devuser") # 預設使用者
        db_password = os.getenv("DB_PASSWORD", "devpass") # 預設密碼
        db_echo = os.getenv("DB_ECHO", "False").lower() == "true"

        if not database_url: # 如果 DATABASE_URL 未直接提供，則嘗試從其他 DB 變數構建
            # 確保使用異步驅動 asyncpg
            database_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        
        # --- JWT 認證配置 ---
        # 重要：生產環境中務必設定一個強隨機的 SECRET_KEY
        secret_key = os.getenv("SECRET_KEY", "a_very_secret_key_that_should_be_changed_in_production")
        if secret_key == "a_very_secret_key_that_should_be_changed_in_production" and environment == "production":
            # 可以在此處添加警告或引發錯誤，提示用戶更改預設密鑰
            print("警告：正在生產環境中使用預設的 JWT SECRET_KEY，請務必更改！")
        
        access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        refresh_token_expire_days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

        # --- 檔案上傳配置 ---
        upload_dir = os.getenv("UPLOAD_DIR", "uploads") # 上傳檔案的儲存目錄
        max_file_size_mb = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
        allowed_audio_extensions_str = os.getenv("ALLOWED_AUDIO_EXTENSIONS", "mp3,wav,m4a,aac,flac,ogg")
        allowed_audio_extensions = [ext.strip() for ext in allowed_audio_extensions_str.split(',')]

        # --- 語音轉文字 (STT) 服務配置 ---
        speech_to_text_provider = os.getenv("SPEECH_TO_TEXT_PROVIDER", "openai").lower()
        whisper_model = os.getenv("WHISPER_MODEL", "whisper-1") # OpenAI Whisper 模型
        deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        deepgram_model = os.getenv("DEEPGRAM_MODEL", "nova-2")
        deepgram_language = os.getenv("DEEPGRAM_LANGUAGE", "zh-TW")
        local_whisper_model_size = os.getenv("LOCAL_WHISPER_MODEL_SIZE", "base")
        local_whisper_compute_type = os.getenv("LOCAL_WHISPER_COMPUTE_TYPE", "default") # 例如 "int8", "float16"
        local_whisper_device = os.getenv("LOCAL_WHISPER_DEVICE", "auto") # "cpu", "cuda"

        # --- AI 模型 (例如 Gemini) 配置 ---
        ai_model_name = os.getenv("AI_MODEL_NAME", "gemini-1.5-flash-latest")
        ai_max_retries = int(os.getenv("AI_MAX_RETRIES", "2"))
        ai_retry_delay_seconds = int(os.getenv("AI_RETRY_DELAY_SECONDS", "5"))

        # --- 背景任務與處理配置 ---
        max_concurrent_jobs = int(os.getenv("MAX_CONCURRENT_JOBS", "4"))
        job_timeout_seconds = int(os.getenv("JOB_TIMEOUT_SECONDS", "1800")) # 30 分鐘

        # --- CORS 和 Trusted Hosts ---
        allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "") # 例如 "http://localhost:3000,https://yourdomain.com"
        allowed_origins = [origin.strip() for origin in allowed_origins_str.split(',') if origin.strip()] if allowed_origins_str else []
        
        allowed_hosts_str = os.getenv("ALLOWED_HOSTS", "*") # 例如 "localhost,yourdomain.com"
        allowed_hosts = [host.strip() for host in allowed_hosts_str.split(',') if host.strip()] if allowed_hosts_str else ["*"]


        # --- Redis 配置 ---
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        redis_password = os.getenv("REDIS_PASSWORD")
        redis_url_env = os.getenv("REDIS_URL")
        
        # 優先使用 REDIS_URL，否則從各部分構建
        redis_url = redis_url_env
        if not redis_url:
            if redis_password:
                redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
            else:
                redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"

        # --- Celery 配置 (如果 REDIS_URL 有效，則預設使用 Redis 作為 Broker 和 Backend) ---
        celery_broker_url = os.getenv("CELERY_BROKER_URL", redis_url if redis_url else None)
        celery_result_backend = os.getenv("CELERY_RESULT_BACKEND", redis_url if redis_url else None)
        
        return cls(
            PROJECT_NAME=os.getenv("PROJECT_NAME", "FastAPI 錄音助手"),
            PROJECT_VERSION=os.getenv("PROJECT_VERSION", "2.1.0"),
            PROJECT_DESCRIPTION=os.getenv("PROJECT_DESCRIPTION", "支援語音轉文字、AI摘要、LINE Bot等功能的 FastAPI 應用程式"),
            API_PREFIX=os.getenv("API_PREFIX", "/api/v1"),
            ENVIRONMENT=environment,
            DEBUG=debug_mode,
            RELOAD=reload_mode,
            HOST=os.getenv("HOST", "0.0.0.0"),
            PORT=int(os.getenv("PORT", "8000")),
            WORKERS=int(os.getenv("WORKERS", "1")),

            LOG_LEVEL=log_level,
            LOG_DIR=log_dir,
            LOG_FILENAME=log_filename,

            LINE_CHANNEL_ACCESS_TOKEN=line_channel_access_token,
            LINE_CHANNEL_SECRET=line_channel_secret,
            
            OPENAI_API_KEY=openai_api_key,
            GEMINI_API_KEY=gemini_api_key,
            
            DATABASE_URL=database_url,
            DB_ECHO=db_echo,
            DATABASE_HOST=db_host, # 儲存原始值，即使已包含在 DATABASE_URL 中
            DATABASE_PORT=db_port,
            DATABASE_NAME=db_name,
            DATABASE_USER=db_user,
            DATABASE_PASSWORD=db_password, # 儲存原始值，即使已包含在 DATABASE_URL 中
            
            SECRET_KEY=secret_key,
            ALGORITHM="HS256", # 通常固定
            ACCESS_TOKEN_EXPIRE_MINUTES=access_token_expire_minutes,
            REFRESH_TOKEN_EXPIRE_DAYS=refresh_token_expire_days,
            
            UPLOAD_DIR=upload_dir,
            MAX_FILE_SIZE_MB=max_file_size_mb,
            ALLOWED_AUDIO_EXTENSIONS=allowed_audio_extensions,
            
            SPEECH_TO_TEXT_PROVIDER=speech_to_text_provider,
            WHISPER_MODEL=whisper_model,
            DEEPGRAM_API_KEY=deepgram_api_key,
            DEEPGRAM_MODEL=deepgram_model,
            DEEPGRAM_LANGUAGE=deepgram_language,
            LOCAL_WHISPER_MODEL_SIZE=local_whisper_model_size,
            LOCAL_WHISPER_COMPUTE_TYPE=local_whisper_compute_type,
            LOCAL_WHISPER_DEVICE=local_whisper_device,

            AI_MODEL_NAME=ai_model_name,
            AI_MAX_RETRIES=ai_max_retries,
            AI_RETRY_DELAY_SECONDS=ai_retry_delay_seconds,

            MAX_CONCURRENT_JOBS=max_concurrent_jobs,
            JOB_TIMEOUT_SECONDS=job_timeout_seconds,

            ALLOWED_ORIGINS=allowed_origins,
            ALLOWED_HOSTS=allowed_hosts,

            REDIS_HOST=redis_host,
            REDIS_PORT=redis_port,
            REDIS_DB=redis_db,
            REDIS_PASSWORD=redis_password,
            REDIS_URL=redis_url,

            CELERY_BROKER_URL=celery_broker_url,
            CELERY_RESULT_BACKEND=celery_result_backend
        )