# 股票数据系统 · 自动技能

## 触发条件
当用户发送以下任一内容时，自动执行对应的分析流程：
- A股代码（6位数字如 600519 / 000001 / 300750）
- 港股代码（5位数字如 00700 / 09988）
- 美股代码（字母如 AAPL / TSLA / NVDA）
- 基金代码（6位数字且以0开头如 020602，或明确说"基金"）

## 自动执行流程

### 第一步：实时行情
```
python scripts/stock_viewer.py <代码>
```
输出：名称、现价、涨跌幅、PE/PB、市值、买卖盘、内外盘

### 第二步：历史K线 + 交互图表
```
python scripts/stock_viewer.py <代码> -t 1y -s    # 保存静态PNG
python -c "
from scripts.realtime_engine import RealtimeEngine
import plotly.graph_objects as go
from plotly.subplots import make_subplots
...
fig.write_html('<代码>_交互K线.html')
"                                                   # 生成交互HTML
```

### 第三步：如果是基金（020602等）
```
python -c "
from scripts.realtime_engine import FundSource
df = FundSource.get_nav('<代码>', days=60)
# 生成净值走势交互图
"
```

### 第四步：打开交互图表
```
start <代码>_交互K线.html
```

## 关键文件
| 文件 | 功能 |
|------|------|
| `scripts/realtime_engine.py` | 实时行情引擎（腾讯+新浪双源） |
| `scripts/stock_viewer.py` | 命令行股票查看器 |
| `scripts/stock_dashboard.py` | Streamlit Web仪表盘 |
| `scripts/quick_start.py` | 一键启动入口 |
| `notebooks/stock_analysis_template.ipynb` | Jupyter深度分析模板 |
| `lib/akshare/` | A股数据源码 |
| `lib/qlib/` | 微软AI量化框架 |
| `lib/PyPortfolioOpt/` | 组合优化 |
| `lib/backtrader/` | 回测框架 |

## 数据能力
- A股实时：腾讯+新浪双源，价格/PE/PB/市值/买卖五档/内外盘/分时
- A股历史：新浪源，前复权日线，含MA/MACD/RSI/布林带
- 指数：上证/深证/创业板/科创50/沪深300/中证500 实时
- 北向资金：沪股通+深股通 每日净流入
- 基金净值：日净值+增长率+历史走势
- 港股：日线K线+涨跌幅
- 美股：yfinance（可能被限流）

## 项目地址
https://github.com/jdaer111/stock-tools
