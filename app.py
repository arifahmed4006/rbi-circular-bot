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
    
    /* Footer Credit */
    .footer-credit {
        margin-top: 20px;
        font-size: 0.85rem;
        color: #64748b;
        border-top: 1px solid #e2e8f0;
        padding-top: 10px;
    }
    
    /* Flowchart Styling */
    .flow-header {
        font-size: 0.75rem;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        margin-top: 10px;
        margin-bottom: 5px;
        letter-spacing: 0.05em;
    }
    .flow-step {
        background-color: #ffffff;
        padding: 8px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        border: 1px solid #e2e8f0;
        margin-bottom: 4px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .tech-badge {
        font-size: 0.7rem;
        background-color: #f1f5f9;
        padding: 2px 6px;
        border-radius: 4px;
        color: #475569;
        font-weight: 600;
    }
    .flow-arrow {
        text-align: center;
        color: #cbd5e1;
        font-size: 0.8rem;
        line-height: 1;
        margin: 2px 0;
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

# 3. Model Selector (Trusted Logic)
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

# --- SIDEBAR (UPDATED) ---
with st.sidebar:
    st.markdown("### 🎛️ Control Center")
    st.markdown("**SYSTEM STATUS**")
    st.markdown('<div style="background:#f0fdf4;color:#15803d;padding:4px 12px;border-radius:20px;text-align:center;font-weight:600;font-size:0.85rem;border:1px solid #bbf7d0;">🟢 Online</div>', unsafe_allow_html=True)
    st.markdown("**DATA SCOPE**\n\n📚 **RBI Circulars**\n(2025 – Present)")
    
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    
    # --- NEW: SYSTEM ARCHITECTURE ---
    with st.expander("⚙️ System Architecture", expanded=False):
        
        # 1. Ingestion Pipeline
        st.markdown('<div class="flow-header">DATA INGESTION PIPELINE</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="flow-step">
            <span>🌐 <b>Browser Mimic</b></span>
            <span class="tech-badge">Playwright</span>
        </div>
        <div class="flow-arrow">⬇</div>
        <div class="flow-step">
            <span>📄 <b>Smart Chunking</b></span>
            <span class="tech-badge">Python</span>
        </div>
        <div class="flow-arrow">⬇</div>
        <div class="flow-step">
            <span>🔢 <b>Vector Embedding</b></span>
            <span class="tech-badge">Gemini 004</span>
        </div>
        <div class="flow-arrow">⬇</div>
        <div class="flow-step">
            <span>💾 <b>Vector Storage</b></span>
            <span class="tech-badge">Supabase</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("")
        
        # 2. Retrieval Pipeline
        st.markdown('<div class="flow-header">RAG INFERENCE PIPELINE</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="flow-step">
            <span>🔍 <b>Semantic Search</b></span>
            <span class="tech-badge">Cosine Sim</span>
        </div>
        <div class="flow-arrow">⬇</div>
        <div class="flow-step">
            <span>🧩 <b>Context Ranking</b></span>
            <span class="tech-badge">RAG Algorithm</span>
        </div>
        <div class="flow-arrow">⬇</div>
        <div class="flow-step">
            <span>🤖 <b>Synthesis</b></span>
            <span class="tech-badge">Gemini 1.5</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    
    # --- CREATOR CREDIT ---
    st.markdown(
        """
        <div class="footer-credit">
            <b>v2.3.0</b> • Engine: <code>""" + chat_model_name.split('/')[-1] + """</code><br>
            Created by <b>Shaik Arif Ahmed</b>
        </div>
        """, 
        unsafe_allow_html=True
    )

# --- MAIN LAYOUT ---
col_spacer1, col_main, col_spacer2 = st.columns([1, 10, 1])

with col_main:
    st.markdown("""
    <div class="hero-header">
        <div class="hero-title">🏛️ RBI Regulatory Intelligence</div>
        <div class="hero-subtitle">Semantic search & conversational intelligence over RBI circulars</div>
    </div>
    """, unsafe_allow_html=True)

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

# --- CHAT INPUT ---
if prompt := st.chat_input("Ask about KYC, Loans, Cyber Security..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# --- RESPONSE GENERATION ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    
    with col_main:
        last_prompt = st.session_state.messages[-1]["content"]
        
        with st.chat_message("assistant"):
            with st.spinner("🔍 Analyzing regulations..."):
                
                # 1. EMBED
                vector = []
                try:
                    vector = genai.embed_content(model="models/text-embedding-004", content=last_prompt, task_type="retrieval_query")['embedding']
                except Exception as e:
                    st.error(f"⚠️ Embedding Error: {e}")
                    vector = []

                # 2. SEARCH (CRITICAL FIX: LOWER THRESHOLD)
                context_text = ""
                sources = []
                debug_info = [] # Store raw results for debugging
                
                if vector:
                    try:
                        # Changed threshold from 0.4 to 0.1 to be more lenient
                        response = supabase.rpc("match_documents", {
                            "query_embedding": vector, "match_threshold": 0.1, "match_count": 10
                        }).execute()
                        
                        seen_urls = set()
                        for match in response.data:
                            title = match.get('title', 'Unknown')
                            url = match.get('url', '#')
                            date = match.get('published_date', 'Unknown')
                            similarity = match.get('similarity', 0)
                            
                            # Add to Context
                            context_text += f"\nTitle: {title}\nDate: {date}\nExcerpt: {match.get('content', '')}\n"
                            
                            # Add to Sources
                            if url not in seen_urls:
                                sources.append({"title": title, "url": url, "date": date})
                                seen_urls.add(url)
                            
                            # Add to Debug Log
                            debug_info.append(f"{similarity:.4f} | {title}")
                            
                    except Exception as e:
                        st.error(f"⚠️ Database Error: {e}")

                if not context_text:
                    context_text = "No specific circulars found."

                # 3. GENERATE
                try:
                    model = genai.GenerativeModel(chat_model_name)
                    full_prompt = f"""
                    You are a senior banking regulatory consultant. 
                    Answer the user's question using ONLY the provided RBI circulars.
                    
                    USER QUESTION: {last_prompt}
                    CONTEXT: {context_text}
                    """
                    ai_response = model.generate_content(full_prompt)
                    answer = ai_response.text
                except Exception as e:
                    answer = f"⚠️ Generation Error: {str(e)}"

                # Save & Display
                st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
                
                # Show Debug info purely for you (the admin) to verify
                if debug_info:
                    with st.expander("🛠️ Debug: Raw DB Matches (Similarity Score | Title)"):
                        st.write(debug_info)
                
                st.rerun()
