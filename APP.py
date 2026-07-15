import streamlit as st
from google.cloud import vision
from google.oauth2 import service_account
from PIL import Image
import io
import re
import pandas as pd
import pdf2image

# 設定網頁標題
st.set_page_config(page_title="Ethan's 發票辨識系統", page_icon="🧾", layout="wide")
st.title("🧾 Ethan's 發票辨識系統")
st.write("利用 Google Cloud Vision API 進行超精準 OCR 解析，並自動分類發票資訊！")

# 1. 初始化 Google Vision 客戶端
@st.cache_resource
def get_vision_client():
    try:
        info = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(info)
        return vision.ImageAnnotatorClient(credentials=credentials)
    except Exception as e:
        st.error(f"⚠️ Google 憑證載入失敗，請確認 Streamlit Secrets 設定。錯誤資訊：{e}")
        return None

client = get_vision_client()

# 2. 自動萃取/解析發票欄位的函數 (Regex 規則)
def parse_invoice_text(text):
    # 初始化資料字典
    data = {
        "發票字母": "未知",
        "發票號碼": "未知",
        "賣方統編": "未知",
        "總金額": "未知",
        "日期": "未知"
    }
    
    # a. 尋找發票號碼與字母 (格式如: BJ-05380109 或 AY-90253355)
    invoice_pattern = re.search(r'([A-Z]{2})-?([0-9]{8})', text)
    if invoice_pattern:
        data["發票字母"] = invoice_pattern.group(1)
        data["發票號碼"] = invoice_pattern.group(2)
        
    # b. 尋找賣方統編 (格式如 賣方:85746748)
    tax_pattern = re.search(r'賣方\s*:\s*([0-9]{8})', text)
    if tax_pattern:
        data["賣方統編"] = tax_pattern.group(1)
    else:
        # 備用：若沒有「賣方:」，直接尋找發票常見統編格式
        all_tax_ids = re.findall(r'\b[0-9]{8}\b', text)
        for tax_id in all_tax_ids:
            if tax_id != data.get("發票號碼"): # 排除發票號碼
                data["賣方統編"] = tax_id
                break
                
    # c. 尋找總金額 (格式如 總計:30, 總計:$20, 總計 : 20, 總 計:$30)
    # 用 Regex 抓取總計或總額後方的數字
    amount_pattern = re.search(r'(?:總計|總計\s*:\s*|總額|總\s*計\s*:\s*)\$?([0-9,]+)', text)
    if amount_pattern:
        data["總金額"] = amount_pattern.group(1).replace(",", "")
        
    # d. 尋找日期 (格式如 2026-05-12 或 2026/05/12)
    date_pattern = re.search(r'(\d{4})[-/](\d{2})[-/](\d{2})', text)
    if date_pattern:
        data["日期"] = f"{date_pattern.group(1)}-{date_pattern.group(2)}-{date_pattern.group(3)}"
        
    return data

# 3. 檔案上傳
uploaded_file = st.file_uploader("請上傳發票/收據圖片或 PDF", type=["jpg", "jpeg", "png", "pdf"])

if uploaded_file is not None and client is not None:
    image_bytes = None
    display_image = None
    
    # 處理 PDF
    if uploaded_file.name.lower().endswith('.pdf'):
        with st.spinner("⏳ 正在轉換 PDF 第一頁..."):
            try:
                pdf_data = uploaded_file.read()
                images = pdf2image.convert_from_bytes(pdf_data)
                if images:
                    display_image = images[0]
                    img_byte_arr = io.BytesIO()
                    display_image.save(img_byte_arr, format='JPEG')
                    image_bytes = img_byte_arr.getvalue()
            except Exception as e:
                st.error(f"PDF 處理失敗: {e}")
    else:
        # 處理一般圖片
        image_bytes = uploaded_file.read()
        display_image = Image.open(io.BytesIO(image_bytes))

    # 執行辨識
    if image_bytes is not None and display_image is not None:
        
        # 建立左右兩欄，左邊放發票圖，右邊放表格
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.image(display_image, caption="📷 上傳的發票畫面", use_container_width=True)
        
        with col2:
            with st.spinner("🔮 Google OCR 正在精準分析文字..."):
                try:
                    vision_image = vision.Image(content=image_bytes)
                    response = client.text_detection(image=vision_image)
                    texts = response.text_annotations
                    
                    if response.error.message:
                        st.error(f"Google Vision API 錯誤: {response.error.message}")
                    elif not texts:
                        st.warning("⚠️ 無法從圖片中辨識出任何文字，請確認發票是否清晰。")
                    else:
                        st.success("🎉 Google OCR 辨識成功！")
                        full_text = texts[0].description
                        
                        # --- 【關鍵部分】自動解析混亂的文字 ---
                        parsed_data = parse_invoice_text(full_text)
                        parsed_data["檔案名稱"] = uploaded_file.name
                        
                        # 整理成 Pandas DataFrame
                        df = pd.DataFrame([parsed_data])
                        # 重新排列欄位順序，貼近您的截圖樣式
                        df = df[["檔案名稱", "發票字母", "發票號碼", "賣方統編", "總金額", "日期"]]
                        
                        st.subheader("📊 發票欄位自動整理結果：")
                        # 以表格方式呈現
                        st.dataframe(df, use_container_width=True)
                        
                        # 額外提供下載為 Excel/CSV 按鈕
                        csv = df.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📥 下載為 CSV 檔",
                            data=csv,
                            file_name="發票辨識結果.csv",
                            mime="text/csv",
                        )
                        
                        # 下方保留原始辨識文字對照
                        with st.expander("🔍 檢視原始 Google OCR 辨識結果"):
                            st.text_area("原始發票文字內容：", value=full_text, height=250)
                        
                except Exception as e:
                    st.error(f"辨識過程中發生錯誤: {e}")