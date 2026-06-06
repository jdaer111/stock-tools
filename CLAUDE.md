# 股票数据 + 基金框架 自动技能 v3.0

## 触发条件
- A股代码（6位数字如 600519）
- 港股/美股代码
- 基金代码（020602）或说"检查/分析/诊断 + 基金"
- "框架分析" / "看盘" / "交易回顾"

## 基金分析（020602）

### 自动运行
- 每工作日 14:30 → `python -X utf8 ../fund-research/scripts/framework_engine.py`
- 输出三选项：买 / 不买 / 等待
- 买时说明金额和理由
- 自动记录到交易账本

### 手动触发
```
"检查 020602" → 运行 framework_engine.py → 六层框架 + 三选项
"交易回顾"    → 查看 data/trade_ledger.json
"记录买入"    → 手动追加买入记录
```

## 系统架构

```
fund-research/scripts/    (4个文件，极简)
├── framework_engine.py   ← 核心：六层框架+触发检查+三选项输出
├── pulse_bus.py          ← 脉冲检测
├── belief_tracker.py     ← 信念追踪
└── metabolism.py         ← 代谢调度

workplace/scripts/        (数据源)
├── realtime_engine.py    ← 腾讯+新浪双源
├── stock_viewer.py       ← 股票K线查看器
└── stock_dashboard.py    ← Streamlit看板
```

## 数据源
- 底层ETF实时: 腾讯API (sh563020 = 红利低波ETF易方达)
- 市场指数: 腾讯API (沪深300/上证/创业板)
- 基金净值 + 宏观: akshare
- 北向 + 市场宽度: realtime_engine
- 双源自动切换: 腾讯(丰富) > 新浪(稳定)

## 020602 持仓
- 第1笔: 2026-04-30 @ 1.0987
- 第2笔: 2026-05-21 @ 1.0720
- 第3笔: 2026-06-05 @ 1.0741
- 平均成本: 1.0816
- 止损: -15% | 止盈: +30% | 仓位上限: 20%

## 五个触发条件
- 净值 < 1.0492 → 买
- ETF跌 > 1.5% → 买
- 上涨占比 < 25% → 买
- 盈利 > 30% → 卖
- 亏损 > 15% → 卖

## 核心理念
不给评分，不替做决定。六层数据 + 逻辑链 + 三选项。决定权在用户。

## 项目地址
https://github.com/jdaer111/stock-tools

## 升级
```bash
bash update.sh    # 一键升级
```
