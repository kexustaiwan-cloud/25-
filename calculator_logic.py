import streamlit as st
import yfinance as yf
import pandas as pd

PERIODS = {"20日": 20, "60日": 60, "180日": 180}


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


def calc_levels(high: float, low: float):
    diff = high - low
    rebound_price = low + diff * 0.618   # 反彈預估價位
    retrace_price = high - diff * 0.618  # 回檔預估價位
    return rebound_price, retrace_price


def run():
    st.caption("輸入台灣股票代號，自動抓取近期高低點，計算反彈與回檔預估價位。")

    stock_id = st.text_input("台灣股票代號（例如：2330）", value="2330").strip()

    if not stock_id:
        st.warning("⚠️ 請輸入股票代號。")
        return

    with st.spinner("資料抓取中..."):
        df, ticker = fetch_tw_stock(stock_id)

    if df is None:
        st.error("❌ 查無此股票代號資料，請確認代號是否正確（上市或上櫃）。")
        return

    st.success(f"✅ 已取得 {ticker} 股價資料")

    rows = []
    for label, days in PERIODS.items():
        sub = df.tail(days)
        if sub.empty:
            continue

        high = float(sub["High"].max())
        low = float(sub["Low"].min())
        rebound_price, retrace_price = calc_levels(high, low)

        rows.append({
            "期間": label,
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
