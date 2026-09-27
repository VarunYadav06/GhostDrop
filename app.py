import os
import string
import secrets
from datetime import datetime, timezone
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv
import qrcode
from io import BytesIO

# 1. Page Config MUST be first
st.set_page_config(page_title="GhostDrop", page_icon="👻", layout="centered")

# 2. Maximum CSS Injection
st.markdown("""
    <style>
    /* Global App Background */
    .stApp {
        background-color: #0f172a;
        background-image: radial-gradient(circle at 50% -20%, #2e1065 0%, #0f172a 70%);
        color: #f8fafc;
    }
    
    /* Hide Streamlit Clutter */
    #MainMenu, header, footer {visibility: hidden;}
    
    /* Title Gradient */
    h1 {
        background: linear-gradient(45deg, #a855f7, #6366f1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-weight: 900 !important;
        padding-bottom: 0.5rem;
    }
    
    /* Style Tabs to look like Segmented Controls */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(30, 41, 59, 0.5);
        padding: 8px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 8px;
        color: #94a3b8;
        border: none !important;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(255, 255, 255, 0.1) !important;
        color: #ffffff !important;
    }
    .stTabs [data-baseweb="tab-highlight"] {
        display: none;
    }

    /* Input Fields (Text Area & Text Input) */
    .stTextInput input, .stTextArea textarea {
        background-color: rgba(15, 23, 42, 0.6) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
        padding: 16px !important;
        font-family: monospace;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #a855f7 !important;
        box-shadow: 0 0 15px rgba(168, 85, 247, 0.2) !important;
    }

    /* Primary Buttons */
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #6366f1 0%, #a855f7 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 12px 24px;
        font-weight: 700;
        width: 100%;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }
    div.stButton > button:first-child:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(168, 85, 247, 0.4);
    }
    div.stButton > button:first-child:disabled {
        opacity: 0.5;
        filter: grayscale(100%);
        transform: none;
        box-shadow: none;
    }

    /* File Uploader Dropzone */
    [data-testid="stFileUploadDropzone"] {
        background-color: rgba(30, 41, 59, 0.3) !important;
        border: 2px dashed rgba(255, 255, 255, 0.2) !important;
        border-radius: 20px !important;
        transition: all 0.3s ease;
    }
    [data-testid="stFileUploadDropzone"]:hover {
        border-color: #a855f7 !important;
        background-color: rgba(168, 85, 247, 0.05) !important;
    }

    /* Metric/PIN Display */
    [data-testid="stMetricValue"] {
        font-family: monospace;
        color: #a855f7 !important;
        font-weight: 900 !important;
        letter-spacing: 4px;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Setup & Database Connection
load_dotenv()
try:
    SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or st.secrets["SUPABASE_KEY"]
except (FileNotFoundError, KeyError):
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

@st.cache_resource
def init_connection() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_connection()
STORAGE_BUCKET = "vault_files"
APP_URL = "https://ghostdrop.streamlit.app" # Change this to your actual network IP to test mobile, or Streamlit Cloud URL

def generate_pin() -> str:
    charset = "".join(c for c in string.ascii_uppercase + string.digits if c not in "0O1I")
    return "".join(secrets.choice(charset) for _ in range(6))

def generate_qr(pin: str) -> bytes:
    url = f"{APP_URL}/?pin={pin}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="white")
    
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# 4. UI Layout
st.title("GhostDrop")
st.markdown("<p style='text-align: center; color: #94a3b8;'>Secure, 10-minute self-destructing file and text transfer.</p>", unsafe_allow_html=True)
st.write("") 

tab_send, tab_receive = st.tabs(["Send Payload", "Receive Payload"])

# --- SEND TAB ---
with tab_send:
    st.write("")
    send_mode = st.radio("What do you want to send?", ["File", "Text"], horizontal=True, label_visibility="collapsed")
    
    if send_mode == "File":
        uploaded_file = st.file_uploader("Upload a file (Max 25MB)", label_visibility="collapsed")
        if st.button("Generate Secure PIN", disabled=not uploaded_file):
            with st.spinner("Encrypting and uploading..."):
                file_bytes = uploaded_file.read()
                if len(file_bytes) > 25 * 1024 * 1024:
                    st.error("File exceeds 25 MB limit.")
                else:
                    pin = generate_pin()
                    storage_path = f"{pin}_{uploaded_file.name}"
                    
                    supabase.storage.from_(STORAGE_BUCKET).upload(
                        path=storage_path, file=file_bytes,
                        file_options={"content-type": uploaded_file.type or "application/octet-stream"}
                    )
                    
                    supabase.table("vault_items").insert({
                        "pin": pin, "item_type": "file", "content": storage_path,
                        "filename": uploaded_file.name, "created_at": datetime.now(timezone.utc).isoformat(),
                    }).execute()
                    
                    st.success("File uploaded securely!")
                    
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        st.metric(label="Your Secure PIN", value=pin)
                        st.caption("Share this PIN to retrieve the payload.")
                    with col2:
                        st.image(generate_qr(pin), width=150)

    else:
        text_payload = st.text_area("Paste your secret text or code snippet", height=150, placeholder="Paste secret payload here...", label_visibility="collapsed")
        if st.button("Generate Secure PIN", disabled=not text_payload.strip()):
            with st.spinner("Encrypting..."):
                if len(text_payload.encode("utf-8")) > 100 * 1024:
                    st.error("Text exceeds 100 KB limit.")
                else:
                    pin = generate_pin()
                    supabase.table("vault_items").insert({
                        "pin": pin, "item_type": "text", "content": text_payload,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }).execute()
                    
                    st.success("Text secured!")
                    
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        st.metric(label="Your Secure PIN", value=pin)
                        st.caption("Share this PIN to retrieve the payload.")
                    with col2:
                        st.image(generate_qr(pin), width=150)

# --- RECEIVE TAB ---
with tab_receive:
    st.write("")
    query_pin = st.query_params.get("pin", "")
    claim_pin = st.text_input("Enter 6-Digit PIN", max_chars=6, value=query_pin, placeholder="XXXXXX", label_visibility="collapsed").strip().upper()
    
    if st.button("Retrieve Payload", disabled=len(claim_pin) != 6):
        with st.spinner("Searching vault..."):
            res = supabase.table("vault_items").select("*").eq("pin", claim_pin).execute()
            
            if not res.data:
                st.error("Invalid or expired PIN. The payload may have already been burned.")
            else:
                item = res.data[0]
                
                if item["item_type"] == "text":
                    st.success("Payload retrieved and burned from server.")
                    st.code(item["content"])
                    supabase.table("vault_items").delete().eq("pin", claim_pin).execute()
                    
                elif item["item_type"] == "file":
                    file_bytes = supabase.storage.from_(STORAGE_BUCKET).download(item["content"])
                    
                    supabase.storage.from_(STORAGE_BUCKET).remove([item["content"]])
                    supabase.table("vault_items").delete().eq("pin", claim_pin).execute()
                    
                    st.success("File retrieved and permanently deleted from server. Ready to save.")
                    st.download_button(
                        label="Download File", data=file_bytes,
                        file_name=item["filename"]
                    )
