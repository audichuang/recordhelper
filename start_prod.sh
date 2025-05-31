#!/bin/bash
# 生產環境啟動腳本

echo "🏭 啟動生產模式..."

# 設定環境變數
export RELOAD=FALSE
export LOG_LEVEL=INFO

# 使用 UV 啟動服務
cd /Users/audi/GoogleDrive/Claude/recordhelper
uv run python run_fastapi.py