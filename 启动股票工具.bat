@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ================================================
echo   📈 股票数据工具 — 快速启动
echo ================================================
echo.
echo   1. 股票查看器 (命令行)
echo   2. 股票仪表盘 (Web界面)
echo   3. Jupyter Notebook (深度分析)
echo   4. 快速看盘 (输入代码)
echo   5. 退出
echo.
set /p choice="请选择 (1-5): "

if "%choice%"=="1" (
    echo.
    set /p code="请输入股票代码: "
    python scripts\stock_viewer.py %code%
    pause
) else if "%choice%"=="2" (
    echo 🚀 正在启动 Streamlit 仪表盘...
    echo 浏览器打开 http://localhost:8501
    python -m streamlit run scripts\stock_dashboard.py --server.port 8501
) else if "%choice%"=="3" (
    echo 🚀 正在启动 Jupyter Notebook...
    python -m jupyter notebook --notebook-dir notebooks
) else if "%choice%"=="4" (
    echo.
    set /p code="请输入股票代码: "
    set /p tf="时间范围 (1mo/3mo/6mo/1y/2y/5y/max, 回车=1y): "
    if "%tf%"=="" set tf=1y
    python scripts\stock_viewer.py %code% -t %tf%
    pause
) else if "%choice%"=="5" (
    exit
) else (
    echo 无效选择
    pause
)
