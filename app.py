import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time
from io import BytesIO
from streamlit_google_picker import google_picker

# --- 1. MODERN UI CONFIG ---
st.set_page_config(page_title="TalentScan Pro", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .stApp { background-color: #fcfcfd; }
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1e293b; }
    .source-card { 
        background: white; border-radius: 12px; padding: 15px; 
        border: 1px solid #e2e8f0; text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize Session State for files so they don't disappear on re-run
if 'cv_sources' not in st.session_state:
    st.session_state.cv_sources = []

# --- 2. SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3858/3858684.png", width=60)
    st.title("Settings")
    gemini_key = st.text_input("Gemini API Key", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
    
    if st.button("🗑️ Clear All Uploads"):
        st.session_state.cv_sources = []
        st.rerun()

# --- 3. MAIN UI ---
st.markdown('<div class="main-header">🚀 AI Talent Scout</div>', unsafe_allow_html=True)

tab_jd, tab_cv = st.tabs(["📋 Job Description", "📄 Candidate Analysis"])

with tab_jd:
    jd_input = st.text_area("Paste Requirements", height=250, placeholder="Requirements...")

with tab_cv:
    col_u, col_g = st.columns(2)
    
    with col_u:
        st.markdown('<div class="source-card">', unsafe_allow_html=True)
        st.markdown("### 📤 Local Upload")
        local_files = st.file_uploader("Upload PDFs", accept_multiple_files=True, type=['pdf'], label_visibility="collapsed")
        if local_files:
            for f in local_files:
                # Avoid duplicates
                if not any(cv['name'] == f.name for cv in st.session_state.cv_sources):
                    st.session_state.cv_sources.append({"name": f.name, "content": f.read()})
        st.markdown('</div>', unsafe_allow_html=True)

    with col_g:
        st.markdown('<div class="source-card">', unsafe_allow_html=True)
        st.markdown("### ☁️ Google Drive")
        
        # FIX: The Picker MUST run in the main flow, not inside a button's 'if'
        g_api = st.secrets.get("GOOGLE_API_KEY")
        g_client = st.secrets.get("GOOGLE_CLIENT_ID")
        
        if g_api and g_client:
            # Appropriate Drive Icon via Markdown
            st.markdown('<img src="https://cdn-icons-png.flaticon.com/512/2965/2965306.png" width="40">', unsafe_allow_html=True)
            
            picked_files = google_picker(
                apiKey=g_api, 
                clientId=g_client, 
                appId=g_client.split("-")[0],
                multiselect=True, types=["pdf"]
            )
            
            if picked_files:
                for pf in picked_files:
                    if not any(cv['name'] == pf['name'] for cv in st.session_state.cv_sources):
                        st.session_state.cv_sources.append({"name": pf['name'], "content": pf['content']})
                st.toast("Files added from Drive!")
        else:
            st.error("Drive API keys missing in Secrets.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.write(f"**Total CVs ready for analysis:** {len(st.session_state.cv_sources)}")
    
    # --- 4. EXECUTION ---
    if st.button("⚡ Run AI Shortlisting", type="primary", use_container_width=True):
        if not gemini_key or not jd_input or not st.session_state.cv_sources:
            st.warning("Ensure API Key, JD, and CVs are all provided.")
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
                    
                    prompt = f"Analyze CV for JD. JSON ONLY. Keys: 'candidate_name', 'match_score', 'reasoning'. JD: {jd_input} CV: {text}"
                    response = model.generate_content(prompt)
                    
                    if response.text:
                        data = json.loads(response.text)
                        if isinstance(data, list): data = data[0]
                        final_report.append({
                            "Name": data.get("candidate_name", cv['name']),
                            "Score": data.get("match_score", 0),
                            "Insight": data.get("reasoning", "N/A")
                        })
                    time.sleep(1.2)
                except Exception as e:
                    st.error(f"Error on {cv['name']}: {e}")
                
                progress.progress((idx + 1) / len(st.session_state.cv_sources))

            status.empty()

            if final_report:
                df = pd.DataFrame(final_report)
                df['Score'] = pd.to_numeric(df['Score'], errors='coerce').fillna(0)
                df = df.sort_values(by="Score", ascending=False)
                
                st.subheader("📊 Ranking Results")
                st.dataframe(df, use_container_width=True, column_config={
                    "Score": st.column_config.ProgressColumn("Match %", min_value=0, max_value=100, format="%d")
                })
