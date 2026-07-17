import streamlit as st
import invoice_logic
import stock_logic

# 設定頁面
st.set_page_config(page_title="Ethan 的綜合工具平台", layout="wide")

# 側邊欄選單
st.sidebar.title("工具選單")
choice = st.sidebar.radio("選擇功能", ["🧾 25型發票掃瞄", "📈 即時價值投資股掃描"])

if choice == "🧾 25型發票掃瞄":
    invoice_logic.run() # 請確保 invoice_logic.py 裡面有一個 run() 函式
elif choice == "📈 即時價值投資股掃描":
    stock_logic.run()   # 請確保 stock_logic.py 裡面有一個 run() 函式