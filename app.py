import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time
import base64
from io import BytesIO

# --- 1. CONFIG & EXPERT UI STYLING ---
st.set_page_config(page_title="TalentScan Intelligence", layout="wide", page_icon="🎯")

# SaaS-style Custom CSS
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main-header { font-size: 2.8rem; font-weight: 800; color: #1e293b; margin-bottom: 0.2rem; }
    .sub-text { color: #64748b; font-size: 1.1rem; margin-bottom: 2rem; }
    .metric-card { background: white; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #f1f5f9; border-radius: 8px; padding: 10px 20px; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { background-color: #2563eb; color: white; }
    embed { border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border: 1px solid #cbd5e1; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. AUTHENTICATION (SECURE SECRETS) ---
try:
    # Pulling from Streamlit Secrets automatically
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    st.error("🛑 API Key Missing: Please add 'GEMINI_API_KEY' to your Streamlit Secrets.")
    st.stop()

# --- 3. SESSION STATE & HELPERS ---
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = None
if 'uploaded_data' not in st.session_state: st.session_state.uploaded_data = []

def display_pdf_native(bytes_data):
    """Native browser embed for PDF viewing"""
    base64_pdf = base64.b64encode(bytes_data).decode('utf-8')
    pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="850" type="application/pdf">'
    st.markdown(pdf_display, unsafe_allow_html=True)

# --- 4. MAIN INTERFACE ---
st.markdown('<div class="main-header">🎯 TalentScan Intelligence</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Advanced AI screening with multi-dimensional candidate scoring.</div>', unsafe_allow_html=True)

tab_input, tab_dashboard = st.tabs(["📥 1. Intake", "📊 2. Intelligence Dashboard"])

with tab_input:
    col_jd, col_up = st.columns([1, 1], gap="large")
    
    with col_jd:
        st.subheader("📌 Job Description")
        jd_text = st.text_area("What are the requirements?", height=350, placeholder="Paste JD details here...")
        
    with col_up:
        st.subheader("📤 Candidate CVs")
        files = st.file_uploader("Upload PDFs", accept_multiple_files=True, type=['pdf'])
        if files:
            for f in files:
                # Avoid duplicate uploads in session state
                if not any(cv['name'] == f.name for cv in st.session_state.uploaded_data):
                    st.session_state.uploaded_data.append({"name": f.name, "content": f.read()})
            st.success(f"✅ {len(st.session_state.uploaded_data)} CVs ready for analysis.")

    if st.button("⚡ Start Deep Screening", type="primary", use_container_width=True):
        if not jd_text or not st.session_state.uploaded_data:
            st.warning("Please provide both a Job Description and at least one CV.")
        else:
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
            all_findings = []
            progress_bar = st.progress(0)
            
            for idx, cv in enumerate(st.session_state.uploaded_data):
                try:
                    reader = PdfReader(BytesIO(cv['content']))
                    cv_text = " ".join([p.extract_text() for p in reader.pages[:4] if p.extract_text()])
                    
                    # Expert Prompt for Multi-Dimensional Scoring
                    prompt = f"""
                    Act as an Executive Recruitment Consultant. Analyze this CV against the JD.
                    Provide a precise numeric evaluation.
                    Return JSON:
                    {{
                      "name": "string",
                      "total_score": integer (0-100),
                      "technical_fit": integer (0-100),
                      "seniority_fit": integer (0-100),
                      "verdict": "short summary",
                      "strengths": ["list of 3 items"],
                      "weaknesses": ["list of 3 items"],
                      "interview_questions": ["3 specific questions based on weaknesses"]
                    }}
                    JD: {jd_text}
                    CV: {cv_text}
                    """
                    
                    response = model.generate_content(prompt)
                    data = json.loads(response.text)
                    if isinstance(data, list): data = data[0]
                    
                    data['filename'] = cv['name'] 
                    all_findings.append(data)
                    time.sleep(1) # Safety buffer
                except Exception as e:
                    st.error(f"Error analyzing {cv['name']}: {e}")
                
                progress_bar.progress((idx + 1) / len(st.session_state.uploaded_data))
            
            st.session_state.analysis_results = all_findings
            st.rerun()

with tab_dashboard:
    if st.session_state.analysis_results:
        df = pd.DataFrame(st.session_state.analysis_results).sort_values(by="total_score", ascending=False)
        
        # --- TOP LEVEL METRICS ---
        m1, m2, m3 = st.columns(3)
        with m1: st.metric("Candidates Screened", len(df))
        with m2: st.metric("Talent Pool Quality", f"{int(df['total_score'].mean())}% Avg")
        with m3: st.metric("Top Fit", df.iloc[0]['name'])
        
        st.divider()

        # --- DUAL-PANE VIEW ---
        col_table, col_viewer = st.columns([0.6, 0.4])

        with col_table:
            st.subheader("🏆 Candidate Rankings")
            selected_name = st.selectbox("Deep Dive Analysis", options=df['name'].tolist())
            
            # Interactive Table
            st.dataframe(
                df[['name', 'total_score', 'technical_fit', 'seniority_fit', 'verdict']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "total_score": st.column_config.ProgressColumn("Overall Match", min_value=0, max_value=100, format="%d%%"),
                    "technical_fit": st.column_config.NumberColumn("Technical %", format="%d%%"),
                    "seniority_fit": st.column_config.NumberColumn("Experience %", format="%d%%"),
                }
            )
            
            # Focused Intelligence for the Selected Candidate
            candidate = next(c for c in st.session_state.analysis_results if c['name'] == selected_name)
            
            c_left, c_right = st.columns(2)
            with c_left:
                st.info("**🚀 Key Strengths**\n\n" + "\n".join([f"- {s}" for s in candidate['strengths']]))
            with c_right:
                st.warning("**⚠️ Critical Gaps**\n\n" + "\n".join([f"- {w}" for w in candidate['weaknesses']]))
            
            with st.expander("❓ AI-Generated Interview Guide"):
                st.write("Based on the identified gaps, ask these questions:")
                for q in candidate['interview_questions']:
                    st.markdown(f"**- {q}**")

        with col_viewer:
            st.subheader("📄 Verification")
            viewer_file = next(cv for cv in st.session_state.uploaded_data if cv['name'] == candidate['filename'])
            display_pdf_native(viewer_file['content'])
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Recruitment Report", data=csv, file_name="talent_report.csv", use_container_width=True)
    else:
        st.info("Results will appear here once the analysis is complete.")

# Sidebar Reset
with st.sidebar:
    if st.button("🗑️ Clear & Start New Session", use_container_width=True):
        st.session_state.analysis_results = None
        st.session_state.uploaded_data = []
        st.rerun()
