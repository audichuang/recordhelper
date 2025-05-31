#!/bin/bash
# UV 環境設置腳本

echo "🔧 設置 UV 環境別名..."

# 檢查使用的 shell
SHELL_RC=""
if [[ $SHELL == *"zsh"* ]]; then
    SHELL_RC="$HOME/.zshrc"
elif [[ $SHELL == *"bash"* ]]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -z "$SHELL_RC" ]; then
    echo "❌ 無法識別 shell 類型"
    exit 1
fi

# 添加 UV 相關別名
cat >> "$SHELL_RC" << 'EOF'

# UV Python 環境管理
alias uvpy='uv run python'
alias uvpip='uv pip'
alias uvrun='uv run'
alias uvact='source .venv/bin/activate'
alias uvdeact='deactivate'
alias uvtest='uv run pytest'
alias uvserver='uv run python run_fastapi.py'

# 快速切換專案
alias cdrecord='cd /Users/audi/GoogleDrive/Claude/recordhelper && uvact'

# 環境檢查
alias checkenv='python -c "import sys; print(f\"Python: {sys.executable}\nVersion: {sys.version.split()[0]}\")"'

# UV 專案初始化函數
uvinit() {
    local project_name="${1:-$(basename $PWD)}"
    local python_version="${2:-3.11}"
    echo "🚀 初始化 UV 專案: $project_name (Python $python_version)"
    uv init --name "$project_name" --python "$python_version"
    uv venv
    echo "✅ 專案初始化完成！"
}

# 自動激活虛擬環境
auto_activate_venv() {
    if [[ -d ".venv" ]]; then
        source .venv/bin/activate
    fi
}

# 每次進入目錄時檢查
if [[ -n "$ZSH_VERSION" ]]; then
    chpwd() {
        auto_activate_venv
    }
fi
EOF

echo "✅ 別名設置完成！"
echo ""
echo "📌 新增的別名："
echo "  uvpy      - 使用 UV 環境執行 Python"
echo "  uvpip     - 使用 UV 管理套件"
echo "  uvrun     - 使用 UV 執行命令"
echo "  uvact     - 激活虛擬環境"
echo "  uvdeact   - 退出虛擬環境"
echo "  uvtest    - 執行測試"
echo "  uvserver  - 啟動 FastAPI 服務"
echo "  cdrecord  - 快速切換到專案並激活環境"
echo "  checkenv  - 檢查當前 Python 環境"
echo "  uvinit    - 初始化新的 UV 專案"
echo ""
echo "🔄 請執行以下命令以生效："
echo "  source $SHELL_RC"