import streamlit as st
import os
import json
from google.oauth2 import service_account
from google.cloud import vision
import pandas as pd

def run():
    # 這是原本的程式碼，全部縮排在 run() 裡面
    st.title("🧾 25型發票資料辨識系統")
    st.subheader("如有問題可發送信件至 KexusTaiwan@gmail.com")

    # 1. 憑證載入機制
    def get_google_client():
        try:
            creds_json_str = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
            if not creds_json_str:
                raise ValueError("找不到環境變數 GOOGLE_APPLICATION_CREDENTIALS_JSON")
            creds_dict = json.loads(creds_json_str)
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