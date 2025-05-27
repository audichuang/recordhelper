# 📁 項目結構重組說明

## 🎯 重組目標

將原本散落在根目錄的所有Python文件按功能分類組織，提高代碼可維護性和清晰度。

## 📂 新的目錄結構

```
recordhelper/
├── config.py                    # 配置管理
├── main.py                      # 應用入口
├── requirements.txt             # 依賴清單
├── README.md                    # 項目說明
│
├── models/                      # 📊 數據模型
│   ├── __init__.py
│   └── base.py                  # 基礎數據模型和異常類
│
├── services/                    # 🔧 業務服務層
│   ├── __init__.py
│   │
│   ├── audio/                   # 🎵 音頻處理服務
│   │   ├── __init__.py
│   │   ├── base.py              # 基礎音頻服務
│   │   ├── speech_to_text.py    # 語音轉文字統一接口
│   │   ├── whisper.py           # OpenAI Whisper 服務
│   │   ├── deepgram.py          # Deepgram 服務
│   │   ├── local_whisper.py     # 本地 Whisper 服務
│   │   ├── faster_whisper.py    # Faster-Whisper 服務
│   │   └── gemini_audio.py      # Gemini 音頻轉文字服務
│   │
│   ├── ai/                      # 🤖 AI 服務
│   │   ├── __init__.py
│   │   └── gemini.py            # Gemini AI 摘要服務
│   │
│   ├── messaging/               # 💬 消息服務
│   │   ├── __init__.py
│   │   └── line_bot.py          # LINE Bot 服務
│   │
│   └── web/                     # 🌐 Web 服務
│       ├── __init__.py
│       └── routes.py            # Flask 路由
│
├── tests/                       # 🧪 測試代碼
│   ├── __init__.py
│   ├── demo_deepgram_switch.py
│   ├── test_faster_whisper.py
│   ├── test_fixes.py
│   ├── test_gemini_audio.py
│   ├── test_gemini_transcription.py
│   ├── test_local_whisper.py
│   ├── test_modules.py
│   ├── test_speech_to_text.py
│   └── test_summary.py
│
└── docs/                        # 📚 文檔
    ├── PROJECT_STRUCTURE.md     # 項目結構說明
    ├── GEMINI_AUDIO_GUIDE.md
    ├── LOCAL_WHISPER_GUIDE.md
    ├── SPEECH_TO_TEXT_OPTIONS.md
    └── ...
```

## 🔄 文件重新命名對照表

### 音頻服務 (services/audio/)
- `audio_service.py` → `services/audio/base.py`
- `speech_to_text_service.py` → `services/audio/speech_to_text.py`
- `whisper_service.py` → `services/audio/whisper.py`
- `deepgram_service.py` → `services/audio/deepgram.py`
- `local_whisper_service.py` → `services/audio/local_whisper.py`
- `faster_whisper_service.py` → `services/audio/faster_whisper.py`
- `gemini_audio_service.py` → `services/audio/gemini_audio.py`

### AI 服務 (services/ai/)
- `gemini_service.py` → `services/ai/gemini.py`

### 消息服務 (services/messaging/)
- `line_bot_service.py` → `services/messaging/line_bot.py`

### Web 服務 (services/web/)
- `web_routes.py` → `services/web/routes.py`

### 數據模型 (models/)
- `models.py` → `models/base.py`

### 測試代碼 (tests/)
- `test_*.py` → `tests/test_*.py`
- `demo_*.py` → `tests/demo_*.py`

### 文檔 (docs/)
- `*.md` → `docs/*.md` (除了根目錄的 README.md)

## 🔧 導入路徑更新

### 主要服務導入
```python
# 舊的導入方式
from line_bot_service import AsyncLineBotService
from speech_to_text_service import SpeechToTextService
from gemini_service import GeminiService
from models import APIError

# 新的導入方式
from services.messaging.line_bot import AsyncLineBotService
from services.audio.speech_to_text import SpeechToTextService
from services.ai.gemini import GeminiService
from models.base import APIError
```

### 音頻服務內部導入
```python
# 在 services/audio/speech_to_text.py 中
from .whisper import WhisperService
from .deepgram import DeepgramService
from .gemini_audio import GeminiAudioService
```

## ✅ 重組優勢

1. **🎯 清晰的功能分離**
   - 音頻處理、AI服務、消息服務、Web服務各自獨立
   - 單一職責原則，每個模塊功能明確

2. **📈 更好的可維護性**
   - 相關功能代碼集中管理
   - 更容易定位和修改特定功能

3. **🔄 便於擴展**
   - 新增音頻服務只需在 `services/audio/` 下添加
   - 新增AI服務只需在 `services/ai/` 下添加

4. **🧪 測試代碼分離**
   - 所有測試代碼集中在 `tests/` 目錄
   - 避免測試代碼與業務代碼混淆

5. **📚 文檔集中管理**
   - 所有說明文檔集中在 `docs/` 目錄
   - 保持根目錄整潔

## 🚀 使用方式

重組後的項目使用方式完全不變：

```bash
# 啟動應用
python main.py

# 運行測試
python tests/test_speech_to_text.py
python tests/test_gemini_audio.py
```

## 📝 注意事項

1. **導入路徑更新**：所有內部導入都已更新，但如果有外部腳本引用這些文件，需要更新導入路徑

2. **配置不變**：`.env` 文件配置完全不需要修改

3. **功能不變**：所有功能和API接口保持不變，只是文件組織結構改變

4. **向後兼容**：主要API接口保持穩定，確保現有功能正常運行

## 🎉 總結

這次重組大幅提升了項目的組織結構和可維護性，讓開發者能夠：
- 快速找到相關功能代碼
- 輕鬆添加新的服務和功能
- 更好地理解項目架構
- 提高代碼復用性和模塊化程度 