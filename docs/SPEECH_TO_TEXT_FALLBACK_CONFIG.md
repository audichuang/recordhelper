# 語音轉文字服務備用順序配置指南

## 概述

系統現在支援智能的語音轉文字服務備用機制，可以在主要服務失敗時自動切換到備用服務。

## 備用順序

1. **主要服務** (根據 `SPEECH_TO_TEXT_PROVIDER` 環境變數配置)
   - 如果設定為 `deepgram` - 使用 Deepgram
   - 如果設定為 `gemini_audio` - 使用 Gemini Audio
   - 如果設定為 `openai` - 使用 OpenAI Whisper
   - 如果設定為 `whisper_local` - 自動改用 Deepgram（本地已棄用）

2. **互為備用** (Deepgram ↔ Gemini Audio)
   - 如果主要服務是 Deepgram 且失敗，自動嘗試 Gemini Audio
   - 如果主要服務是 Gemini Audio 且失敗，自動嘗試 Deepgram

3. **最後備用** - OpenAI Whisper
   - 當上述服務都失敗時，使用 OpenAI Whisper 作為最後備用方案

## API Key 負載均衡

### Deepgram API Keys
支援多個 API key 進行負載均衡：
```bash
# 方式一：多個 API key
DEEPGRAM_API_KEY_1=your-first-key
DEEPGRAM_API_KEY_2=your-second-key
DEEPGRAM_API_KEY_3=your-third-key
# ... 最多支援到 DEEPGRAM_API_KEY_10

# 方式二：單一 API key
DEEPGRAM_API_KEY=your-single-key
```

### Gemini API Keys
支援多個 API key 進行負載均衡：
```bash
# 方式一：多個 API key
GOOGLE_API_KEY_1=your-first-key
GOOGLE_API_KEY_2=your-second-key
GOOGLE_API_KEY_3=your-third-key
# ... 最多支援到 GOOGLE_API_KEY_10

# 方式二：單一 API key
GOOGLE_API_KEY=your-single-key
```

系統會自動隨機選擇一個可用的 API key，實現負載均衡。

## 配置範例

### 使用 Deepgram 為主，Gemini 為備用
```bash
SPEECH_TO_TEXT_PROVIDER=deepgram
DEEPGRAM_API_KEY_1=xxx
DEEPGRAM_API_KEY_2=yyy
GOOGLE_API_KEY_1=aaa
GOOGLE_API_KEY_2=bbb
OPENAI_API_KEY=ccc  # 最後備用
```

### 使用 Gemini 為主，Deepgram 為備用
```bash
SPEECH_TO_TEXT_PROVIDER=gemini_audio
GOOGLE_API_KEY_1=aaa
GOOGLE_API_KEY_2=bbb
DEEPGRAM_API_KEY_1=xxx
DEEPGRAM_API_KEY_2=yyy
OPENAI_API_KEY=ccc  # 最後備用
```

## 特性

1. **自動容錯** - 當一個服務失敗時，自動嘗試下一個服務
2. **負載均衡** - Deepgram 和 Gemini 都支援多個 API key 隨機選擇
3. **時間軸支援** - Deepgram 提供時間軸逐字稿功能
4. **智能日誌** - 詳細記錄每次嘗試和結果

## 注意事項

- 本地 Whisper 已從備用順序中移除（處理速度太慢）
- 確保至少配置一個服務的 API key
- 建議配置多個 API key 以提高可用性
- 備用服務的結果會包含 `backup_provider` 欄位，標示實際使用的服務