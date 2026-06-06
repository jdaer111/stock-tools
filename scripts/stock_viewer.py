#!/usr/bin/env python3
"""
股票实时走势 & 历史数据查看器
支持：A股（akshare）、港股/美股（yfinance）
用法：
    python stock_viewer.py 600519              # A股：贵州茅台（实时行情）
    python stock_viewer.py 000001              # A股：平安银行
    python stock_viewer.py 00700               # 港股：腾讯 (自动识别)
    python stock_viewer.py AAPL               # 美股：Apple
    python stock_viewer.py 600519 -t 1y        # 指定时间范围查看K线
    python stock_viewer.py 600519 -l           # 列出所有功能
"""

import sys
import os

# Windows下强制UTF-8编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
import numpy as np

# ========== 1. A股数据：akshare ==========

def _add_a_prefix(code: str) -> str:
    """给A股代码加 sh/sz 前缀"""
    code = code.replace("sh", "").replace("sz", "").strip()
    if code.startswith(("6", "5", "9")):
        return f"sh{code}"
    else:
        return f"sz{code}"


def get_a_share_realtime(symbol: str) -> pd.DataFrame:
    """获取A股实时行情（仅交易日有效）"""
    import akshare as ak
    code = symbol.replace("sh", "").replace("sz", "").strip()
    try:
        # 使用实时引擎（腾讯+新浪双源，自动切换）
        from realtime_engine import RealtimeEngine
        engine = RealtimeEngine()
        quote = engine.get_quote(code)
        if quote:
            return quote  # 返回dict格式，下游已兼容
    except Exception:
        pass
    # fallback: 尝试东方财富
    try:
        df = ak.stock_zh_a_spot_em()
        match = df[df["代码"] == code]
        if match.empty:
            match = df[df["名称"].str.contains(symbol, na=False)]
        if match.empty:
            print(f"未找到股票：{symbol}")
            return {}
        return match
    except Exception:
        print(f"实时行情获取失败（非交易时间或网络问题）")
        return {}
    except Exception as e:
        print(f"实时行情获取失败（可能非交易时间）: {e}")
        return pd.DataFrame()


def get_a_share_history(symbol: str, period: str = "daily", days: int = 365) -> pd.DataFrame:
    """获取A股历史K线数据（新浪数据源，稳定可靠）"""
    import akshare as ak
    prefixed = _add_a_prefix(symbol)

    period_map = {
        "1mo": 30, "3mo": 90, "6mo": 180,
        "1y": 365, "2y": 730, "5y": 1825, "max": 3650,
    }
    lookback = period_map.get(period, days)
    cutoff_date = datetime.now() - timedelta(days=lookback)

    # 优先使用新浪数据源（更稳定）
    try:
        df = ak.stock_zh_a_daily(symbol=prefixed, adjust="qfq")
        if df is not None and not df.empty:
            df = df.rename(columns={
                "date": "Date", "open": "Open", "close": "Close",
                "high": "High", "low": "Low", "volume": "Volume",
                "amount": "Amount", "turnover": "Turnover",
            })
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date").sort_index()
            # 按时间范围裁剪
            df = df[df.index >= pd.Timestamp(cutoff_date)]
        return df
    except Exception as e1:
        # 备用：腾讯数据源
        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = cutoff_date.strftime("%Y%m%d")
            df = ak.stock_zh_a_hist_tx(symbol=prefixed, start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "date": "Date", "open": "Open", "close": "Close",
                    "high": "High", "low": "Low", "amount": "Amount",
                })
                df["Date"] = pd.to_datetime(df["Date"])
                df = df.set_index("Date").sort_index()
                if "Volume" not in df.columns:
                    df["Volume"] = 0
            return df
        except Exception as e2:
            print(f"akshare获取历史数据失败: 新浪={e1}, 腾讯={e2}")
            return pd.DataFrame()


def get_a_share_info(symbol: str) -> dict:
    """获取A股个股基本信息"""
    import akshare as ak
    try:
        code = symbol.replace("sh", "").replace("sz", "").strip()
        info = ak.stock_individual_info_em(symbol=code)
        if info is not None and not info.empty:
            return dict(zip(info["item"], info["value"]))
    except Exception:
        pass
    return {}


# ========== 2. 港股/美股数据：yfinance ==========
import json
import time as _time

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _yf_cache_path(symbol: str, kind: str) -> str:
    safe = symbol.replace("/", "_").replace("\\", "_")
    return os.path.join(CACHE_DIR, f"yf_{safe}_{kind}.json")


