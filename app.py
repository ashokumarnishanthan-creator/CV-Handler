import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time
from streamlit_google_picker import google_picker

# --- 1. CONFIGURATION & UI STYLING ---
st.set_page_config(page_title="TalentScan Pro", layout="wide", page_icon="🔍")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main-header { font-size: 2.5rem; font-weight: 800; color: #1e293b; margin-bottom: 1rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: white; border-radius: 5px; padding: 10px 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SIDEBAR (SECURITY & KEYS) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1055/1055644.png", width=80)
    st.title("TalentScan Settings")
    
    # Priority: Secrets (Cloud) -> Manual Input (Local)
    gemini_key = st.text_input("Gemini API Key", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
    
    st.divider()
    st.markdown("### ☁️ Google Cloud Integration")
    g_api_key = st.secrets.get("GOOGLE_API_KEY", "")
    g_client_id = st.secrets.get("GOOGLE_CLIENT_ID", "")
    
    if not g_api_key or not g_client_id:
        st.warning("⚠️ Google Drive keys missing in Secrets.")
    else:
        st.success("✅ Google Drive APIs Connected")

# --- 3. MAIN DASHBOARD ---
st.markdown('<div class="main-header">🚀 AI Recruitment Dashboard</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📋 Job Requirements", "📊 CV Analysis"])

with tab1:
    jd_input = st.text_area("Paste Job Description:", height=300, placeholder="Requirements, Skills, etc.")

with tab2:
    col_u, col_g = st.columns([1, 1])
    
    all_cv_files = [] # This will hold both local and Drive files

    with col_u:
        local_files = st.file_uploader("Upload Local CVs", accept_multiple_files=True, type=['pdf'])
        if local_files:
            all_cv_files.extend(local_files)

    with col_g:
        st.write("---")
        if st.button("📁 Select from Google Drive"):
            if not g_api_key or not g_client_id:
                st.error("Configure Google API Key and Client ID in Streamlit Secrets first!")
            else:
                # Triggers the Google Picker Pop-up
                drive_files = google_picker(
                    apiKey=g_api_key,
                    clientId=g_client_id,
                    appId=g_client_id.split("-")[0],
                    multiselect=True,
                    types=["pdf"]
                )
                if drive_files:
                    all_cv_files.extend(drive_files)
                    st.success(f"Added {len(drive_files)} files from Drive")

    # --- 4. PROCESSING ENGINE ---
    if st.button("⚡ Start Analysis") and jd_input and all_cv_files:
        if not gemini_key:
            st.error("Please provide your Gemini API Key.")
        else:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(
                model_name='gemini-2.0-flash',
                generation_config={"response_mime_type": "application/json"}
            )
            
            final_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, file in enumerate(all_cv_files):
                # Handle both Streamlit UploadedFile and Picker File objects
                filename = getattr(file, 'name', file.get('name') if isinstance(file, dict) else "Unknown")
                status_text.text(f"Analyzing ({i+1}/{len(all_cv_files)}): {filename}")
                
                try:
                    # A. Read Content (Standardized for both sources)
                    content = file.read() if hasattr(file, 'read') else file.get('content')
                    reader = PdfReader(BytesIO(content))
                    cv_text = " ".join([page.extract_text() for page in reader.pages[:3] if page.extract_text()])
                    
                    # B. AI Analysis
                    prompt = f"Analyze CV for JD. Return JSON: {{'name','score','verdict'}}. JD: {jd_input} CV: {cv_text}"
                    response = model.generate_content(prompt)
                    
                    # C. Safe Parse & Enforce Schema
                    data = json.loads(response.text)
                    if isinstance(data, list): data = data[0] # Fixes 'list index' error
                    
                    # Standardize keys to lowercase
                    clean_data = {k.lower(): v for k, v in data.items()}
                    final_results.append({
                        "name": clean_data.get("name", filename),
                        "score": clean_data.get("score", 0),
                        "verdict": clean_data.get("verdict", "N/A")
                    })
                    
                    time.sleep(1.5) # Rate limit protection

                except Exception as e:
                    st.error(f"Failed {filename}: {str(e)}")
                
                progress_bar.progress((i + 1) / len(all_cv_files))

            # --- 5. RESULTS DISPLAY ---
            if final_results:
                df = pd.DataFrame(final_results)
                df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0)
                df = df.sort_values(by="score", ascending=False)
                
                st.subheader("🏆 Candidate Shortlist")
                st.dataframe(df, use_container_width=True, column_config={
                    "score": st.column_config.ProgressColumn("Match", min_value=0, max_value=100, format="%d%%")
                })
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Export Report", data=csv, file_name="ai_shortlist.csv")
