import streamlit as st
import streamlit.components.v1 as components
import invoice_logic
import stock_logic
import calculator_logic

# =========================
# 頁面設定
# =========================
st.set_page_config(
    page_title="Ethan 的工具平台",
    page_icon="📊",
    layout="wide"
)

# =========================
# Google AdSense 中繼標記驗證
# 將此段代碼替換為 AdSense 提供的 Meta Tag
# =========================
adsense_meta_tag = """
<meta name="google-adsense-account" content="ca-pub-XXXXXXXXXXXXXXXX">
"""
# 使用 height=0 隱藏元件，使其作為頁面元數據的一部分
components.html(adsense_meta_tag, height=0)

# =========================
# Sidebar
# =========================
st.sidebar.title("🛠️ 工具選單")

choice = st.sidebar.radio(
    "選擇功能",
    [
        "🧾 25型發票掃瞄",
        "📈 即時價值投資股掃描",
        "📐 股價反彈/回檔計算"
    ]
)

# =========================
# 主畫面
# =========================

if choice == "🧾 25型發票掃瞄":
    st.title("🧾 25型發票資料掃瞄")
    st.caption("OCR 辨識發票內容，快速整理資料")
    invoice_logic.run()

elif choice == "📈 即時價值投資股掃描":
    st.title("📈 即時價值投資股掃描")
    st.caption("依據財務條件與價值投資指標進行股票篩選")
    stock_logic.run()

elif choice == "📐 股價反彈/回檔計算":
    st.title("📐 股價反彈 / 回檔計算")
    st.caption("使用黃金切割率(Fibonacci)計算支撐與壓力區")
    calculator_logic.run()

# =========================
# 側邊欄免責聲明
# =========================
st.sidebar.markdown("---")

with st.sidebar.expander("📢 免責聲明"):
    st.markdown("""
### 📈 股票分析聲明
- 本網站僅提供股票資訊整理、數據分析及篩選工具服務。
- 網站內容不構成任何投資、理財、法律或稅務建議。
- 本網站非證券投資顧問機構，亦不提供個人化投資建議。
- 所有股票篩選結果僅為演算法運算結果。
- 不推薦任何股票買進、賣出或持有。
- 不保證資料完整性、即時性及正確性。
- 過往績效不代表未來報酬。
- 投資有風險，盈虧由使用者自行承擔。

### 🤖 AI分析聲明
- AI分析結果僅供研究與教育用途。
- AI模型可能因資料品質、市場變化或演算法限制產生誤差。
- AI預測結果不保證準確。
- 不應作為投資決策唯一依據。

### 🧾 發票掃描聲明
- OCR辨識結果可能存在錯誤或遺漏。
- 辨識內容僅供參考。
- 請以原始發票內容為準。
- 本網站不保證辨識結果百分之百正確。
- 因辨識誤差造成之損失，本網站概不負責。

### 📐 股價回檔 / 反彈計算聲明
- 黃金切割率(Fibonacci)僅為技術分析工具。
- 計算結果不代表未來股價走勢。
- 不構成買賣建議。
- 使用者應自行判斷並承擔投資風險。

---
⚠️ 使用本網站即表示您已了解並同意上述聲明。
""")

# =========================
# Footer
# =========================
st.markdown("---")
st.caption("© Ethan Tools Platform | 股票分析、發票掃描與黃金切割率計算工具")