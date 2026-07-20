import streamlit as st
import yfinance as yf
import pandas as pd

PERIODS = {"20日": 20, "60日": 60, "180日": 180}

METHODS = {
    "簡單絕對高低法": "simple",
    "波段轉折法（局部極值）": "swing",
    "ZigZag門檻法": "zigzag",
}


# ---------------- 資料抓取 ----------------

def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """新版 yfinance 有時會回傳 MultiIndex 欄位，這裡統一攤平"""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def fetch_tw_stock(stock_id: str):
    """依序嘗試上市(.TW)與上櫃(.TWO)代號，回傳(資料, 完整代號)"""
    for suffix in [".TW", ".TWO"]:
        ticker = f"{stock_id}{suffix}"
        df = yf.download(ticker, period="1y", progress=False, auto_adjust=False)
        if df is not None and not df.empty:
            return _flatten_columns(df), ticker
    return None, None


# ---------------- 三種高低點判斷算法 ----------------

def get_high_low_simple(sub: pd.DataFrame):
    """算法一：簡單絕對高低法，直接取區間內最大最小值"""
    high = float(sub["High"].max())
    low = float(sub["Low"].min())
    return high, low, "絕對高低"


def get_high_low_swing(sub: pd.DataFrame, window: int = 3):
    """算法二：波段轉折法，抓最近一組局部極值（前後window天都沒被超越）"""
    highs = sub["High"]
    lows = sub["Low"]

    swing_highs = highs[(highs.shift(window) < highs) & (highs.shift(-window) < highs)]
    swing_lows = lows[(lows.shift(window) > lows) & (lows.shift(-window) > lows)]

    if swing_highs.empty or swing_lows.empty:
        # 抓不到轉折點時，退回簡單絕對高低法
        high, low, _ = get_high_low_simple(sub)
        return high, low, "絕對高低（無足夠轉折點，已退回）"

    high = float(swing_highs.iloc[-1])
    low = float(swing_lows.iloc[-1])
    return high, low, "波段轉折"


def get_high_low_zigzag(sub: pd.DataFrame, threshold: float = 0.05):
    """算法三：ZigZag門檻法，反轉幅度需超過threshold才算新轉折點"""
    closes = sub["Close"]
    pivots = []
    last_pivot_price = float(closes.iloc[0])
    last_pivot_type = None  # 'high' 或 'low'

    for i in range(1, len(closes)):
        price = float(closes.iloc[i])
        change = (price - last_pivot_price) / last_pivot_price

        if last_pivot_type != "high" and change >= threshold:
            pivots.append((closes.index[i], price, "high"))
            last_pivot_price, last_pivot_type = price, "high"
        elif last_pivot_type != "low" and change <= -threshold:
            pivots.append((closes.index[i], price, "low"))
            last_pivot_price, last_pivot_type = price, "low"

    pivot_highs = [p for p in pivots if p[2] == "high"]
    pivot_lows = [p for p in pivots if p[2] == "low"]

    if not pivot_highs or not pivot_lows:
        # 門檻太高抓不到轉折點時，退回簡單絕對高低法
        high, low, _ = get_high_low_simple(sub)
        return high, low, "絕對高低（無足夠轉折點，已退回）"

    high = pivot_highs[-1][1]
    low = pivot_lows[-1][1]
    return high, low, "ZigZag轉折"


def get_high_low(sub: pd.DataFrame, method: str, window: int, threshold: float):
    if method == "simple":
        return get_high_low_simple(sub)
    elif method == "swing":
        return get_high_low_swing(sub, window=window)
    elif method == "zigzag":
        return get_high_low_zigzag(sub, threshold=threshold)
    else:
        return get_high_low_simple(sub)


# ---------------- 反彈 / 回檔計算 ----------------

def calc_levels(high: float, low: float):
    diff = high - low
    rebound_price = low + diff * 0.618   # 反彈預估價位
    retrace_price = high - diff * 0.618  # 回檔預估價位
    return rebound_price, retrace_price


# ---------------- 主程式 ----------------

def run():
    st.caption("輸入台灣股票代號，自動抓取近期高低點，計算反彈與回檔預估價位。")

    stock_id = st.text_input("台灣股票代號（例如：2330）", value="2330").strip()

    method_label = st.selectbox("高低點判斷算法", list(METHODS.keys()))
    method = METHODS[method_label]

    window = 3
    threshold = 0.05

    if method == "swing":
        window = st.slider("波段轉折判斷天數（左右各N天）", min_value=1, max_value=10, value=3)
    elif method == "zigzag":
        threshold = st.slider("ZigZag反轉門檻（%）", min_value=1, max_value=15, value=5) / 100

    if not stock_id:
        st.warning("⚠️ 請輸入股票代號。")
        return

    with st.spinner("資料抓取中..."):
        df, ticker = fetch_tw_stock(stock_id)

    if df is None:
        st.error("❌ 查無此股票代號資料，請確認代號是否正確（上市或上櫃）。")
        return

    st.success(f"✅ 已取得 {ticker} 股價資料（採用：{method_label}）")

    rows = []
    for label, days in PERIODS.items():
        sub = df.tail(days)
        if sub.empty or len(sub) < 2:
            continue

        high, low, note = get_high_low(sub, method, window, threshold)
        if high <= low:
            continue

        rebound_price, retrace_price = calc_levels(high, low)

        rows.append({
            "期間": label,
            "判斷方式": note,
            "期間高點": round(high, 2),
            "期間低點": round(low, 2),
            "反彈預估價位": round(rebound_price, 2),
            "回檔預估價位": round(retrace_price, 2),
        })

    if rows:
        st.table(pd.DataFrame(rows))
    else:
        st.warning("⚠️ 資料不足，無法計算。")


if __name__ == "__main__":
    run()
