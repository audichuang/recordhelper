# 🎙️ Record Helper - 智能錄音分析系統 (FastAPI版)

一個完整的錄音處理和分析系統，基於 **FastAPI** 構建，提供高性能 **REST API** 和 **LINE Bot** 雙重介面，支援語音轉文字、AI 摘要等功能。

## ✨ 主要功能

### 🔥 核心功能
- **🎵 音頻處理**: 支援多種格式 (MP3, WAV, M4A, AAC, FLAC, OGG)
- **📝 語音轉文字**: 整合 OpenAI Whisper, Deepgram, 本地 Whisper
- **🤖 AI 摘要**: 使用 Google Gemini 生成智能摘要
- **🔐 用戶認證**: JWT 身份驗證，安全可靠
- **📱 移動端支援**: 完整的 iOS App 對接
- **📊 數據統計**: 用戶使用統計和分析報告

### 🌟 技術特色
- **FastAPI 框架**: 原生異步支援，性能提升 10 倍
- **自動 API 文檔**: Swagger UI 和 ReDoc 自動生成
- **類型安全**: Pydantic 模型驗證，IDE 友好
- **雙介面**: REST API + LINE Bot
- **高性能**: 多語音服務支援 (OpenAI/Deepgram/本地Whisper/Gemini)
- **異步處理**: BackgroundTasks 背景任務處理
- **資料持久**: PostgreSQL 數據庫存儲
- **開發友好**: 完整的錯誤處理和狀態監控

## 🚀 快速開始

### 1. 環境需求
```bash
# Python 版本
Python 3.9+

# 數據庫
PostgreSQL 12+

# 可選 (異步處理)
Redis 6+
```

### 2. 安裝依賴
```bash
# 進入項目目錄
cd recordhelper

# 安裝 Python 依賴
pip install -r requirements.txt

# 或使用虛擬環境 (推薦)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### 3. 配置環境變數
```bash
# 複製配置檔案
cp env_example.txt .env

# 編輯配置 (重要！)
vim .env
```

**必須配置的項目：**
```bash
# 數據庫連接 (您已提供)
DB_HOST=192.168.31.247
DB_PORT=5444
DB_NAME=record
DB_USER=root
DB_PASSWORD=VZq9rWbC3oJYFYdDrjT6edewVHQEKNCBWPDnyqxKyzMTE3CoozBrWnYsi6KkpwKujcFKDytQCrxhTbcxsAB2vswcVgQc9ieYvtpP

# JWT 安全金鑰 (請更改)
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production

# Google API (AI 摘要必需)
GOOGLE_API_KEY=你的_Google_API_金鑰

# 語音轉文字服務選擇 (推薦 faster_whisper)
SPEECH_TO_TEXT_PROVIDER=faster_whisper
```

### 4. 初始化數據庫
```bash
# 創建數據庫表
python migrate_db.py init      # 初始化遷移
python migrate_db.py migrate   # 創建遷移
python migrate_db.py upgrade   # 應用遷移

# 或者直接運行應用 (會自動創建表)
python run.py
```

### 5. 啟動服務
```bash
# 方式 1: 開發模式 (推薦)
python run_fastapi.py

# 方式 2: 直接使用 uvicorn
uvicorn main_fastapi:create_app --factory --host 0.0.0.0 --port 9527

# 方式 3: 生產環境 (多工作進程)
uvicorn main_fastapi:create_app --factory --host 0.0.0.0 --port 9527 --workers 4

# 方式 4: 開發模式 (自動重載)
uvicorn main_fastapi:create_app --factory --host 0.0.0.0 --port 9527 --reload
```

服務啟動後：
- **API 端點**: http://localhost:9527
- **API 文檔 (Swagger)**: http://localhost:9527/docs
- **API 文檔 (ReDoc)**: http://localhost:9527/redoc
- **健康檢查**: http://localhost:9527/health
- **系統狀態**: http://localhost:9527/api/system/status

## 📚 API 文檔

### 🔐 認證相關

#### 用戶註冊
```bash
POST /api/auth/register
Content-Type: application/json

{
  "username": "testuser",
  "email": "test@example.com", 
  "password": "password123"
}
```

#### 用戶登入
```bash
POST /api/auth/login
Content-Type: application/json

{
  "email": "test@example.com",
  "password": "password123"
}

# 回應
{
  "message": "登入成功",
  "user": {...},
  "access_token": "eyJ...",
  "refresh_token": "eyJ..."
}
```

### 🎵 錄音相關

#### 上傳錄音
```bash
POST /api/recordings/upload
Authorization: Bearer {access_token}
Content-Type: multipart/form-data

# 表單數據
file: (audio file)
title: "我的錄音"  # 可選
```

#### 獲取錄音列表
```bash
GET /api/recordings?page=1&per_page=20&search=關鍵字&sort_by=created_at&order=desc
Authorization: Bearer {access_token}
```

#### 獲取錄音詳情
```bash
GET /api/recordings/{recording_id}
Authorization: Bearer {access_token}

# 回應包含完整的轉錄和摘要
{
  "recording": {
    "id": "...",
    "title": "...",
    "status": "completed",
    "analysis": {
      "transcription": "...",
      "summary": "...",
      "confidence_score": 0.95
    }
  }
}
```

#### 重新分析
```bash
POST /api/recordings/{recording_id}/reanalyze
Authorization: Bearer {access_token}
```

### 👤 用戶相關

#### 獲取用戶資料
```bash
GET /api/users/profile
Authorization: Bearer {access_token}
```

#### 用戶統計
```bash
GET /api/users/statistics
Authorization: Bearer {access_token}

