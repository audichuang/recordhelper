# SRT 字幕格式指南

## 什麼是 SRT 格式？

SRT (SubRip Subtitle) 是最廣泛使用的字幕格式，具有以下優點：
- 📝 純文字格式，易於編輯
- ⏱️ 精確的時間戳記
- 🌍 跨平台相容性高
- 🎬 所有主流播放器支援

## SRT 格式結構

```srt
1
00:00:00,000 --> 00:00:05,500
第一段字幕文字

2
00:00:05,500 --> 00:00:10,000
第二段字幕文字

3
00:00:10,000 --> 00:00:15,750
第三段字幕文字
```

每個字幕段包含：
1. **序號**：從 1 開始的連續數字
2. **時間碼**：開始時間 --> 結束時間 (格式: HH:MM:SS,mmm)
3. **字幕文字**：實際顯示的內容
4. **空行**：分隔不同字幕段

## 為什麼選擇 AssemblyAI 和 Deepgram？

### 🥇 AssemblyAI - SRT 格式最佳選擇

**原生 SRT 支援**：
- ✅ 直接輸出標準 SRT 格式
- ✅ 精確到毫秒的時間戳
- ✅ 自動分段，適合字幕顯示
- ✅ 支援說話者識別（多人對話）

**API 範例**：
```python
# AssemblyAI 會自動生成 SRT
result = await assemblyai_service.transcribe_audio(file_path)
srt_url = result.srt_url  # 直接獲得 SRT 檔案 URL
```

### 🥈 Deepgram - 速度與準確性平衡

**優秀的時間戳記**：
- ✅ 單詞級時間戳
- ✅ 易於轉換為 SRT 格式
- ✅ 即時串流處理
- ✅ 成本效益最高

**轉換範例**：
```python
# Deepgram 提供詳細的時間資訊
segments = result.segments
srt_content = generate_srt_from_segments(segments)
```

## SRT 格式在專案中的應用

### 1. 精確定位
使用 SRT 格式可以讓用戶：
- 🎯 快速跳轉到特定時間點
- 📍 精確引用某段對話
- ⏩ 瀏覽長錄音的重點部分

### 2. 多語言支援
- 🌏 同一錄音可有多語言字幕
- 🔄 方便翻譯和本地化
- 📱 適合國際化應用

### 3. 搜尋優化
- 🔍 可搜尋時間戳內的文字
- 📊 建立時間索引資料庫
- 🎯 快速定位關鍵詞出現時間

## 實際使用案例

### 會議記錄
```srt
1
00:00:00,000 --> 00:00:03,500
[主持人] 大家好，今天的會議主題是產品發布計劃

2
00:00:03,500 --> 00:00:08,200
[產品經理] 我們預計在下個月15號正式發布新版本

3
00:00:08,200 --> 00:00:12,750
[技術總監] 目前開發進度已完成 85%，測試階段順利
```

### 課程字幕
```srt
1
00:00:00,000 --> 00:00:04,000
今天我們要學習 Python 的基礎語法

2
00:00:04,000 --> 00:00:09,500
首先，讓我們從變數宣告開始
變數是用來儲存資料的容器

3
00:00:09,500 --> 00:00:14,000
在 Python 中，我們不需要宣告變數類型
直接賦值即可使用
```

## 技術實作建議

### 1. 分段策略
- **句子邊界**：在句號、問號處分段
- **時間長度**：每段不超過 5-7 秒
- **字數限制**：每段不超過兩行文字

### 2. 時間戳精確度
- **AssemblyAI**：毫秒級精確度，無需調整
- **Deepgram**：可能需要微調重疊部分
- **本地處理**：建議使用 VAD（語音活動檢測）

### 3. 字元編碼
- 使用 UTF-8 編碼儲存
- 支援所有語言字符
- 避免 BOM 標記

## 整合到 RecordHelper

### API 端點擴充
```python
# 新增 SRT 下載端點
@router.get("/recordings/{recording_id}/srt")
async def download_srt(recording_id: int):
    """下載錄音的 SRT 字幕檔案"""
    # 回傳 SRT 格式的字幕
```

### 資料庫儲存
```sql
-- 新增 SRT 相關欄位
ALTER TABLE recordings 
ADD COLUMN srt_content TEXT,
ADD COLUMN srt_url VARCHAR(255),
ADD COLUMN has_timestamps BOOLEAN DEFAULT FALSE;
```

### 前端顯示
```swift
// iOS 應用中顯示時間戳
struct TranscriptionView: View {
    let segments: [TranscriptionSegment]
    
    var body: some View {
        ForEach(segments) { segment in
            HStack {
                Text(formatTime(segment.start))
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text(segment.text)
                    .font(.body)
            }
        }
    }
}
```

## 最佳實踐

1. **自動儲存**：轉錄完成後自動生成並儲存 SRT
2. **快取策略**：SRT 檔案較小，可完整快取
3. **版本控制**：編輯後保留原始版本
4. **匯出選項**：提供 SRT、VTT、TXT 等格式

## 總結

採用 AssemblyAI 和 Deepgram 作為主要語音轉文字服務，不僅能提供高品質的轉錄結果，更重要的是它們對 SRT 格式的優秀支援，讓 RecordHelper 能夠：

- 🎯 提供精確的時間定位功能
- 📱 增強用戶體驗（快速瀏覽、搜尋）
- 🌍 支援多語言和國際化
- 💰 在成本和品質間取得最佳平衡

透過 SRT 格式的標準化，我們可以確保轉錄結果在各種場景下都能發揮最大價值。