# SRT 字幕模式專用設定

## 概述

本系統已調整為只支援 SRT 字幕格式的逐字稿，移除了純文字模式。這確保所有逐字稿都有精確的時間戳記，可以與音頻同步播放。

## 支援的語音轉文字服務

目前只支援能產生 SRT 格式的服務：

1. **AssemblyAI** (推薦首選)
   - 最佳的 SRT 支援
   - 高精確度的時間戳記
   - 支援中文 (zh)
   - 配置：`SPEECH_TO_TEXT_PROVIDER=assemblyai`

2. **Deepgram** (備用選項)
   - 優秀的 SRT 支援
   - 轉錄速度最快
   - 支援繁體中文 (zh-TW)
   - 配置：`SPEECH_TO_TEXT_PROVIDER=deepgram`

## 不再支援的服務

以下服務因為不支援 SRT 格式，已不再作為選項：

- OpenAI Whisper
- 本地 Whisper (Faster Whisper)
- Gemini Audio

## 前端變更

### RecordingDetailView.swift

1. **移除純文字模式**
   - 移除了 `showTimelineTranscript` 狀態
   - 移除了時間軸/純文字切換按鈕
   - 移除了 SRT 模式切換按鈕

2. **自動顯示邏輯**
   - 如果有 SRT 內容 → 自動顯示互動式字幕
   - 如果沒有 SRT 內容 → 顯示純文字（向後相容）

3. **懸浮播放器**
   - 只要有 SRT 片段就自動顯示
   - 提供播放控制和進度顯示

## 後端優化

### speech_to_text_async.py

1. **智能備用方案**
   ```python
   優先順序：
   1. 主要服務 (根據配置)
   2. AssemblyAI (如果主要服務失敗)
   3. Deepgram (最後備用)
   ```

2. **自動轉換**
   - 如果配置了不支援 SRT 的服務，自動切換到 AssemblyAI
   - 確保所有轉錄都能產生 SRT 格式

## 環境變數配置

```bash
# .env 文件
SPEECH_TO_TEXT_PROVIDER=assemblyai  # 或 deepgram

# AssemblyAI 配置
ASSEMBLYAI_API_KEY_1=your_key_here
ASSEMBLYAI_API_KEY_2=your_backup_key  # 可選備用金鑰

# Deepgram 配置 (備用)
DEEPGRAM_API_KEY_1=your_key_here
DEEPGRAM_API_KEY_2=your_backup_key  # 可選備用金鑰
```

## 資料庫注意事項

確保資料庫中的錄音記錄包含：
- `srt_content`: SRT 格式的字幕內容
- `has_timestamps`: 標記是否有時間戳記

## 測試建議

1. 清空錄音表後，所有新上傳的錄音都會使用支援 SRT 的服務
2. 確認 SRT 內容正確儲存在 `srt_content` 欄位
3. 測試 iOS 前端能正確顯示互動式字幕
4. 測試音頻同步播放功能

## 效能優化

- SRT 解析已優化，支援大量字幕片段
- 使用虛擬化列表，只渲染可見的字幕
- 懸浮播放器使用簡化設計，確保流暢體驗