def _yf_cached_get(symbol: str, kind: str, ttl: int = 3600):
    """读取缓存，TTL秒内有效"""
    path = _yf_cache_path(symbol, kind)
    if os.path.exists(path):
        age = _time.time() - os.path.getmtime(path)
        if age < ttl:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


def _yf_cached_set(symbol: str, kind: str, data):
    """写入缓存（仅可JSON序列化的数据）"""
    path = _yf_cache_path(symbol, kind)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
    except Exception:
        pass


def _yf_retry(func, max_retries=3, base_delay=5):
    """带重试的yfinance调用"""
    import yfinance.exceptions as yfe
    for attempt in range(max_retries):
        try:
            return func()
        except yfe.YFRateLimitError:
            if attempt < max_retries - 1:
                wait = base_delay * (2 ** attempt)
                print(f"  ⏳ 被限流，{wait}秒后重试... (attempt {attempt+1}/{max_retries})")
                _time.sleep(wait)
            else:
                raise
        except Exception:
            if attempt < max_retries - 1:
                _time.sleep(base_delay)
            else:
                raise


def get_global_realtime(symbol: str) -> dict:
    """获取港股/美股实时报价（延迟15分钟）"""
    import yfinance as yf

    # 先查缓存（5分钟有效）
    cached = _yf_cached_get(symbol, "quote", ttl=300)
    if cached:
        return cached

    try:
        def _fetch():
            ticker = yf.Ticker(symbol)
            info = ticker.info
            price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
            prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
            change = (price - prev_close) if price and prev_close else None
            change_pct = (change / prev_close * 100) if change is not None and prev_close else None

            result = {
                "名称": info.get("longName") or info.get("shortName", symbol),
                "代码": info.get("symbol", symbol),
                "最新价": price,
                "昨收": prev_close,
                "涨跌额": round(change, 2) if change else None,
                "涨跌幅": f"{change_pct:+.2f}%" if change_pct is not None else None,
                "最高": info.get("dayHigh"),
                "最低": info.get("dayLow"),
                "开盘": info.get("regularMarketOpen"),
                "成交量": info.get("regularMarketVolume") or info.get("volume"),
                "市值": info.get("marketCap"),
                "市盈率": info.get("trailingPE") or info.get("forwardPE"),
                "52周最高": info.get("fiftyTwoWeekHigh"),
                "52周最低": info.get("fiftyTwoWeekLow"),
                "货币": info.get("currency", "USD"),
            }
            _yf_cached_set(symbol, "quote", result)
            return result

        return _yf_retry(_fetch)
    except Exception as e:
        # 尝试返回过期缓存
        stale = _yf_cached_get(symbol, "quote", ttl=86400)
        if stale:
            print(f"  ⚠️ 实时数据获取失败，显示缓存数据: {e}")
            return stale
        print(f"  ⚠️  yfinance获取实时数据失败: {e}")
        return {}


def get_global_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    """获取港股/美股历史K线数据"""
    import yfinance as yf
    interval_map = {
        "1mo": ("1mo", "60m"),
        "3mo": ("3mo", "1d"),
        "6mo": ("6mo", "1d"),
        "1y": ("1y", "1d"),
        "2y": ("2y", "1d"),
        "5y": ("5y", "1wk"),
        "max": ("max", "1wk"),
    }
    yf_period, yf_interval = interval_map.get(period, ("1y", "1d"))

    def _fetch():
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=yf_period, interval=yf_interval)
        if df is not None and not df.empty:
            df = df.rename(columns={
                "Open": "Open", "High": "High", "Low": "Low",
                "Close": "Close", "Volume": "Volume",
            })
        return df

    try:
        return _yf_retry(_fetch)
    except Exception as e:
        print(f"  ⚠️  yfinance获取历史数据失败（多次重试后）: {e}")
        print(f"  💡 提示: Yahoo Finance可能被限流，请稍后再试。A股数据不受影响。")
        return pd.DataFrame()


# ========== 3. 市场识别 ==========

