import streamlit as st
import streamlit.components.v1 as components
import invoice_logic
import stock_logic

# 1. 頁面設定
st.set_page_config(page_title="Ethan 的工具平台", layout="wide")

# 2. Google AdSense 驗證碼注入
adsense_code = """
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXX" crossorigin="anonymous"></script>
"""
components.html(adsense_code, height=0)

# 3. 側邊欄選單
st.sidebar.title("工具選單")
choice = st.sidebar.radio("選擇功能", ["🧾 25型發票掃瞄", "📈 即時價值投資股掃描"])

# 4. 主功能顯示區域
if choice == "🧾 25型發票掃瞄":
    st.title("🧾 25型發票資料掃瞄")
    invoice_logic.run()

elif choice == "📈 即時價值投資股掃描":
    st.title("📈 即時價值投資股掃描")
    stock_logic.run()

# 5. 底部免責聲明 (使用 expander 保持介面整潔)
st.sidebar.markdown("---")
with st.sidebar.expander("📢 免責聲明"):
    st.markdown("""
    **標準版免責聲明**
    
    * 本網站僅提供股票資訊整理、數據分析及篩選工具服務。
    * 網站內容不構成任何投資、理財、法律或稅務建議。
    * 本網站非證券投資顧問機構，亦不提供個人化投資建議。
    * 所有股票篩選結果僅為演算法運算結果，不代表推薦買進、賣出或持有任何標的。
    * 金融市場具有高度風險，投資可能導致部分或全部資金損失。
    * 使用者應自行進行研究與風險評估，並諮詢專業人士意見。
    * 本網站不保證資料之完整性、即時性及正確性。
    * 因使用本網站資訊所產生之任何投資損益，本網站概不負責。
    """)