import streamlit as st
from google.cloud import vision
from google.oauth2 import service_account
from PIL import Image
import io
import re
import pandas as pd
import pdf2image

# 設定網頁標題與版面
st.set_page_config(page_title="Ethan's 發票辨識系統", page_icon="🧾", layout="wide")
st.title("🧾 Ethan's 發票辨識系統")
st.write("利用 Google Cloud Vision API 進行超精準 OCR 解析，並自動分類多張發票資訊！")

# 1. 初始化 Google Vision 客戶端 (從 Streamlit 後台 Secrets 安全讀取)
@st.cache_resource
def get_vision_client():
    try:
        # 將 secrets 轉為 dict 格式傳給 Google 憑證庫
        info = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(info)
        return vision.ImageAnnotatorClient(credentials=credentials)
    except Exception as e:
        st.error(f"⚠️ Google 憑證載入失敗，請確認 Streamlit Secrets 設定。錯誤資訊：{e}")
        return None

client = get_vision_client()

# 2. 進階多發票區段解析器 (Regex 規則)
def parse_all_invoices(text):
    # 尋找所有發票號碼的位置 (例如 BJ-05380109 或 AY-90253355)
    matches = list(re.finditer(r'([A-Z]{2})-?([0-9]{8})', text))
    if not matches:
        return []
    
    invoices = []
    for i, match in enumerate(matches):
        start_idx = match.start()
        # 下一條發票的起點，或是整段文字的終點
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(text)
        
        # 往前多看 150 個字元，防止賣方統編或公司名稱寫在發票號碼上方
        lookback = max(0, start_idx - 150)
        segment = text[lookback:end_idx]
        
        # 提取發票號碼
        inv_letter = match.group(1)
        inv_num = match.group(2)
        
        # a. 尋找賣方統編 (優先找「賣方: 8碼」，其次找該區段內非發票號碼的8碼數字)
        tax_id = "未知"
        tax_match = re.search(r'賣方\s*[:：]?\s*([0-9]{8})', segment)
        if tax_match:
            tax_id = tax_match.group(1)
        else:
            all_8_digits = re.findall(r'\b[0-9]{8}\b', segment)
            for num in all_8_digits:
                if num != inv_num:
                    tax_id = num
                    break
        
        # b. 尋找總金額 (尋找 總計/總額/總計 後方的金額數字)
        amount = "未知"
        amount_match = re.search(r'(?:總計|總額|總\s*計|計)\s*[:：]?\s*\$?([0-9,]+)', segment)
        if amount_match:
            amount = amount_match.group(1).replace(",", "")
            
        # c. 尋找日期 (YYYY-MM-DD 或 YYYY/MM/DD)
        date_str = "未知"
        date_match = re.search(r'(\d{4})[-/](\d{2})[-/](\d{2})', segment)
        if date_match:
            date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
            
        invoices.append({
            "發票字母": inv_letter,
            "發票號碼": inv_num,
            "賣方統編": tax_id,
            "總金額": amount,
            "日期": date_str
        })
        
    return invoices

# 3. 檔案上傳
uploaded_file = st.file_uploader("請上傳發票/收據圖片或 PDF", type=["jpg", "jpeg", "png", "pdf"])

if uploaded_file is not None and client is not None:
    # 用來存放每一頁要送給 Google 的圖片 Bytes
    pages_to_process = []
    
    # 處理 PDF (將每一頁都轉成圖片)
    if uploaded_file.name.lower().endswith('.pdf'):
        with st.spinner("⏳ 正在轉換 PDF 所有頁面..."):
            try:
                pdf_data = uploaded_file.read()
                images = pdf2image.convert_from_bytes(pdf_data)
                for img in images:
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='JPEG')
                    pages_to_process.append(img_byte_arr.getvalue())
            except Exception as e:
                st.error(f"PDF 處理失敗: {e}")
    else:
        # 處理單張圖片
        image_bytes = uploaded_file.read()
        pages_to_process.append(image_bytes)

    # 執行 OCR 辨識
    if pages_to_process:
        all_results = []
        raw_texts = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 逐頁發送給 Google OCR
        for idx, page_bytes in enumerate(pages_to_process):
            status_text.text(f"🔮 正在使用 Google OCR 辨識第 {idx + 1} / {len(pages_to_process)} 頁...")
            progress_bar.progress((idx + 1) / len(pages_to_process))
            
            try:
                vision_image = vision.Image(content=page_bytes)
                response = client.text_detection(image=vision_image)
                texts = response.text_annotations
                
                if response.error.message:
                    st.error(f"Google Vision API 錯誤: {response.error.message}")
                elif texts:
                    full_text = texts[0].description
                    raw_texts.append(f"--- 第 {idx + 1} 頁原始文字 ---\n{full_text}")
                    
                    # 解析該頁的所有發票
                    page_invoices = parse_all_invoices(full_text)
                    for inv in page_invoices:
                        # 標註來源頁數
                        inv["檔案名稱"] = f"{uploaded_file.name} (第 {idx + 1} 頁)" if len(pages_to_process) > 1 else uploaded_file.name
                        all_results.append(inv)
                        
            except Exception as e:
                st.error(f"第 {idx + 1} 頁辨識發生錯誤: {e}")
                
        status_text.text("🎉 辨識與整理完成！")
        progress_bar.empty()
        
        # 4. 顯示與輸出結果
        if all_results:
            st.success(f"成功在您的檔案中偵測到 {len(all_results)} 張發票！")
            
            # 轉換為 DataFrame 顯示
            df = pd.DataFrame(all_results)
            df = df[["檔案名稱", "發票字母", "發票號碼", "賣方統編", "總金額", "日期"]]
            
            # 將表格索引（Index）從 1 開始計算，不要從 0 開始
            df.index = df.index + 1
            
            # 展示表格
            st.subheader("📊 發票欄位自動整理結果：")
            st.dataframe(df, use_container_width=True)
            
            # 提供 CSV 下載 (設定 index=True 且將 index 命名為 "項次" 一併匯出)
            df.index.name = "項次"
            csv = df.to_csv(index=True).encode('utf-8-sig')
            st.download_button(
                label="📥 下載為 Excel/CSV 檔案",
                data=csv,
                file_name="Ethan_發票多筆辨識結果.csv",
                mime="text/csv",
            )
        else:
            st.warning("⚠️ 沒能成功解析出任何發票，請確認檔案格式是否清晰。")
            
        # 原始文字折疊區
        with st.expander("🔍 檢視原始 Google OCR 各頁辨識文字"):
            for rt in raw_texts:
                st.text_area("", value=rt, height=200, key=rt[:30])