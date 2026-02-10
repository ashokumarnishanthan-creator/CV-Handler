import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time
from io import BytesIO
from streamlit_google_picker import google_picker
from streamlit_oauth import OAuth2Component

# --- 1. APP INITIALIZATION & UI ---
st.set_page_config(page_title="TalentScan Pro", layout="wide", page_icon="🎯")

# Modern SaaS Styling
st.markdown("""
    <style>
    .stApp { background-color: #fcfcfd; }
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1e293b; margin-bottom: 20px; }
    .source-card { 
        background: white; border-radius: 12px; padding: 20px; 
        border: 1px solid #e2e8f0; text-align: center; height: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# Session State for persisting data across re-runs
if 'cv_sources' not in st.session_state:
    st.session_state.cv_sources = []
if 'token' not in st.session_state:
    st.session_state.token = None

# --- 2. GOOGLE OAUTH 2.0 CONFIG ---
CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
API_KEY = st.secrets["GOOGLE_API_KEY"]
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/drive.readonly"

oauth2 = OAuth2Component(CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL, TOKEN_URL, SCOPE)

# --- 3. SIDEBAR (AUTH & SETTINGS) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3858/3858684.png", width=60)
    st.title("Settings")
    
    # AI Engine Key
    gemini_key = st.text_input("Gemini API Key", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
    
    st.divider()
    
    # OAuth Login Flow
    if not st.session_state.token:
        result = oauth2.authorize_button(
            name="Login with Google",
            icon="https://www.google.com/favicon.ico",
            redirect_uri="https://share.streamlit.io/oauth2callback",
            scope=SCOPE,
            key="google_auth"
        )
        if result and 'token' in result:
            st.session_state.token = result['token']
            st.rerun()
    else:
        st.success("Google Connected")
        if st.button("Logout"):
            st.session_state.token = None
            st.session_state.cv_sources = []
            st.rerun()

# --- 4. MAIN INTERFACE ---
st.markdown('<div class="main-header">🚀 AI Talent Scout</div>', unsafe_allow_html=True)

tab_jd, tab_cv = st.tabs(["📋 Step 1: Requirements", "📄 Step 2: Source CVs"])

with tab_jd:
    jd_input = st.text_area("Paste Job Description", height=250, placeholder="What skills are you looking for?")

with tab_cv:
    col_u, col_g = st.columns(2)
    
    with col_u:
        st.markdown('<div class="source-card">', unsafe_allow_html=True)
        st.markdown("### 📤 Local Upload")
        local_files = st.file_uploader("Upload PDFs", accept_multiple_files=True, type=['pdf'], label_visibility="collapsed")
        if local_files:
            for f in local_files:
                if not any(cv['name'] == f.name for cv in st.session_state.cv_sources):
                    st.session_state.cv_sources.append({"name": f.name, "content": f.read()})
        st.markdown('</div>', unsafe_allow_html=True)

    with col_g:
        st.markdown('<div class="source-card">', unsafe_allow_html=True)
        st.markdown("### ☁️ Google Drive")
        if st.session_state.token:
            # The Picker Component
            # 
            picked_files = google_picker(
                apiKey=API_KEY,
                token=st.session_state.token.get("access_token"),
                appId=CLIENT_ID.split("-")[0],
                multiselect=True,
                type=["pdf"],
                key="drive_picker"
            )
            if picked_files:
                for pf in picked_files:
                    if not any(cv['name'] == pf['name'] for cv in st.session_state.cv_sources):
                        st.session_state.cv_sources.append({"name": pf['name'], "content": pf['content']})
                st.toast("Files added from Drive!")
        else:
            st.info("Please 'Login with Google' in the sidebar to access Drive.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.write(f"📂 **Files in Queue:** {len(st.session_state.cv_sources)}")
    
    if st.button("⚡ Run AI Analysis", type="primary", use_container_width=True):
        if not gemini_key or not jd_input or not st.session_state.cv_sources:
            st.warning("Please ensure API Key, JD, and CVs are provided.")
        else:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
            
            final_report = []
            status = st.empty()
            progress = st.progress(0)

            for idx, cv in enumerate(st.session_state.cv_sources):
                status.info(f"Analyzing {cv['name']}...")
                try:
                    reader = PdfReader(BytesIO(cv['content']))
                    text = " ".join([p.extract_text() for p in reader.pages[:2] if p.extract_text()])
                    
                    prompt = f"Analyze CV for JD. JSON: {{'candidate_name','match_score','reasoning'}}. JD: {jd_input} CV: {text}"
                    response = model.generate_content(prompt)
                    
                    data = json.loads(response.text)
                    if isinstance(data, list): data = data[0]
                    
                    final_report.append({
                        "Name": data.get("candidate_name", cv['name']),
                        "Score": data.get("match_score", 0),
                        "Insight": data.get("reasoning", "N/A")
                    })
                    time.sleep(1.5) # Rate limit protection
                except Exception as e:
                    st.error(f"Error on {cv['name']}: {e}")
                
                progress.progress((idx + 1) / len(st.session_state.cv_sources))

            status.empty()
            if final_report:
                df = pd.DataFrame(final_report).sort_values(by="Score", ascending=False)
                st.subheader("📊 Ranking Results")
                st.dataframe(df, use_container_width=True, column_config={
                    "Score": st.column_config.ProgressColumn("Match %", min_value=0, max_value=100, format="%d")
                })
                
