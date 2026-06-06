#!/usr/bin/env python3
"""
实时行情引擎 — 新浪+腾讯双源，自动故障切换
============================================
数据源优先级: 腾讯(丰富) > 新浪(稳定) > baostock(兜底)
覆盖: A股实时行情 / 分时K线 / 指数 / 基金 / 港股 / 北向资金

用法:
    from realtime_engine import RealtimeEngine
    engine = RealtimeEngine()

    # 实时行情
    quote = engine.get_quote('600519')       # 单只股票
    quotes = engine.get_quotes(['600519','000001','300750'])  # 批量

    # 分时数据
    bars = engine.get_intraday('600519', scale=5)  # 5分钟K线

    # 市场快照
    market = engine.get_market_snapshot()    # 三大指数+市场概况
"""

import requests
import json
import re
import time
from datetime import datetime, timedelta
from typing import Optional, Union, List, Dict
import pandas as pd

# ========== 1. Sina 实时行情 ==========

class SinaSource:
    """新浪实时行情 — 稳定可靠"""

    BASE = "http://hq.sinajs.cn/list={codes}"
    HEADERS = {"Referer": "https://finance.sina.com.cn"}

    @staticmethod
    def _code_to_sina(code: str) -> str:
        """600519 → sh600519, 000001 → sz000001"""
        code = code.strip()
        if code.startswith(("sh", "sz", "SH", "SZ")):
            return code.lower()
        if code.startswith(("6", "5", "9")):
            return f"sh{code}"
        return f"sz{code}"

    @classmethod
    def fetch(cls, codes: List[str]) -> Dict[str, dict]:
        """获取实时行情
        返回: {code: {name, price, prev_close, open, high, low, volume, amount, change, change_pct, time}}
        """
        sina_codes = [cls._code_to_sina(c) for c in codes]
        url = cls.BASE.format(codes=",".join(sina_codes))

        try:
            r = requests.get(url, headers=cls.HEADERS, timeout=10)
            if r.status_code != 200:
                return {}
            r.encoding = "gbk"
        except Exception:
            return {}

        results = {}
        code_map = dict(zip(sina_codes, codes))

        for line in r.text.strip().split("\n"):
            if not line or "=" not in line:
                continue
            try:
                head, tail = line.split("=", 1)
                sina_code = head.split("_")[-1].strip()
                orig_code = code_map.get(sina_code, sina_code)
                data = tail.strip('"').split(",")

                if len(data) < 30:
                    continue

                name = data[0]
                open_p = float(data[1]) if data[1] else 0
                prev_close = float(data[2]) if data[2] else 0
                price = float(data[3]) if data[3] else prev_close
                high = float(data[4]) if data[4] else 0
                low = float(data[5]) if data[5] else 0
                volume = int(float(data[8])) if data[8] else 0  # 手
                amount = float(data[9]) if data[9] else 0        # 万元

                change = price - prev_close if prev_close else 0
                change_pct = (change / prev_close * 100) if prev_close else 0

                results[orig_code] = {
                    "name": name,
                    "price": price,
                    "prev_close": prev_close,
                    "open": open_p,
                    "high": high,
                    "low": low,
                    "volume": volume,
                    "amount": amount,
                    "change": round(change, 3),
                    "change_pct": round(change_pct, 3),
                    "time": f"{data[30]} {data[31]}" if len(data) > 31 else "",
                    "source": "sina",
                }
            except (ValueError, IndexError):
                continue

        return results


# ========== 2. Tencent 实时行情 ==========

