# 增强的分阶段推送通知系统

## 📋 功能概述

实现了更细致的录音处理状态管理和推送通知系统，将录音处理过程分为多个阶段，每个阶段都会发送相应的推送通知。

## 🚀 新功能

### 1. 扩展的录音状态

新增了以下录音处理状态：

| 状态 | 值 | 描述 |
|------|---------|------|
| `UPLOADING` | `uploading` | 上传中 |
| `PROCESSING` | `processing` | 准备处理 |
| `TRANSCRIBING` | `transcribing` | **新增** - 逐字稿处理中 |
| `TRANSCRIBED` | `transcribed` | **新增** - 逐字稿完成，摘要处理中 |
| `SUMMARIZING` | `summarizing` | **新增** - 摘要处理中 |
| `COMPLETED` | `completed` | 全部完成 |
| `FAILED` | `failed` | 处理失败 |

### 2. 分阶段推送通知

#### 2.1 上传录音后的处理流程
```
上传录音 → TRANSCRIBING → 逐字稿完成通知 → TRANSCRIBED → SUMMARIZING → 摘要完成通知 → COMPLETED
```

#### 2.2 通知类型

##### 逐字稿完成通知
- **标题**: "逐字稿完成"
- **内容**: "「{录音标题}」的逐字稿已生成，正在生成摘要..."
- **数据**: `type: "transcription_update", status: "transcription_completed"`

##### 摘要完成通知（全部完成）
- **标题**: "处理完成"
- **内容**: "「{录音标题}」的逐字稿和摘要已全部完成"
- **数据**: `type: "summary_update", status: "all_completed"`

##### 重新生成通知
- **完成**: "逐字稿更新完成" / "摘要更新完成"
- **失败**: "逐字稿生成失败" / "摘要生成失败"

### 3. 重新生成功能增强

#### 3.1 重新生成逐字稿
- **API**: `POST /api/analysis/{recording_id}/regenerate-transcription`
- **流程**: 
  1. 后台处理逐字稿
  2. 发送完成/失败通知

#### 3.2 重新生成摘要
- **API**: `POST /api/analysis/{recording_id}/regenerate-summary`
- **流程**:
  1. 后台处理摘要
  2. 发送完成/失败通知

## 🛠️ 技术实现

### 1. APNS 服务扩展

#### 新增方法：
```python
# 逐字稿完成通知
send_transcription_completed_notification()

# 摘要完成通知
send_summary_completed_notification()

# 重新生成通知
send_regeneration_notification()
```

### 2. 推送通知管理

#### 统一通知函数：
```python
async def send_push_notification_for_recording(
    session: AsyncSession,
    user_id: uuid.UUID,
    recording_id: str,
    recording_title: str,
    notification_type: str,  # "transcription_completed", "summary_completed", "regeneration_update"
    has_error: bool = False,
    analysis_type: str = None,  # "transcription" or "summary"
    regeneration_status: str = None  # "completed", "failed"
)
```

### 3. 处理流程修改

#### 上传录音处理流程：
```python
async def process_recording_async(recording_id: str):
    # 阶段1: 更新状态为 TRANSCRIBING
    # 阶段2: 处理逐字稿
    # 阶段3: 发送逐字稿完成通知，更新状态为 TRANSCRIBED
    # 阶段4: 更新状态为 SUMMARIZING
    # 阶段5: 处理摘要
    # 阶段6: 发送摘要完成通知，更新状态为 COMPLETED
```

## 📱 iOS 应用支持

### 通知数据结构

#### 逐字稿完成通知
```json
{
  "aps": {
    "alert": {
      "title": "逐字稿完成",
      "body": "「测试录音」的逐字稿已生成，正在生成摘要..."
    }
  },
  "type": "transcription_update",
  "recordingId": "recording-123",
  "status": "transcription_completed"
}
```

#### 摘要完成通知
```json
{
  "aps": {
    "alert": {
      "title": "处理完成",
      "body": "「测试录音」的逐字稿和摘要已全部完成"
    }
  },
  "type": "summary_update",
  "recordingId": "recording-123",
  "status": "all_completed"
}
```

#### 重新生成通知
```json
{
  "aps": {
    "alert": {
      "title": "逐字稿更新完成",
      "body": "「测试录音」的逐字稿已重新生成完成"
    }
  },
  "type": "regeneration_update",
  "recordingId": "recording-123",
  "analysisType": "transcription",
  "status": "completed"
}
```

## 🧪 测试

### 测试脚本
```bash
cd /Users/audi/GoogleDrive/Claude/recordhelper
python test_new_notification_system.py
```

### 测试内容
1. 逐字稿完成通知
2. 摘要完成通知
3. 重新生成完成通知

## 📝 使用示例

### 1. 上传录音
```bash
curl -X POST "http://audimacbookpro:9527/api/recordings/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test.mp3" \
  -F "title=测试录音"
```

用户将收到：
1. 逐字稿完成通知（几秒后）
2. 摘要完成通知（逐字稿完成后几秒）

### 2. 重新生成逐字稿
```bash
curl -X POST "http://audimacbookpro:9527/api/analysis/RECORDING_ID/regenerate-transcription" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

用户将收到：
1. 重新生成完成通知（处理完成后）

### 3. 重新生成摘要
```bash
curl -X POST "http://audimacbookpro:9527/api/analysis/RECORDING_ID/regenerate-summary" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

用户将收到：
1. 重新生成完成通知（处理完成后）

## 🔄 数据库变更

### 迁移
- 添加了新的录音状态枚举值
- 无需修改表结构（状态字段已是 VARCHAR）

### 向后兼容
- 原有的 `send_recording_completed_notification` 方法仍然可用
- 自动重定向到新的 `send_summary_completed_notification` 方法

## 🎯 好处

1. **更好的用户体验**: 用户可以及时了解处理进度
2. **清晰的状态管理**: 每个处理阶段都有明确的状态
3. **灵活的通知系统**: 支持不同类型的通知
4. **向后兼容**: 不影响现有功能
5. **易于扩展**: 可以轻松添加新的通知类型