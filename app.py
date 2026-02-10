import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time

# --- CONFIG & STYLING ---
st.set_page_config(page_title="TalentScan AI", layout="wide", page_icon="🔍")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main-header { font-size: 2.5rem; font-weight: 800; color: #1e293b; margin-bottom: 1rem; }
    .card { background-color: white; border-radius: 15px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: AUTH & SETTINGS ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1055/1055644.png", width=80)
    st.title("Settings")
    
    # Best Practice: Try to get key from secrets first, else use input
    secret_key = st.secrets.get("GEMINI_API_KEY", "")
    api_key = st.text_input("Gemini API Key", value=secret_key, type="password")
    
    st.divider()
    st.info("📊 Model: Gemini 2.0 Flash\n\nSpeed: Optimized")

# --- MAIN INTERFACE ---
st.markdown('<div class="main-header">🚀 AI Recruitment Dashboard</div>', unsafe_allow_html=True)

jd_tab, analysis_tab = st.tabs(["📌 Job Requirement", "📊 Candidate Ranking"])

with jd_tab:
    jd_input = st.text_area("Paste Job Description Here", height=300, placeholder="Describe the ideal candidate...")

with analysis_tab:
    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_files = st.file_uploader("Upload CVs (PDF)", accept_multiple_files=True, type=['pdf'])
    with col2:
        st.write("---")
        st.caption("Cloud Storage (Google Drive) Integration")
        if st.button("📁 Import from Google Drive"):
            st.warning("To enable this, configure Google Picker API in your Cloud Console.")

    if st.button("⚡ Start Shortlisting"):
        if not api_key:
            st.error("Please provide a Gemini API Key in the sidebar.")
        elif not jd_input or not uploaded_files:
            st.warning("Please provide both a Job Description and at least one CV.")
        else:
            # Configure AI
            genai.configure(api_key=api_key)
            # Use JSON mode for best practices
            model = genai.GenerativeModel(
                model_name='gemini-2.0-flash',
                generation_config={"response_mime_type": "application/json"}
            )
            
            final_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, file in enumerate(uploaded_files):
                status_text.text(f"Analyzing: {file.name}...")
                
                try:
                    # 1. Extract Text
                    for i, file in enumerate(uploaded_files):
    try:
        # 1. SMART EXTRACTION
        # Check if 'file' is a dictionary (from Picker) or an object (from Upload)
        if isinstance(file, dict):
            # This handles the Google Picker data structure
            file_name = file.get("name", f"Candidate_{i}")
            # If using Picker, you need to download/access the bytes correctly
            # Note: For rookies, local upload is more stable than Picker bytes
            st.error(f"Google Picker requires additional API auth to read content.")
            continue 
        else:
            # This handles standard Streamlit UploadedFile
            file_name = file.name
            reader = PdfReader(file)
            cv_text = " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
                    # 2. AI Prompt
                    prompt = f"""
                    Act as an expert technical recruiter. Compare the CV to the Job Description.
                    Return a JSON object with:
                    - "name": Full name of candidate
                    - "score": Numeric match score (0-100)
                    - "verdict": Short professional fit summary
                    
                    JD: {jd_input}
                    CV: {cv_text}
                    """
                    
                    response = model.generate_content(prompt)
                    
                    # 3. Safe Parsing
                    res_json = json.loads(response.text)
                    # Ensure filename is added for reference
                    if "name" not in res_json or res_json["name"] == "Candidate Name":
                        res_json["name"] = file.name
                        
                    final_results.append(res_json)
                    
                except Exception as e:
                    st.error(f"Could not process {file.name}: {str(e)}")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.text("Analysis Complete!")

            # --- DATA PROCESSING & SORTING ---
            if final_results:
                df = pd.DataFrame(final_results)
                
                # Standardize Columns
                df.columns = df.columns.str.strip().str.lower()
                
                # Column check for 'score'
                if 'score' in df.columns:
                    df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0)
                    df = df.sort_values(by="score", ascending=False)
                
                st.subheader("🏆 Ranked Candidates")
                st.dataframe(
                    df,
                    use_container_width=True,
                    column_config={
                        "score": st.column_config.ProgressColumn("Match Score", min_value=0, max_value=100, format="%d%%"),
                        "verdict": st.column_config.TextColumn("AI Summary", width="large")
                    }
                )
                
                # Export Feature
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Report (CSV)", data=csv, file_name="shortlist_report.csv", mime="text/csv")
            else:
                st.error("No data could be extracted. Please check the PDF contents.")
