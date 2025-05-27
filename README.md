# 🎙️ 異步LINE Bot 錄音助手

一個高性能的 LINE Bot 錄音轉文字和 AI 摘要服務，支援超長錄音處理和 HTML 美化顯示。

## 🚀 主要特色

### 🎯 核心功能
- **語音轉文字**: 支援 OpenAI Whisper 和 Deepgram 雙引擎，可隨時切換
- **AI 智能摘要**: 使用 Google Gemini AI 生成結構化摘要
- **HTML 美化顯示**: 將 Markdown 格式摘要轉換為專業網頁
- **超長錄音支援**: 智能分段處理，支援 2-3 小時錄音
- **成本優化**: Deepgram 比 OpenAI Whisper 便宜約 28%

### ⚡ 性能優化
- **異步處理**: 避免 LINE webhook 超時和重複訊息
- **多線程支援**: 同時處理多個用戶請求
- **智能重試**: API 失敗自動切換備用金鑰
- **狀態管理**: 防止重複處理同一訊息

### 🎨 用戶體驗
- **即時回應**: 25 秒內必定有回應
- **進度通知**: 長錄音處理時的多階段提醒
- **響應式設計**: 手機和電腦完美適配
- **摘要管理**: 24 小時內可隨時查看歷史摘要

## 📁 項目結構

```
recordhelper/
├── main.py              # 主程序入口
├── config.py            # 配置管理
├── models.py            # 數據模型和異常類
├── audio_service.py           # 音訊處理服務
├── whisper_service.py         # OpenAI Whisper 語音轉文字服務
├── deepgram_service.py        # Deepgram 語音轉文字服務
├── speech_to_text_service.py  # 統一語音轉文字介面
├── gemini_service.py          # Gemini AI 摘要服務
├── line_bot_service.py  # LINE Bot 核心服務
├── web_routes.py        # Flask Web 路由
├── requirements.txt     # 依賴套件
├── .env                 # 環境變數配置
└── README.md           # 項目說明
```

### 🏗️ 模塊化設計

#### `config.py` - 配置管理
- 環境變數載入和驗證
- 系統參數配置
- API 金鑰管理

#### `models.py` - 數據模型
- 異常類定義 (`AudioProcessingError`, `APIError`)
- 處理狀態管理 (`ProcessingStatus`)
- 摘要存儲管理 (`SummaryStorage`)

#### `audio_service.py` - 音訊處理
- FFmpeg 音訊格式轉換
- 臨時檔案管理
- 音訊品質優化

#### `whisper_service.py` / `deepgram_service.py` - 語音轉文字
- OpenAI Whisper API 整合 (更高精度)
- Deepgram API 整合 (更低成本)
- 音訊檔案大小檢查
- 轉錄結果處理

#### `speech_to_text_service.py` - 統一介面
- 支援 OpenAI Whisper 和 Deepgram 無縫切換
- 統一的 API 介面
- 自動錯誤處理和重試
- 服務狀態監控

#### `gemini_service.py` - AI 摘要生成
- Google Gemini AI 整合
- 智能分段摘要策略
- 多種摘要模式（完整/重點/結構化/分段式）

#### `line_bot_service.py` - LINE Bot 服務
- LINE Bot 事件處理
- 異步音訊處理流程
- 用戶互動管理

#### `web_routes.py` - Web 介面
- Flask 路由定義
- HTML 摘要頁面
- 系統狀態監控

## 🛠️ 安裝和設置

### 1. 環境需求
- Python 3.8+
- FFmpeg
- LINE Bot Channel
- 語音轉文字服務 API Key (二選一):
  - OpenAI API Key (Whisper)
  - Deepgram API Key 
- Google AI API Key (Gemini)

### 2. 安裝依賴
```bash
pip install -r requirements.txt
```

### 3. 環境變數設置
創建 `.env` 文件：
```env
# LINE Bot 配置
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_CHANNEL_SECRET=your_line_channel_secret

# 語音轉文字服務配置 (選擇一個)
SPEECH_TO_TEXT_PROVIDER=deepgram  # 或 "openai"

# Deepgram 配置 (推薦 - 更便宜)
DEEPGRAM_API_KEY=your_deepgram_api_key
# 支援多個 Deepgram API Key 提高穩定性和配額
DEEPGRAM_API_KEY_1=your_deepgram_api_key_1
DEEPGRAM_API_KEY_2=your_deepgram_api_key_2
DEEPGRAM_API_KEY_3=your_deepgram_api_key_3
DEEPGRAM_MODEL=nova-2
DEEPGRAM_LANGUAGE=zh-TW

# OpenAI 配置 (備選 - 更精確)
OPENAI_API_KEY=your_openai_api_key
WHISPER_MODEL_NAME=whisper-1

# Google Gemini AI 配置 (必需)
GOOGLE_API_KEY_1=your_google_api_key_1
GOOGLE_API_KEY_2=your_google_api_key_2
# 可設置多個 Google API Key (GOOGLE_API_KEY_1 到 GOOGLE_API_KEY_10)

# 可選配置
GEMINI_MODEL_NAME=gemini-2.5-flash-preview-05-20
MAX_WORKERS=4
WEBHOOK_TIMEOUT=25
FULL_ANALYSIS=true
MAX_SEGMENTS_FOR_FULL_ANALYSIS=50
```