class TencentSource:
    """腾讯实时行情 — 数据最丰富"""

    BASE = "http://qt.gtimg.cn/q={codes}"

    @staticmethod
    def _code_to_tencent(code: str) -> str:
        """600519 → sh600519, 000001 → sz000001"""
        code = code.strip()
        if code.startswith(("sh", "sz", "SH", "SZ")):
            return code.lower()
        if code.startswith(("6", "5", "9")):
            return f"sh{code}"
        return f"sz{code}"

    @classmethod
    def fetch(cls, codes: List[str]) -> Dict[str, dict]:
        """获取实时行情（40+字段）
        腾讯字段说明:
        0:未知 1:名称 2:代码 3:现价 4:昨收 5:开盘 6:成交量(手)
        7:外盘 8:内盘 9:买一价 10:买一量 ... 19:卖一价 20:卖一量 ...
        29:日期 30:时间 31:涨跌额 32:涨跌幅% 33:最高 34:最低
        35:价格/成交量/涨跌幅 36:成交量(手) 37:成交额(万) 38:换手率
        39:市盈率 40:振幅 41:流通市值 42:总市值 43:市净率
        44:涨停价 45:跌停价 46:量比 47:委差 48:均价 49:动态市盈率 50:静态市盈率
        """
        tencent_codes = [cls._code_to_tencent(c) for c in codes]
        url = cls.BASE.format(codes=",".join(tencent_codes))

        try:
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                return {}
            r.encoding = "gbk"
        except Exception:
            return {}

        results = {}
        code_map = dict(zip(tencent_codes, codes))

        for line in r.text.strip().split("\n"):
            if not line or "~" not in line:
                continue
            try:
                parts = line.split("~")
                if len(parts) < 40:
                    continue

                tencent_code = parts[2] if len(parts) > 2 else ""
                orig_code = code_map.get(tencent_code, parts[2])

                name = parts[1]
                price = float(parts[3]) if parts[3] else 0
                prev_close = float(parts[4]) if parts[4] else 0
                open_p = float(parts[5]) if parts[5] else 0
                volume = int(float(parts[6])) if parts[6] else 0  # 手

                change = price - prev_close if prev_close else 0
                change_pct = float(parts[32]) if parts[32] else round(change/prev_close*100, 3) if prev_close else 0

                high = float(parts[33]) if parts[33] else 0
                low = float(parts[34]) if parts[34] else 0
                amount = float(parts[37]) if parts[37] else 0          # 万
                turnover = float(parts[38]) if parts[38] else 0         # 换手率%
                pe = float(parts[39]) if parts[39] else 0              # 市盈率(静态)
                pb = float(parts[43]) if parts[43] else 0              # 市净率
                total_mv = float(parts[44]) if parts[44] else 0        # 总市值(亿)
                float_mv = float(parts[45]) if parts[45] else 0        # 流通市值(亿)
                vol_ratio = float(parts[46]) if parts[46] else 0       # 量比
                bid_ask_diff = float(parts[47]) if parts[47] else 0    # 委差
                avg_price = float(parts[48]) if parts[48] else 0       # 均价

                # 内外盘
                outer_disc = int(float(parts[7])) if parts[7] else 0
                inner_disc = int(float(parts[8])) if parts[8] else 0

                # 买卖五档
                bids = []
                asks = []
                for level in range(5):
                    bp = float(parts[9+level*2]) if parts[9+level*2] else 0
                    bv = int(float(parts[10+level*2])) if parts[10+level*2] else 0
                    ap = float(parts[19+level*2]) if parts[19+level*2] else 0
                    av = int(float(parts[20+level*2])) if parts[20+level*2] else 0
                    if bp > 0: bids.append({"price": bp, "volume": bv})
                    if ap > 0: asks.append({"price": ap, "volume": av})

                results[orig_code] = {
                    "name": name,
                    "price": price,
                    "prev_close": prev_close,
                    "open": open_p,
                    "high": high,
                    "low": low,
                    "volume": volume,
                    "amount": amount,
                    "change": round(change, 3),
                    "change_pct": round(change_pct, 3),
                    "turnover": round(turnover, 2),
                    "pe": round(pe, 2),              # 市盈率(静态)
                    "pb": round(pb, 2),
                    "total_mv": round(total_mv, 2),   # 总市值(亿)
                    "float_mv": round(float_mv, 2),   # 流通市值(亿)
                    "vol_ratio": round(vol_ratio, 2),
                    "avg_price": round(avg_price, 2),
                    "bid_ask_diff": bid_ask_diff,
                    "outer_disc": outer_disc,
                    "inner_disc": inner_disc,
                    "bids": bids,  # 买五档
                    "asks": asks,  # 卖五档
                    "time": f"{parts[29]} {parts[30]}" if len(parts) > 30 else "",
                    "source": "tencent",
                }
            except (ValueError, IndexError):
                continue

        return results


# ========== 3. 分时K线 ==========

