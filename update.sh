#!/bin/bash
set -e
export PATH="/c/Program Files/Git/bin:$PATH"
cd "$(dirname "$0")"

echo "============================================"
echo "  股票工具套件 · 自动升级"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

# 1. 更新 Python 包
echo ""
echo "[1/4] 更新 Python 依赖..."
pip install --upgrade akshare yfinance pandas plotly streamlit baostock --quiet
echo "  ✅ Python 包已更新"

# 2. 更新第三方库
echo ""
echo "[2/4] 更新 GitHub 开源库..."
for lib in akshare qlib PyPortfolioOpt backtrader Ashare; do
    if [ -d "lib/$lib/.git" ]; then
        echo "  → $lib..."
        cd "lib/$lib"
        git pull --ff-only 2>&1 | tail -1 || echo "    (跳过，可能有本地修改)"
        cd ../..
    else
        echo "  → $lib (跳过，非git仓库)"
    fi
done
echo "  ✅ 开源库已更新"

# 3. 更新自己的代码
echo ""
echo "[3/4] 更新 stock-tools..."
git pull --ff-only 2>&1 || echo "    (已是最新)"
echo "  ✅ stock-tools 已更新"

# 4. 验证
echo ""
echo "[4/4] 验证环境..."
python -c "
from scripts.realtime_engine import RealtimeEngine
e = RealtimeEngine()
q = e.get_quote('600519')
print(f'  ✅ 实时行情引擎正常 - {q[\"name\"]} {q[\"price\"]:.2f}')
" 2>&1

echo ""
echo "============================================"
echo "  ✅ 升级完成"
echo "============================================"
