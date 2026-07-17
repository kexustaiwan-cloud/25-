import streamlit as st
import invoice_logic
import stock_logic
import calculator_logic  # 黃金切割率 回檔/反彈 計算

st.set_page_config(page_title="Ethan 的工具平台", layout="wide")

# 側邊欄選單
st.sidebar.title("工具選單")
choice = st.sidebar.radio(
    "選擇功能",
    ["🧾 25型發票掃瞄", "📈 即時價值投資股掃描", "📐 股價反彈/回檔計算"]
)

# 根據選擇顯示內容
if choice == "🧾 25型發票掃瞄":
    st.title("🧾 25型發票資料掃瞄")
    invoice_logic.run()  # 這裡會呼叫 invoice_logic.py 裡面的 run() 函式

elif choice == "📈 即時價值投資股掃描":
    st.title("📈 即時價值投資股掃描")
    stock_logic.run()    # 這裡會呼叫 stock_logic.py 裡面的 run() 函式

elif choice == "📐 股價反彈/回檔計算":
    st.title("📐 股價反彈/回檔計算（黃金切割率）")
    calculator_logic.run()  # 這裡會呼叫 calculator_logic.py 裡面的 run() 函式
