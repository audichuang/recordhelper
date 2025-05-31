#!/bin/bash
# 添加 UV 服務啟動別名

echo "" >> ~/.zshrc
echo "# UV FastAPI 啟動別名" >> ~/.zshrc
echo "alias uvdev='cd /Users/audi/GoogleDrive/Claude/recordhelper && RELOAD=TRUE uv run python run_fastapi.py'" >> ~/.zshrc
echo "alias uvprod='cd /Users/audi/GoogleDrive/Claude/recordhelper && RELOAD=FALSE uv run python run_fastapi.py'" >> ~/.zshrc
echo "alias uvstart='cd /Users/audi/GoogleDrive/Claude/recordhelper && ./start_dev.sh'" >> ~/.zshrc

echo "✅ 別名已添加到 ~/.zshrc"
echo "📌 新增的啟動別名："
echo "  uvdev   - 開發模式（自動重載）"
echo "  uvprod  - 生產模式"
echo "  uvstart - 使用腳本啟動"