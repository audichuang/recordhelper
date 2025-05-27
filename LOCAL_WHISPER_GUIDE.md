# 本地 OpenAI Whisper 服務指南

## 概述

本地 OpenAI Whisper 服務使用官方的 `openai-whisper` 庫，在您的本地設備上運行語音轉文字，無需 API 調用，完全免費且保護隱私。

## 安裝

### 1. 安裝依賴

```bash
# 安裝官方 openai-whisper 庫
pip install openai-whisper

# 或安裝最新開發版
pip install --upgrade --no-deps --force-reinstall git+https://github.com/openai/whisper.git
```

### 2. 安裝系統依賴

#### macOS
```bash
# 安裝 ffmpeg（用於音訊處理）
brew install ffmpeg
```

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install ffmpeg
```

#### Windows
- 下載並安裝 [FFmpeg](https://ffmpeg.org/download.html)
- 或使用 Chocolatey: `choco install ffmpeg`

## 配置

### 環境變數配置

在 `.env` 檔案中設定：

```env
# 語音轉文字服務提供商
SPEECH_TO_TEXT_PROVIDER=local_whisper

# 本地 Whisper 配置
LOCAL_WHISPER_MODEL=turbo          # 模型選擇
LOCAL_WHISPER_LANGUAGE=zh          # 語言設定
LOCAL_WHISPER_TASK=transcribe      # 任務類型
```

### 可用模型

| 模型名稱 | 參數量 | 英語專用 | 多語言 | 需要VRAM | 相對速度 |
|---------|-------|---------|-------|----------|----------|
| tiny    | 39 M  | ✓       | ✓     | ~1 GB    | ~32x     |
| base    | 74 M  | ✓       | ✓     | ~1 GB    | ~16x     |
| small   | 244 M | ✓       | ✓     | ~2 GB    | ~6x      |
| medium  | 769 M | ✓       | ✓     | ~5 GB    | ~2x      |
| large   | 1550 M| X       | ✓     | ~10 GB   | 1x       |
| large-v2| 1550 M| X       | ✓     | ~10 GB   | 1x       |
| large-v3| 1550 M| X       | ✓     | ~10 GB   | 1x       |
| turbo   | 809 M | X       | ✓     | ~6 GB    | ~8x      |

**推薦：**
- **turbo**: 最新模型，平衡了速度和準確性
- **small**: 適合一般用途，資源需求較低
- **large-v3**: 最高準確性，但需要更多資源

### 支援語言

支援 100 種語言，包括但不限於：
- `zh`: 中文（包含簡體和繁體中文，Whisper 會自動識別和處理）
- `yue`: 粵語（廣東話）
- `ja`: 日語
- `en`: 英語
- `ko`: 韓語
- `fr`: 法語
- `de`: 德語
- `es`: 西班牙語

**重要說明：**
- **繁體中文使用者請設定 `LOCAL_WHISPER_LANGUAGE=zh`**
- Whisper 沒有區分簡體和繁體中文的獨立代碼
- 模型會自動處理繁體中文輸入和輸出

## 使用方法

### 1. 基本轉錄

```python
from speech_to_text_service import SpeechToTextService
from config import AppConfig

# 載入配置
config = AppConfig.from_env()

# 初始化服務
stt_service = SpeechToTextService(config)

# 轉錄音訊
result = stt_service.transcribe_audio("audio.mp3")
print(f"轉錄結果: {result}")
```

### 2. 詳細轉錄（包含時間戳）

```python
# 獲取詳細轉錄結果
detailed_result = stt_service.transcribe_with_timestamps("audio.mp3")

print(f"文字: {detailed_result['text']}")
print(f"語言: {detailed_result['language']}")
print(f"處理時間: {detailed_result['processing_time']:.2f}秒")

# 顯示時間戳
for segment in detailed_result['segments']:
    start = segment['start']
    end = segment['end']
    text = segment['text']
    print(f"[{start:.2f}s - {end:.2f}s] {text}")
```

### 3. 命令列使用

```bash
# 測試本地 Whisper 服務
python test_local_whisper.py

# 測試特定音訊檔案
python test_local_whisper.py /path/to/audio.mp3

# 使用官方 whisper 命令列工具
whisper audio.mp3 --model turbo --language zh
```

## 性能優化

### 1. GPU 加速

如果您有 NVIDIA GPU：

```bash
# 安裝 CUDA 支援的 PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 2. Apple Silicon 優化

在 Apple M1/M2 Mac 上會自動使用 Metal Performance Shaders (MPS) 加速。

### 3. 記憶體優化

對於記憶體受限的環境：
- 使用較小的模型（`tiny`, `base`, `small`）
- 設定 `LOCAL_WHISPER_MODEL=small`

## 優勢比較

| 特性 | 本地 Whisper | OpenAI API | Deepgram |
|------|-------------|------------|----------|
| 成本 | 免費 | $0.006/分鐘 | $0.0043/分鐘 |
| 隱私 | 完全本地 | 雲端處理 | 雲端處理 |
| 離線使用 | ✓ | ✗ | ✗ |
| 時間戳 | ✓ | ✗ | ✓ |
| 多語言 | 99 種語言 | 多語言 | 多語言 |
| 速度 | 取決於硬體 | 快 | 快 |
| 準確性 | 高 | 高 | 高 |

## 故障排除

### 常見問題

1. **模型下載慢**
   ```bash
   # 手動下載模型到快取目錄
   python -c "import whisper; whisper.load_model('turbo')"
   ```

2. **記憶體不足**
   ```env
   # 使用較小的模型
   LOCAL_WHISPER_MODEL=small
   ```

3. **FFmpeg 錯誤**
   ```bash
   # 確保 FFmpeg 已安裝並在 PATH 中
   ffmpeg -version
   ```

4. **CUDA 錯誤**
   ```bash
   # 檢查 PyTorch CUDA 支援
   python -c "import torch; print(torch.cuda.is_available())"
   ```

### 日誌除錯

啟用詳細日誌：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 最佳實踐

1. **模型選擇**：
   - 開發/測試：使用 `small` 或 `base`
   - 生產環境：使用 `turbo` 或 `large-v3`

2. **批次處理**：
   - 對於大量音訊文件，考慮批次處理
   - 使用多執行緒處理多個檔案

3. **快取管理**：
   - 模型會自動快取到 `~/.cache/whisper/`
   - 定期清理舊模型節省空間

4. **監控資源**：
   - 監控 CPU/GPU 使用率
   - 監控記憶體使用情況

## 支援

如果遇到問題，請檢查：
1. [OpenAI Whisper 官方文檔](https://github.com/openai/whisper)
 