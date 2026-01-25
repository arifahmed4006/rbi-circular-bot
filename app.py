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

# --- PROFESSIONAL CSS STYLING (UI Enhancement) ---
st.markdown("""
<style>
    /* Global Font & Colors */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Main Background */
    .stApp {
        background-color: #f8fafc; /* Very light blue-grey for enterprise feel */
    }
    
    /* HERO HEADER STYLING */
    .hero-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); /* Dark Navy/Slate */
        padding: 2.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        border: 1px solid #334155;
    }
    .hero-title {
        color: #ffffff;
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 1rem;
        margin-top: 8px;
        font-weight: 400;
    }

    /* SIDEBAR STYLING */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    .sidebar-label {
        color: #64748b;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }
    .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        background-color: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 9999px;
        color: #15803d;
        font-size: 0.85rem;
        font-weight: 500;
        width: 100%;
        justify-content: center;
    }
    
    /* CHAT MESSAGE STYLING */
    .stChatMessage {
        background-color: transparent;
        border: none;
    }
    
    /* User Message */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #f1f5f9;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid #e2e8f0;
    }
    
    /* Assistant Message */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(even) {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }

    /* SOURCE CARD STYLING */
    .source-box {
        background-color: #f8fafc;
        border-left: 4px solid #3b82f6; /* Enterprise Blue */
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
    .source-box a:hover {
        text-decoration: underline;
        color: #2563eb;
    }
    .source-date {
        color: #64748b;
        font-size: 0.8rem;
        margin-top: 4px;
    }

    /* CHIP SUGGESTIONS (Non-functional UI) */
    .chip-container {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin-top: 1rem;
    }
    .chip {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 0.85rem;
        color: #475569;
        cursor: default;
        transition: all 0.2s;
    }
    .chip:hover {
        border-color: #cbd5e1;
        background-color: #f8fafc;
    }
</style>
""", unsafe_allow_html=True)

# 2. Setup Connections
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"⚠️ System Error: {e}")
    st.stop()

# 3. Model Selector (Logic Unchanged)
@st.cache_resource
def get_chat_model_name():
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for preferred in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']:
            if preferred in available_models: return preferred
        return available_models[0] if available_models else "models/gemini-pro"
    except:
        return "models/gemini-pro"

chat_model_name = get_chat_model_name()

