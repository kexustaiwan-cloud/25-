import streamlit as st
from PIL import Image
import easyocr
import numpy as np
import pdf2image  # 新增 PDF 轉換工具

# 設定網頁標題與圖示
st.set_page_config(page_title="發票 OCR 辨識系統", page_icon="🧾")

st.title("🧾 發票/收據文字辨識系統")
st.write("請上傳您的發票掃描檔、照片或 PDF 檔，系統將自動解析文字內容。")

# 建立上傳檔案的區塊（新增 pdf 支援）
uploaded_file = st.file_uploader("請選擇發票圖片或 PDF (支援 JPG, JPEG, PNG, PDF)", type=["jpg", "jpeg", "png", "pdf"])

if uploaded_file is not None:
    image = None
    
    # 判斷是否為 PDF
    if uploaded_file.name.lower().endswith('.pdf'):
        with st.spinner("⏳ 正在將 PDF 轉為圖片..."):
            try:
                # 讀取 PDF 並將第一頁轉成圖片
                pdf_bytes = uploaded_file.read()
                images = pdf2image.convert_from_bytes(pdf_bytes)
                if images:
                    image = images[0]  # 取第一頁
                else:
                    st.error("無法讀取該 PDF 檔案。")
            except Exception as e:
                st.error(f"PDF 轉換失敗，可能需要安裝系統環境 (poppler)：{e}")
    else:
        # 一般圖片直接讀取
        image = Image.open(uploaded_file)
    
    # 開始辨識
    if image is not None:
        st.image(image, caption='📷 待辨識的發票畫面', use_container_width=True)
        
        with st.spinner("⏳ 正在辨識發票內容，請稍候..."):
            try:
                # 初始化 OCR 辨識引擎
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
                    if confidence > 0.2:
                        extracted_text.append(text)
                        st.write(f"- {text}")
                        
                # 提供一鍵複製功能
                full_text = "\n".join(extracted_text)
                st.text_area("您可以複製下方文字：", value=full_text, height=200)
                
            except Exception as e:
                st.error(f"辨識過程中發生錯誤：{e}")