def identify_market(symbol: str) -> str:
    """自动识别股票市场"""
    s = symbol.upper().strip()
    # 纯数字6位 → A股
    if s.isdigit() and len(s) == 6:
        return "a_share"
    # 数字5位（港股代码）
    if s.isdigit() and len(s) == 5:
        return "hk"
    # 字母结尾 .HK / .SS / .SZ
    if s.endswith(".HK"):
        return "hk"
    if s.endswith((".SS", ".SZ")):
        return "a_share"
    # 纯字母 → 美股或港股
    if s.isalpha():
        if len(s) <= 4:
            return "us"  # 短字母大概率美股
        return "hk"      # 长字母如 BABA → 也用yfinance
    # 4位数字且以0开头 → 港股
    if s.isdigit() and len(s) <= 5:
        return "hk"
    return "us"


# ========== 4. 可视化 ==========

def plot_candlestick(df: pd.DataFrame, title: str, market: str = "us"):
    """绘制K线图 + 成交量 + 均线"""
    if df.empty:
        print("⚠️  无数据可绘制")
        return

    # 准备数据
    df = df.copy()
    required_cols = ["Open", "High", "Low", "Close", "Volume"]
    for c in required_cols:
        if c not in df.columns:
            print(f"⚠️  缺少列: {c}")
            return

    # 计算均线
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()

    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    # 创建图表
    fig = plt.figure(figsize=(16, 10))
    gs = GridSpec(2, 1, height_ratios=[3, 1], hspace=0.05)

    # 主图：K线
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)

    # 判断涨跌颜色
    colors = ['#ef5350' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#26a69a'
              for i in range(len(df))]

    # 绘制K线
    width = max(0.6, 0.8 * (df.index[1] - df.index[0]).days if len(df) > 1 else 0.8)
    if hasattr(width, 'days'):
        width = width * 0.8

    body_width = 0.6
    wick_width = 0.1

    for i, (idx, row) in enumerate(df.iterrows()):
        color = colors[i]
        # 影线
        ax1.plot([idx, idx], [row["Low"], row["High"]],
                 color=color, linewidth=wick_width + 0.5, zorder=1)
        # 实体
        body_bottom = min(row["Open"], row["Close"])
        body_height = abs(row["Close"] - row["Open"])
        if body_height > 0:
            ax1.bar(idx, body_height, body_width, bottom=body_bottom,
                    color=color, edgecolor=color, linewidth=0.5, zorder=2)

    # 均线
    ax1.plot(df.index, df["MA5"], color='#FFB74D', linewidth=0.8, label='MA5')
    ax1.plot(df.index, df["MA20"], color='#64B5F6', linewidth=0.8, label='MA20')
    ax1.plot(df.index, df["MA60"], color='#CE93D8', linewidth=0.8, label='MA60')

    ax1.set_title(title, fontsize=16, fontweight='bold', pad=15)
    ax1.legend(loc='upper left', fontsize=9)
    ax1.set_ylabel("Price", fontsize=11)
    ax1.grid(True, alpha=0.3)

    # 成交量
    vol_colors = ['#ef5350' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#26a69a'
                  for i in range(len(df))]
    ax2.bar(df.index, df["Volume"], width=body_width, color=vol_colors, alpha=0.7)
    ax2.set_ylabel("Volume", fontsize=11)
    ax2.grid(True, alpha=0.3)

    # 格式化x轴
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=max(1, len(df) // 12)))
    fig.autofmt_xdate()

    # 价格标注
    last_price = df["Close"].iloc[-1]
    change = df["Close"].iloc[-1] - df["Close"].iloc[0]
    change_pct = (change / df["Close"].iloc[0] * 100)
    color_tag = '#ef5350' if change >= 0 else '#26a69a'
    ax1.annotate(
        f'{last_price:.2f}\n({change_pct:+.2f}%)',
        xy=(df.index[-1], last_price),
        xytext=(15, 0), textcoords='offset points',
        fontsize=11, fontweight='bold', color=color_tag,
        va='center',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8)
    )

    plt.tight_layout()
    return fig


# ========== 5. 实时行情面板（纯文本） ==========