### 💰 成本比較
| 服務 | 價格/分鐘 | 特色 | 適用場景 |
|------|----------|------|---------|
| **Deepgram** | $0.0043 | 🚀 更快速、更便宜 | 高頻使用、成本敏感 |
| **OpenAI Whisper** | $0.006 | 🎯 更高精度 | 重要會議、高精度需求 |

### 4. 啟動服務
```bash
python main.py
```

## 🎯 使用方式

### LINE Bot 功能
1. **發送錄音**: 直接發送音訊檔案給 Bot
2. **查看摘要**: 點擊回傳的 "🌐 美化顯示" 鏈接
3. **系統狀態**: 發送 "狀態" 查看系統資訊
4. **功能測試**: 發送 "測試" 檢查 AI 功能

### Web 介面
- **首頁**: `http://localhost:5001/` - 系統狀態和配置資訊
- **摘要管理**: `http://localhost:5001/summaries` - 查看所有摘要
- **健康檢查**: `http://localhost:5001/health` - API 狀態監控
- **Gemini 測試**: `http://localhost:5001/test-gemini` - AI 功能測試

## 🧠 AI 摘要策略

### 智能分段處理
根據錄音長度自動選擇最適合的處理策略：

1. **短錄音** (< 10分鐘): 完整摘要
2. **中等錄音** (10-30分鐘): 重點摘要
3. **長錄音** (30分鐘-1.5小時): 結構化摘要
4. **超長錄音** (> 1.5小時): 分段式摘要

### 完整分析模式
- 可配置是否分析所有段落
- 支援最多 50 段的完整分析
- 智能選取關鍵段落作為備選方案

## 🌐 HTML 美化顯示

### 主要特色
- **Markdown 渲染**: 完美支援標題、列表、粗體等格式
- **響應式設計**: 自動適配手機和電腦螢幕
- **統計面板**: 顯示錄音時長、字數、處理時間等
- **交互功能**: 可切換顯示/隱藏完整逐字稿
- **專業設計**: 漸層背景、卡片布局、現代化 UI

### 摘要管理
- **24小時保存**: 摘要自動保存 24 小時
- **列表檢視**: 按時間排序的摘要列表
- **快速預覽**: 每個摘要的前 200 字預覽
- **詳細統計**: 創建時間、處理時間、字數等資訊

## 🔧 系統配置

### 性能參數
- `MAX_WORKERS`: 線程池大小 (預設: 4)
- `WEBHOOK_TIMEOUT`: Webhook 超時時間 (預設: 25秒)
- `FULL_ANALYSIS`: 是否完整分析 (預設: true)
- `MAX_SEGMENTS_FOR_FULL_ANALYSIS`: 最大分析段數 (預設: 50)

### API 配置
- 支援多個 Google API Key 輪詢使用
- 自動重試和錯誤處理
- API 配額和速率限制管理

## 📊 監控和日誌

### 日誌系統
- 詳細的處理流程記錄
- 錯誤追蹤和診斷
- 性能指標監控

### 健康檢查
- 系統狀態監控
- API 可用性檢查
- 處理統計資訊

## 🚀 部署建議

### 生產環境
1. 使用 Gunicorn 或 uWSGI 作為 WSGI 服務器
2. 配置 Nginx 作為反向代理
3. 設置 SSL 證書
4. 配置日誌輪轉
5. 設置監控和告警

### Docker 部署
```dockerfile
FROM python:3.9-slim
RUN apt-get update && apt-get install -y ffmpeg
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

## 🧪 測試和驗證

### 語音轉文字服務測試
```bash
# 測試語音轉文字服務配置和切換
python test_speech_to_text.py
```

### 模塊測試
```bash
# 測試所有模塊功能
python test_modules.py
```

### 服務切換指南

#### 切換到 Deepgram (推薦)
1. 設定環境變數：
   ```env
   SPEECH_TO_TEXT_PROVIDER=deepgram
   DEEPGRAM_API_KEY=your_deepgram_api_key
   ```
2. 安裝依賴：`pip install deepgram-sdk>=4.0.0`
3. 重啟服務

#### 切換到 OpenAI Whisper
1. 設定環境變數：
   ```env
   SPEECH_TO_TEXT_PROVIDER=openai
   OPENAI_API_KEY=your_openai_api_key
   ```
2. 重啟服務

### 服務狀態監控
- **Web 首頁**: 顯示當前使用的語音轉文字服務
- **健康檢查 API**: `/health` 端點提供詳細的服務狀態
- **日誌監控**: 系統會記錄服務切換和性能指標

## 📞 技術支援

### 常見問題
1. **Deepgram API 金鑰獲取**: 訪問 [Deepgram 官網](https://deepgram.com/) 註冊並獲取 API 金鑰
2. **成本控制**: 設定 Deepgram 的使用限額和告警
3. **服務切換**: 無需停機，修改環境變數後重啟即可

### 效能調優
- **Deepgram 模型選擇**: `nova-2` (平衡) 或 `nova-3` (精度更高但稍貴)
- **語言設定**: 設定正確的語言代碼可提高識別準確度
- **並發設定**: 根據 API 配額調整 `MAX_WORKERS` 參數

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request 來改進這個項目！

## 📄 授權

MIT License

---

🤖 **Powered by OpenAI Whisper & Google Gemini AI** 