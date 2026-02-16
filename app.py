import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time
from io import BytesIO
from datetime import datetime

# --- 1. CONFIG & UI ---
st.set_page_config(page_title="TalentScan Pro", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    .log-container { background-color: #f8fafc; padding: 10px; border-radius: 8px; font-family: monospace; font-size: 0.8rem; height: 150px; overflow-y: scroll; border: 1px solid #e2e8f0; }
    .status-pill { padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: bold; text-transform: uppercase; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SESSION STATE (WORKFLOW STORAGE) ---
if 'cv_data' not in st.session_state: st.session_state.cv_data = []
if 'results' not in st.session_state: st.session_state.results = []
if 'workflow_logs' not in st.session_state: st.session_state.workflow_logs = []

def add_log(action):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.workflow_logs.insert(0, f"[{timestamp}] {action}")

# --- 3. SIDEBAR (LOGS & SETTINGS) ---
with st.sidebar:
    st.title("⚙️ Workflow")
    st.markdown("### System Logs")
    log_html = "".join([f"<div>{log}</div>" for log in st.session_state.workflow_logs])
    st.markdown(f'<div class="log-container">{log_html}</div>', unsafe_allow_html=True)
    
    st.divider()
    if st.button("Clear Session", use_container_width=True):
        st.session_state.cv_data = []
        st.session_state.results = []
        st.session_state.workflow_logs = []
        st.rerun()

# --- 4. MAIN INTERFACE ---
st.title("TalentScan Intelligence")

t1, t2, t3 = st.tabs(["📥 Intake", "📊 Analysis", "📝 Management"])

with t1:
    col_a, col_b = st.columns(2)
    with col_a:
        jd_input = st.text_area("Job Description", height=200)
    with col_b:
        uploaded = st.file_uploader("Upload CVs", accept_multiple_files=True, type=['pdf'])
        if uploaded:
            for f in uploaded:
                if not any(cv['name'] == f.name for cv in st.session_state.cv_data):
                    st.session_state.cv_data.append({"name": f.name, "content": f.read()})
                    add_log(f"Uploaded {f.name}")

    if st.button("⚡ Run Precision Analysis", type="primary", use_container_width=True):
        if jd_input and st.session_state.cv_data:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            new_results = []
            start_time = time.time()
            
            for cv in st.session_state.cv_data:
                add_log(f"Processing {cv['name']}...")
                reader = PdfReader(BytesIO(cv['content']))
                text = " ".join([p.extract_text() for p in reader.pages[:3] if p.extract_text()])
                
                # Optimized prompt for the new workflow
                prompt = f"Analyze CV for JD. Return JSON: {{'name':'str', 'score':int, 'verdict':'str'}}. JD: {jd_input} CV: {text}"
                resp = model.generate_content(prompt)
                data = json.loads(resp.text)
                
                # Add default workflow metadata
                data['stage'] = "New"
                data['notes'] = ""
                data['filename'] = cv['name']
                new_results.append(data)
                
            st.session_state.results = new_results
            add_log(f"Analysis Complete in {round(time.time()-start_time, 2)}s")
            st.rerun()

with t2:
    if st.session_state.results:
        df = pd.DataFrame(st.session_state.results).sort_values(by="score", ascending=False)
        st.dataframe(df[['name', 'score', 'verdict', 'stage']], use_container_width=True, hide_index=True,
                     column_config={"score": st.column_config.ProgressColumn("Fit", min_value=0, max_value=100)})
    else:
        st.info("No analysis data found.")

with t3:
    if st.session_state.results:
        st.subheader("Candidate Pipeline Management")
        sel_name = st.selectbox("Select Candidate to Manage", options=[c['name'] for c in st.session_state.results])
        
        # Get the current candidate's data
        idx = next(i for i, c in enumerate(st.session_state.results) if c['name'] == sel_name)
        cand = st.session_state.results[idx]
        
        c1, c2 = st.columns(2)
        with c1:
            new_stage = st.select_slider("Move Stage", options=["New", "Screened", "Interview", "Offer", "Rejected"], value=cand['stage'])
            if new_stage != cand['stage']:
                st.session_state.results[idx]['stage'] = new_stage
                add_log(f"Moved {sel_name} to {new_stage}")
                st.rerun()
        
        with c2:
            new_notes = st.text_area("Internal Notes", value=cand['notes'], placeholder="Add comments here...")
            if st.button("Save Notes"):
                st.session_state.results[idx]['notes'] = new_notes
                add_log(f"Updated notes for {sel_name}")
                st.toast("Notes Saved!")

        st.divider()
        st.download_button("📥 Export Full Workflow Report", pd.DataFrame(st.session_state.results).to_csv(index=False), "workflow_report.csv")