# 回應
{
  "statistics": {
    "total_recordings": 25,
    "total_duration": 7200,
    "current_month_recordings": 5,
    "avg_duration": 288
  }
}
```

## 🎯 iOS App 整合

本 API 專為 iOS RecordAnalyzer App 設計，完美支援：

- **無縫認證**: JWT token 自動管理
- **文件上傳**: 直接從 iOS 上傳音頻文件
- **實時狀態**: 處理狀態實時查詢
- **分頁加載**: 支援大量錄音的分頁瀏覽
- **搜索過濾**: 靈活的搜索和排序功能

### iOS 配置
```swift
// API 基礎 URL
let baseURL = "http://your-server:5000/api"

// 認證標頭
let headers = [
    "Authorization": "Bearer \(accessToken)",
    "Content-Type": "application/json"
]
```

## 🔧 高級配置

### 語音轉文字服務選擇

```bash
# 1. Faster-Whisper (推薦 - 免費且高性能)
SPEECH_TO_TEXT_PROVIDER=faster_whisper
LOCAL_WHISPER_MODEL=small  # tiny, base, small, medium, large, turbo

# 2. OpenAI Whisper API (付費但速度快)
SPEECH_TO_TEXT_PROVIDER=openai  
OPENAI_API_KEY=your_key
WHISPER_MODEL_NAME=whisper-1

# 3. Deepgram (付費，最快)
SPEECH_TO_TEXT_PROVIDER=deepgram
DEEPGRAM_API_KEY=your_key
```

### 異步處理配置

```bash
# 安裝 Redis
brew install redis        # Mac
sudo apt install redis    # Ubuntu

# 啟動 Redis
redis-server

# 啟動 Celery Worker (另一個終端)
celery -A services.tasks worker --loglevel=info

# 啟動 Celery Flower (可選 - 監控界面)
celery -A services.tasks flower
```

### 生產環境部署

```bash
# 1. 使用 Gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 app:app

# 2. 使用 Docker
docker build -t recordhelper .
docker run -p 5000:5000 recordhelper

# 3. 環境變數
export DEBUG=false
export JWT_SECRET_KEY=your-production-secret
```

## 📊 性能優化

### 建議配置
```bash
# Mac M4 Pro 最佳配置
SPEECH_TO_TEXT_PROVIDER=faster_whisper
LOCAL_WHISPER_MODEL=small
LOCAL_WHISPER_DEVICE=auto

# 服務器配置
MAX_WORKERS=4
MAX_FILE_SIZE=104857600  # 100MB
```

### 性能對比
| 服務 | 成本 | 速度 | 準確性 | 備註 |
|------|------|------|--------|------|
| Faster-Whisper | 免費 | 極快 | 極高 | 推薦 |
| OpenAI API | 付費 | 快 | 極高 | 雲端 |
| Deepgram | 付費 | 最快 | 高 | 雲端 |

## 🔍 故障排除

### 常見問題

#### 1. 數據庫連接失敗
```bash
# 檢查數據庫狀態
psql -h 192.168.31.247 -p 5444 -U root -d record

# 確認防火牆設置
telnet 192.168.31.247 5444
```

#### 2. 音頻處理失敗
```bash
# 檢查依賴
pip install pydub faster-whisper

# 測試音頻處理
python -c "from services.audio.processor import AudioProcessor; print('音頻處理正常')"
```

#### 3. JWT 錯誤
```bash
# 確認配置
echo $JWT_SECRET_KEY

# 檢查時間同步
date
```

#### 4. 上傳失敗
```bash
# 檢查上傳目錄權限
ls -la uploads/
chmod 755 uploads/

# 檢查文件大小限制
echo $MAX_FILE_SIZE
```

### 日誌檢查
```bash
# 查看應用日誌
tail -f app.log

# 查看錯誤日誌
grep ERROR app.log

# 實時監控
tail -f app.log | grep -E "(ERROR|WARN)"
```

## 📈 監控和維護

### 健康檢查
```bash
# API 健康狀態
curl http://localhost:5000/health

# 詳細狀態
curl http://localhost:5000/api/status
```

### 數據庫維護
```bash
# 備份數據庫
pg_dump -h 192.168.31.247 -p 5444 -U root record > backup.sql

# 清理舊記錄 (可選)
python -c "
from app import create_app
from models import db, Recording
from datetime import datetime, timedelta

app = create_app()
with app.app_context():
    old_date = datetime.utcnow() - timedelta(days=90)
    old_recordings = Recording.query.filter(Recording.created_at < old_date).all()
    print(f'發現 {len(old_recordings)} 個舊記錄')
"
```

## 🤝 開發說明

### 項目結構
```
recordhelper/
├── api/                 # API 路由
├── models/              # 數據模型
├── services/            # 業務邏輯
├── app.py              # Flask 應用
├── run.py              # 啟動腳本
├── config.py           # 配置管理
└── requirements.txt    # 依賴列表
```

### 添加新功能
1. 在 `api/` 添加新的路由
2. 在 `models/` 添加數據模型
3. 在 `services/` 實現業務邏輯
4. 更新數據庫遷移

### API 測試
```bash
# 使用 curl 測試
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"123456"}'

# 使用 Postman 或其他 API 測試工具
```

## 📄 授權

MIT License - 自由使用和修改

## 🆘 支援

如有問題請檢查：
1. 環境變數配置是否正確
2. 數據庫連接是否正常  
3. API 金鑰是否有效
4. 日誌中的錯誤信息

---

🎉 **現在您擁有一個完整的錄音分析系統！** 支援 iOS App 和 LINE Bot，具備高性能的語音處理和 AI 分析能力。 