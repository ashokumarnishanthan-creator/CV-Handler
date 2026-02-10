import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time
from io import BytesIO
from streamlit_google_picker import google_picker

# --- CONFIG ---
st.set_page_config(page_title="TalentScan Pro", layout="wide")

# --- AUTH & KEYS ---
gemini_key = st.sidebar.text_input("Gemini API Key", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
g_api_key = st.secrets.get("GOOGLE_API_KEY", "")
g_client_id = st.secrets.get("GOOGLE_CLIENT_ID", "")

# --- UI ---
st.title("🚀 AI CV Shortlister")
jd_input = st.text_area("Paste Job Description:")
uploaded_files = st.file_uploader("Upload CVs", accept_multiple_files=True, type=['pdf'])

# --- LOGIC ---
if st.button("Start Analysis") and jd_input and uploaded_files:
    if not gemini_key:
        st.error("Enter API Key")
    else:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
        
        final_results = []
        # We use a placeholder to avoid refreshing the whole screen too often
        status = st.empty()
        
        for i, file in enumerate(uploaded_files):
            try:
                # 1. READ BYTES SAFELY
                content = file.read()
                pdf_file = BytesIO(content)
                reader = PdfReader(pdf_file)
                
                # Limit text to avoid Server Timeout
                text = " ".join([p.extract_text() for p in reader.pages[:2] if p.extract_text()])
                
                # 2. CALL AI
                prompt = f"Rank CV for JD. JSON: {{'name','score','verdict'}}. JD: {jd_input} CV: {text}"
                response = model.generate_content(prompt)
                
                # 3. PARSE
                if response.text:
                    res = json.loads(response.text)
                    if isinstance(res, list): res = res[0]
                    final_results.append(res)
                
                # 4. SLEEP TO PREVENT 429 & SERVER STALL
                time.sleep(2)
                
            except Exception as e:
                st.error(f"Error on {file.name}: {e}")

        if final_results:
            df = pd.DataFrame(final_results)
            st.dataframe(df.sort_values(by="score", ascending=False))
