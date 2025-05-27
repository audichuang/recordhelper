# 🎵 Gemini 音頻理解服務指南

## 📝 簡介

Gemini 音頻理解服務是最新添加的語音轉文字選項，基於 Google 的 Gemini 2.0 模型，支援直接處理音頻文件並提供智能分析。

## ✨ 主要特色

### 🎯 核心功能
- **直接音頻理解**：無需先轉換格式，直接處理音頻文件
- **同時轉錄+摘要**：一次調用獲得完整逐字稿和智能摘要
- **非語音內容分析**：可理解背景音、音樂、環境聲音等
- **多語言支援**：支援中文、英文及多種語言

### 🚀 獨特優勢
- **一步到位**：單次 API 調用同時完成轉錄和摘要
- **深度理解**：可分析說話者情緒、語調、音頻品質
- **格式廣泛**：支援 MP3、WAV、AIFF、AAC、OGG、FLAC
- **大文件支援**：最大支援 100MB，9.5小時音頻

## 🛠️ 配置方法

### 1. 環境變數設定

在 `.env` 文件中設定：

```bash
# 語音轉文字服務選擇 Gemini 音頻
SPEECH_TO_TEXT_PROVIDER=gemini_audio

# Google API 金鑰（必須）
GOOGLE_API_KEY=你的_Google_API_金鑰

# 可選：多個 API 金鑰輪換使用
GOOGLE_API_KEY_1=你的_第一個_Google_API_金鑰
GOOGLE_API_KEY_2=你的_第二個_Google_API_金鑰
GOOGLE_API_KEY_3=你的_第三個_Google_API_金鑰
```

### 2. API 金鑰申請

1. 前往 [Google AI Studio](https://aistudio.google.com/)
2. 登入您的 Google 帳戶
3. 創建新的 API 金鑰
4. 確保啟用 Gemini API 權限

## 📊 支援格式與限制

### ✅ 支援的音頻格式
| 格式 | MIME 類型 | 說明 |
|------|-----------|------|
| MP3  | audio/mp3 | 最常用格式 |
| WAV  | audio/wav | 無損音質 |
| AIFF | audio/aiff | Apple 格式 |
| AAC  | audio/aac | 高效壓縮 |
| OGG  | audio/ogg | 開源格式 |
| FLAC | audio/flac | 無損壓縮 |
| M4A  | audio/aac | iTunes 格式 |

### 📏 技術限制
- **最大文件大小**：100MB
- **最大音頻長度**：9.5小時
- **Token 計算**：每秒音頻 = 32 tokens
- **處理方式**：上傳到 Google 雲端處理

## 🎮 使用方法

### 💬 LINE Bot 使用

1. 確保已配置 `SPEECH_TO_TEXT_PROVIDER=gemini_audio`
2. 重啟服務：`python main.py`
3. 傳送音頻訊息到 LINE Bot
4. 系統將自動：
   - 下載音頻文件
   - 上傳到 Gemini 處理
   - 同時獲得轉錄和摘要
   - 回傳結果

### 🧪 直接測試

```bash
# 測試 Gemini 音頻服務
python test_gemini_audio.py

# 測試特定音頻文件
python -c "
from gemini_audio_service import GeminiAudioService
from config import AppConfig

config = AppConfig.from_env()
service = GeminiAudioService(config)

# 基本轉錄
transcription = service.transcribe_audio('your_audio.mp3')
print('轉錄:', transcription)

# 轉錄+摘要
result = service.transcribe_and_summarize('your_audio.mp3')
print('轉錄:', result['transcription'])
print('摘要:', result['summary'])
"
```

### 🌐 Web API 測試

```bash
# 檢查服務狀態
curl http://localhost:5001/test-gemini-audio

# 查看健康狀態
curl http://localhost:5001/health
```

## 🆚 服務比較

| 特色 | Gemini Audio | Faster-Whisper | OpenAI Whisper | Deepgram |
|------|--------------|----------------|----------------|----------|
| **成本** | 依 API 計費 | 免費 | $0.006/分鐘 | $0.0043/分鐘 |
| **速度** | 快 | 極快 | 快 | 最快 |
| **準確性** | 極高 | 極高 | 極高 | 高 |
| **同時摘要** | ✅ | ❌ | ❌ | ❌ |
| **音頻分析** | ✅ | ❌ | ❌ | ❌ |
| **離線使用** | ❌ | ✅ | ❌ | ❌ |
| **文件大小限制** | 100MB | 無限制 | 25MB | 無限制 |

## 🎯 最佳使用場景

### ✅ 適合使用 Gemini Audio 的情況：
- 需要同時獲得轉錄和摘要
- 音頻包含多種聲音（音樂、環境音等）
- 需要分析說話者情緒和語調
- 對音頻內容進行深度理解
- 音頻文件較小（<100MB）

### ❌ 不建議使用的情況：
- 音頻文件超過 100MB
- 需要離線處理
- 對成本非常敏感
- 只需要基本轉錄功能

## 🔧 進階功能

### 自定義音頻分析

```python
from gemini_audio_service import GeminiAudioService
from config import AppConfig

config = AppConfig.from_env()
service = GeminiAudioService(config)

# 自定義分析提示
custom_prompt = """
請分析這個音頻文件：
1. 說話者的情緒狀態
2. 語速和停頓模式
3. 背景環境分析
4. 音頻品質評估
5. 主要話題和關鍵詞
"""

analysis = service.analyze_audio_content(
    'audio_file.mp3', 
    custom_prompt
)
print(analysis)
```

### Token 計算

```python
# 計算音頻文件需要的 tokens
tokens = service.count_tokens('audio_file.mp3')
print(f"音頻文件需要 {tokens} tokens")

# 估算成本（假設每 1M tokens $1.5）
estimated_cost = (tokens / 1000000) * 1.5
print(f"估算成本: ${estimated_cost:.4f}")
```

## 🚨 注意事項

### 隱私考量
- 音頻文件會暫時上傳到 Google 雲端
- 處理完成後會自動刪除
- 請確保符合您的隱私政策要求

### 錯誤處理
- 如果 Gemini 音頻處理失敗，系統會自動退回到基本轉錄
- 支援 API 金鑰輪換，提高穩定性
- 完整的錯誤日誌記錄

### 性能優化
- 建議使用多個 API 金鑰分散負載
- 音頻文件越小處理越快
- 可根據音頻長度自動調整處理策略

## 🛠️ 疑難排解

### 常見問題

**Q: 為什麼處理失敗？**
A: 檢查：
1. API 金鑰是否正確
2. 音頻文件是否存在
3. 文件大小是否超過 100MB
4. 網路連接是否正常

**Q: 如何提高處理速度？**
A: 
1. 使用較小的音頻文件
2. 配置多個 API 金鑰
3. 選擇合適的音頻格式（MP3 推薦）

**Q: 轉錄準確性如何？**
A: Gemini 2.0 音頻理解準確性很高，特別適合：
- 清晰的語音內容
- 標準普通話/英語
- 無嚴重背景噪音的錄音

## 📚 參考資源

- [Gemini API 音頻理解文檔](https://ai.google.dev/gemini-api/docs/audio?hl=zh-tw)
- [Google AI Studio](https://aistudio.google.com/)
- [專案 GitHub](https://github.com/your-repo/recordhelper)

---

*最後更新：2025-05-27* 