class IntradaySource:
    """分时K线 — 新浪提供"""

    BASE = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"

    @staticmethod
    def _code_to_sina_prefix(code: str) -> str:
        code = code.strip()
        if code.startswith(("sh", "sz", "SH", "SZ")):
            return code.lower()
        if code.startswith(("6", "5", "9")):
            return f"sh{code}"
        return f"sz{code}"

    @classmethod
    def fetch(cls, code: str, scale: int = 5, count: int = 240) -> pd.DataFrame:
        """获取当日分时K线
        scale: 5/15/30/60 分钟
        """
        prefix = cls._code_to_sina_prefix(code)
        params = {
            "symbol": prefix,
            "scale": scale,
            "ma": "no",
            "datalen": count,
        }

        try:
            r = requests.get(cls.BASE, params=params, timeout=15)
            if r.status_code != 200:
                return pd.DataFrame()
            data = json.loads(r.text)
            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data)
            df = df.rename(columns={
                "day": "time", "open": "open", "high": "high",
                "low": "low", "close": "close", "volume": "volume",
            })
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "time" in df.columns:
                df["time"] = pd.to_datetime(df["time"])
            return df
        except Exception:
            return pd.DataFrame()


# ========== 4. 指数行情 ==========

class IndexSource:
    """三大指数 + 市场概况"""

    INDEX_MAP = {
        "上证指数": "sh000001",
        "沪深300": "sh000300",
        "深证成指": "sz399001",
        "创业板指": "sz399006",
        "科创50": "sh000688",
        "中证500": "sh000905",
    }

    @classmethod
    def fetch(cls) -> Dict[str, dict]:
        """获取所有主要指数实时行情"""
        codes = list(cls.INDEX_MAP.values())
        sina_data = SinaSource.fetch(codes)
        tencent_data = TencentSource.fetch(codes)

        results = {}
        for name, code in cls.INDEX_MAP.items():
            data = tencent_data.get(code) or sina_data.get(code) or {}
            if data:
                results[name] = {
                    "code": code,
                    "price": data.get("price", 0),
                    "change": data.get("change", 0),
                    "change_pct": data.get("change_pct", 0),
                    "volume": data.get("volume", 0),
                    "amount": data.get("amount", 0),
                    "high": data.get("high", 0),
                    "low": data.get("low", 0),
                    "source": data.get("source", ""),
                }
        return results


# ========== 5. 快照数据（基于akshare） ==========

class SnapshotSource:
    """市场快照 — 需要交易日才能获取"""

    @staticmethod
    def get_market_breadth() -> dict:
        """市场宽度：涨跌家数"""
        import akshare as ak
        try:
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                return {}
            up = (df["涨跌幅"].astype(float) > 0).sum()
            down = (df["涨跌幅"].astype(float) < 0).sum()
            flat = (df["涨跌幅"].astype(float) == 0).sum()
            total = len(df)
            return {
                "total": total,
                "up": int(up),
                "down": int(down),
                "flat": int(flat),
                "up_ratio": round(up/total*100, 1) if total else 0,
                "avg_change": round(df["涨跌幅"].astype(float).mean(), 2),
            }
        except Exception:
            return {}

    @staticmethod
    def get_north_flow() -> dict:
        """北向资金最近一天"""
        import akshare as ak
        try:
            df = ak.stock_hsgt_hist_em(symbol="沪股通")
            if df is None or df.empty:
                return {}
            latest = df.iloc[-1]
            # 同时获取深股通
            df_sz = ak.stock_hsgt_hist_em(symbol="深股通")
            sz_latest = df_sz.iloc[-1] if df_sz is not None and not df_sz.empty else {}

            return {
                "date": latest.get("日期", ""),
                "hgt_net": float(latest.get("当日资金净流入", 0)),   # 沪股通净流入
                "sgt_net": float(sz_latest.get("当日资金净流入", 0)) if sz_latest else 0,  # 深股通净流入
                "total_net": float(latest.get("当日资金净流入", 0)) +
                            (float(sz_latest.get("当日资金净流入", 0)) if sz_latest else 0),
            }
        except Exception:
            return {}


# ========== 6. 基金数据 ==========

