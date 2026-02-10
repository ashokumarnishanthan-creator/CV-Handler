import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
import json
import time
from io import BytesIO
from streamlit_google_picker import google_picker
from streamlit_oauth import OAuth2Component

# --- 1. CONFIG & UI ---
st.set_page_config(page_title="TalentScan Pro", layout="wide", page_icon="🎯")

# Ensure Secrets are present
if not all(k in st.secrets for k in ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_API_KEY"]):
    st.error("Missing Google Secrets! Please add Client ID, Secret, and API Key to secrets.toml")
    st.stop()

# --- 2. GOOGLE OAUTH 2.0 SETUP ---
CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
# Scope needed for Picker
SCOPE = "https://www.googleapis.com/auth/drive.readonly"

oauth2 = OAuth2Component(CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL, TOKEN_URL, SCOPE)

# --- 3. SESSION STATE ---
if 'cv_sources' not in st.session_state:
    st.session_state.cv_sources = []
if 'token' not in st.session_state:
    st.session_state.token = None

# --- 4. LOGIN / AUTH FLOW ---
with st.sidebar:
    st.title("Settings")
    if not st.session_state.token:
        # Show login button if not authenticated
        result = oauth2.authorize_button(
            name="Login with Google",
            icon="https://www.google.com/favicon.ico",
            redirect_uri="https://share.streamlit.io/oauth2callback",
            scope=SCOPE,
            key="google_auth"
        )
        if result and 'token' in result:
            st.session_state.token = result['token']
            st.rerun()
    else:
        st.success("Authenticated with Google")
        if st.button("Logout"):
            st.session_state.token = None
            st.rerun()

# --- 5. MAIN UI & PICKER ---
st.header("🚀 AI Talent Scout")

if st.session_state.token:
    access_token = st.session_state.token.get("access_token")
    
    # TRIGGER THE PICKER
    # Parameters: token (REQUIRED), apiKey, appId, type (singular)
    picked_files = google_picker(
        label="📂 Pick from Google Drive",
        token=access_token,
        apiKey=st.secrets["GOOGLE_API_KEY"],
        appId=CLIENT_ID.split("-")[0],
        multiselect=True,
        type=["pdf"], # Parameter must be 'type'
        key="drive_picker"
    )

    if picked_files:
        for pf in picked_files:
            if not any(cv['name'] == pf['name'] for cv in st.session_state.cv_sources):
                st.session_state.cv_sources.append({"name": pf['name'], "content": pf['content']})
        st.toast("Files added successfully!")

# ... (rest of your AI shortlisting logic below)
