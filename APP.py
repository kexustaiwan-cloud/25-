import streamlit as st
from PIL import Image
import easyocr
import numpy as np

# 設定網頁標題與圖示
st.set_page_config(page_title="發票 OCR 辨識系統", page_icon="🧾")

st.title("🧾 發票/收據文字辨識系統")
st.write("請上傳您的發票掃描檔或照片，系統將自動解析文字內容。")

# 建立上傳檔案的區塊
uploaded_file = st.file_uploader("請選擇發票圖片 (支援 JPG, JPEG, PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # 顯示上傳的圖片
    image = Image.open(uploaded_file)
    st.image(image, caption='📷 已上傳的發票圖片', use_container_width=True)
    
    with st.spinner("⏳ 正在辨識發票內容，請稍候..."):
        try:
            # 初始化 OCR 辨識引擎（設定支援繁體中文 'ch_tra' 與英文 'en'）
            reader = easyocr.Reader(['ch_tra', 'en'], gpu=False)
            
            # 將圖片轉為 numpy 陣列供 easyocr 讀取
            img_np = np.array(image)
            
            # 進行文字辨識
            results = reader.readtext(img_np)
            
            st.success("🎉 辨識完成！")
            st.subheader("📋 擷取到的發票文字：")
            
            # 格式化輸出辨識到的文字
            extracted_text = []
            for line in results:
                text = line[1]
                confidence = line[2]
                # 只有辨識信心度大於 20% 才顯示，避免雜訊
                if confidence > 0.2:
                    extracted_text.append(text)
                    st.write(f"- {text}")
                    
            # 提供一鍵複製功能
            full_text = "\n".join(extracted_text)
            st.text_area("您可以複製下方文字：", value=full_text, height=200)
            
        except Exception as e:
            st.error(f"辨識過程中發生錯誤：{e}")