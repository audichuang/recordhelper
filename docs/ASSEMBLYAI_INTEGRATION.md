# AssemblyAI 語音轉文字服務整合指南

## 概述

AssemblyAI 是一個強大的雲端語音識別服務，提供高準確度的語音轉文字功能，支援說話者識別、單詞級時間戳、自動標點符號等進階功能。

## 功能特點

- ✅ **高準確度**：使用最先進的語音識別模型
- ✅ **說話者識別**：自動區分不同說話者
- ✅ **單詞級時間戳**：精確到每個單詞的開始和結束時間
- ✅ **自動標點符號**：智能添加標點符號
- ✅ **大檔案支援**：最大支援 5GB 音檔
- ✅ **自動壓縮**：檔案過大時自動壓縮
- ✅ **API 金鑰輪詢**：支援多個 API 金鑰輪流使用

## 設定步驟

### 1. 獲取 API 金鑰

1. 前往 [AssemblyAI 官網](https://www.assemblyai.com/)
2. 註冊或登入帳號
3. 在控制台獲取 API 金鑰

### 2. 配置環境變數

在 `.env` 檔案中添加：

```bash
# 使用 AssemblyAI 作為主要語音轉文字服務
SPEECH_TO_TEXT_PROVIDER=assemblyai

# AssemblyAI API 金鑰（單一金鑰）
ASSEMBLYAI_API_KEY=你的_AssemblyAI_API_金鑰

# 或者使用多個 API 金鑰（提高配額和穩定性）
ASSEMBLYAI_API_KEY_1=第一個_API_金鑰
ASSEMBLYAI_API_KEY_2=第二個_API_金鑰
ASSEMBLYAI_API_KEY_3=第三個_API_金鑰

# 模型設定（可選）
ASSEMBLYAI_MODEL=best    # 可選: best, conformer, nano
ASSEMBLYAI_LANGUAGE=zh   # 可選: zh=中文, en=英文, auto=自動檢測
```

### 3. 安裝依賴

確保已安裝必要的 Python 套件：

```bash
pip install -r requirements.txt
```

## 使用方式

### 作為主要服務

設定 `SPEECH_TO_TEXT_PROVIDER=assemblyai` 後，所有語音轉文字請求都會使用 AssemblyAI：

```python
# 在 API 端點中自動使用
POST /api/recordings/upload
POST /api/analysis/transcribe
```

### 作為備用服務

當主要服務（如 Deepgram 或 Gemini Audio）失敗時，系統會自動嘗試使用 AssemblyAI 作為備用方案。

### 直接調用（開發測試）

```python
from config import AppConfig
from services.audio.assemblyai_async import AsyncAssemblyAIService

# 創建服務實例
config = AppConfig.from_env()
service = AsyncAssemblyAIService(config)

# 轉錄音檔
result = await service.transcribe("path/to/audio.mp3")
print(result['transcript'])
```

## 價格說明

- **定價**：$0.00025/秒（約 $0.015/分鐘）
- **免費額度**：新用戶通常有免費試用額度
- **計費方式**：按實際處理的音頻時長計費

## 支援格式

AssemblyAI 支援以下音頻格式：
- MP3
- WAV
- M4A
- AAC
- FLAC
- OGG
- 其他常見音頻格式

## 進階功能

### 1. 自動檔案壓縮

當音檔超過 5GB 限制時，系統會自動壓縮：

```python
# 自動壓縮設定
compress_if_needed=True  # 預設開啟
```

### 2. API 金鑰輪詢

配置多個 API 金鑰時，系統會自動輪流使用，提高服務穩定性：

```bash
ASSEMBLYAI_API_KEY_1=key1
ASSEMBLYAI_API_KEY_2=key2
ASSEMBLYAI_API_KEY_3=key3
```

### 3. 語言設定

```bash
# 指定語言
ASSEMBLYAI_LANGUAGE=zh    # 中文
ASSEMBLYAI_LANGUAGE=en    # 英文
ASSEMBLYAI_LANGUAGE=auto  # 自動檢測
```

## 測試

執行測試腳本：

```bash
cd recordhelper
python tests/test_assemblyai.py
```

測試前請確保：
1. 已配置 API 金鑰
2. 準備測試音檔在 `/tmp/test_audio.mp3`

## 故障排除

### 常見問題

1. **API 金鑰無效**
   - 檢查 `.env` 檔案中的金鑰是否正確
   - 確認金鑰有足夠的額度

2. **檔案上傳失敗**
   - 檢查網路連接
   - 確認檔案格式支援
   - 檢查檔案大小（最大 5GB）

3. **轉錄結果為空**
   - 確認音檔中有可識別的語音
   - 檢查語言設定是否正確

### 錯誤訊息

- `AssemblyAI API 金鑰未設置`：需要在 `.env 中配置 API 金鑰
- `檔案大小超過限制`：檔案超過 5GB，需要壓縮或使用其他服務
- `轉錄超時`：音檔處理時間過長，可能是檔案太大或網路問題

## 與其他服務比較

| 特性 | AssemblyAI | OpenAI Whisper | Deepgram | Gemini Audio |
|------|------------|----------------|----------|--------------|
| 價格 | $0.015/分鐘 | $0.006/分鐘 | $0.0043/分鐘 | 依 Gemini 計費 |
| 速度 | 快 | 快 | 最快 | 快 |
| 準確度 | 極高 | 極高 | 高 | 極高 |
| 說話者識別 | ✅ | ❌ | ✅ | ❌ |
| 單詞時間戳 | ✅ | ✅ | ✅ | ❌ |
| 最大檔案 | 5GB | 25MB | 2GB | 100MB |
| 特色功能 | 豐富的進階功能 | 多語言支援 | 即時串流 | 音頻理解+摘要 |

## 更多資訊

- [AssemblyAI 官方文檔](https://www.assemblyai.com/docs)
- [API 參考](https://www.assemblyai.com/docs/api-reference)
- [定價說明](https://www.assemblyai.com/pricing)