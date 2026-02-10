import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time
from io import BytesIO

# --- 1. CONFIGURATION & UI ---
st.set_page_config(page_title="TalentScan Pro", layout="wide", page_icon="🔍")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .main-header { font-size: 2.5rem; font-weight: 800; color: #1e293b; margin-bottom: 1.5rem; }
    .status-box { padding: 10px; border-radius: 8px; border: 1px solid #e2e8f0; background: white; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SIDEBAR (AUTHENTICATION) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1055/1055644.png", width=70)
    st.title("TalentScan Settings")
    
    # Securely retrieve API Key
    api_key_secret = st.secrets.get("GEMINI_API_KEY", "")
    api_key_input = st.text_input("Enter Gemini API Key", value=api_key_secret, type="password")
    
    st.divider()
    st.info("💡 **Pro Tip:** If using the Free Tier, wait 2-3 seconds between batches to avoid 429 errors.")

# --- 3. MAIN DASHBOARD ---
st.markdown('<div class="main-header">🚀 AI Recruitment Dashboard</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📋 Job Description", "📊 CV Analysis & Ranking"])

with tab1:
    jd_input = st.text_area("Paste the Job Requirements (JD):", height=300, 
                            placeholder="e.g. Seeking a Senior Developer with experience in Python and AWS...")

with tab2:
    col_u, col_d = st.columns([1, 1])
    with col_u:
        uploaded_files = st.file_uploader("Upload CVs (PDF Only)", accept_multiple_files=True, type=['pdf'])
    
    with col_d:
        st.write("---")
        st.caption("Google Drive Sync")
        st.markdown("To analyze Drive files, select them via your synced **local folder** in the uploader above.")

    # --- 4. ENGINE (SHORTLISTING LOGIC) ---
    if st.button("⚡ Start AI Analysis"):
        if not api_key_input:
            st.error("Please provide an API Key in the sidebar.")
        elif not jd_input or not uploaded_files:
            st.warning("Please provide both a JD and at least one CV.")
        else:
            # Initialize Gemini
            genai.configure(api_key=api_key_input)
            model = genai.GenerativeModel(
                model_name='gemini-2.0-flash',
                generation_config={"response_mime_type": "application/json"}
            )
            
            final_data = []
            progress_bar = st.progress(0)
            status_container = st.empty()

            for i, file in enumerate(uploaded_files):
                filename = file.name
                status_container.info(f"Processing ({i+1}/{len(uploaded_files)}): {filename}")
                
                try:
                    # A. Robust PDF Extraction
                    reader = PdfReader(file)
                    # Use only first 3 pages to be cost-effective and avoid token limits
                    raw_text = " ".join([page.extract_text() for page in reader.pages[:3] if page.extract_text()])
                    
                    if not raw_text.strip():
                        st.error(f"Failed to read text from {filename}. Skipping.")
                        continue

                    # B. Strict AI Prompt
                    prompt = f"""
                    Compare the CV to the Job Description provided.
                    Return a JSON object with EXACTLY these keys: "name", "score", "verdict".
                    "score" must be a whole number (0-100). 
                    "verdict" must be a 1-sentence fit summary.
                    
                    JD: {jd_input}
                    CV TEXT: {raw_text}
                    """
                    
                    response = model.generate_content(prompt)
                    
                    # C. Schema Enforcement (Fixes "list index" and "KeyError")
                    raw_json = json.loads(response.text)
                    
                    # If AI returns a list [{"name":...}], pick the first object
                    if isinstance(raw_json, list):
                        raw_json = raw_json[0]
                    
                    # Standardize keys to lowercase
                    analysis = {k.lower(): v for k, v in raw_json.items()}
                    
                    # Ensure essential keys exist
                    shortlist_entry = {
                        "name": analysis.get("name", filename),
                        "score": analysis.get("score", 0),
                        "verdict": analysis.get("verdict", "No summary provided.")
                    }
                    
                    final_data.append(shortlist_entry)
                    
                    # D. Rate Limit Protection (Trial Tier Safety)
                    time.sleep(1.5)

                except Exception as e:
                    if "429" in str(e):
                        st.error(f"Rate Limit reached at {filename}. Waiting 10s...")
                        time.sleep(10)
                    else:
                        st.error(f"System error on {filename}: {str(e)}")
                
                progress_bar.progress((i + 1) / len(uploaded_files))

            status_container.success("🎯 Analysis Complete!")

            # --- 5. RESULTS DISPLAY ---
            if final_data:
                df = pd.DataFrame(final_data)
                
                # Double-check "score" is numeric for sorting
                df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0)
                df = df.sort_values(by="score", ascending=False)
                
                st.divider()
                st.subheader("📊 Candidate Ranking Table")
                st.dataframe(
                    df,
                    use_container_width=True,
                    column_config={
                        "score": st.column_config.ProgressColumn("Match", min_value=0, max_value=100, format="%d%%"),
                        "name": "Candidate Name",
                        "verdict": st.column_config.TextColumn("AI Evaluation", width="large")
                    }
                )
                
                # Export functionality
                csv_data = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Results (CSV)", data=csv_data, file_name="cv_shortlist.csv", mime="text/csv")
            else:
                st.info("No data to display. Please ensure PDFs are readable.")
