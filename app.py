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

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="TalentScan Pro v2", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main-header { font-size: 2.5rem; font-weight: 800; color: #1e293b; margin-bottom: 1rem; }
    .source-card { background: white; border-radius: 12px; padding: 20px; border: 1px solid #e2e8f0; height: 180px; text-align: center; }
    iframe { border-radius: 10px; border: 1px solid #cbd5e1; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
    </style>
    """, unsafe_allow_html=True)

# Helper: Enhanced PDF Viewer
def display_pdf(bytes_data):
    base64_pdf = base64.b64encode(bytes_data).decode('utf-8')
    # Using 'embedded' mode for better browser compatibility
    pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="850" type="application/pdf">'
    st.markdown(pdf_display, unsafe_allow_html=True)

# Session State
if 'cv_sources' not in st.session_state: st.session_state.cv_sources = []
if 'token' not in st.session_state: st.session_state.token = None
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = None

# --- 2. AUTHENTICATION ---
try:
    S = st.secrets
    genai.configure(api_key=S["GEMINI_API_KEY"])
    oauth2 = OAuth2Component(S["GOOGLE_CLIENT_ID"], S["GOOGLE_CLIENT_SECRET"], 
                             "https://accounts.google.com/o/oauth2/v2/auth", 
                             "https://oauth2.googleapis.com/token", 
                             "https://oauth2.googleapis.com/token", 
                             "https://www.googleapis.com/auth/drive.readonly")
except Exception as e:
    st.error("Secrets Configuration Error. Please check your TOML file.")
    st.stop()

# --- 3. SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3858/3858684.png", width=60)
    st.title("Control Center")
    if not st.session_state.token:
        res = oauth2.authorize_button("Connect Google Drive", "https://www.google.com/favicon.ico", 
                                       "https://share.streamlit.io/oauth2callback")
        if res: 
            st.session_state.token = res.get('token')
            st.rerun()
    else:
        st.success("Google Connected")
        if st.button("Clear App Session"):
            for key in st.session_state.keys(): del st.session_state[key]
            st.rerun()

# --- 4. MAIN INTERFACE ---
st.markdown('<div class="main-header">🚀 AI Talent Scout</div>', unsafe_allow_html=True)
t1, t2 = st.tabs(["📌 1. Requirements", "📊 2. Results & Preview"])

with t1:
    jd_input = st.text_area("Detailed Job Description", height=250, placeholder="Include technical skills, years of experience, and soft skills...")

with t2:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="source-card"><h4>📤 Local Upload</h4>', unsafe_allow_html=True)
        files = st.file_uploader("Upload CVs", accept_multiple_files=True, type=['pdf'], label_visibility="collapsed")
        if files:
            for f in files:
                if not any(x['name'] == f.name for x in st.session_state.cv_sources):
                    st.session_state.cv_sources.append({"name": f.name, "content": f.read()})
        st.markdown('</div>', unsafe_allow_html=True)
    
    with c2:
        st.markdown('<div class="source-card"><h4>☁️ Google Drive</h4>', unsafe_allow_html=True)
        if st.session_state.token:
            picked = google_picker(S["GOOGLE_API_KEY"], st.session_state.token.get("access_token"), S["GOOGLE_CLIENT_ID"].split("-")[0], True, ["pdf"], "p1")
            if picked:
                for pf in picked:
                    if not any(x['name'] == pf['name'] for x in st.session_state.cv_sources):
                        st.session_state.cv_sources.append({"name": pf['name'], "content": pf['content']})
        else: st.info("Connect Drive in Sidebar")
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("⚡ Analyze & Rank Candidates", type="primary", use_container_width=True):
        if jd_input and st.session_state.cv_sources:
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
            results = []
            prog = st.progress(0)
            
            for idx, cv in enumerate(st.session_state.cv_sources):
                try:
                    text = " ".join([p.extract_text() for p in PdfReader(BytesIO(cv['content'])).pages[:3] if p.extract_text()])
                    
                    # ENHANCED PROMPT FOR BETTER RANKING
                    prompt = f"""
                    Act as a Senior Technical Recruiter. Rate this candidate out of 100 based strictly on the Job Description.
                    Evaluation Criteria:
                    1. Hard Skills Match (40%)
                    2. Experience Level (40%)
                    3. Education & Certs (20%)
                    
                    Return JSON: {{ "candidate_name": "string", "score": integer, "key_strengths": "string", "missing_skills": "string" }}
                    
                    JD: {jd_input}
                    CV TEXT: {text}
                    """
                    
                    resp = model.generate_content(prompt)
                    data = json.loads(resp.text)
                    if isinstance(data, list): data = data[0]
                    
                    results.append({
                        "Name": data.get("candidate_name", cv['name']),
                        "Score": int(data.get("score", 0)),
                        "Strengths": data.get("key_strengths", ""),
                        "Gaps": data.get("missing_skills", "")
                    })
                    time.sleep(1)
                except Exception as e: st.error(f"Error {cv['name']}: {e}")
                prog.progress((idx + 1) / len(st.session_state.cv_sources))
            
            st.session_state.analysis_results = results
            st.rerun()

# --- 5. ENHANCED DISPLAY & PREVIEW ---
if st.session_state.analysis_results:
    st.divider()
    df = pd.DataFrame(st.session_state.analysis_results).sort_values(by="Score", ascending=False)
    
    col_data, col_view = st.columns([0.5, 0.5])
    
    with col_data:
        st.subheader("🏆 Candidate Rankings")
        # Selection for Viewer
        sel_candidate = st.selectbox("Select Candidate to Verify", options=df['Name'].tolist())
        
        st.dataframe(df, use_container_width=True, hide_index=True, column_config={
            "Score": st.column_config.ProgressColumn("Match Score", min_value=0, max_value=100, format="%d%%"),
            "Strengths": st.column_config.TextColumn("Top Skills Found", width="medium"),
            "Gaps": st.column_config.TextColumn("Missing/Weak Areas", width="medium")
        })
        
    with col_view:
        st.subheader("📄 Full CV Preview")
        viewer_obj = next((x for x in st.session_state.cv_sources if x["name"] == sel_candidate), None)
        if viewer_obj:
            display_pdf(viewer_obj["content"])
