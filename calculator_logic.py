import streamlit as st

# 常用的黃金切割率參考比例（0.618 為主要計算依據）
FIB_RATIOS = [0.191, 0.382, 0.5, 0.618, 0.809]


def run():

    st.caption("依據上一波高低點，計算高檔拉回的支撐價位，或低檔反彈的壓力價位。")

    tab1, tab2 = st.tabs(["📉 回檔計算（高檔拉回）", "📈 反彈計算（低檔反彈）"])

    # ---------------- 回檔計算 ----------------
    with tab1:
      

        col1, col2 = st.columns(2)
        with col1:
            high_price = st.number_input(
                "上一個高點價位", min_value=0.0, value=100.0, step=0.05,
                format="%.2f", key="retrace_high"
            )
        with col2:
            low_price = st.number_input(
                "目前低點價位", min_value=0.0, value=80.0, step=0.05,
                format="%.2f", key="retrace_low"
            )

        if high_price <= low_price:
            st.warning("⚠️ 高點價位必須大於低點價位，請重新輸入。")
        else:
            diff = high_price - low_price
            main_price = high_price - diff * 0.618

            st.success(f"🎯 主要回檔價位（0.618）：**{main_price:.2f}**")

            data = [
                {
                    "回檔比例": f"{r:.3f}",
                    "回檔價位": round(high_price - diff * r, 2),
                }
                for r in FIB_RATIOS
            ]
            st.table(data)

    # ---------------- 反彈計算 ----------------
    with tab2:


        col3, col4 = st.columns(2)
        with col3:
            low_price2 = st.number_input(
                "上一個低點價位", min_value=0.0, value=80.0, step=0.05,
                format="%.2f", key="rebound_low"
            )
        with col4:
            high_price2 = st.number_input(
                "目前高點價位", min_value=0.0, value=100.0, step=0.05,
                format="%.2f", key="rebound_high"
            )

        if high_price2 <= low_price2:
            st.warning("⚠️ 高點價位必須大於低點價位，請重新輸入。")
        else:
            diff2 = high_price2 - low_price2
            main_price2 = low_price2 + diff2 * 0.618

            st.success(f"🎯 主要反彈價位（0.618）：**{main_price2:.2f}**")

            data2 = [
                {
                    "反彈比例": f"{r:.3f}",
                    "反彈價位": round(low_price2 + diff2 * r, 2),
                }
                for r in FIB_RATIOS
            ]
            st.table(data2)
