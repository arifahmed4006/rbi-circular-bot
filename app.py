import streamlit as st
import google.generativeai as genai
from supabase import create_client
import os
from dotenv import load_dotenv

# 1. Configuration & Secrets
load_dotenv()
st.set_page_config(
    page_title="RBI Regulatory Intelligence",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL CSS STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: #f8fafc;
    }
    
    /* Hero Header */
    .hero-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        color: white;
    }
    .hero-title {
        font-size: 1.8rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 1rem;
    }

    /* Message Styling */
    .stChatMessage {
        background-color: transparent;
        border: none;
    }
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #f1f5f9;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid #e2e8f0;
    }
    .stChatMessage[data-testid="stChatMessage"]:nth-child(even) {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }

    /* Sources */
    .source-box {
        background-color: #f8fafc;
        border-left: 4px solid #3b82f6;
        padding: 12px 16px;
        margin-top: 12px;
        border-radius: 0 4px 4px 0;
        font-size: 0.9rem;
    }
    .source-box a {
        color: #0f172a;
        font-weight: 600;
        text-decoration: none;
    }
    .source-date {
        color: #64748b;
        font-size: 0.8rem;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# 2. Setup
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"⚠️ System Error: {e}")
    st.stop()

@st.cache_resource
def get_chat_model_name():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        return next((m for m in ['models/gemini-1.5-flash', 'models/gemini-pro'] if m in models), "models/gemini-pro")
    except:
        return "models/gemini-pro"

chat_model_name = get_chat_model_name()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🎛️ Control Center")
    st.markdown("**SYSTEM STATUS**")
    st.markdown('<div style="background:#f0fdf4;color:#15803d;padding:4px 12px;border-radius:20px;text-align:center;font-weight:600;font-size:0.85rem;border:1px solid #bbf7d0;">🟢 Online</div>', unsafe_allow_html=True)
    st.markdown("**DATA SCOPE**\n\n📚 **RBI Circulars**\n(2025 – Present)")
    
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    st.caption(f"v2.1.0 • {chat_model_name.split('/')[-1]}")

# --- MAIN LAYOUT ---
# 1. The Header (Centered)
col_spacer1, col_main, col_spacer2 = st.columns([1, 10, 1])

with col_main:
    st.markdown("""
    <div class="hero-header">
        <div class="hero-title">🏛️ RBI Regulatory Intelligence</div>
        <div class="hero-subtitle">Semantic search & conversational intelligence over RBI circulars</div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Chat History (Centered)
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if not st.session_state.messages:
        st.info("👋 Welcome! Try asking about **KYC norms**, **Digital Lending**, or **Cyber Security**.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "sources" in msg and msg["sources"]:
                with st.expander("📚 Verified References"):
                    for source in msg["sources"]:
                        st.markdown(f"<div class='source-box'><a href='{source['url']}' target='_blank'>📄 {source['title']}</a><div class='source-date'>{source['date']}</div></div>", unsafe_allow_html=True)

# --- CHAT INPUT (THE FIX) ---
# IMPORTANT: This is now OUTSIDE the columns. 
# It sits at the root level, which forces it to be sticky at the bottom.
if prompt := st.chat_input("Ask a question about RBI regulations..."):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    # We must rerun to render the user message inside the column structure above
    st.rerun()

# --- LOGIC HANDLER ---
# This runs after the rerun to generate the response
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    
    # We need to re-enter the column context just for the "Thinking" spinner
    with col_main:
        last_prompt = st.session_state.messages[-1]["content"]
        
        with st.chat_message("assistant"):
            with st.spinner("🔍 Analyzing regulations..."):
                # Embed
                try:
                    vector = genai.embed_content(model="models/text-embedding-004", content=last_prompt, task_type="retrieval_query")['embedding']
                except:
                    vector = []
                
                # Search
                context_text = ""
                sources = []
                if vector:
                    try:
                        response = supabase.rpc("match_documents", {
                            "query_embedding": vector, "match_threshold": 0.4, "match_count": 10
                        }).execute()
                        for match in response.data:
                            title = match.get('title', 'Unknown')
                            url = match.get('url', '#')
                            date = match.get('published_date', 'Unknown')
                            context_text += f"\nTitle: {title}\nDate: {date}\nExcerpt: {match.get('content', '')}\n"
                            if url not in [s['url'] for s in sources]:
                                sources.append({"title": title, "url": url, "date": date})
                    except:
                        pass
                
                if not context_text: context_text = "No specific circulars found."

                # Generate
                try:
                    model = genai.GenerativeModel(chat_model_name)
                    ai_response = model.generate_content(f"You are an RBI expert. Answer using ONLY this context:\n\n{context_text}\n\nQuestion: {last_prompt}").text
                except:
                    ai_response = "System is busy. Please try again."

                # Save Response
                st.session_state.messages.append({"role": "assistant", "content": ai_response, "sources": sources})
                st.rerun() # Rerun one last time to show the AI response
