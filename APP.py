import streamlit as st
import streamlit.components.v1 as components

# 設定網頁標題
st.set_page_config(page_title="Ethan 的綜合工具平台", layout="wide")

# --- 廣告函式 ---
def show_ads():
    # 請將這裡的 ca-pub-xxx 和 data-ad-slot 換成你從 AdSense 拿到的真實數據
    ads_code = """
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXX" crossorigin="anonymous"></script>
    <ins class="adsbygoogle"
         style="display:block"
         data-ad-client="ca-pub-XXXXXXXXXXXX"
         data-ad-slot="XXXXXXXXXXXX"
         data-ad-format="auto"
         data-full-width-responsive="true"></ins>
    <script>(adsbygoogle = window.adsbygoogle || []).push({});</script>
    """
    components.html(ads_code, height=280)

# --- 側邊欄導航 ---
st.sidebar.title("工具選單")
choice = st.sidebar.radio("請選擇服務：", ["🧾 25型發票掃瞄", "📈 即時價值投資股掃描", "🔄 股價反彈/回檔計算"])

# --- 廣告顯示位置 (放在側邊欄下方，所有頁面共用) ---
st.sidebar.markdown("---")
st.sidebar.write("贊助商廣告")
show_ads()

# --- 頁面內容邏輯 ---
if choice == "🧾 25型發票掃瞄":
    st.title("🧾 25型發票資料掃瞄")
    st.write("這是您的發票辨識系統...")
    # 在這裡放入你原本的發票掃瞄程式碼
    # ...

elif choice == "📈 即時價值投資股掃描":
    st.title("📈 即時價值投資股掃描")
    st.write("這裡是投資掃描功能...")
    # 在這裡放入投資掃描的程式碼
    # ...

elif choice == "🔄 股價反彈/回檔計算":
    st.title("🔄 股價反彈/回檔計算")
    st.write("這裡是股價計算功能...")
    # 在這裡放入股價計算的程式碼
    # ...

# --- 頁面底部廣告 ---
st.markdown("---")
show_ads()