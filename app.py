import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from supabase import create_client, Client
import pandas as pd
import json
import time
import re
from io import BytesIO
from datetime import datetime

# --- 1. CONFIG & DB CONNECTION ---
st.set_page_config(page_title="TalentScan Enterprise", layout="wide", page_icon="🎯")

@st.cache_resource
def init_db():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except KeyError:
        st.error("Missing Supabase Secrets (URL or Key). Check your Streamlit Secrets.")
        st.stop()

supabase = init_db()

# --- 2. MINIMALIST UI STYLING ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #1e293b; }
    .main-header { font-size: 2.2rem; font-weight: 700; color: #0f172a; margin-bottom: 0.2rem; }
    .sub-text { color: #64748b; font-size: 1rem; margin-bottom: 2rem; }
    div.stTextArea textarea { border-radius: 8px; border: 1px solid #e2e8f0; background-color: #f8fafc; }
    [data-testid="stMetric"] { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #f1f5f9; }
    .status-card { padding: 15px; border-radius: 10px; background-color: #f8fafc; border: 1px solid #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---
def save_candidate_to_db(data):
    supabase.table("candidate_logs").insert(data).execute()

def load_db_data():
    res = supabase.table("candidate_logs").select("*").order("created_at", desc=True).execute()
    return pd.DataFrame(res.data)

# --- 4. SESSION STATE ---
if 'cv_data' not in st.session_state: st.session_state.cv_data = []

# --- 5. MAIN INTERFACE ---
st.markdown('<div class="main-header">TalentScan Intelligence</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Persistent Enterprise Screening Engine</div>', unsafe_allow_html=True)

tab_scan, tab_history, tab_analytics = st.tabs(["⚡ New Analysis", "📜 History", "📈 Analytics"])

with tab_scan:
    col_jd, col_up = st.columns([1, 1], gap="large")
    
    with col_jd:
        job_title = st.text_input("Role Title", placeholder="e.g. Senior Software Engineer")
        jd_input = st.text_area("Job Requirements", height=200, placeholder="Detail the tech stack and seniority...")
        
    with col_up:
        files = st.file_uploader("Upload PDFs", accept_multiple_files=True, type=['pdf'])
        if files:
            for f in files:
                if not any(cv['name'] == f.name for cv in st.session_state.cv_data):
                    st.session_state.cv_data.append({"name": f.name, "content": f.read()})
            st.info(f"{len(st.session_state.cv_data)} documents loaded.")

    if st.button("Start Precision Screening", type="primary", use_container_width=True):
        if not jd_input or not st.session_state.cv_data or not job_title:
            st.warning("Please fill in Job Title, JD, and upload CVs.")
        else:
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
                
                prog = st.progress(0)
                for idx, cv in enumerate(st.session_state.cv_data):
                    reader = PdfReader(BytesIO(cv['content']))
                    text = " ".join([p.extract_text() for p in reader.pages[:3] if p.extract_text()])
                    
                    # High-Accuracy Multi-Pillar Prompt
                    prompt = f"""
                    Role: Technical Recruiter. Task: High-Precision Evaluation.
                    Relevance: If not a CV, score 0.
                    Scoring: tech_fit (40%), exp_fit (40%), edu_fit (20%).
                    If candidate lacks required years of experience, penalize exp_fit heavily.
                    Return JSON: {{"name":"str", "total":int, "verdict":"str", "strengths":["list"], "gaps":["list"]}}
                    JD: {jd_input} | CV: {text}
                    """
                    
                    resp = model.generate_content(prompt)
                    data = json.loads(resp.text)
                    if isinstance(data, list): data = data[0]
                    
                    # Sync to Supabase
                    save_candidate_to_db({
                        "candidate_name": data.get("name", cv['name']),
                        "score": data.get("total", 0),
                        "verdict": data.get("verdict", ""),
                        "job_title": job_title,
                        "notes": f"Strengths: {', '.join(data.get('strengths', []))}",
                        "stage": "New"
                    })
                    time.sleep(1)
                    prog.progress((idx + 1) / len(st.session_state.cv_data))
                
                st.session_state.cv_data = [] # Clear upload buffer
                st.success("Analysis Complete. View results in History tab.")
                st.rerun()
            except Exception as e:
                st.error(f"Analysis failed: {e}")

with tab_history:
    df_history = load_db_data()
    if not df_history.empty:
        # Filter Logic
        roles = ["All Roles"] + sorted(df_history['job_title'].unique().tolist())
        selected_role = st.selectbox("Filter by Job Posting", roles)
        
        display_df = df_history if selected_role == "All Roles" else df_history[df_history['job_title'] == selected_role]
        
        st.dataframe(
            display_df[['candidate_name', 'score', 'stage', 'job_title', 'verdict']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "score": st.column_config.ProgressColumn("Overall Fit", min_value=0, max_value=100, format="%d%%"),
            }
        )
        
        st.divider()
        # Management Section
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            target = st.selectbox("Select Candidate to Manage", display_df['candidate_name'].tolist())
            cand_id = display_df[display_df['candidate_name'] == target]['id'].iloc[0]
            current_stage = display_df[display_df['candidate_name'] == target]['stage'].iloc[0]
        with col_m2:
            new_stage = st.select_slider("Move Stage", options=["New", "Screened", "Interview", "Offer", "Rejected"], value=current_stage)
            if st.button("Update Database"):
                supabase.table("candidate_logs").update({"stage": new_stage}).eq("id", cand_id).execute()
                st.toast(f"{target} moved to {new_stage}")
                st.rerun()
    else:
        st.info("No records found in database.")

with tab_analytics:
    df_all = load_db_data()
    if not df_all.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Talent Pipeline Distribution**")
            st.bar_chart(df_all['stage'].value_counts())
        with c2:
            st.markdown("**Historical Score Trends**")
            st.line_chart(df_all['score'])
        
        st.markdown("**Average Score per Role**")
        st.table(df_all.groupby('job_title')['score'].mean())
    else:
        st.info("Insufficient data for analytics.")
