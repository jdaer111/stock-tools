#!/usr/bin/env python3
"""
📈 股票实时仪表盘 — Web交互界面
启动: streamlit run stock_dashboard.py
支持A股、港股、美股实时行情 + 历史K线
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

st.set_page_config(
    page_title="📈 股票仪表盘",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ========== 数据获取 ==========

@st.cache_data(ttl=60)  # 60秒缓存
def fetch_a_share_spot():
    """获取A股全市场实时行情"""
    import akshare as ak
    try:
        df = ak.stock_zh_a_spot_em()
        # 转换数值列
        for col in ["最新价", "涨跌幅", "涨跌额", "成交量", "成交额", "换手率", "市盈率-动态"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except Exception as e:
        st.error(f"获取A股行情失败: {e}")
        return pd.DataFrame()


def _add_a_prefix(code: str) -> str:
    """给A股代码加 sh/sz 前缀"""
    code = code.replace("sh", "").replace("sz", "").strip()
    if code.startswith(("6", "5", "9")):
        return f"sh{code}"
    else:
        return f"sz{code}"


@st.cache_data(ttl=300)
def fetch_a_share_history(symbol: str, days: int = 365):
    """获取A股历史K线（新浪数据源，稳定可靠）"""
    import akshare as ak
    prefixed = _add_a_prefix(symbol)
    cutoff_date = datetime.now() - timedelta(days=days)
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
            df = df[df.index >= pd.Timestamp(cutoff_date)]
        return df
    except Exception as e:
        # 备用腾讯数据源
        try:
            end = datetime.now().strftime("%Y%m%d")
            start = cutoff_date.strftime("%Y%m%d")
            df = ak.stock_zh_a_hist_tx(symbol=prefixed, start_date=start, end_date=end)
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
            st.error(f"获取A股历史失败: {e2}")
            return pd.DataFrame()


@st.cache_data(ttl=120)
def fetch_global_quote(symbol: str):
    """获取美股/港股实时报价"""
    import yfinance as yf
    try:
        t = yf.Ticker(symbol)
        info = t.info
        return {
            "名称": info.get("longName") or info.get("shortName", symbol),
            "代码": info.get("symbol", symbol),
            "最新价": info.get("currentPrice") or info.get("regularMarketPrice"),
            "昨收": info.get("previousClose") or info.get("regularMarketPreviousClose"),
            "最高": info.get("dayHigh"),
            "最低": info.get("dayLow"),
            "开盘": info.get("regularMarketOpen"),
            "成交量": info.get("regularMarketVolume") or info.get("volume"),
            "市值": info.get("marketCap"),
            "市盈率": info.get("trailingPE"),
            "52周高": info.get("fiftyTwoWeekHigh"),
            "52周低": info.get("fiftyTwoWeekLow"),
            "货币": info.get("currency", "USD"),
        }
    except Exception as e:
        st.warning(f"yfinance获取失败: {e}")
        return {}


@st.cache_data(ttl=300)
def fetch_global_history(symbol: str, period: str = "1y"):
    """获取美股/港股历史K线"""
    import yfinance as yf
    interval_map = {
        "1mo": ("1mo", "60m"), "3mo": ("3mo", "1d"),
        "6mo": ("6mo", "1d"), "1y": ("1y", "1d"),
        "2y": ("2y", "1d"), "5y": ("5y", "1wk"), "max": ("max", "1wk"),
    }
    yf_period, yf_interval = interval_map.get(period, ("1y", "1d"))
    try:
        t = yf.Ticker(symbol)
        df = t.history(period=yf_period, interval=yf_interval)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        st.error(f"获取历史数据失败: {e}")
        return pd.DataFrame()


# ========== K线图（Plotly交互版） ==========

def plot_candlestick_plotly(df: pd.DataFrame, title: str, market: str = "us"):
    """使用Plotly绘制交互式K线图"""
    if df.empty:
        st.warning("无数据可供绘图")
        return

    df = df.copy()

    # 均线
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()
    df["MA120"] = df["Close"].rolling(120).mean()

    # MACD
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.55, 0.25, 0.20],
        subplot_titles=(title, "Volume", "MACD"),
    )

    # === K线 ===
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        name="K线",
        increasing=dict(line=dict(color='#ef5350')),
        decreasing=dict(line=dict(color='#26a69a')),
    ), row=1, col=1)

    # 均线
    for ma, color in [("MA5", "#FFB74D"), ("MA20", "#64B5F6"), ("MA60", "#CE93D8"), ("MA120", "#BDBDBD")]:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[ma],
            mode="lines", line=dict(width=1, color=color),
            name=ma,
        ), row=1, col=1)

    # === 成交量 ===
    vol_colors = ['#ef5350' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#26a69a' for i in range(len(df))]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"],
        name="Volume", marker_color=vol_colors,
        opacity=0.7,
    ), row=2, col=1)

    # === MACD ===
    macd_colors = ['#ef5350' if v >= 0 else '#26a69a' for v in df["MACD_Hist"]]
    fig.add_trace(go.Bar(
        x=df.index, y=df["MACD_Hist"],
        name="MACD柱", marker_color=macd_colors,
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["MACD"],
        mode="lines", line=dict(width=1.5, color='#1E88E5'),
        name="MACD",
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["MACD_Signal"],
        mode="lines", line=dict(width=1, color='#FF9800'),
        name="Signal",
    ), row=3, col=1)

    # 布局
    fig.update_layout(
        height=750,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        margin=dict(l=10, r=10, t=60, b=10),
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="MACD", row=3, col=1)

    st.plotly_chart(fig, use_container_width=True)


# ========== 市场识别 ==========

def identify_market(symbol: str) -> str:
    s = symbol.upper().strip()
    if s.isdigit() and len(s) == 6:
        return "a_share"
    if s.isdigit() and len(s) <= 5:
        return "hk"
    if s.endswith(".HK"):
        return "hk"
    if s.endswith((".SS", ".SZ")):
        return "a_share"
    if s.isalpha() and len(s) <= 4:
        return "us"
    return "us"


# ========== 主界面 ==========

def main():
    st.title("📈 股票实时行情 & 历史分析仪表盘")
    st.markdown(f"*数据更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    # === 侧边栏 ===
    with st.sidebar:
        st.header("⚙️ 控制面板")

        # 查看模式
        mode = st.radio(
            "📌 模式选择",
            ["🔍 单股深度分析", "📊 A股市场扫描", "🌍 全球市场快照"],
            key="mode",
        )

        st.divider()

        if mode == "🔍 单股深度分析":
            symbol = st.text_input("🔖 股票代码", value="600519",
                                   help="A股:6位数字 | 港股:5位数字 | 美股:字母代码")
            timeframe = st.selectbox("⏱ 时间范围",
                                     ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
                                     index=3)

            st.divider()
            st.markdown("""
            ### 💡 常用代码
            **A股**
            - 600519 贵州茅台
            - 000001 平安银行
            - 000858 五粮液
            - 300750 宁德时代

            **港股**
            - 00700 腾讯控股
            - 09988 阿里巴巴
            - 01810 小米集团

            **美股**
            - AAPL Apple
            - TSLA Tesla
            - NVDA NVIDIA
            - MSFT Microsoft
            """)

            search_btn = st.button("🔍 查询", type="primary", use_container_width=True)

        elif mode == "📊 A股市场扫描":
            st.markdown("扫描A股全市场，发现异动个股")
            scan_filter = st.selectbox("筛选条件", [
                "涨幅前20", "跌幅前20", "成交额前20",
                "换手率前20", "5日涨幅前20",
            ])
            search_btn = st.button("🔍 扫描", type="primary", use_container_width=True)

        else:
            global_symbol = st.text_input("🌐 股票代码", value="AAPL")
            global_tf = st.selectbox("⏱ 时间范围",
                                     ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
                                     index=3)
            search_btn = st.button("🔍 查询", type="primary", use_container_width=True)

    # === 主内容区 ===
    if mode == "🔍 单股深度分析" and search_btn:
        market = identify_market(symbol)
        market_label = {"a_share": "A股", "hk": "港股", "us": "美股"}.get(market, "未知")

        st.subheader(f"📈 {symbol} ({market_label})")

        # --- 实时行情 ---
        if market == "a_share":
            with st.spinner("正在获取A股实时行情..."):
                spot_df = fetch_a_share_spot()
                code = symbol.replace("sh", "").replace("sz", "")
                spot = spot_df[spot_df["代码"] == code] if not spot_df.empty else pd.DataFrame()

            if not spot.empty:
                row = spot.iloc[0]
                col1, col2, col3, col4, col5 = st.columns(5)
                change_pct = row.get("涨跌幅", 0)
                delta_color = "normal"
                col1.metric("最新价", f"{row.get('最新价', 'N/A')}", delta=f"{change_pct:+.2f}%" if pd.notna(change_pct) else None)
                col2.metric("涨跌额", f"{row.get('涨跌额', 'N/A')}")
                col3.metric("最高 / 最低", f"{row.get('最高', 'N/A')} / {row.get('最低', 'N/A')}")
                col4.metric("成交量(手)", f"{row.get('成交量', 'N/A')}")
                col5.metric("换手率", f"{row.get('换手率', 'N/A')}%")
            else:
                st.warning("未找到该股票实时数据，可能非交易时间")

            with st.spinner("获取历史K线数据..."):
                days_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "max": 3650}
                df = fetch_a_share_history(symbol, days=days_map.get(timeframe, 365))
        else:
            with st.spinner("获取全球市场数据..."):
                info = fetch_global_quote(symbol)
            if info:
                col1, col2, col3, col4 = st.columns(4)
                price = info.get("最新价", 0)
                prev = info.get("昨收", 0)
                change = (price - prev) if price and prev else 0
                change_pct = (change / prev * 100) if prev else 0
                col1.metric("最新价", f"{price}", delta=f"{change:+.2f} ({change_pct:+.2f}%)")
                col2.metric("开盘 / 最高 / 最低",
                            f"{info.get('开盘', 'N/A')} / {info.get('最高', 'N/A')} / {info.get('最低', 'N/A')}")
                col3.metric("市值", f"{info.get('市值', 'N/A')}")
                col4.metric("52周高/低", f"{info.get('52周高', 'N/A')} / {info.get('52周低', 'N/A')}")

            with st.spinner("获取历史K线..."):
                df = fetch_global_history(symbol, period=timeframe)

        # --- K线图 ---
        if not df.empty:
            st.markdown("---")
            market_label_cn = {"a_share": "A股", "us": "美股", "hk": "港股"}.get(market, "")
            plot_candlestick_plotly(
                df,
                f"{symbol}  {market_label_cn}  |  {timeframe}  |  {df.index[-1].strftime('%Y-%m-%d') if len(df) > 0 else ''}",
                market,
            )

            # --- 数据表 ---
            with st.expander("📋 查看原始数据"):
                st.dataframe(
                    df[["Open", "High", "Low", "Close", "Volume"]].tail(60).sort_index(ascending=False),
                    use_container_width=True,
                )

    elif mode == "📊 A股市场扫描" and search_btn:
        with st.spinner("正在扫描A股全市场..."):
            spot_df = fetch_a_share_spot()

        if not spot_df.empty:
            st.subheader(f"📊 A股市场扫描 — {scan_filter}")

            # 数值化
            for col in ["涨跌幅", "成交额", "换手率"]:
                if col in spot_df.columns:
                    spot_df[col] = pd.to_numeric(spot_df[col], errors="coerce")

            sort_map = {
                "涨幅前20": ("涨跌幅", False),
                "跌幅前20": ("涨跌幅", True),
                "成交额前20": ("成交额", False),
                "换手率前20": ("换手率", False),
                "5日涨幅前20": ("涨跌幅", False),  # 近似
            }
            sort_col, ascending = sort_map.get(scan_filter, ("涨跌幅", False))
            result = spot_df.sort_values(sort_col, ascending=ascending).head(20)

            # 显示列
            display_cols = ["代码", "名称", "最新价", "涨跌幅", "涨跌额", "成交量", "成交额", "换手率"]
            available_cols = [c for c in display_cols if c in result.columns]
            st.dataframe(
                result[available_cols].style.format({
                    "涨跌幅": "{:.2f}%", "最新价": "{:.2f}",
                    "成交额": "{:.0f}", "换手率": "{:.2f}%",
                }),
                use_container_width=True, height=600,
            )

            # 可视化
            st.markdown("---")
            st.subheader("📈 涨跌幅柱状图")
            bar_fig = go.Figure()
            colors = ['#ef5350' if v >= 0 else '#26a69a' for v in result["涨跌幅"]]
            bar_fig.add_trace(go.Bar(
                x=result["名称"], y=result["涨跌幅"],
                marker_color=colors,
                text=result["涨跌幅"].apply(lambda x: f'{x:+.2f}%'),
                textposition='outside',
            ))
            bar_fig.update_layout(
                height=400, template="plotly_white",
                xaxis_tickangle=-45,
                margin=dict(l=10, r=10, t=10, b=80),
            )
            st.plotly_chart(bar_fig, use_container_width=True)

    elif mode == "🌍 全球市场快照" and search_btn:
        market = identify_market(global_symbol)
        info = fetch_global_quote(global_symbol)
        df = fetch_global_history(global_symbol, period=global_tf)

        if info:
            st.subheader(f"🌍 {info.get('名称', global_symbol)} ({info.get('代码', global_symbol)})")
            col1, col2, col3, col4 = st.columns(4)
            price = info.get("最新价", 0) or 0
            prev = info.get("昨收", 0) or 0
            change = (price - prev) if price and prev else 0
            change_pct = (change / prev * 100) if prev else 0

            col1.metric("最新价", f"{info.get('货币', '$')} {price}",
                        delta=f"{change:+.2f} ({change_pct:+.2f}%)")
            col2.metric("日最高/最低", f"{info.get('最高', 'N/A')} / {info.get('最低', 'N/A')}")
            col3.metric("市值", f"{info.get('市值', 'N/A')}")
            col4.metric("市盈率", f"{info.get('市盈率', 'N/A')}")

        if not df.empty:
            st.markdown("---")
            market_label = {"us": "美股", "hk": "港股"}.get(market, "")
            plot_candlestick_plotly(
                df,
                f"{global_symbol}  {market_label}  |  {global_tf}  |  {df.index[-1].strftime('%Y-%m-%d')}",
                market,
            )

    else:
        # 默认欢迎页
        st.markdown("""
        ## 👋 欢迎使用股票仪表盘

        选择左侧的模式开始分析：

        - **🔍 单股深度分析** — 输入股票代码，查看实时行情 + 交互K线图（含MACD、均线）
        - **📊 A股市场扫描** — 扫描A股全市场，发现涨跌幅/成交额/换手率异动
        - **🌍 全球市场快照** — 查看美股/港股实时报价和历史走势

        ### 📌 快速开始
        在左侧输入股票代码（如 `600519` 茅台），点击查询即可。
        """)


if __name__ == "__main__":
    main()
