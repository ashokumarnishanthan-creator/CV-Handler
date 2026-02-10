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

# --- 1. SETTINGS & MODERN UI ---
st.set_page_config(page_title="TalentScan Pro", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .stApp { background-color: #fcfcfd; }
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1e293b; margin-bottom: 20px; }
    .source-card { 
        background: white; border-radius: 12px; padding: 20px; 
        border: 1px solid #e2e8f0; text-align: center; height: 180px;
    }
    .status-pill { padding: 5px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# Session State Initialization
if 'cv_sources' not in st.session_state: st.session_state.cv_sources = []
if 'token' not in st.session_state: st.session_state.token = None

# --- 2. GOOGLE OAUTH CONFIG ---
# Verify secrets exist to prevent KeyError
try:
    CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError as e:
    st.error(f"Missing Secret Key: {e}. Please add it to Streamlit Secrets.")
    st.stop()

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/drive.readonly"

oauth2 = OAuth2Component(CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL, TOKEN_URL, SCOPE)

# --- 3. SIDEBAR (AUTH & CONTROL) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3858/3858684.png", width=60)
    st.title("TalentScan AI")
    
    if not st.session_state.token:
        # Step 1: Fix 403 Error by logging in
        # Ensure you have added your email to "Test Users" in Google Cloud Console
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
        st.success("Connected to Google")
        if st.button("Logout & Clear"):
            st.session_state.token = None
            st.session_state.cv_sources = []
            st.rerun()

# --- 4. MAIN INTERFACE ---
st.markdown('<div class="main-header">🚀 AI Recruitment Dashboard</div>', unsafe_allow_html=True)

tab_jd, tab_cv = st.tabs(["📋 Step 1: Job Description", "📄 Step 2: Source CVs"])

with tab_jd:
    jd_input = st.text_area("Paste Requirements", height=250, placeholder="Requirements, Skills, Qualifications...")

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
            # Step 2: Integrated Google Picker with proper Drive Icon
            st.markdown('<img src="https://cdn-icons-png.flaticon.com/512/2965/2965306.png" width="40" style="margin-bottom:10px">', unsafe_allow_html=True)
            
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
                st.toast("Files added from Google Drive!")
        else:
            st.info("Login via Sidebar to enable Google Drive")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- 5. AI PROCESSING ---
    st.write(f"📂 **Queue:** {len(st.session_state.cv_sources)} files ready.")
    
    if st.button("⚡ Run AI Analysis", type="primary", use_container_width=True):
        if not jd_input or not st.session_state.cv_sources:
            st.warning("Please provide both Job Description and CVs.")
        else:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
            
            final_report = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, cv in enumerate(st.session_state.cv_sources):
                status_text.info(f"Analyzing: {cv['name']}...")
                try:
                    # Robust PDF parsing
                    reader = PdfReader(BytesIO(cv['content']))
                    text = " ".join([p.extract_text() for p in reader.pages[:2] if p.extract_text()])
                    
                    prompt = f"""
                    Compare CV to JD. Return JSON: {{"name":"str", "score":int, "reasoning":"1 sentence"}}.
                    JD: {jd_input}
                    CV Text: {text}
                    """
                    response = model.generate_content(prompt)
                    
                    # Safe Parsing
                    data = json.loads(response.text)
                    if isinstance(data, list): data = data[0]
                    
                    # Standardize Score for the Match % bar
                    score_val = data.get("score", 0)
                    if isinstance(score_val, str):
                        score_val = int(re.search(r'\d+', score_val).group()) if re.search(r'\d+', score_val) else 0

                    final_report.append({
                        "Candidate Name": data.get("name", cv['name']),
                        "Match Score": score_val,
                        "AI Evaluation": data.get("reasoning", "No data")
                    })
                    time.sleep(1.5) # Protect rate limits
                except Exception as e:
                    st.error(f"Error on {cv['name']}: {str(e)}")
                
                progress_bar.progress((idx + 1) / len(st.session_state.cv_sources))

            status_text.empty()
            
            # --- 6. RESULTS & RANKING ---
            if final_report:
                df = pd.DataFrame(final_report).sort_values(by="Match Score", ascending=False)
                st.subheader("📊 Ranking Results")
                
                # Step 3: Progressive Match % Bar
                st.dataframe(
                    df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Match Score": st.column_config.ProgressColumn(
                            "Match %", min_value=0, max_value=100, format="%d%%"
                        ),
                        "AI Evaluation": st.column_config.TextColumn("AI Insight", width="large")
                    }
                )
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Excel/CSV Report", data=csv, file_name="ai_recruitment_shortlist.csv")
