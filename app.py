import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time
from io import BytesIO
from streamlit_google_picker import google_picker

# --- 1. MODERN UI CONFIGURATION ---
st.set_page_config(page_title="TalentScan Pro", layout="wide", page_icon="🎯")

# Modern CSS Injection
st.markdown("""
    <style>
    .stApp { background-color: #fcfcfd; }
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1e293b; letter-spacing: -0.5px; }
    .card { background: white; border-radius: 12px; padding: 20px; border: 1px solid #e2e8f0; }
    .stButton>button { border-radius: 8px; font-weight: 600; transition: all 0.3s; }
    .stButton>button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SIDEBAR & API SETUP ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3858/3858684.png", width=60) # Modern AI Icon
    st.title("TalentScan Settings")
    
    # Secure API Input
    gemini_key = st.text_input("Gemini API Key", value=st.secrets.get("GEMINI_API_KEY", ""), type="password")
    
    st.divider()
    st.caption("Environment Status")
    if gemini_key:
        st.success("AI Engine Ready")
    else:
        st.warning("Awaiting API Key")

# --- 3. MAIN INTERFACE ---
st.markdown('<div class="main-header">🚀 AI Talent Scout</div>', unsafe_allow_html=True)
st.write("Shortlist candidates using Gemini 2.0 Flash intelligence.")

tab_jd, tab_cv = st.tabs(["📋 Job Description", "📄 Candidate Analysis"])

with tab_jd:
    jd_input = st.text_area("Paste Requirements", height=300, placeholder="What are the key skills and experience needed?")

with tab_cv:
    # Action Icons/Buttons
    col_u, col_g = st.columns(2)
    
    cv_sources = [] # Container for file data

    with col_u:
        st.markdown("### 📤 Local Upload")
        local_files = st.file_uploader("Upload PDFs", accept_multiple_files=True, type=['pdf'], label_visibility="collapsed")
        if local_files:
            for f in local_files:
                cv_sources.append({"name": f.name, "content": f.read()})

    with col_g:
        st.markdown("### ☁️ Google Drive")
        # Modern Google Drive Icon usage
        if st.button("📂 Import from Drive", use_container_width=True):
            g_api = st.secrets.get("GOOGLE_API_KEY")
            g_client = st.secrets.get("GOOGLE_CLIENT_ID")
            
            if not g_api or not g_client:
                st.error("Google Drive keys missing in Secrets.")
            else:
                picked_files = google_picker(
                    apiKey=g_api, 
                    clientId=g_client, 
                    appId=g_client.split("-")[0],
                    multiselect=True, types=["pdf"]
                )
                if picked_files:
                    for pf in picked_files:
                        cv_sources.append({"name": pf['name'], "content": pf['content']})
                    st.toast(f"Imported {len(picked_files)} files from Drive!")

    st.divider()

    # --- 4. EXECUTION ENGINE ---
    if st.button("⚡ Run AI Shortlisting", type="primary", use_container_width=True):
        if not gemini_key:
            st.error("Please provide a Gemini API Key.")
        elif not jd_input or not cv_sources:
            st.warning("Missing JD or Candidate CVs.")
        else:
            # Init AI
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
            
            final_report = []
            status_placeholder = st.empty()
            progress_bar = st.progress(0)

            for idx, cv in enumerate(cv_sources):
                status_placeholder.info(f"Analyzing {cv['name']}...")
                
                try:
                    # Memory-safe PDF Extraction
                    reader = PdfReader(BytesIO(cv['content']))
                    # Extraction limited to top 2 pages (most relevant info) to prevent timeouts
                    text = " ".join([p.extract_text() for p in reader.pages[:2] if p.extract_text()])
                    
                    prompt = f"""
                    Analyze this CV against the JD. Return JSON ONLY.
                    Keys: "candidate_name", "match_score", "reasoning".
                    JD: {jd_input}
                    CV: {text}
                    """
                    
                    response = model.generate_content(prompt)
                    
                    if response.text:
                        data = json.loads(response.text)
                        # Handle potential list response
                        if isinstance(data, list): data = data[0]
                        # Fixes common naming mismatches
                        final_report.append({
                            "Name": data.get("candidate_name", cv['name']),
                            "Score": data.get("match_score", 0),
                            "Insight": data.get("reasoning", "N/A")
                        })
                    
                    # Rate Limit Buffer
                    time.sleep(1.2)
                    
                except Exception as e:
                    st.error(f"Error analyzing {cv['name']}: {e}")
                
                progress_bar.progress((idx + 1) / len(cv_sources))

            status_placeholder.empty()

            # --- 5. RESULTS ---
            if final_report:
                df = pd.DataFrame(final_report)
                df['Score'] = pd.to_numeric(df['Score'], errors='coerce').fillna(0)
                df = df.sort_values(by="Score", ascending=False)
                
                st.subheader("📊 Ranking Results")
                st.dataframe(
                    df, 
                    use_container_width=True,
                    column_config={
                        "Score": st.column_config.ProgressColumn("Match %", min_value=0, max_value=100, format="%d"),
                        "Insight": st.column_config.TextColumn("AI Evaluation", width="large")
                    }
                )
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Report", data=csv, file_name="shortlist.csv", mime="text/csv")
            else:
                st.error("No analysis was generated. Check API and CV content.")