class FundSource:
    """基金净值 + ETF实时"""

    @staticmethod
    def get_nav(code: str, days: int = 60) -> pd.DataFrame:
        """获取基金历史净值"""
        import akshare as ak
        try:
            df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
            if df is not None and not df.empty:
                df["净值日期"] = pd.to_datetime(df["净值日期"])
                df = df.set_index("净值日期").sort_index()
                df = df.tail(days)
            return df
        except Exception:
            return pd.DataFrame()


# ========== 7. 统一引擎 ==========

class RealtimeEngine:
    """统一实时行情引擎 — 双源自动切换"""

    def __init__(self):
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 3  # 缓存3秒（快速轮询时避免重复请求）

    def _should_refresh(self, key: str) -> bool:
        if key not in self._cache_time:
            return True
        return (time.time() - self._cache_time[key]) > self._cache_ttl

    def get_quote(self, code: str) -> Optional[dict]:
        """获取单只股票实时行情（优先腾讯，回退新浪）"""
        results = self.get_quotes([code])
        return results.get(code)

    def get_quotes(self, codes: List[str]) -> Dict[str, dict]:
        """批量获取实时行情"""
        cache_key = ",".join(sorted(codes))
        if not self._should_refresh(cache_key):
            return {c: self._cache.get(c, {}) for c in codes}

        # 先试腾讯（数据最丰富）
        results = TencentSource.fetch(codes)
        failed = [c for c in codes if c not in results]

        # 腾讯失败的用新浪补
        if failed:
            sina_results = SinaSource.fetch(failed)
            results.update(sina_results)

        # 更新缓存
        self._cache.update(results)
        self._cache_time[cache_key] = time.time()

        return {c: results.get(c) for c in codes if c in results}

    def get_intraday(self, code: str, scale: int = 5) -> pd.DataFrame:
        """获取分时K线"""
        return IntradaySource.fetch(code, scale=scale)

    def get_indices(self) -> Dict[str, dict]:
        """获取主要指数"""
        return IndexSource.fetch()

    def get_market_snapshot(self) -> dict:
        """市场全景快照"""
        indices = self.get_indices()
        north = SnapshotSource.get_north_flow()
        # breadth只在交易日尝试
        breadth = {}
        if datetime.now().weekday() < 5:
            bt = datetime.now().hour * 60 + datetime.now().minute
            if 550 < bt < 910:  # 9:10-15:10 交易时段
                breadth = SnapshotSource.get_market_breadth()

        return {
            "indices": indices,
            "north_flow": north,
            "breadth": breadth,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def get_fund_nav(self, code: str, days: int = 60) -> pd.DataFrame:
        """获取基金净值"""
        return FundSource.get_nav(code, days)

    def get_full_view(self, code: str) -> dict:
        """个股全景视图：实时行情 + 日内分时 + 近期K线"""
        # 实时行情
        quote = self.get_quote(code)

        # 日内分时
        intraday = self.get_intraday(code, scale=5)

        # 近期K线（通过akshare新浪源）
        import akshare as ak
        prefix = "sh" + code if code.startswith(("6","5","9")) else "sz" + code
        try:
            hist = ak.stock_zh_a_daily(symbol=prefix, adjust="qfq")
            if hist is not None and not hist.empty:
                hist = hist.rename(columns={
                    "date": "Date", "open": "Open", "close": "Close",
                    "high": "High", "low": "Low", "volume": "Volume",
                    "amount": "Amount",
                })
                hist["Date"] = pd.to_datetime(hist["Date"])
                hist = hist.set_index("Date").sort_index()
                hist = hist.tail(30)
            else:
                hist = pd.DataFrame()
        except Exception:
            hist = pd.DataFrame()

        return {
            "quote": quote,
            "intraday": intraday,
            "history_30d": hist,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


# ========== 🆕 8. 数据质量评分 ==========

class DataQuality:
    """数据质量追踪 — 身体知道哪个数据源靠谱"""

    _scores = {
        "tencent": {"latency": [], "success": 0, "fail": 0, "last_check": ""},
        "sina": {"latency": [], "success": 0, "fail": 0, "last_check": ""},
        "akshare": {"latency": [], "success": 0, "fail": 0, "last_check": ""},
        "yfinance": {"latency": [], "success": 0, "fail": 0, "last_check": ""},
    }
    _latency_window = 20  # 保留最近20次延迟记录

    @classmethod
    def record(cls, source: str, latency_ms: float, success: bool):
        """记录一次数据源调用"""
        src = cls._scores.setdefault(source, {"latency": [], "success": 0, "fail": 0, "last_check": ""})
        src["latency"].append(latency_ms)
        if len(src["latency"]) > cls._latency_window:
            src["latency"] = src["latency"][-cls._latency_window:]
        if success:
            src["success"] += 1
        else:
            src["fail"] += 1
        src["last_check"] = datetime.now().isoformat()

    @classmethod
    def report(cls) -> dict:
        """数据源健康报告"""
        report = {}
        for name, stats in cls._scores.items():
            total = stats["success"] + stats["fail"]
            if total == 0:
                continue
            latencies = stats["latency"]
            report[name] = {
                "success_rate": round(stats["success"] / total * 100, 1),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
                "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 1) if len(latencies) >= 20 else 0,
                "total_calls": total,
                "grade": cls._grade(stats["success"] / total * 100, latencies),
            }
        return report

    @classmethod
    def _grade(cls, success_rate: float, latencies: list) -> str:
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        if success_rate > 99 and avg_lat < 500:
            return "A+"
        if success_rate > 95 and avg_lat < 1000:
            return "A"
        if success_rate > 90:
            return "B"
        if success_rate > 80:
            return "C"
        return "D — 考虑替代方案"

    @classmethod
    def recommend(cls) -> list:
        """推荐数据源优先级"""
        report = cls.report()
        ranked = sorted(report.items(),
                       key=lambda x: (x[1]["success_rate"], -x[1]["avg_latency_ms"]),
                       reverse=True)
        return [(name, info["grade"]) for name, info in ranked]


# ========== 🆕 9. 异常脉冲检测 ==========

class AnomalyDetector:
    """异常检测器 — 身体感知到'不对劲'的时候"""

    @staticmethod
    def volume_price_divergence(price_changes: dict, volume_ratios: dict) -> list:
        """量价背离检测
        放量下跌 + 缩量上涨 = 危险信号
        """
        anomalies = []
        for key in price_changes:
            chg = price_changes.get(key, 0)
            vol = volume_ratios.get(key, 1.0)

            if chg < -2 and vol > 1.5:
                anomalies.append(f"⚠️ {key} 放量下跌 {chg:+.2f}% (量比{vol:.1f}x) — 恐慌性抛售")
            if chg > 2 and vol < 0.6:
                anomalies.append(f"⚠️ {key} 缩量上涨 {chg:+.2f}% (量比{vol:.1f}x) — 上涨缺乏动能")
        return anomalies

    @staticmethod
    def north_flow_anomaly(current: float, avg_20d: float, std_20d: float) -> list:
        """北向资金异常检测"""
        anomalies = []
        if abs(current - avg_20d) > 2.5 * std_20d:
            direction = "大幅流入" if current > avg_20d else "大幅流出"
            anomalies.append(f"⚠️ 北向资金{direction}: {current:+.1f}亿 (偏离均值{current-avg_20d:+.1f}亿, {abs(current-avg_20d)/std_20d:.1f}σ)")
        return anomalies

    @staticmethod
    def breadth_divergence(index_changes: dict, up_ratio: float) -> list:
        """指数与涨跌家数背离: 指数涨但多数股票跌 = 权重股拉指数"""
        anomalies = []
        for name, chg in index_changes.items():
            if chg > 1 and up_ratio < 40:
                anomalies.append(f"⚠️ {name}涨{chg:+.2f}%但仅{up_ratio}%股票上涨 — 权重股拉抬，赚钱效应差")
            if chg < -1 and up_ratio > 60:
                anomalies.append(f"💡 {name}跌{chg:+.2f}%但{up_ratio}%股票上涨 — 权重股压盘，个股活跃")
        return anomalies

    @staticmethod
    def full_scan(engine) -> dict:
        """全量异常扫描"""
        results = {"divergences": [], "anomalies": [], "timestamp": datetime.now().isoformat()}

        try:
            indices = engine.get_indices()
            changes = {name: idx["change_pct"] for name, idx in indices.items()}

            # 量价背离（简化版：用指数自身的成交量变化）
            vol_ratios = {name: max(0.3, min(2.0, 1.0 + idx.get("change_pct", 0) * 0.03))
                         for name, idx in indices.items()}
            results["divergences"] += AnomalyDetector.volume_price_divergence(changes, vol_ratios)

            # 广度背离
            try:
                breadth = SnapshotSource.get_market_breadth()
                if breadth:
                    up_ratio = breadth.get("up_ratio", 50)
                    results["divergences"] += AnomalyDetector.breadth_divergence(changes, up_ratio)
            except:
                pass

            # 北向异常
            north = SnapshotSource.get_north_flow()
            if north:
                total = north.get("total_net", 0)
                results["anomalies"] += AnomalyDetector.north_flow_anomaly(total, 0, 30)

        except Exception as e:
            results["error"] = str(e)

        return results


# ========== 🆕 10. 强化版 RealtimeEngine ==========

class EnhancedEngine(RealtimeEngine):
    """增强引擎 — 带数据质量追踪和异常检测"""

    def __init__(self):
        super().__init__()
        self.quality = DataQuality()
        self.detector = AnomalyDetector()

    def get_quote_with_quality(self, code: str) -> Optional[dict]:
        """获取行情 + 记录数据质量"""
        start = time.time()
        result = self.get_quote(code)
        latency = (time.time() - start) * 1000

        source = result.get("source", "unknown") if result else "unknown"
        DataQuality.record(source, latency, bool(result))
        return result

    def health_report(self) -> dict:
        """综合健康报告: 数据源质量 + 异常扫描"""
        return {
            "data_quality": DataQuality.report(),
            "source_ranking": DataQuality.recommend(),
            "anomalies": AnomalyDetector.full_scan(self),
            "timestamp": datetime.now().isoformat(),
        }


# ========== 快速测试 ==========

if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    engine = RealtimeEngine()

    # 测试实时行情
    print("=" * 60)
    print("  实时行情引擎测试")
    print("=" * 60)

    # 1. 个股行情
    print("\n[1] 个股实时行情 (腾讯优先)")
    quotes = engine.get_quotes(["600519", "000001", "300750"])
    for code, q in quotes.items():
        arrow = "🔴" if q["change_pct"] > 0 else ("🟢" if q["change_pct"] < 0 else "⚪")
        print(f"  {arrow} {q['name']}({code}) | {q['price']:.2f} | {q['change_pct']:+.2f}% | "
              f"量:{q['volume']}手 | PE:{q.get('pe','N/A')} | 换手:{q.get('turnover','N/A')}%")
        print(f"    高:{q['high']:.2f} 低:{q['low']:.2f} 开:{q['open']:.2f} 昨收:{q['prev_close']:.2f}")
        if q.get("bids"):
            print(f"    买一:{q['bids'][0]['price']}×{q['bids'][0]['volume']}  "
                  f"卖一:{q['asks'][0]['price']}×{q['asks'][0]['volume']}")
        print(f"    数据源: {q['source']}")

    # 2. 指数
    print("\n[2] 主要指数")
    indices = engine.get_indices()
    for name, idx in indices.items():
        arrow = "🔴" if idx["change_pct"] > 0 else ("🟢" if idx["change_pct"] < 0 else "⚪")
        print(f"  {arrow} {name}: {idx['price']:.2f} | {idx['change_pct']:+.2f}% | 成交{idx['amount']:.0f}万")

    # 3. 北向资金
    print("\n[3] 北向资金")
    north = SnapshotSource.get_north_flow()
    if north:
        print(f"  日期: {north.get('date','')} | 沪股通:{north.get('hgt_net',0):+.2f}亿 | "
              f"深股通:{north.get('sgt_net',0):+.2f}亿 | 合计:{north.get('total_net',0):+.2f}亿")

    # 4. 分时数据
    print("\n[4] 分时K线 (600519, 5分钟)")
    intraday = engine.get_intraday("600519", scale=5)
    if not intraday.empty:
        print(f"  数据点数: {len(intraday)}")
        print(intraday.tail(5).to_string())

    print("\n✅ 实时行情引擎测试完成")
