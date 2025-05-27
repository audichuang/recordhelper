# 語音轉文字服務選項

您的系統現在支援三種語音轉文字服務，可以根據需求選擇最適合的方案。

## 🎯 三種服務比較

| 特性 | 本地 Whisper | OpenAI Whisper API | Deepgram |
|------|-------------|-------------------|----------|
| **成本** | 免費 | $0.006/分鐘 | $0.0043/分鐘 |
| **隱私** | 完全本地處理 | 雲端處理 | 雲端處理 |
| **離線使用** | ✅ 支援 | ❌ 需要網路 | ❌ 需要網路 |
| **設定複雜度** | 中等 | 簡單 | 簡單 |
| **硬體需求** | 中到高 | 無 | 無 |
| **處理速度** | 取決於硬體 | 快 | 快 |
| **準確性** | 高 | 高 | 高 |
| **時間戳** | ✅ 詳細 | ❌ 無 | ✅ 支援 |
| **多語言** | 99+ 語言 | 多語言 | 多語言 |
| **批次處理** | ✅ 支援 | ❌ 單檔 | ❌ 單檔 |

## 🔧 配置方法

### 方案一：本地 OpenAI Whisper（推薦）

**適用情況：**
- 希望節省 API 成本
- 重視隱私保護
- 需要離線使用
- 需要詳細時間戳
- 有足夠的計算資源

**配置：**
```env
SPEECH_TO_TEXT_PROVIDER=local_whisper
LOCAL_WHISPER_MODEL=turbo
LOCAL_WHISPER_LANGUAGE=zh          # 繁體中文也使用 zh
LOCAL_WHISPER_TASK=transcribe
```

**安裝：**
```bash
# 安裝依賴
pip install git+https://github.com/openai/whisper.git

# macOS 安裝 FFmpeg
brew install ffmpeg

# 測試
python test_local_whisper.py
```

### 方案二：OpenAI Whisper API

**適用情況：**
- 需要穩定的雲端服務
- 硬體資源有限
- 不介意 API 成本
- 需要最高準確性

**配置：**
```env
SPEECH_TO_TEXT_PROVIDER=openai
OPENAI_API_KEY=你的_OpenAI_API_金鑰
WHISPER_MODEL_NAME=whisper-1
```

### 方案三：Deepgram

**適用情況：**
- 希望降低成本（比 OpenAI 便宜 28%）
- 需要即時轉錄
- 需要時間戳功能
- 商業用途

**配置：**
```env
SPEECH_TO_TEXT_PROVIDER=deepgram
DEEPGRAM_API_KEY=你的_Deepgram_API_金鑰
DEEPGRAM_MODEL=nova-2
DEEPGRAM_LANGUAGE=zh-TW
```

## 📊 成本分析

### 月使用量 100 小時（6000 分鐘）的成本：

| 服務 | 月成本 | 年成本 | 節省 |
|------|--------|--------|------|
| 本地 Whisper | $0 | $0 | 100% |
| Deepgram | $25.8 | $309.6 | 28% vs OpenAI |
| OpenAI Whisper | $36 | $432 | 基準 |

**電力成本估算（本地 Whisper）：**
- Apple M2 Mac: ~$2-5/月
- 高階 GPU: ~$10-20/月
- 仍然比 API 便宜很多

## 🚀 使用範例

### 統一介面使用

```python
from speech_to_text_service import SpeechToTextService
from config import AppConfig

# 載入配置（會根據 SPEECH_TO_TEXT_PROVIDER 選擇服務）
config = AppConfig.from_env()
stt_service = SpeechToTextService(config)

# 基本轉錄
result = stt_service.transcribe_audio("audio.mp3")
print(f"轉錄結果: {result}")

# 獲取服務資訊
print(f"當前使用: {stt_service.get_provider_name()}")
```

### 本地 Whisper 專用功能

```python
# 詳細轉錄（僅本地 Whisper 支援）
detailed = stt_service.transcribe_with_timestamps("audio.mp3")

print(f"文字: {detailed['text']}")
print(f"語言: {detailed['language']}")
print(f"處理時間: {detailed['processing_time']:.2f}秒")

# 時間戳詳情
for segment in detailed['segments']:
    start, end, text = segment['start'], segment['end'], segment['text']
    print(f"[{start:.2f}s - {end:.2f}s] {text}")
```

### 命令列使用

```bash
# 本地 Whisper 命令列
whisper audio.mp3 --model turbo --language zh --output_format srt

# 測試腳本
python test_local_whisper.py audio.mp3

# 測試所有服務
python test_speech_to_text.py
```

## 🎯 推薦選擇指南

### 個人/開發者
- **推薦：本地 Whisper**
- 理由：免費、隱私、功能豐富

### 小型企業
- **推薦：Deepgram**
- 理由：成本效益、穩定性、商業支援

### 大型企業
- **推薦：OpenAI Whisper API**
- 理由：最高準確性、企業級穩定性

### 特殊需求
- **離線使用：** 必須選擇本地 Whisper
- **即時轉錄：** Deepgram 或 OpenAI API
- **詳細時間戳：** 本地 Whisper 或 Deepgram
- **最低成本：** 本地 Whisper

## 🔄 切換服務

切換服務非常簡單，只需修改環境變數：

```bash
# 切換到本地 Whisper
echo "SPEECH_TO_TEXT_PROVIDER=local_whisper" >> .env

# 切換到 Deepgram
echo "SPEECH_TO_TEXT_PROVIDER=deepgram" >> .env

# 切換到 OpenAI
echo "SPEECH_TO_TEXT_PROVIDER=openai" >> .env
```

重啟服務即可生效，無需修改程式碼。

## 📈 性能優化建議

### 本地 Whisper
- 使用 SSD 存儲
- 充足的 RAM（8GB+）
- GPU 加速（如有）
- 選擇合適的模型大小

### 雲端服務
- 使用多個 API 金鑰輪換
- 實施重試機制
- 監控 API 配額

## 🆘 故障排除

### 本地 Whisper 常見問題
1. **模型下載慢：** 使用代理或手動下載
2. **記憶體不足：** 使用較小模型（small, base）
3. **FFmpeg 錯誤：** 確保已正確安裝

### API 服務問題
1. **配額耗盡：** 設定多個 API 金鑰
2. **網路超時：** 增加超時時間
3. **認證失敗：** 檢查 API 金鑰正確性

## 📚 相關文檔

- [本地 Whisper 詳細指南](LOCAL_WHISPER_GUIDE.md)
- [環境變數設定範例](env_example.txt)
- [測試腳本使用說明](test_local_whisper.py)

---

**建議：** 先從本地 Whisper 開始測試，體驗免費且功能豐富的語音轉文字服務！ 