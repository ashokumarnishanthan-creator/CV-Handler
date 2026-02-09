import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json

# --- CONFIG & STYLING ---
st.set_page_config(page_title="TalentScan AI", layout="wide", page_icon="🔍")

# Injecting Custom CSS for a modern "SaaS" look
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .css-1r6slb0 { background-color: white; border-radius: 15px; padding: 2rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    .main-header { font-size: 2.5rem; font-weight: 800; color: #1e293b; margin-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR & KEYS ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1055/1055644.png", width=100)
    st.title("TalentScan Settings")
    gemini_key = st.text_input("Gemini API Key", type="password")
    # For a rookie, we'll stick to a simple upload but mention Drive integration below
    st.divider()
    st.info("💡 To use Google Drive, ensure your API keys are set in Streamlit Secrets.")

# --- MAIN INTERFACE ---
st.markdown('<div class="main-header">🚀 AI Recruitment Dashboard</div>', unsafe_allow_html=True)

jd_tab, analysis_tab = st.tabs(["📌 Job Requirement", "📊 Candidate Ranking"])

with jd_tab:
    jd_input = st.text_area("Paste Job Description Here", height=300, placeholder="Required skills, years of experience...")

with analysis_tab:
    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_files = st.file_uploader("Upload CVs", accept_multiple_files=True, type=['pdf'])
    with col2:
        st.write("--- or ---")
        # In a real cloud env, this button triggers the Google Picker pop-up
        if st.button("📁 Import from Google Drive"):
            st.warning("Cloud integration requires OAuth setup. Currently using Local Upload.")

    if st.button("⚡ Start Shortlisting") and jd_input and uploaded_files:
        if not gemini_key:
            st.error("Missing Gemini API Key!")
        else:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            final_data = []
            progress_bar = st.progress(0)
            
            for i, file in enumerate(uploaded_files):
                # 1. Extract Text
                reader = PdfReader(file)
                cv_text = " ".join([page.extract_text() for page in reader.pages])
                
                # 2. AI Analysis
                prompt = f"""
Act as a professional recruiter. Compare this CV to the Job Description.
RETURN ONLY A JSON OBJECT. DO NOT INCLUDE MARKDOWN BLOCKS.
Expected JSON Keys: 
"name": Candidate full name
"score": A number from 0-100
"verdict": A 1-sentence summary

JD: {jd_text}
CV: {cv_text}
"""
                """
                response = model.generate_content(prompt)
                
                # 3. Parse and Store
                try:
                    # Cleaning common AI markdown artifacts
                    clean_json = response.text.replace('```json', '').replace('```', '')
                    final_data.append(json.loads(clean_json))
                except:
                    st.error(f"Error parsing {file.name}")
                
                progress_bar.progress((i + 1) / len(uploaded_files))



# Convert the list of AI results into a DataFrame
df = pd.DataFrame(results)

if not df.empty:
    # 1. Clean column names (remove spaces and make lowercase)
    df.columns = df.columns.str.strip().str.lower()
    
    # 2. Safety Check: If 'score' is missing, look for common AI variations
    if 'score' not in df.columns:
        # Check if AI used "match_score", "ranking", or "fit_score"
        for alt in ['match_score', 'ranking', 'rating', 'fit_score']:
            if alt in df.columns:
                df = df.rename(columns={alt: 'score'})
                break
    
    # 3. Final Fallback: If 'score' is STILL missing, create it so the app doesn't crash
    if 'score' not in df.columns:
        st.warning("⚠️ AI provided inconsistent data. Adding a default score column.")
        df['score'] = 0
    
    # 4. Clean the Score (AI sometimes sends "85%" as a string; we need the number 85)
    df['score'] = pd.to_numeric(
        df['score'].astype(str).str.replace('%', '').str.strip(), 
        errors='coerce'
    ).fillna(0)

    # 5. Now it is safe to sort!
    df = df.sort_values(by="score", ascending=False)
    
    st.subheader("🏆 Ranked Candidates")
    st.dataframe(
        df, 
        use_container_width=True,
        column_config={
            "score": st.column_config.ProgressColumn("Match Score", min_value=0, max_value=100, format="%d%%")
        }
    )
else:
    st.error("❌ No candidates were analyzed successfully. Check your API key or CV text.")
    st.subheader("🏆 Ranked Candidates")
    st.dataframe(df, use_container_width=True)

            
            # 4. Display Results in a Beautiful Table
            df = pd.DataFrame(final_data)
            st.subheader("🏆 Ranked Candidates")
            st.dataframe(
                df.sort_values(by="score", ascending=False),
                column_config={
                    "score": st.column_config.ProgressColumn("Match Score", min_value=0, max_value=100),
                    "verdict": st.column_config.TextColumn("AI Summary", width="large")
                },
                use_container_width=True
            )
