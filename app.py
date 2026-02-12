import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time
import re
from io import BytesIO
from streamlit_google_picker import google_picker
from streamlit_oauth import OAuth2Component
from streamlit_pdf_viewer import pdf_viewer

# --- 1. SETTINGS & UI STYLING ---
st.set_page_config(page_title="TalentScan Pro", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1e293b; margin-bottom: 20px; }
    .source-card { 
        background: white; border-radius: 12px; padding: 20px; 
        border: 1px solid #e2e8f0; text-align: center; height: 200px;
    }
    .preview-container { border: 1px solid #e2e8f0; border-radius: 12px; background: white; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

# Initialize Session States
if 'cv_sources' not in st.session_state: st.session_state.cv_sources = []
if 'token' not in st.session_state: st.session_state.token = None
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = None

# --- 2. AUTHENTICATION (GOOGLE & GEMINI) ---
try:
    CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError as e:
    st.error(f"Missing Secret: {e}. Please add all keys to Streamlit Secrets.")
    st.stop()

# OAuth Setup
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/drive.readonly"
oauth2 = OAuth2Component(CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL, TOKEN_URL, SCOPE)

# --- 3. SIDEBAR CONTROLS ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3858/3858684.png", width=60)
    st.title("TalentScan Control")
    
    if not st.session_state.token:
        result = oauth2.authorize_button(
            name="Login with Google",
            icon="https://www.google.com/favicon.ico",
            redirect_uri="https://share.streamlit.io/oauth2callback",
            scope=SCOPE, key="google_auth"
        )
        if result and 'token' in result:
            st.session_state.token = result['token']
            st.rerun()
    else:
        st.success("✅ Connected")
        if st.button("Logout & Reset"):
            st.session_state.token = None
            st.session_state.cv_sources = []
            st.session_state.analysis_results = None
            st.rerun()

# --- 4. MAIN INTERFACE ---
st.markdown('<div class="main-header">🚀 AI Talent Scout Dashboard</div>', unsafe_allow_html=True)

tab_jd, tab_cv = st.tabs(["📋 Step 1: Job Description", "📄 Step 2: Source & Analyze"])

with tab_jd:
    jd_input = st.text_area("Paste Requirements", height=250, placeholder="Requirements, Skills, Qualifications...")

with tab_cv:
    col_u, col_g = st.columns(2)
    
    with col_u:
        st.markdown('<div class="source-card">', unsafe_allow_html=True)
        st.markdown("### 📤 Local Upload")
        local_files = st.file_uploader("PDFs", accept_multiple_files=True, type=['pdf'], label_visibility="collapsed")
        if local_files:
            for f in local_files:
                if not any(cv['name'] == f.name for cv in st.session_state.cv_sources):
                    st.session_state.cv_sources.append({"name": f.name, "content": f.read()})
        st.markdown('</div>', unsafe_allow_html=True)

    with col_g:
        st.markdown('<div class="source-card">', unsafe_allow_html=True)
        st.markdown("### ☁️ Google Drive")
        if st.session_state.token:
            # Modern Drive Icon
            st.markdown('<img src="https://cdn-icons-png.flaticon.com/512/2965/2965306.png" width="40">', unsafe_allow_html=True)
            picked_files = google_picker(
                apiKey=API_KEY, token=st.session_state.token.get("access_token"),
                appId=CLIENT_ID.split("-")[0], multiselect=True, type=["pdf"], key="drive_picker"
            )
            if picked_files:
                for pf in picked_files:
                    if not any(cv['name'] == pf['name'] for cv in st.session_state.cv_sources):
                        st.session_state.cv_sources.append({"name": pf['name'], "content": pf['content']})
                st.toast("Files added from Google Drive!")
        else:
            st.info("Login via Sidebar to enable Drive")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- PROCESSING ---
    st.write(f"📂 **Current Queue:** {len(st.session_state.cv_sources)} files.")
    
    if st.button("⚡ Run AI Analysis", type="primary", use_container_width=True):
        if not jd_input or not st.session_state.cv_sources:
            st.warning("Please provide JD and CVs.")
        else:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
            
            temp_results = []
            progress = st.progress(0)
            status = st.empty()

            for idx, cv in enumerate(st.session_state.cv_sources):
                status.info(f"Analyzing: {cv['name']}...")
                try:
                    reader = PdfReader(BytesIO(cv['content']))
                    text = " ".join([p.extract_text() for p in reader.pages[:2] if p.extract_text()])
                    
                    prompt = f"Analyze CV for JD. Return JSON: {{'name':'str', 'score':int, 'reasoning':'str'}}. JD: {jd_input} CV: {text}"
                    response = model.generate_content(prompt)
                    data = json.loads(response.text)
                    if isinstance(data, list): data = data[0]

                    # Extract score safely
                    score_raw = data.get("score", 0)
                    score_clean = int(re.search(r'\d+', str(score_raw)).group()) if re.search(r'\d+', str(score_raw)) else 0

                    temp_results.append({
                        "Name": data.get("name", cv['name']),
                        "Score": score_clean,
                        "Evaluation": data.get("reasoning", "No summary.")
                    })
                    time.sleep(1.2)
                except Exception as e:
                    st.error(f"Error on {cv['name']}: {str(e)}")
                progress.progress((idx + 1) / len(st.session_state.cv_sources))

            st.session_state.analysis_results = temp_results
            status.empty()
            st.rerun()

# --- 5. RESULTS & SIDE-BY-SIDE PREVIEW ---
if st.session_state.analysis_results:
    st.divider()
    df = pd.DataFrame(st.session_state.analysis_results).sort_values(by="Score", ascending=False)
    
    col_table, col_viewer = st.columns([0.6, 0.4])

    with col_table:
        st.subheader("📊 Ranking Results")
        
        # Selectbox to control the PDF viewer
        selected_candidate = st.selectbox(
            "Select a candidate to view their CV:",
            options=df['Name'].tolist()
        )

        st.dataframe(
            df, use_container_width=True, hide_index=True,
            column_config={
                "Score": st.column_config.ProgressColumn("Match %", min_value=0, max_value=100, format="%d%%"),
                "Evaluation": st.column_config.TextColumn("AI Insight", width="large")
            }
        )
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Shortlist", data=csv, file_name="ai_shortlist.csv")

    with col_viewer:
        st.subheader("📄 Document Viewer")
        # Find bytes for the selected candidate in session state
        viewer_data = next((item for item in st.session_state.cv_sources if item["name"] == selected_candidate), None)
        
        if viewer_data:
            st.markdown(f"**Viewing:** {selected_candidate}")
            with st.container(height=600):
                pdf_viewer(viewer_data["content"])
        else:
            st.info("Select a candidate to load preview.")
