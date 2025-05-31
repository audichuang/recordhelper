#!/bin/bash
# 開發環境啟動腳本

echo "🚀 啟動開發模式..."

# 設定環境變數
export RELOAD=TRUE
export LOG_LEVEL=DEBUG

# SSL 證書修復
CERT_PATH=$(cd /Users/audi/GoogleDrive/Claude/recordhelper && uv run python -c "import certifi; print(certifi.where())" 2>/dev/null)
export SSL_CERT_FILE="$CERT_PATH"
export REQUESTS_CA_BUNDLE="$CERT_PATH"
export HTTPX_CA_BUNDLE="$CERT_PATH"

# 使用 UV 啟動服務
cd /Users/audi/GoogleDrive/Claude/recordhelper
uv run python run_fastapi.py