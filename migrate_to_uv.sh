#!/bin/bash
# UV 遷移腳本

echo "🚀 開始遷移到 UV..."

# 1. 檢查 UV 是否已安裝
if ! command -v uv &> /dev/null; then
    echo "📦 安裝 UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# 2. 初始化 UV 專案
echo "🔧 初始化 UV 專案..."
uv init --name recordhelper --python 3.11

# 3. 創建虛擬環境
echo "🌟 創建虛擬環境..."
uv venv

# 4. 安裝現有依賴
echo "📚 安裝依賴..."
uv pip install -r requirements.txt

# 5. 生成 UV 格式的依賴文件
echo "📝 生成 pyproject.toml..."
cat > pyproject.toml.new << EOF
[project]
name = "recordhelper"
version = "0.1.0"
description = "錄音分析助手後端服務"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.104.1",
    "uvicorn[standard]>=0.24.0",
    "sqlalchemy>=2.0.23",
    "alembic>=1.12.1",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.6",
    "aiofiles>=23.2.1",
    "httpx>=0.25.2",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "google-generativeai>=0.3.0",
    "assemblyai>=0.31.0",
    "deepgram-sdk>=2.0.0",
    "psycopg2-binary>=2.9.9",
    "tenacity>=8.2.3",
    "cryptography>=41.0.7",
    "h2>=4.1.0",
    "hpack>=4.0.0",
    "hyperframe>=6.0.1",
]

[tool.uv]
dev-dependencies = [
    "pytest>=7.4.3",
    "pytest-asyncio>=0.21.1",
    "httpx>=0.25.2",
]
EOF

echo "✅ UV 遷移完成！"
echo ""
echo "📌 後續使用方式："
echo "  cd $(pwd)"
echo "  source .venv/bin/activate  # 或讓 UV 自動處理"
echo "  uv run python main_fastapi.py"
echo ""
echo "🔍 驗證環境："
echo "  uv pip list  # 查看已安裝套件"
echo "  uv python --version  # 查看 Python 版本"