import streamlit as st
from streamlit_chat import message
import time

# ---------- Page Config ----------
st.set_page_config(
    page_title="AI Document Chatbot",
    page_icon="🤖",
    layout="wide"
)

# ---------- Custom CSS (Light + Dark Mode) ----------
st.markdown("""
<style>
    :root {
        --primary: #4F46E5;
        --bg-light: #F9FAFB;
        --text-light: #111827;
        --bg-dark: #0F172A;
        --text-dark: #E5E7EB;
    }

    .main-title {
        font-size: 38px;
        font-weight: 800;
        color: var(--primary);
        text-align: center;
    }
    .subtitle {
        text-align: center;
        font-size: 17px;
        margin-bottom: 25px;
        color: #6B7280;
    }
    .chat-container {
        padding: 20px;
        border-radius: 15px;
        height: 470px;
        overflow-y: auto;
        background: #F1F5F9;
    }
    .sidebar-box {
        background: #EEF2FF;
        border-radius: 14px;
        padding: 15px;
    }
    .status-badge {
        display: inline-block;
        padding: 5px 12px;
        border-radius: 30px;
        background: #DCFCE7;
        color: #166534;
        font-size: 13px;
        margin-top: 10px;
    }
    .footer-text {
        text-align: center;
        font-size: 13px;
        color: #9CA3AF;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ---------- Session State ----------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "doc_status" not in st.session_state:
    st.session_state.doc_status = "No documents uploaded"

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("## ⚙️ Control Panel")

    st.markdown('<div class="sidebar-box">', unsafe_allow_html=True)

    st.toggle("🌙 Dark Mode", key="dark_mode")

    uploaded_files = st.file_uploader(
        "📂 Upload documents",
        accept_multiple_files=True
    )

    if st.button("📥 Process Documents"):
        with st.spinner("Processing documents..."):
            time.sleep(2)
            st.session_state.doc_status = "✅ Documents processed"

    st.markdown(
        f'<div class="status-badge">{st.session_state.doc_status}</div>',
        unsafe_allow_html=True
    )

    st.markdown('</div>', unsafe_allow_html=True)


# ---------- Main Section ----------
st.markdown('<div class="main-title">AI Document Chatbot 🤖</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Smart answers from your uploaded documents</div>', unsafe_allow_html=True)

# ---------- Chat Box ----------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

for i, chat in enumerate(st.session_state.chat_history):
    if chat["role"] == "user":
        message(chat["content"], is_user=True, key=f"user_{i}")
    else:
        message(chat["content"], key=f"bot_{i}")

st.markdown('</div>', unsafe_allow_html=True)

# ---------- Input Section ----------
col1, col2 = st.columns([4, 1])
with col1:
    user_input = st.text_input("💬 Ask your question...")

with col2:
    send = st.button("🚀 Send")

# ---------- Bot Logic (Simulated Typing Effect) ----------
if send and user_input:
    st.session_state.chat_history.append(
        {"role": "user", "content": user_input}
    )

    # Simulated typing
    bot_placeholder = st.empty()
    response = "Analyzing documents and generating a response..."

    typed_text = ""
    for char in response:
        typed_text += char
        time.sleep(0.02)
        bot_placeholder.markdown(f"**🤖 {typed_text}**")

    st.session_state.chat_history.append(
        {"role": "bot", "content": response}
    )

    st.rerun()

# ---------- Footer ----------
st.markdown(
    '<div class="footer-text">Powered by LLM + RAG Technology</div>',
    unsafe_allow_html=True
)
