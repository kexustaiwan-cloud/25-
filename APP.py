import streamlit as st
from google.cloud import vision
from google.oauth2 import service_account
from PIL import Image
import io
import pdf2image

# 設定網頁標題
st.set_page_config(page_title="Google OCR 發票辨識系統", page_icon="🧾")
st.title("🧾 Google OCR 發票辨識網頁版")
st.write("直接上傳發票，由網頁背景直接呼叫 Google 頂級 Vision API 進行高精準辨識！")

# 初始化 Google Vision 客户端 (從 Streamlit 後台 Secrets 安全讀取)
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

# 上傳檔案
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
        # 在網頁畫面上展示圖片
        st.image(display_image, caption="📷 上傳的發票畫面", use_container_width=True)
        
        with st.spinner("🔮 Google OCR 正在精準分析文字..."):
            try:
                # 呼叫 Google OCR API
                vision_image = vision.Image(content=image_bytes)
                response = client.text_detection(image=vision_image)
                texts = response.text_annotations
                
                if response.error.message:
                    st.error(f"Google Vision API 錯誤: {response.error.message}")
                elif not texts:
                    st.warning("⚠️ 無法從圖片中辨識出任何文字，請確認發票是否清晰。")
                else:
                    st.success("🎉 Google OCR 辨識成功！")
                    
                    # 取出完整辨識結果
                    full_text = texts[0].description
                    
                    st.subheader("📋 擷取文字結果：")
                    # 直接在網頁上顯示，使用者可以自由複製、修改
                    st.text_area("發票文字內容：", value=full_text, height=350)
                    
            except Exception as e:
                st.error(f"辨識過程中發生錯誤: {e}")