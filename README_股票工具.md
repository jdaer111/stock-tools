# 📈 股票实时走势 & 历史数据工具配置

> 配置日期: 2026-06-06 | 为投资认知系统 v2.0 配套

## 🎯 已配置的工具

| 工具 | 文件 | 功能 | 启动方式 |
|------|------|------|----------|
| **命令行查看器** | `scripts/stock_viewer.py` | 实时行情 + 历史K线 | `python scripts/stock_viewer.py <代码>` |
| **Web仪表盘** | `scripts/stock_dashboard.py` | 交互式图表、市场扫描 | `streamlit run scripts/stock_dashboard.py` |
| **Jupyter Notebook** | `notebooks/stock_analysis_template.ipynb` | 深度分析：技术指标、收益风险、大盘对比 | `jupyter notebook` |
| **一键启动** | `scripts/quick_start.py` | 统一入口 | `python scripts/quick_start.py <命令>` |
| **Windows批处理** | `启动股票工具.bat` | 图形化菜单启动 | 双击运行 |

## 📊 支持的市场

### A股（akshare - 新浪数据源 ✅ 稳定）
```bash
python scripts/stock_viewer.py 600519          # 贵州茅台
python scripts/stock_viewer.py 000001          # 平安银行
python scripts/stock_viewer.py 300750 -t 1y    # 宁德时代 + 1年K线
```

### 港股 & 美股（yfinance ⚠️ 可能限流）
```bash
python scripts/stock_viewer.py 00700           # 腾讯
python scripts/stock_viewer.py AAPL -t 6mo     # Apple
```

## 🚀 快速开始

### 方法1：命令行（最简单）
```bash
cd C:\Users\35273\workplace

# 查看A股实时行情（仅交易日有效）
python scripts\stock_viewer.py 600519

# 查看A股历史K线 + 图表
python scripts\stock_viewer.py 600519 -t 1y

# 保存图表为PNG
python scripts\stock_viewer.py 600519 -t 1y -s
```

### 方法2：Web仪表盘（推荐）
```bash
cd C:\Users\35273\workplace
streamlit run scripts\stock_dashboard.py
# 浏览器自动打开 http://localhost:8501
```

### 方法3：Jupyter深度分析
```bash
cd C:\Users\35273\workplace
jupyter notebook --notebook-dir notebooks
# 打开 stock_analysis_template.ipynb
```

### 方法4：一键启动
```bash
python scripts\quick_start.py dashboard    # 启动仪表盘
python scripts\quick_start.py notebook     # 启动Jupyter
python scripts\quick_start.py 600519       # 快速查看
```

## 🛠 已安装的Python包

| 包名 | 版本 | 用途 |
|------|------|------|
| akshare | 1.18.64 | A股数据（新浪/腾讯源） |
| yfinance | 1.4.1 | 美股/港股数据（⚠️ 可能被限流） |
| pandas | 3.0.3 | 数据处理 |
| matplotlib | 3.10.9 | 静态图表 |
| plotly | 6.8.0 | 交互式图表 |
| mplfinance | latest | K线图专用 |
| streamlit | 待安装 | Web仪表盘 |
| jupyterlab | 4.5.7 | 交互式分析 |

## ⚠️ 注意事项

1. **实时行情**：仅交易时间（周一至周五 9:30-15:00）可用
2. **美股数据**：yfinance 限流较频繁，失败请稍等15-60分钟再试
3. **A股数据源**：优先使用新浪（稳定），备用腾讯
4. **缓存**：yfinance数据会缓存在 `.cache/` 目录（5分钟有效期）

## 📁 目录结构

```
workplace/
├── scripts/
│   ├── stock_viewer.py       # 核心：股票查看器
│   ├── stock_dashboard.py    # Web：Streamlit仪表盘
│   └── quick_start.py        # 一键启动入口
├── notebooks/
│   └── stock_analysis_template.ipynb  # Jupyter分析模板
├── .cache/                   # 数据缓存（自动创建）
├── 启动股票工具.bat           # Windows启动脚本
└── README_股票工具.md         # 本文件
```
