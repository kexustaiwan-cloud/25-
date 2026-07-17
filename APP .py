import streamlit as st

st.set_page_config(page_title="Ethan's 綜合工具平台", layout="wide")

# --- 側邊欄或上方廣告 (全站通用) ---
st.markdown("<!-- 這裡插入你的 AdSense 廣告 Code -->", unsafe_allow_html=True)

st.title("🚀 Ethan 的綜合工具平台")

# 使用 Session State 紀錄目前在哪個頁面
if 'current_page' not in st.session_state:
    st.session_state.current_page = "首頁"

# 首頁按鈕邏輯
if st.session_state.current_page == "首頁":
    st.subheader("請選擇您的工具：")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📈 即時價值投資股掃描"):
            st.session_state.current_page = "價值投資"
            st.rerun()
    with col2:
        if st.button("🔄 股價反彈/回檔計算"):
            st.session_state.current_page = "股價計算"
            st.rerun()
    with col3:
        if st.button("🧾 25型發票資料掃瞄"):
            st.session_state.current_page = "發票掃瞄"
            st.rerun()

# 頁面切換邏輯
elif st.session_state.current_page == "價值投資":
    st.title("📈 即時價值投資股掃描")
    # 這裡放入你的投資掃描程式碼...
    if st.button("⬅️ 返回首頁"):
        st.session_state.current_page = "首頁"
        st.rerun()

elif st.session_state.current_page == "股價計算":
    st.title("🔄 股價反彈/回檔計算")
    # 這裡放入你的計算機程式碼...
    if st.button("⬅️ 返回首頁"):
        st.session_state.current_page = "首頁"
        st.rerun()

elif st.session_state.current_page == "發票掃瞄":
    st.title("🧾 25型發票資料掃瞄")
    # 這裡放入原本的發票辨識程式碼...
    if st.button("⬅️ 返回首頁"):
        st.session_state.current_page = "首頁"
        st.rerun()