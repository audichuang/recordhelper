# 錄音助手 LINE Bot

這是一個異步處理的 LINE Bot，能夠將語音訊息轉換為文字並生成摘要。

## 功能特色

- 🎙️ 語音轉文字（使用 OpenAI Whisper）
- 📝 智能摘要（使用 Google Gemini）
- 🌐 **HTML 美化顯示**：將 Markdown 格式完美轉換為網頁展示
- ⚡ 異步處理，避免重複請求
- 🔄 多 API 金鑰輪替使用
- ⏱️ 超時保護機制
- 📊 系統狀態監控
- 🎨 **專業級摘要頁面**：包含統計資訊、可切換顯示逐字稿

## 安裝與設定

### 1. 安裝相依套件

```bash
pip install -r requirements.txt
```

### 2. 環境變數設定

創建 `.env` 檔案並設定以下變數：

```bash
# LINE Bot 設定（必要）
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token_here
LINE_CHANNEL_SECRET=your_line_channel_secret_here

# OpenAI API（必要）
OPENAI_API_KEY=your_openai_api_key_here

# Google API Keys（至少設定一個）
GOOGLE_API_KEY=your_google_api_key_here
# 可選：多個API金鑰輪替使用
# GOOGLE_API_KEY_1=your_google_api_key_1_here
# GOOGLE_API_KEY_2=your_google_api_key_2_here

# 模型設定（可選）
WHISPER_MODEL_NAME=whisper-1
GEMINI_MODEL_NAME=gemini-2.5-flash-preview-05-20

# 系統設定（可選）
THINKING_BUDGET=256
MAX_RETRIES=2
MAX_WORKERS=4
WEBHOOK_TIMEOUT=25

# 長錄音分析設定（可選）
FULL_ANALYSIS=true  # true=完整分析所有段落, false=智能選取關鍵段落
MAX_SEGMENTS_FOR_FULL_ANALYSIS=50  # 完整分析時的最大段落數
```

### 3. 檢查 FFmpeg 安裝

確保系統已安裝 FFmpeg：

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# 檢查安裝
ffmpeg -version
```

### 4. 運行服務

```bash
python main.py
```

服務將在 `http://127.0.0.1:5001` 啟動。

## API 端點

- `GET /` - 首頁和系統資訊
- `POST /callback` - LINE Bot webhook
- `GET /health` - 健康檢查
- `GET /test-gemini` - 測試 Gemini API 功能
- 🆕 `GET /summary/<summary_id>` - 查看美化的 HTML 摘要頁面
- 🆕 `GET /summaries` - 摘要管理中心

## 問題排除

### 常見錯誤

1. **404 錯誤 `/test-gemini`**
   - 已修復：新增測試端點

2. **`Invalid reply token` 錯誤**
   - 原因：reply token 過期或重複使用
   - 解決：系統已改用 push message 發送結果

3. **音訊處理超時**
   - 原因：較長的音訊檔案需要更多處理時間
   - 解決：已加入超時通知機制

4. **摘要處理不完整（MAX_TOKEN 錯誤）**
   - 原因：錄音內容過長，超過 token 限制
   - 解決：已實作智能分段處理
   - 新功能：**支援 2-3 小時超長錄音**
   - 處理策略：
     - 短錄音（<10分鐘）：完整摘要
     - 中等錄音（10-30分鐘）：重點摘要  
     - 長錄音（30分鐘-1.5小時）：結構化摘要
          - **超長錄音（>1.5小時）：分段式摘要**
        - 自動分割成多個段落
        - **🆕 支援完整分析**：分析所有段落（默認啟用）
        - **智能選取模式**：只分析關鍵段落（可選）
        - 生成整體摘要 + 分段重點
        - 包含錄音時長和分析說明

5. **環境變數未設定**
   - 檢查 `.env` 檔案是否存在並正確設定
   - 確保所有必要的 API 金鑰都已填入

### 日誌說明

- `處理時間較長，請稍候` - 正常的超時通知
- `Reply token 已失效或過期` - 正常的 token 過期警告
- `音訊處理完成` - 處理成功完成
- `Whisper 處理時間` - 語音轉文字耗時
- `Gemini 處理時間` - 摘要生成耗時

## 系統要求

- Python 3.8+
- FFmpeg
- LINE Bot API 帳號
- OpenAI API 金鑰
- Google AI API 金鑰

## 長錄音處理能力

### 🎯 **新增超長錄音支援**
- **支援時長**：2-3 小時錄音
- **檔案大小**：最大 100MB
- **🆕 完整分析模式**：
  - **完整分析**：分析所有段落（默認），提供最詳細的摘要
  - **智能選取**：只分析關鍵段落，節省時間和成本
  - 可通過 `FULL_ANALYSIS` 環境變數控制
- **智能處理**：
  - 自動音訊優化（16kHz，單聲道，64k位元率）
  - 分段式摘要生成
  - 多階段處理通知
  - 備用處理機制

### ⏱️ **處理時間說明**
- 短錄音（<10分鐘）：1-2分鐘
- 中等錄音（10-30分鐘）：2-5分鐘
- 長錄音（30分鐘-1.5小時）：5-10分鐘
- **超長錄音（1.5-3小時）：10-20分鐘**

### 📊 **用戶通知機制**
- 25秒：第一次處理通知
- 2分鐘：詳細流程說明
- 5分鐘：最終階段提醒

## 🌐 HTML 美化顯示功能

### 💡 **解決 Markdown 顯示問題**
Gemini 回傳的摘要通常包含 Markdown 格式（如 `**粗體**`、`### 標題`），在 LINE 中顯示會很亂。新的 HTML 美化功能完美解決了這個問題！

### ✨ **主要特色**
- **自動 Markdown 轉換**：將 `**文字**` 轉為 **粗體**，`### 標題` 轉為標題格式
- **美觀的網頁界面**：專業級設計，支援手機和電腦瀏覽
- **統計資訊面板**：錄音時長、字數、處理時間一目了然
- **可切換逐字稿**：點擊按鈕即可顯示/隱藏完整轉錄內容
- **24小時保存**：摘要自動保存24小時，方便隨時查看

### 🔗 **使用方式**
1. 發送錄音給 LINE Bot
2. 處理完成後會收到文字摘要 + HTML 頁面鏈接
3. 點擊 "🌐 美化顯示" 鏈接查看專業格式的摘要
4. 或訪問 `/summaries` 查看所有摘要的管理頁面

### 📱 **響應式設計**
- 手機、平板、電腦完美適配
- 優雅的漸層背景和陰影效果
- 智能的內容折疊和展開

## 注意事項

- 這是開發版本，生產環境請使用 WSGI 服務器
- 建議設定多個 Google API 金鑰以提高穩定性
- **長錄音處理**：2-3小時錄音可能需要10-20分鐘處理時間
- **檔案限制**：建議單個檔案不超過100MB
- **網路穩定性**：長錄音處理需要穩定的網路連線
- **HTML 摘要**：保存24小時後自動清理，建議及時查看 