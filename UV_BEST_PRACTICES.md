# UV 環境隔離最佳實踐指南

## 🛡️ 環境隔離已完成設置

### ✅ 已完成的設置

1. **UV 工具安裝** - 超快速的 Python 套件管理器
2. **獨立虛擬環境** - `.venv` 目錄完全隔離
3. **依賴鎖定** - 所有套件版本已固定
4. **便捷別名** - 簡化日常操作

### 🚀 日常使用指南

#### 1. 進入專案並激活環境
```bash
# 方法 1：使用別名
cdrecord

# 方法 2：手動方式
cd /Users/audi/GoogleDrive/Claude/recordhelper
source .venv/bin/activate

# 方法 3：使用 UV（推薦）
cd /Users/audi/GoogleDrive/Claude/recordhelper
# UV 會自動處理環境
```

#### 2. 執行 Python 程式
```bash
# 使用 UV（推薦）
uv run python main_fastapi.py
# 或使用別名
uvpy main_fastapi.py

# 激活環境後
python main_fastapi.py
```

#### 3. 安裝新套件
```bash
# 使用 UV（推薦）
uv add package-name
# 或
uv pip install package-name

# 開發依賴
uv add --dev pytest
```

#### 4. 更新套件
```bash
# 更新特定套件
uv update fastapi

# 更新所有套件
uv update
```

### 🔒 環境隔離保證

1. **完全隔離** - 每個專案有獨立的 `.venv`
2. **版本鎖定** - `uv.lock` 確保一致性
3. **自動切換** - 進入目錄自動使用正確環境
4. **無全域污染** - 套件只安裝在專案內

### 📋 常用命令速查

| 任務 | 命令 | 別名 |
|------|------|------|
| 執行 Python | `uv run python script.py` | `uvpy script.py` |
| 安裝套件 | `uv add package` | `uvpip install package` |
| 啟動服務 | `uv run python run_fastapi.py` | `uvserver` |
| 執行測試 | `uv run pytest` | `uvtest` |
| 檢查環境 | `uv pip list` | `checkenv` |

### 🎯 最佳實踐

1. **始終使用 UV 命令**
   ```bash
   # ✅ 好
   uv add requests
   
   # ❌ 避免
   pip install requests
   ```

2. **定期更新 lock 文件**
   ```bash
   # 更新依賴後
   uv lock
   ```

3. **團隊協作**
   ```bash
   # 克隆專案後
   uv sync  # 自動安裝所有依賴
   ```

4. **多專案管理**
   ```bash
   # 專案 A
   cd project-a
   uv run python main.py  # 自動使用 project-a 的環境
   
   # 專案 B
   cd ../project-b
   uv run python main.py  # 自動切換到 project-b 的環境
   ```

### 🚨 注意事項

1. **不要混用 pip 和 uv**
   - 統一使用 UV 管理套件
   - 避免直接使用 pip install

2. **保持 uv.lock 同步**
   - 添加新依賴後提交 uv.lock
   - 團隊成員使用 `uv sync` 同步

3. **環境變數**
   - `.env` 文件用於應用配置
   - `.venv` 目錄是虛擬環境（不要提交）

### 💡 疑難排解

#### 問題：找不到套件
```bash
# 解決方案
uv sync  # 同步所有依賴
```

#### 問題：Python 版本不對
```bash
# 解決方案
uv python pin 3.11  # 指定 Python 版本
uv venv --python 3.11  # 重建虛擬環境
```

#### 問題：套件衝突
```bash
# 解決方案
uv pip uninstall package
uv add package@version  # 指定版本
```

### 🎉 恭喜！

你的 Python 環境現在已經完全隔離，不會再有套件混雜的問題了！

享受清爽、高效的開發體驗吧！ 🚀