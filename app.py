import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="TalentScan Pro", layout="wide", page_icon="🔍")

# Professional UI Styling
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stMetricValue"] { font-size: 1.8rem; color: #1e40af; }
    .main-header { font-size: 2.5rem; font-weight: 800; color: #1e293b; margin-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. AUTHENTICATION & SECRETS ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1055/1055644.png", width=80)
    st.title("Control Panel")
    
    # Priority: 1. Sidebar Input, 2. Streamlit Secrets
    api_key_input = st.text_input("Gemini API Key", type="password")
    gemini_key = api_key_input if api_key_input else st.secrets.get("GEMINI_API_KEY", "")
    
    st.divider()
    st.markdown("### ⚙️ Engine")
    st.info("Model: **Gemini 2.0 Flash**\n\nRate Limit: 15 RPM (Free) / 2000 RPM (Paid)")

# --- 3. UI TABS ---
st.markdown('<div class="main-header">🚀 AI Recruitment Dashboard</div>', unsafe_allow_html=True)
jd_tab, analysis_tab = st.tabs(["📌 Job Requirement", "📊 Candidate Ranking"])

with jd_tab:
    st.subheader("Define the Ideal Candidate")
    jd_input = st.text_area("Paste the Job Description (JD) here:", height=300, 
                            placeholder="e.g. Seeking a Python Developer with 3 years experience...")

with analysis_tab:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Source Materials")
        uploaded_files = st.file_uploader("Upload CVs (PDF Only)", accept_multiple_files=True, type=['pdf'])
    
    with col2:
        st.subheader("Cloud Integration")
        st.write("To analyze Google Drive files, ensure your Drive is synced to your PC or use the local uploader.")
        if st.button("📁 Folder Sync Instructions"):
            st.info("Best practice: Open your local Google Drive folder in the uploader to avoid API permission errors.")

    # --- 4. CORE PROCESSING LOGIC ---
    if st.button("⚡ Start AI Shortlisting"):
        if not gemini_key:
            st.error("Missing Gemini API Key! Please enter it in the sidebar.")
        elif not jd_input:
            st.warning("Please provide a Job Description.")
        elif not uploaded_files:
            st.warning("Please upload at least one CV.")
        else:
            # Configure API
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(
                model_name='gemini-2.0-flash',
                generation_config={"response_mime_type": "application/json"}
            )
            
            final_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, file in enumerate(uploaded_files):
                # UI Update
                current_name = file.name
                status_text.text(f"Analyzing {i+1}/{len(uploaded_files)}: {current_name}")
                
                try:
                    # A. PDF TEXT EXTRACTION
                    reader = PdfReader(file)
                    # Limit to first 3 pages to save tokens and avoid errors
                    cv_text = " ".join([page.extract_text() for page in reader.pages[:3] if page.extract_text()])
                    
                    if not cv_text.strip():
                        st.error(f"Skipping {current_name}: No readable text found.")
                        continue

                    # B. AI ANALYSIS
                    prompt = f"""
                    Act as an HR expert. Compare the CV to the JD. 
                    Return ONLY JSON with these keys: "name", "score", "verdict".
                    
                    JD: {jd_input}
                    CV Text: {cv_text}
                    """
                    
                    response = model.generate_content(prompt)
                    
                    # C. SAFE JSON PARSING
                    try:
                        # Ensure we handle the response text safely
                        analysis = json.loads(response.text)
                        # Fallback if name is missing from AI
                        if "name" not in analysis or analysis["name"] == "Candidate Name":
                            analysis["name"] = current_name
                        
                        final_results.append(analysis)
                    except json.JSONDecodeError:
                        st.error(f"AI returned invalid format for {current_name}")

                    # D. RATE LIMIT PROTECTION (Important for Free Trials)
                    time.sleep(2) 

                except Exception as e:
                    if "429" in str(e):
                        st.error("🚦 Rate Limit Reached. Pausing for 10 seconds...")
                        time.sleep(10)
                    else:
                        st.error(f"Error processing {current_name}: {str(e)}")
                
                # Update progress
                progress_bar.progress((i + 1) / len(uploaded_files))

            status_text.success("✅ Analysis Complete!")

            # --- 5. DATA VISUALIZATION ---
            if final_results:
                df = pd.DataFrame(final_results)
                
                # Force Score to Numeric (Removes "KeyError: score" issues)
                df.columns = df.columns.str.strip().str.lower()
                if 'score' in df.columns:
                    df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0)
                    df = df.sort_values(by="score", ascending=False)
                
                st.divider()
                st.subheader("🏆 Candidate Rankings")
                
                # Beautiful Table Display
                st.dataframe(
                    df,
                    use_container_width=True,
                    column_config={
                        "score": st.column_config.ProgressColumn(
                            "Match Score", min_value=0, max_value=100, format="%d%%"
                        ),
                        "verdict": st.column_config.TextColumn("AI Insight", width="large"),
                        "name": "Candidate Name"
                    }
                )
                
                # CSV Export
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Shortlist Report",
                    data=csv,
                    file_name="ai_recruitment_report.csv",
                    mime="text/csv",
                )
            else:
                st.info("No candidates were successfully analyzed.")
