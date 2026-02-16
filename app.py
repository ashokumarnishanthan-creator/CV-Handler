import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time
import re
from io import BytesIO

# --- 1. MINIMALIST UI CONFIG ---
st.set_page_config(page_title="TalentScan", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #1e293b; }
    .main-header { font-size: 2rem; font-weight: 700; color: #0f172a; margin-bottom: 0.2rem; }
    .sub-text { color: #64748b; font-size: 1rem; margin-bottom: 2rem; }
    div.stTextArea textarea { border-radius: 8px; border: 1px solid #e2e8f0; background-color: #f8fafc; }
    [data-testid="stMetric"] { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #f1f5f9; }
    .status-card { padding: 20px; border-radius: 12px; background-color: #f8fafc; border: 1px solid #e2e8f0; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SESSION STATE ---
if 'results' not in st.session_state: st.session_state.results = None
if 'cv_data' not in st.session_state: st.session_state.cv_data = []

# --- 3. AUTH & API ---
try:
    # Pulling from st.secrets
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except KeyError:
    st.error("Missing GEMINI_API_KEY in Secrets.")
    st.stop()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.markdown("### 🎯 TalentScan")
    st.caption("Precision Recruitment Engine")
    st.divider()
    if st.button("Clear All Data", use_container_width=True):
        st.session_state.results = None
        st.session_state.cv_data = []
        st.rerun()

# --- 5. MAIN INTERFACE ---
st.markdown('<div class="main-header">TalentScan Intelligence</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Minimalist AI screening with high-accuracy ranking.</div>', unsafe_allow_html=True)

col_jd, col_up = st.columns([1, 1], gap="medium")

with col_jd:
    jd_text = st.text_area("Job Requirements", height=200, placeholder="Define the role stack and seniority...")

with col_up:
    files = st.file_uploader("Upload Candidate PDFs", accept_multiple_files=True, type=['pdf'], label_visibility="collapsed")
    if files:
        for f in files:
            if not any(cv['name'] == f.name for cv in st.session_state.cv_data):
                st.session_state.cv_data.append({"name": f.name, "content": f.read()})
    
    if st.session_state.cv_data:
        st.info(f"📁 {len(st.session_state.cv_data)} documents loaded.")

if st.button("Execute Precision Analysis", type="primary", use_container_width=True):
    if jd_text and st.session_state.cv_data:
        model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
        all_findings = []
        prog = st.progress(0)
        
        for idx, cv in enumerate(st.session_state.cv_data):
            try:
                reader = PdfReader(BytesIO(cv['content']))
                text = " ".join([p.extract_text() for p in reader.pages[:3] if p.extract_text()])
                
                # REFINED ACCURACY PROMPT
                prompt = f"""
                Strict Recruiter Role. 
                1. Relevance Check: If not a CV, all scores = 0.
                2. Pillar Scoring (0-100): 
                   - tech_fit (40%): Tooling match.
                   - exp_fit (40%): Years & seniority match.
                   - edu_fit (20%): Degree relevance.
                3. Calculate Total: (tech*0.4 + exp*0.4 + edu*0.2).
                
                Return JSON: {{"name":"str", "total":int, "tech":int, "exp":int, "verdict":"str", "strengths":["list"], "gaps":["list"]}}
                JD: {jd_text}
                CV: {text}
                """
                resp = model.generate_content(prompt)
                data = json.loads(resp.text)
                if isinstance(data, list): data = data[0]
                data['filename'] = cv['name'] 
                all_findings.append(data)
                time.sleep(1) # API protection
            except Exception as e:
                st.error(f"Error {cv['name']}: {e}")
            prog.progress((idx + 1) / len(st.session_state.cv_data))
        
        st.session_state.results = all_findings
        st.rerun()

# --- 6. DASHBOARD RESULTS ---
if st.session_state.results:
    st.divider()
    df = pd.DataFrame(st.session_state.results).sort_values(by="total", ascending=False)
    
    # KPIs
    m1, m2, m3 = st.columns(3)
    m1.metric("Qualified Pool", len(df[df['total'] > 50]))
    m2.metric("Avg Match %", f"{int(df['total'].mean())}%")
    m3.metric("Irrelevant Docs", len(df[df['total'] == 0]))

    # Dashboard Layout
    col_rank, col_intel = st.columns([0.6, 0.4], gap="large")

    with col_rank:
        st.markdown("#### Ranking Shortlist")
        st.dataframe(
            df[['name', 'total', 'tech', 'exp']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total": st.column_config.ProgressColumn("Overall Score", min_value=0, max_value=100, format="%d%%"),
                "tech": "Technical",
                "exp": "Experience"
            }
        )
        st.download_button("📥 Export Shortlist (CSV)", df.to_csv(index=False), "shortlist.csv", use_container_width=True)

    with col_intel:
        st.markdown("#### Selection Intelligence")
        selected_name = st.selectbox("Detailed Review:", options=df['name'].tolist(), label_visibility="collapsed")
        
        item = next(c for c in st.session_state.results if c['name'] == selected_name)
        orig_file = next(f for f in st.session_state.cv_data if f['name'] == item['filename'])

        # Detailed Stats
        st.markdown(f"**Verdict:** {item['verdict']}")
        
        c_left, c_right = st.columns(2)
        c_left.success("**Strengths**\n\n" + "\n".join([f"- {s}" for s in item['strengths']]))
        c_right.warning("**Gaps**\n\n" + "\n".join([f"- {g}" for g in item['gaps']]))
        
        st.divider()
        # WORKING ALTERNATIVE TO VIEWER: Direct Verified Access
        st.markdown("##### 📄 Verify Original Document")
        st.download_button(
            label=f"Open {item['filename']}",
            data=orig_file['content'],
            file_name=item['filename'],
            mime="application/pdf",
            use_container_width=True
        )
