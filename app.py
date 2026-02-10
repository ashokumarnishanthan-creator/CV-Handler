import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="TalentScan Pro", layout="wide", page_icon="🔍")

# Professional UI Styling
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stMetricValue"] { font-size: 1.8rem; color: #1e40af; }
    .main-header { font-size: 2.5rem; font-weight: 800; color: #1e293b; margin-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. AUTHENTICATION & SECRETS ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1055/1055644.png", width=80)
    st.title("Control Panel")
    
    # Priority: 1. Sidebar Input, 2. Streamlit Secrets
    api_key_input = st.text_input("Gemini API Key", type="password")
    gemini_key = api_key_input if api_key_input else st.secrets.get("GEMINI_API_KEY", "")
    
    st.divider()
    st.markdown("### ⚙️ Engine")
    st.info("Model: **Gemini 2.0 Flash**\n\nRate Limit: 15 RPM (Free) / 2000 RPM (Paid)")

# --- 3. UI TABS ---
st.markdown('<div class="main-header">🚀 AI Recruitment Dashboard</div>', unsafe_allow_html=True)
jd_tab, analysis_tab = st.tabs(["📌 Job Requirement", "📊 Candidate Ranking"])

with jd_tab:
    st.subheader("Define the Ideal Candidate")
    jd_input = st.text_area("Paste the Job Description (JD) here:", height=300, 
                            placeholder="e.g. Seeking a Python Developer with 3 years experience...")

with analysis_tab:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Source Materials")
        uploaded_files = st.file_uploader("Upload CVs (PDF Only)", accept_multiple_files=True, type=['pdf'])
    
    with col2:
        st.subheader("Cloud Integration")
        st.write("To analyze Google Drive files, ensure your Drive is synced to your PC or use the local uploader.")
        if st.button("📁 Folder Sync Instructions"):
            st.info("Best practice: Open your local Google Drive folder in the uploader to avoid API permission errors.")

    # --- 4. CORE PROCESSING LOGIC ---
    if st.button("⚡ Start AI Shortlisting"):
        if not gemini_key:
            st.error("Missing Gemini API Key! Please enter it in the sidebar.")
        elif not jd_input:
            st.warning("Please provide a Job Description.")
        elif not uploaded_files:
            st.warning("Please upload at least one CV.")
        else:
            # Configure API
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(
                model_name='gemini-2.0-flash',
                generation_config={"response_mime_type": "application/json"}
            )
            
            final_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, file in enumerate(uploaded_files):
                # UI Update
