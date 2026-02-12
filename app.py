import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time
import re
import base64
from io import BytesIO

# --- 1. CONFIG & SAAS STYLING ---
st.set_page_config(page_title="TalentScan Intelligence", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .stApp { background-color: #fcfcfd; }
    .main-header { font-size: 2.8rem; font-weight: 800; color: #1e293b; margin-bottom: 0.5rem; }
    .sub-text { color: #64748b; font-size: 1.1rem; margin-bottom: 2rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { 
        background-color: #f1f5f9; border-radius: 8px; padding: 10px 20px; color: #475569;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { 
        background-color: #2563eb; color: white; 
    }
    embed { border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SESSION STATE & HELPERS ---
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = None
if 'uploaded_data' not in st.session_state: st.session_state.uploaded_data = []

def display_pdf_native(bytes_data):
    base64_pdf = base64.b64encode(bytes_data).decode('utf-8')
    pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf">'
    st.markdown(pdf_display, unsafe_allow_html=True)

# --- 3. SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3858/3858684.png", width=60)
    st.title("TalentScan AI")
    gemini_key = st.text_input("Gemini API Key", type="password")
    
    st.divider()
    st.markdown("### 🛠️ Analysis Toggles")
    strict_mode = st.toggle("Strict Seniority Check", value=True)
    extract_questions = st.checkbox("Generate Interview Questions", value=True)
    
    if st.button("🗑️ Reset Application"):
        st.session_state.analysis_results = None
        st.session_state.uploaded_data = []
        st.rerun()

# --- 4. MAIN UI ---
st.markdown('<div class="main-header">🚀 TalentScan Intelligence</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">AI-driven candidate screening and deep-fit analysis.</div>', unsafe_allow_html=True)

tab_input, tab_results = st.tabs(["📥 1. Intake", "📊 2. Intelligence Dashboard"])

with tab_input:
    col_jd, col_up = st.columns([1, 1], gap="large")
    
    with col_jd:
        st.subheader("📌 Job Description")
        jd_text = st.text_area("What are you looking for?", height=300, placeholder="Paste JD here...")
        
    with col_up:
        st.subheader("📤 Candidate CVs")
        files = st.file_uploader("Upload PDFs", accept_multiple_files=True, type=['pdf'])
        if files:
            for f in files:
                if not any(cv['name'] == f.name for cv in st.session_state.uploaded_data):
                    st.session_state.uploaded_data.append({"name": f.name, "content": f.read()})
            st.success(f"{len(st.session_state.uploaded_data)} CVs ready for analysis.")

    if st.button("⚡ Start Deep Screening", type="primary", use_container_width=True):
        if not gemini_key or not jd_text or not st.session_state.uploaded_data:
            st.error("Please provide an API Key, JD, and CVs.")
        else:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
            
            all_findings = []
            progress_bar = st.progress(0)
            
            for idx, cv in enumerate(st.session_state.uploaded_data):
                try:
                    reader = PdfReader(BytesIO(cv['content']))
                    # Read more pages for "Deep Analysis"
                    cv_text = " ".join([p.extract_text() for p in reader.pages[:4] if p.extract_text()])
                    
                    prompt = f"""
                    Act as an Executive Headhunter. Analyze this CV against the JD.
                    Be critical and precise.
                    Return JSON:
                    {{
                      "name": "string",
                      "total_score": integer (0-100),
                      "tech_score": integer (0-100),
                      "exp_score": integer (0-100),
                      "summary": "1 sentence verdict",
                      "strengths": ["list"],
                      "gaps": ["list"],
                      "interview_questions": ["3 questions"]
                    }}
                    JD: {jd_text}
                    CV: {cv_text}
                    """
                    
                    response = model.generate_content(prompt)
                    data = json.loads(response.text)
                    if isinstance(data, list): data = data[0]
                    
                    data['filename'] = cv['name'] # Keep link to file
                    all_findings.append(data)
                    time.sleep(1) # Rate limit safety
                except Exception as e:
                    st.error(f"Error analyzing {cv['name']}: {e}")
                
                progress_bar.progress((idx + 1) / len(st.session_state.uploaded_data))
            
            st.session_state.analysis_results = all_findings
            st.rerun()

with tab_results:
    if st.session_state.analysis_results:
        df = pd.DataFrame(st.session_state.analysis_results).sort_values(by="total_score", ascending=False)
        
        # Dashboard KPIs
        k1, k2, k3 = st.columns(3)
        k1.metric("Total Candidates", len(df))
        k2.metric("Avg Match %", f"{int(df['total_score'].mean())}%")
        k3.metric("Top Candidate", df.iloc[0]['name'])
        
        st.divider()

        col_table, col_view = st.columns([0.6, 0.4])

        with col_table:
            st.subheader("🏆 Candidate Ranking")
            selected_name = st.selectbox("Select Candidate for Deep Dive", options=df['name'].tolist())
            
            st.dataframe(
                df[['name', 'total_score', 'tech_score', 'exp_score', 'summary']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "total_score": st.column_config.ProgressColumn("Overall Fit", min_value=0, max_value=100, format="%d%%"),
                    "tech_score": st.column_config.NumberColumn("Tech Match", format="%d%%"),
                    "exp_score": st.column_config.NumberColumn("Exp Match", format="%d%%"),
                }
            )
            
            # Show specific intelligence for selected candidate
            candidate_data = next(c for c in st.session_state.analysis_results if c['name'] == selected_name)
            
            c_left, c_right = st.columns(2)
            with c_left:
                st.info("**✅ Key Strengths**\n\n" + "\n".join([f"- {s}" for s in candidate_data['strengths']]))
            with c_right:
                st.warning("**⚠️ Critical Gaps**\n\n" + "\n".join([f"- {g}" for g in candidate_data['gaps']]))
            
            if extract_questions:
                with st.expander("❓ Recommended Interview Questions"):
                    for q in candidate_data['interview_questions']:
                        st.write(f"- {q}")

        with col_view:
            st.subheader("📄 Document Viewer")
            viewer_file = next(cv for cv in st.session_state.uploaded_data if cv['name'] == candidate_data['filename'])
            display_pdf_native(viewer_file['content'])
    else:
        st.info("Run analysis to see results.")
