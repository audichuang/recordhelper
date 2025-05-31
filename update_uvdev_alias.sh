#!/bin/bash
# 更新 uvdev 別名以包含 SSL 修復

# 先移除舊的別名行
sed -i '' '/alias uvdev=/d' ~/.zshrc

# 添加新的別名（包含 SSL 修復）
cat >> ~/.zshrc << 'EOF'

# 更新的 UV 啟動別名（包含 SSL 修復）
alias uvdev='cd /Users/audi/GoogleDrive/Claude/recordhelper && CERT_PATH=$(uv run python -c "import certifi; print(certifi.where())" 2>/dev/null) && SSL_CERT_FILE="$CERT_PATH" REQUESTS_CA_BUNDLE="$CERT_PATH" HTTPX_CA_BUNDLE="$CERT_PATH" RELOAD=TRUE uv run python run_fastapi.py'
EOF

echo "✅ uvdev 別名已更新，現在包含 SSL 修復"
echo "🔄 請執行: source ~/.zshrc"