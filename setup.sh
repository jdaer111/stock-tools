#!/bin/bash
# ============================================
#  股票工具套件 · 一键部署脚本
#  在任何新电脑上运行此脚本即可
# ============================================
set -e

echo "============================================"
echo "  📈 股票工具套件 · 部署中..."
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

# 0. 条件：需要有 Python 和 Git
echo ""
echo "[0/5] 检查环境..."
python3 --version 2>/dev/null || python --version 2>/dev/null || {
    echo "❌ 请先安装 Python 3.10+"
    exit 1
}
git --version 2>/dev/null || {
    echo "❌ 请先安装 Git"
    exit 1
}
echo "  ✅ 环境就绪"

# 1. 克隆仓库
echo ""
echo "[1/5] 从 GitHub 克隆代码..."
REPO="git@github.com:jdaer111/stock-tools.git"
DIR="stock-tools"

if [ -d "$DIR" ]; then
    echo "  → 目录已存在，执行 git pull..."
    cd "$DIR"
    git pull
    cd ..
else
    git clone "$REPO" "$DIR"
fi
echo "  ✅ 代码已就绪"

# 2. 安装依赖
echo ""
echo "[2/5] 安装 Python 依赖..."
cd "$DIR"
pip install -r requirements.txt --quiet
echo "  ✅ 依赖安装完成"

# 3. 克隆开源库
echo ""
echo "[3/5] 克隆 GitHub 开源量化库..."
mkdir -p lib
cd lib

clone_if_missing() {
    local name=$1
    local repo=$2
    if [ -d "$name" ]; then
        echo "  → $name (已存在)"
    else
        echo "  → 克隆 $name..."
        git clone "$repo" --depth 1 2>/dev/null && echo "     ✅" || echo "     ⚠️ 跳过"
    fi
}

clone_if_missing "akshare" "git@github.com:akfamily/akshare.git"
clone_if_missing "qlib" "git@github.com:microsoft/qlib.git"
clone_if_missing "PyPortfolioOpt" "git@github.com:robertmartin8/PyPortfolioOpt.git"
clone_if_missing "backtrader" "git@github.com:mementum/backtrader.git"

cd ..
echo "  ✅ 开源库就绪"

# 4. 配置 SSH Key（如果还没有）
echo ""
echo "[4/5] 配置 GitHub SSH..."
if [ ! -f ~/.ssh/id_ed25519 ]; then
    echo "  → 生成新的 SSH Key..."
    ssh-keygen -t ed25519 -C "stock-tools@auto" -f ~/.ssh/id_ed25519 -N "" 2>/dev/null
    echo ""
    echo "  ⚠️  请将以下公钥添加到 GitHub："
    echo "     https://github.com/settings/ssh/new"
    echo ""
    cat ~/.ssh/id_ed25519.pub
    echo ""
else
    echo "  ✅ SSH Key 已存在"
fi

# 5. 验证
echo ""
echo "[5/5] 验证环境..."
python -c "
from scripts.realtime_engine import RealtimeEngine
e = RealtimeEngine()
q = e.get_quote('600519')
print(f'  ✅ 实时行情正常: {q[\"name\"]} ¥{q[\"price\"]:.2f}')
" 2>&1 || echo "  ⚠️ 行情验证跳过（非交易时间或网络）"

echo ""
echo "============================================"
echo "  ✅ 部署完成！"
echo ""
echo "  使用方法："
echo "    python scripts/stock_viewer.py 600519"
echo "    streamlit run scripts/stock_dashboard.py"
echo "    bash update.sh    (每周升级)"
echo "============================================"