def print_realtime_panel(symbol: str, market: str):
    """印出实时行情面板"""
    print(f"\n{'='*65}")
    print(f"  📊 实时行情  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}")

    if market == "a_share":
        result = get_a_share_realtime(symbol)

        # 判断是dict（新引擎）还是DataFrame（旧格式）
        if isinstance(result, dict) and result:
            q = result
            cp = q.get("change_pct", 0)
            arrow = "🔴" if cp > 0 else ("🟢" if cp < 0 else "⚪")

            print(f"  {arrow} {q.get('name','N/A')}({symbol})  数据源: {q.get('source','')}")
            print(f"  {'─'*55}")
            print(f"  最新价: {q.get('price','N/A'):>10.2f}    今开: {q.get('open','N/A'):>10.2f}")
            print(f"  涨跌额: {q.get('change','N/A'):>10.3f}    昨收: {q.get('prev_close','N/A'):>10.2f}")
            print(f"  涨跌幅: {q.get('change_pct','N/A'):>+9.2f}%    最高: {q.get('high','N/A'):>10.2f}")
            print(f"  换手率: {q.get('turnover','N/A'):>9.2f}%    最低: {q.get('low','N/A'):>10.2f}")
            print(f"  成交量: {q.get('volume','N/A'):>10}    成交额: {q.get('amount','N/A'):>10.0f}万")
            print(f"  市盈率: {q.get('pe','N/A'):>10}    总市值: {q.get('total_mv','N/A'):>10.2f}亿")
            print(f"  市净率: {q.get('pb','N/A')}    量比: {q.get('vol_ratio','N/A')}")
            if q.get("bids") and q.get("asks"):
                b1, a1 = q["bids"][0], q["asks"][0]
                print(f"  买一: {b1['price']}×{b1['volume']}手    卖一: {a1['price']}×{a1['volume']}手")
            print(f"  外盘: {q.get('outer_disc','N/A')}    内盘: {q.get('inner_disc','N/A')}    均价: {q.get('avg_price','N/A')}")

        elif isinstance(result, pd.DataFrame) and not result.empty:
            df = result
            row = df.iloc[0]
            name = row.get("名称", "N/A")
            code = row.get("代码", symbol)
            price = row.get("最新价", "N/A")
            prev_close = row.get("昨收", "N/A")
            change = row.get("涨跌额", "N/A")
            change_pct = row.get("涨跌幅", "N/A")
            high = row.get("最高", "N/A")
            low = row.get("最低", "N/A")
            open_ = row.get("今开", "N/A")
            volume = row.get("成交量", "N/A")
            amount = row.get("成交额", "N/A")
            turnover = row.get("换手率", "N/A")
            pe = row.get("市盈率-动态", "N/A")
            total_mv = row.get("总市值", "N/A")

            try:
                cp = float(change_pct)
                arrow = "🔴" if cp > 0 else ("🟢" if cp < 0 else "⚪")
            except (ValueError, TypeError):
                arrow = "⚪"

            print(f"  {arrow} {name}({code})")
            print(f"  {'─'*55}")
            print(f"  最新价: {price:>10}    今开: {open_:>10}")
            print(f"  涨跌额: {change:>10}    昨收: {prev_close:>10}")
            print(f"  涨跌幅: {change_pct:>10}    最高: {high:>10}")
            print(f"  换手率: {turnover:>10}    最低: {low:>10}")
            print(f"  成交量: {volume:>10}    成交额: {amount:>10}")
            print(f"  市盈率: {pe:>10}    总市值: {total_mv:>10}")
            print(f"  {'─'*55}")
        else:
            print("  ⚠️ 实时行情暂不可用（非交易时间或网络问题）")
            print(f"  💡 历史数据仍可查看：python stock_viewer.py {symbol} -t 1y")

    elif market in ("us", "hk"):
        info = get_global_realtime(symbol)
        if not info:
            return

        price = info.get("最新价", "N/A")
        prev = info.get("昨收", "N/A")
        change_val = info.get("涨跌额", "N/A")
        change_pct = info.get("涨跌幅", "N/A")

        try:
            cp_str = str(change_pct)
            cp = float(cp_str.replace("%", ""))
            arrow = "🔴" if cp > 0 else ("🟢" if cp < 0 else "⚪")
        except (ValueError, TypeError):
            arrow = "⚪"

        print(f"  {arrow} {info.get('名称', symbol)} ({info.get('代码', symbol)})")
        print(f"  {'─'*55}")
        print(f"  最新价: {price:>10}    货币: {info.get('货币', 'USD'):>10}")
        print(f"  涨跌额: {change_val:>10}    昨收: {prev:>10}")
        print(f"  涨跌幅: {change_pct:>10}    开盘: {info.get('开盘', 'N/A')}")
        print(f"  最高价: {info.get('最高', 'N/A'):>10}    最低: {info.get('最低', 'N/A')}")
        print(f"  成交量: {info.get('成交量', 'N/A'):>10}")
        print(f"  市值:   {info.get('市值', 'N/A'):>10}    市盈率: {info.get('市盈率', 'N/A')}")
        print(f"  52周高: {info.get('52周最高', 'N/A'):>10}    52周低: {info.get('52周最低', 'N/A')}")
        print(f"  {'─'*55}")

    print(f"{'='*65}\n")


