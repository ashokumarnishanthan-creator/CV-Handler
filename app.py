import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time
import base64
import re
from io import BytesIO

# --- 1. CONFIG & UI ---
st.set_page_config(page_title="TalentScan Precision", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main-header { font-size: 2.8rem; font-weight: 800; color: #1e293b; margin-bottom: 0.2rem; }
    .metric-card { background: white; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; }
    embed { border-radius: 12px; border: 1px solid #cbd5e1; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. AUTHENTICATION ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except KeyError:
    st.error("Missing GEMINI_API_KEY in Secrets.")
    st.stop()

# --- 3. SESSION STATE ---
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = None
if 'uploaded_data' not in st.session_state: st.session_state.uploaded_data = []

def display_pdf_native(bytes_data):
    base64_pdf = base64.b64encode(bytes_data).decode('utf-8')
    pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="850" type="application/pdf">'
    st.markdown(pdf_display, unsafe_allow_html=True)

# --- 4. MAIN UI ---
st.markdown('<div class="main-header">🎯 TalentScan Precision</div>', unsafe_allow_html=True)
st.write("Advanced Signal Filtering for High-Accuracy Recruitment.")

tab_input, tab_dashboard = st.tabs(["📥 Intake CVs", "📊 Precision Dashboard"])

with tab_input:
    col_jd, col_up = st.columns([1, 1], gap="large")
    
    with col_jd:
        jd_text = st.text_area("Job Requirements", height=300, placeholder="Detail the technical stack and years of experience...")
        
    with col_up:
        files = st.file_uploader("Upload PDFs", accept_multiple_files=True, type=['pdf'])
        if files:
            for f in files:
                if not any(cv['name'] == f.name for cv in st.session_state.uploaded_data):
                    st.session_state.uploaded_data.append({"name": f.name, "content": f.read()})
            st.success(f"Files ready: {len(st.session_state.uploaded_data)}")

    if st.button("⚡ Execute High-Accuracy Screening", type="primary", use_container_width=True):
        if not jd_text or not st.session_state.uploaded_data:
            st.warning("Input JD and CVs first.")
        else:
            # Use 2.0 Flash for speed and complex reasoning
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
            all_findings = []
            progress_bar = st.progress(0)
            
            for idx, cv in enumerate(st.session_state.uploaded_data):
                try:
                    reader = PdfReader(BytesIO(cv['content']))
                    # Extraction for better context
                    cv_text = " ".join([p.extract_text() for p in reader.pages[:4] if p.extract_text()])
                    
                    # --- THE PRECISION PROMPT ---
                    prompt = f"""
                    You are a strict technical recruiter. Your goal is to eliminate irrelevant documents and provide a mathematically accurate score.

                    STEP 1: RELEVANCE CHECK
                    - If the document is NOT a Resume/CV or is completely unrelated to the JD, set ALL scores to 0.

                    STEP 2: MULTI-PILLAR SCORING (0-100)
                    - technical_fit (40%): Only score based on direct evidence of technical tools/skills in JD.
                    - experience_fit (40%): Score based on YEARS and SENIORITY. (e.g., If JD asks for 5 years and candidate has 2, max score is 40).
                    - education_fit (20%): Degree and certification relevance.

                    STEP 3: FINAL SCORE
                    - total_score = (technical * 0.4) + (experience * 0.4) + (education * 0.2)

                    Return ONLY JSON:
                    {{
                      "name": "string",
                      "total_score": int,
                      "technical_fit": int,
                      "experience_fit": int,
                      "verdict": "Critical summary of fit",
                      "strengths": ["list"],
                      "gaps": ["list"],
                      "interview_questions": ["3 hard-hitting questions"]
                    }}

                    JD: {jd_text}
                    CV CONTENT: {cv_text}
                    """
                    
                    response = model.generate_content(prompt)
                    data = json.loads(response.text)
                    if isinstance(data, list): data = data[0]
                    
                    data['filename'] = cv['name'] 
                    all_findings.append(data)
                    time.sleep(1) # API Cooling
                except Exception as e:
                    st.error(f"Error {cv['name']}: {e}")
                
                progress_bar.progress((idx + 1) / len(st.session_state.uploaded_data))
            
            st.session_state.analysis_results = all_findings
            st.rerun()

# --- 5. DASHBOARD & FILTERING ---
with tab_dashboard:
    if st.session_state.analysis_results:
        df = pd.DataFrame(st.session_state.analysis_results)
        
        # Cleanup Score formatting (Force Integer)
        for col in ['total_score', 'technical_fit', 'experience_fit']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

        # Dashboard View
        df = df.sort_values(by="total_score", ascending=False)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Qualified Pool", len(df[df['total_score'] > 50]))
        m2.metric("Average Fit", f"{int(df['total_score'].mean())}%")
        m3.metric("Irrelevant Docs", len(df[df['total_score'] == 0]))

        st.divider()

        col_table, col_view = st.columns([0.6, 0.4])

        with col_table:
            st.subheader("🏆 Accuracy-Ranked Shortlist")
            selected_name = st.selectbox("Detailed Intelligence Review", options=df['name'].tolist())
            
            st.dataframe(
                df[['name', 'total_score', 'technical_fit', 'experience_fit', 'verdict']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "total_score": st.column_config.ProgressColumn("Overall Precision", min_value=0, max_value=100, format="%d%%"),
                    "technical_fit": st.column_config.NumberColumn("Tech Match", format="%d%%"),
                    "experience_fit": st.column_config.NumberColumn("Exp Match", format="%d%%"),
                }
            )
            
            # Deep Dive for selection
            candidate = next(c for c in st.session_state.analysis_results if c['name'] == selected_name)
            
            cl, cr = st.columns(2)
            with cl: st.info("**✅ Verified Strengths**\n\n" + "\n".join([f"- {s}" for s in candidate['strengths']]))
            with cr: st.warning("**⚠️ Identified Gaps**\n\n" + "\n".join([f"- {g}" for g in candidate['gaps']]))
            
            with st.expander("❓ Target Interview Questions (Gap-focused)"):
                for q in candidate['interview_questions']:
                    st.write(f"- {q}")

        with col_view:
            st.subheader("📄 Verification Viewer")
            v_file = next(cv for cv in st.session_state.uploaded_data if cv['name'] == candidate['filename'])
            display_pdf_native(v_file['content'])
            
            st.download_button("📥 Export Precision Report", df.to_csv(index=False), "recruitment_report.csv", use_container_width=True)
    else:
        st.info("Results will appear here. Irrelevant documents will be automatically ranked at 0%.")

# Sidebar Utility
with st.sidebar:
    if st.button("🗑️ Reset Session"):
        st.session_state.analysis_results = None
        st.session_state.uploaded_data = []
        st.rerun()
