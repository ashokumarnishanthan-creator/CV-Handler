import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time
import re
import base64
from io import BytesIO
from streamlit_google_picker import google_picker
from streamlit_oauth import OAuth2Component

# --- 1. SETTINGS & UI STYLING ---
st.set_page_config(page_title="TalentScan Pro", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1e293b; margin-bottom: 20px; }
    .source-card { 
        background: white; border-radius: 12px; padding: 20px; 
        border: 1px solid #e2e8f0; text-align: center; height: 180px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    iframe { border-radius: 10px; border: 1px solid #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

# Helper function for PDF Display
def display_pdf_native(bytes_data):
    """Converts PDF bytes to a base64 string and embeds it in an iframe."""
    base64_pdf = base64.b64encode(bytes_data).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

# Session State Init
if 'cv_sources' not in st.session_state: st.session_state.cv_sources = []
if 'token' not in st.session_state: st.session_state.token = None
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = None

# --- 2. AUTHENTICATION ---
try:
    CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError as e:
    st.error(f"Missing Secret: {e}. Please update Streamlit Secrets.")
    st.stop()

oauth2 = OAuth2Component(CLIENT_ID, CLIENT_SECRET, 
                         "https://accounts.google.com/o/oauth2/v2/auth", 
                         "https://oauth2.googleapis.com/token", 
                         "https://oauth2.googleapis.com/token", 
                         "https://www.googleapis.com/auth/drive.readonly")

# --- 3. SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3858/3858684.png", width=60)
    st.title("TalentScan Control")
    if not st.session_state.token:
        result = oauth2.authorize_button("Login with Google", "https://www.google.com/favicon.ico",
                                         "https://share.streamlit.io/oauth2callback", 
                                         "https://www.googleapis.com/auth/drive.readonly", key="google_auth")
        if result and 'token' in result:
            st.session_state.token = result['token']; st.rerun()
    else:
        st.success("Connected to Google")
        if st.button("Reset Session"):
            st.session_state.token = None; st.session_state.cv_sources = []; st.session_state.analysis_results = None; st.rerun()

# --- 4. MAIN UI ---
st.markdown('<div class="main-header">🚀 AI Recruitment Dashboard</div>', unsafe_allow_html=True)
t1, t2 = st.tabs(["📌 Requirements", "📊 Analysis & Preview"])

with t1:
    jd_input = st.text_area("Job Description", height=250, placeholder="Requirements...")

with t2:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="source-card">### 📤 Local</div>', unsafe_allow_html=True)
        local_files = st.file_uploader("Upload", accept_multiple_files=True, type=['pdf'], label_visibility="collapsed")
        if local_files:
            for f in local_files:
                if not any(cv['name'] == f.name for cv in st.session_state.cv_sources):
                    st.session_state.cv_sources.append({"name": f.name, "content": f.read()})
    with c2:
        st.markdown('<div class="source-card">### ☁️ Drive</div>', unsafe_allow_html=True)
        if st.session_state.token:
            picked = google_picker(API_KEY, st.session_state.token.get("access_token"), CLIENT_ID.split("-")[0], True, ["pdf"], "dr_picker")
            if picked:
                for pf in picked:
                    if not any(cv['name'] == pf['name'] for cv in st.session_state.cv_sources):
                        st.session_state.cv_sources.append({"name": pf['name'], "content": pf['content']})
                st.toast("Drive files added!")
        else: st.info("Login via sidebar for Drive access")

    if st.button("⚡ Run AI Analysis", type="primary", use_container_width=True):
        if jd_input and st.session_state.cv_sources:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
            results = []
            prog = st.progress(0)
            for idx, cv in enumerate(st.session_state.cv_sources):
                try:
                    reader = PdfReader(BytesIO(cv['content']))
                    text = " ".join([p.extract_text() for p in reader.pages[:2] if p.extract_text()])
                    resp = model.generate_content(f"Analyze CV for JD. JSON: {{'name','score','reason'}}. JD: {jd_input} CV: {text}")
                    data = json.loads(resp.text)
                    if isinstance(data, list): data = data[0]
                    score = int(re.search(r'\d+', str(data.get('score', 0))).group()) if re.search(r'\d+', str(data.get('score', 0))) else 0
                    results.append({"Name": data.get('name', cv['name']), "Score": score, "Insight": data.get('reason', 'N/A')})
                    time.sleep(1.2)
                except Exception as e: st.error(f"Error {cv['name']}: {e}")
                prog.progress((idx + 1) / len(st.session_state.cv_sources))
            st.session_state.analysis_results = results; st.rerun()

# --- 5. RESULTS & PREVIEW (NATIVE IFRAME) ---
if st.session_state.analysis_results:
    st.divider()
    df = pd.DataFrame(st.session_state.analysis_results).sort_values(by="Score", ascending=False)
    col_t, col_v = st.columns([0.55, 0.45])
    
    with col_t:
        st.subheader("📊 Ranking")
        sel_name = st.selectbox("Preview Candidate:", options=df['Name'].tolist())
        st.dataframe(df, use_container_width=True, hide_index=True, column_config={
            "Score": st.column_config.ProgressColumn("Match", min_value=0, max_value=100, format="%d%%"),
            "Insight": st.column_config.TextColumn("AI Evaluation", width="large")
        })
        st.download_button("📥 Download Results", df.to_csv(index=False), "shortlist.csv")

    with col_v:
        st.subheader("📄 Document Preview")
        viewer_data = next((item for item in st.session_state.cv_sources if item["name"] == sel_name), None)
        if viewer_data:
            display_pdf_native(viewer_data["content"])