# --- SIDEBAR: CONTROL CENTER (UI Enhancement) ---
with st.sidebar:
    st.markdown('<div style="padding-bottom: 20px;">', unsafe_allow_html=True)
    st.markdown("### 🎛️ Control Center")
    
    st.markdown('<p class="sidebar-label">SYSTEM STATUS</p>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="status-badge">
            🟢 Online &bull; Gemini Flash
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    st.markdown('<p class="sidebar-label">DATA SCOPE</p>', unsafe_allow_html=True)
    st.info("📚 **RBI Circulars**\n\nRange: 2025 – Present")
    
    st.markdown('<p class="sidebar-label">UTILITIES</p>', unsafe_allow_html=True)
    if st.button("🗑️ Clear Conversation", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    st.caption(f"**Version:** 2.1.0 (2026)\n**Architecture:** RAG + Vector DB\n**Engine:** `{chat_model_name.split('/')[-1]}`")
    st.markdown('</div>', unsafe_allow_html=True)

# --- MAIN PANEL: HEADER (UI Enhancement) ---
# Using a clean column layout to center the chat interface
col_spacer1, col_main, col_spacer2 = st.columns([1, 10, 1])

with col_main:
    st.markdown(
        """
        <div class="hero-header">
            <div class="hero-title">
                🏛️ RBI Regulatory Intelligence
            </div>
            <div class="hero-subtitle">
                Semantic search & conversational intelligence over RBI circulars (2025–present)
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # --- CHAT LOGIC ---
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # EMPTY STATE UI (UX Enhancement)
    if not st.session_state.messages:
        st.markdown(
            """
            <div style="text-align: center; padding: 40px 20px; color: #475569;">
                <h4>👋 Welcome to Regulatory Intelligence</h4>
                <p style="font-size: 0.95rem;">I can help you navigate complex RBI regulations, find specific circulars, and summarize compliance requirements.</p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        # Visual-only chips as requested (no logic attached to keep code safe)
        st.markdown('<p style="font-size:0.8rem; color:#64748b; margin-bottom:10px;">TRY ASKING ABOUT:</p>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="chip-container">
                <div class="chip">📝 Latest KYC Master Directions</div>
                <div class="chip">💳 Digital Lending Guidelines 2025</div>
                <div class="chip">🛡️ Cyber Security Framework</div>
                <div class="chip">🏠 Housing Finance Rules</div>
            </div>
            <br>
            """, 
            unsafe_allow_html=True
        )

    # Display History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Render Sources Card (UI Enhancement)
            if "sources" in msg and msg["sources"]:
                with st.expander("📚 Verified References", expanded=False):
                    for source in msg["sources"]:
                        st.markdown(
                            f"""
                            <div class="source-box">
                                <a href="{source['url']}" target="_blank">📄 {source['title']}</a>
                                <div class="source-date">Published: {source['date']}</div>
                            </div>
                            """, 
                            unsafe_allow_html=True
                        )

    # --- CHAT INPUT (UI Enhancement) ---
    # Sticky bottom placement is handled by Streamlit default behavior
    if prompt := st.chat_input("Ask about KYC, Loans, Cyber Security, Digital Lending, Payments, etc."):
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            # Subtle loading state (UX Enhancement)
            with st.spinner("🔍 Searching regulatory database..."):
                # A. Embed
                try:
                    vector = genai.embed_content(model="models/text-embedding-004", content=prompt, task_type="retrieval_query")['embedding']
                except:
                    vector = []

                # B. Search
                context_text = ""
                sources = []
                if vector:
                    try:
                        response = supabase.rpc("match_documents", {
                            "query_embedding": vector, "match_threshold": 0.4, "match_count": 10
                        }).execute()
                        
                        matches = response.data
                        seen_urls = set()
                        if matches:
                            for match in matches:
                                title = match.get('title', 'Unknown')
                                url = match.get('url', '#')
                                date = match.get('published_date', 'Unknown')
                                
                                context_text += f"\n---\nTitle: {title}\nDate: {date}\nExcerpt: {match.get('content', '')}\n"
                                
                                if url not in seen_urls:
                                    sources.append({"title": title, "url": url, "date": date})
                                    seen_urls.add(url)
                    except Exception as e:
                        st.error(f"Database Connection Error: {e}")

                if not context_text:
                    context_text = "No specific circulars found."

                # C. Generate
                try:
                    model = genai.GenerativeModel(chat_model_name)
                    full_prompt = f"""
                    You are a senior banking regulatory consultant. 
                    Answer the user's question using ONLY the provided RBI circulars.
                    
                    Guidelines:
                    1. Be authoritative, concise, and accurate.
                    2. Use clear headings and bullet points.
                    3. If the answer is not in the circulars, clearly state that.
                    
                    USER QUESTION: {prompt}
                    CONTEXT: {context_text}
                    """
                    ai_response = model.generate_content(full_prompt)
                    answer = ai_response.text
                except:
                    answer = "System is experiencing high load. Please try again."

                # D. Render Response
                message_placeholder.markdown(answer)
                
                # Render Sources Card immediately after response
                if sources:
                    with st.expander("📚 Verified References", expanded=False):
                        for source in sources:
                            st.markdown(
                                f"""
                                <div class="source-box">
                                    <a href="{source['url']}" target="_blank">📄 {source['title']}</a>
                                    <div class="source-date">Published: {source['date']}</div>
                                </div>
                                """, 
                                unsafe_allow_html=True
                            )

                # Save to history
                st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
