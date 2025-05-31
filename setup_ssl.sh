#!/bin/bash
# SSL 證書修復腳本

echo "🔧 設定 SSL 證書環境變數..."

# 獲取 certifi 路徑
CERT_PATH=$(cd /Users/audi/GoogleDrive/Claude/recordhelper && uv run python -c "import certifi; print(certifi.where())")

# 添加到 shell 配置
cat >> ~/.zshrc << EOF

# Python SSL 證書修復 (for recordhelper)
export SSL_CERT_FILE="$CERT_PATH"
export REQUESTS_CA_BUNDLE="$CERT_PATH"
export HTTPX_CA_BUNDLE="$CERT_PATH"
EOF

echo "✅ 已添加環境變數到 ~/.zshrc"
echo ""
echo "📌 環境變數："
echo "   SSL_CERT_FILE=$CERT_PATH"
echo "   REQUESTS_CA_BUNDLE=$CERT_PATH"
echo "   HTTPX_CA_BUNDLE=$CERT_PATH"
echo ""
echo "🔄 請執行以下命令以生效："
echo "   source ~/.zshrc"