# ========== 6. 主入口 ==========

def main():
    parser = argparse.ArgumentParser(
        description="📈 股票实时走势 & 历史数据查看器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python stock_viewer.py 600519              A股实时行情
  python stock_viewer.py 600519 -t 1y        A股+历史K线图
  python stock_viewer.py 600519 -s           保存图表为PNG
  python stock_viewer.py AAPL -t 6mo         美股Apple+半年K线
  python stock_viewer.py 00700 -t 3mo        港股腾讯+三月K线
  python stock_viewer.py 600519 -o json      输出JSON格式数据

支持的市场:
  A股: 6位数字代码 (600519=茅台, 000001=平安银行)
  港股: 5位数字代码 (00700=腾讯, 09988=阿里巴巴)
  美股: 字母代码  (AAPL=Apple, TSLA=Tesla, NVDA=NVIDIA)
        """)

    parser.add_argument("symbol", help="股票代码")
    parser.add_argument("-t", "--timeframe", default="realtime",
                        choices=["realtime", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
                        help="时间范围 (default: realtime 仅实时行情)")
    parser.add_argument("-s", "--save", action="store_true",
                        help="保存K线图为PNG文件")
    parser.add_argument("-o", "--output", choices=["text", "json"], default="text",
                        help="输出格式")
    parser.add_argument("--no-chart", action="store_true",
                        help="不显示图表（只打印数据）")

    args = parser.parse_args()
    symbol = args.symbol.strip().upper()
    market = identify_market(symbol)

    print(f"🔍 识别市场: {'A股' if market == 'a_share' else '港股' if market == 'hk' else '美股'}")

    # 1) 实时行情
    if args.timeframe == "realtime":
        print_realtime_panel(symbol, market)
        return

    # 2) 历史数据 + K线图
    print(f"\n⏳ 正在获取 {symbol} 的 {args.timeframe} 历史数据...")

    if market == "a_share":
        df = get_a_share_history(symbol, period=args.timeframe)
    else:
        df = get_global_history(symbol, period=args.timeframe)

    if df.empty:
        print("❌ 未能获取历史数据")
        return

    # 输出摘要
    last = df["Close"].iloc[-1]
    first = df["Close"].iloc[0]
    change = last - first
    change_pct = (change / first) * 100
    high = df["High"].max()
    low = df["Low"].min()
    avg_vol = df["Volume"].mean()

    print(f"\n📊 历史数据摘要 ({args.timeframe})")
    print(f"  {'─'*45}")
    print(f"  数据点: {len(df)}    区间: {df.index[0].strftime('%Y-%m-%d')} → {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"  期初价: {first:.2f}    期末价: {last:.2f}")
    print(f"  涨跌幅: {change_pct:+.2f}%    涨跌额: {change:+.2f}")
    print(f"  最高价: {high:.2f}    最低价: {low:.2f}")
    print(f"  日均量: {avg_vol:,.0f}")
    print(f"  {'─'*45}\n")

    if args.output == "json":
        print(df.tail(10).to_json(orient="records", date_format="iso", force_ascii=False))
        return

    # 打印最近10天数据
    print("📋 最近10个交易日:")
    pd.set_option('display.max_columns', 10)
    pd.set_option('display.width', 120)
    pd.set_option('display.float_format', lambda x: f'{x:.2f}')
    print(df[["Open", "High", "Low", "Close", "Volume"]].tail(10).to_string())
    print()

    # 3) 绘制K线图
    if not args.no_chart:
        market_names = {"a_share": "A股", "us": "美股", "hk": "港股"}
        title = f"{symbol}  {market_names.get(market, '')}  |  {args.timeframe}  |  {df.index[-1].strftime('%Y-%m-%d')}"

        fig = plot_candlestick(df, title, market)

        if args.save:
            filename = f"{symbol}_{args.timeframe}_{datetime.now().strftime('%Y%m%d')}.png"
            fig.savefig(filename, dpi=150, bbox_inches='tight', facecolor='white')
            print(f"✅ 图表已保存: {filename}")

        plt.show()


if __name__ == "__main__":
    main()
