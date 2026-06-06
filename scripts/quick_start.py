#!/usr/bin/env python3
"""
一键启动脚本 — 股票数据工具
用法:
    python quick_start.py dashboard    → 启动Streamlit仪表盘
    python quick_start.py notebook     → 启动Jupyter Notebook
    python quick_start.py 600519       → 快速查看A股实时行情
    python quick_start.py 600519 -t 1y → 查看A股+历史K线
    python quick_start.py AAPL         → 快速查看美股
"""

import sys
import os
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STOCK_VIEWER = os.path.join(SCRIPT_DIR, "stock_viewer.py")
DASHBOARD = os.path.join(SCRIPT_DIR, "stock_dashboard.py")
NOTEBOOK_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "notebooks")


def launch_dashboard():
    """启动Streamlit Web仪表盘"""
    print("🚀 正在启动股票仪表盘...")
    print(f"  浏览器将自动打开 http://localhost:8501\n")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", DASHBOARD,
        "--server.port", "8501",
        "--browser.serverAddress", "localhost",
    ])


def launch_notebook():
    """启动Jupyter Notebook"""
    os.makedirs(NOTEBOOK_DIR, exist_ok=True)
    print("🚀 正在启动Jupyter Notebook...")
    subprocess.run([
        sys.executable, "-m", "jupyter", "notebook",
        "--notebook-dir", NOTEBOOK_DIR,
    ])


def quick_view(args):
    """快速查看单只股票"""
    cmd = [sys.executable, STOCK_VIEWER] + args
    subprocess.run(cmd)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("示例:")
        print("  python quick_start.py dashboard")
        print("  python quick_start.py notebook")
        print("  python quick_start.py 600519")
        print("  python quick_start.py AAPL -t 1y")
        return

    arg1 = sys.argv[1].lower()

    if arg1 == "dashboard":
        launch_dashboard()
    elif arg1 == "notebook":
        launch_notebook()
    elif arg1 == "help" or arg1 == "-h" or arg1 == "--help":
        print(__doc__)
    else:
        # 当作股票代码
        quick_view(sys.argv[1:])


if __name__ == "__main__":
    main()
