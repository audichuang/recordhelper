# UV 環境同步指南

## 🔄 環境同步完成

### ✅ 已完成的同步工作

1. **pyproject.toml 已更新** - 包含所有專案依賴
2. **requirements.txt 已同步** - 與 pyproject.toml 保持一致
3. **構建配置已修正** - 添加了必要的 hatch 配置
4. **所有依賴已安裝** - 130 個套件成功安裝

### 📋 檔案同步對照

| 用途 | 檔案 | 說明 |
|------|------|------|
| UV 管理 | `pyproject.toml` | UV 的主要配置檔 |
| 傳統方式 | `requirements.txt` | 保留給不使用 UV 的情況 |
| 版本鎖定 | `uv.lock` | 自動生成，確保版本一致 |

### 🚀 快速啟動

```bash
# 1. 同步所有依賴（拉取專案後執行）
uv sync

# 2. 啟動開發模式
uvdev

# 3. 啟動生產模式
uvprod
```

### 🔧 依賴管理

#### 新增依賴
```bash
# 添加生產依賴
uv add package-name

# 添加開發依賴
uv add --dev package-name

# 指定版本
uv add package-name==1.0.0
```

#### 更新依賴
```bash
# 更新特定套件
uv update package-name

# 更新所有套件
uv update
```

#### 移除依賴
```bash
uv remove package-name
```

### 📝 重要提醒

1. **優先使用 UV 命令** - 不要直接編輯 pyproject.toml
2. **保持同步** - 修改依賴後記得提交 `uv.lock`
3. **團隊協作** - 其他人拉取後執行 `uv sync`

### 🛠️ 疑難排解

#### 問題：sync 失敗
```bash
# 清理快取重試
uv cache clean
uv sync --refresh
```

#### 問題：依賴衝突
```bash
# 查看依賴樹
uv tree

# 強制重新解析
uv lock --refresh
```

### 📊 當前環境狀態

- Python 版本: 3.11.7
- 總依賴數: 130 個套件
- 虛擬環境: `.venv` (完全隔離)
- 專案名稱: recordhelper

### ✨ 最佳實踐提醒

1. **每次拉取後執行 `uv sync`**
2. **使用別名簡化操作 (uvdev, uvprod)**
3. **定期更新依賴確保安全**
4. **提交前測試服務是否正常啟動**

環境現在已經完全同步且隔離良好！ 🎉