import streamlit as st
import os
import json
from google.oauth2 import service_account
from google.cloud import vision
import pandas as pd

st.set_page_config(page_title="Ethan's 發票辨識系統", layout="wide")

st.title("🧾 25型發票資料辨識系統")
st.subheader("如有問題可發送信件至 KexusTaiwan@gmail.com")

# 1. 憑證載入機制 (改為讀取環境變數)
def get_google_client():
    try:
        # 從 Render 的環境變數中讀取 JSON 字串
        creds_json_str = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        
        if not creds_json_str:
            raise ValueError("找不到環境變數 GOOGLE_APPLICATION_CREDENTIALS_JSON")
        
        # 將 JSON 字串轉回字典
        creds_dict = json.loads(creds_json_str)
        
        # 建立憑證物件
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        return vision.ImageAnnotatorClient(credentials=credentials)
    except Exception as e:
        st.error(f"⚠️ Google 憑證載入失敗：{e}")
        st.stop()

client = get_google_client()

uploaded_files = st.file_uploader("請選擇要上傳的發票圖片 (支援多張上傳)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if uploaded_files:
    st.write(f"已成功載入 {len(uploaded_files)} 張發票，準備進行辨識...")
    
    for uploaded_file in uploaded_files:
        st.image(uploaded_file, caption=uploaded_file.name, width=300)
        # 這裡放入你原本的發票辨識處理邏輯...