# SRT 字幕格式支援說明

## 概述

本專案的語音識別服務現已支援標準 SRT (SubRip) 字幕格式輸出。支援的服務包括：

- **AssemblyAI**: 支援單詞級時間戳和說話者識別
- **Deepgram**: 支援說話者識別和精確時間戳
- **Gemini Audio**: 支援說話者識別和時間戳記解析

## SRT 格式說明

SRT 是最常見的字幕格式，格式如下：

```srt
1
00:00:00,000 --> 00:00:05,500
[說話者A] 這是第一句話

2
00:00:05,500 --> 00:00:10,000
[說話者B] 這是第二句話
```

## 功能特點

### 1. 自動說話者識別
- 所有服務都支援說話者識別功能
- 字幕中會標註說話者（如 `[說話者A]`、`[Speaker 1]` 等）

### 2. 精確時間戳
- 支援毫秒級精度的時間戳
- 自動調整字幕時長，避免重疊

### 3. 智能分段
- 根據說話者變化自動分段
- 根據句子結構和標點符號智能斷句
- 支援最大字元數限制，避免字幕過長

## API 回應格式

所有語音識別服務的回應都包含以下 SRT 相關欄位：

```json
{
  "transcript": "完整的轉錄文本",
  "srt": "標準 SRT 格式的字幕內容",
  "has_srt": true,
  "words": [
    {
      "text": "單詞",
      "start": 0.0,
      "end": 0.5,
      "speaker": "A"
    }
  ],
  "segments": [
    {
      "text": "分段文字",
      "start": 0.0,
      "end": 5.0,
      "speaker": "說話者A"
    }
  ]
}
```

## 使用範例

### AssemblyAI
```python
from services.audio.assemblyai_async import AsyncAssemblyAIService

service = AsyncAssemblyAIService(config)
result = await service.transcribe("audio.mp3")

# 獲取 SRT 字幕
srt_content = result.get('srt', '')
if result.get('has_srt'):
    # 儲存為 .srt 檔案
    with open('subtitles.srt', 'w', encoding='utf-8') as f:
        f.write(srt_content)
```

### Deepgram
```python
from services.audio.deepgram_async import AsyncDeepgramService

service = AsyncDeepgramService(config)
result = await service.transcribe("audio.mp3")

# Deepgram 支援兩種方式生成 SRT
# 1. 從 words 數據（如果可用）
# 2. 從 utterances 數據
srt_content = result.get('srt', '')
```

### Gemini Audio
```python
from services.audio.gemini_audio_async import AsyncGeminiAudioService

service = AsyncGeminiAudioService(config)
result = await service.transcribe("audio.mp3")

# Gemini 會解析其特殊格式的時間戳記
# 格式如：[00:01] 說話者A：內容
srt_content = result.get('srt', '')
```

## SRT 格式化工具

專案提供了 `SRTFormatter` 工具類，可以自定義 SRT 生成：

```python
from services.audio.srt_formatter import SRTFormatter

# 格式化時間戳
timestamp = SRTFormatter.format_timestamp(61.5)  # "00:01:01,500"

# 從單詞數據生成 SRT
words = [
    {'text': '你好', 'start': 0, 'end': 0.5, 'speaker': 'A'},
    {'text': '世界', 'start': 0.5, 'end': 1.0, 'speaker': 'A'}
]
srt = SRTFormatter.generate_srt_from_words(
    words, 
    max_chars_per_line=80,  # 每行最大字元數
    max_duration=5.0        # 單個字幕最大持續時間（秒）
)

# 從分段數據生成 SRT
segments = [
    {'text': '第一段', 'start': 0, 'end': 5, 'speaker': '說話者A'},
    {'text': '第二段', 'start': 5, 'end': 10, 'speaker': '說話者B'}
]
srt = SRTFormatter.generate_srt_from_segments(segments)

# 解析 SRT 檔案
subtitles = SRTFormatter.parse_srt(srt_content)
```

## 配置說明

### AssemblyAI 配置
```python
# 啟用說話者識別
speaker_labels = True

# 啟用標點符號
punctuate = True

# 格式化文字
format_text = True
```

### Deepgram 配置
```python
# 啟用說話者識別
diarize = True

# 啟用智能格式化
smart_format = True

# 啟用話語分段
utterances = True
```

### Gemini Audio
Gemini 預設會返回帶時間戳和說話者的格式，無需額外配置。

## 注意事項

1. **檔案大小限制**
   - AssemblyAI: 5GB（支援自動壓縮）
   - Deepgram: 2GB
   - Gemini Audio: 100MB

2. **語言支援**
   - 所有服務都支援中文（zh）
   - 可在配置中指定其他語言

3. **時間戳精度**
   - AssemblyAI: 毫秒級
   - Deepgram: 秒級（小數點）
   - Gemini: 秒級

4. **說話者數量**
   - 大部分服務支援自動識別多個說話者
   - 說話者標識可能因服務而異

## 常見問題

### Q: 如何處理長音頻檔案？
A: AssemblyAI 支援自動壓縮大檔案。其他服務建議先手動壓縮音頻。

### Q: 字幕時間不準確怎麼辦？
A: 可以使用 `SRTFormatter` 的自定義參數調整分段策略，或手動編輯生成的 SRT。

### Q: 如何合併多個服務的結果？
A: 可以優先使用有單詞級時間戳的服務（如 AssemblyAI），並用其他服務的結果進行驗證。

## 未來改進

1. 支援更多字幕格式（VTT、ASS 等）
2. 自動翻譯字幕
3. 字幕樣式自定義
4. 多語言字幕同步