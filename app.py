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

# --- BULLETPROOF MODEL SELECTOR ---
@st.cache_resource
def get_valid_model_name():
    """
    Dynamically lists models available to the API key and picks the best one.
    This prevents '404 Model Not Found' errors.
    """
    try:
        # Get list of all models valid for this API key
        models = list(genai.list_models())
        
        # Filter for models that support text generation ('generateContent')
        chat_models = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
        
        if not chat_models:
            return None

        # Priority Selection: Try to find the best model in this order
        # 1. Flash (Fastest/Cheapest)
        for m in chat_models:
            if 'flash' in m and '1.5' in m: return m
        
        # 2. Pro 1.5 (Smarter)
        for m in chat_models:
            if 'pro' in m and '1.5' in m: return m
            
        # 3. Pro 1.0 (Standard)
        for m in chat_models:
            if 'gemini-pro' in m: return m

        # 4. Fallback: Just take the first valid one found
        return chat_models[0]
        
    except Exception as e:
        # If listing fails, return a safe default and hope for the best
        return "models/gemini-pro"

# Get the valid model name once
active_model_name = get_valid_model_name()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🎛️ Control Center")
    st.markdown("**SYSTEM STATUS**")
    
    if active_model_name:
        st.markdown(f'<div style="background:#f0fdf4;color:#15803d;padding:4px 12px;border-radius:20px;text-align:center;font-weight:600;font-size:0.85rem;border:1px solid #bbf7d0;">🟢 Online</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="background:#fef2f2;color:#991b1b;padding:4px 12px;border-radius:20px;text-align:center;font-weight:600;font-size:0.85rem;border:1px solid #fecaca;">🔴 Error</div>', unsafe_allow_html=True)

    st.markdown("**DATA SCOPE**\n\n📚 **RBI Circulars**\n(2025 – Present)")
    
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    # Show the user exactly which model we found (Debugging)
    display_name = active_model_name.replace("models/", "") if active_model_name else "No Model Found"
    st.caption(f"v2.3.0 • {display_name}")

# --- MAIN LAYOUT ---
col_spacer1, col_main, col_spacer2 = st.columns([1, 10, 1])

with col_main:
    st.markdown("""
    <div class="hero-header">
        <div class="hero-title">🏛️ RBI Regulatory Intelligence</div>
        <div class="hero-subtitle">Semantic search & conversational intelligence over RBI circulars</div>
    </div>
    """, unsafe_allow_html=True)

    # Critical Error Check
    if not active_model_name:
        st.error("❌ API Error: No Gemini models found for your API Key. Please check if 'Generative Language API' is enabled in your Google Cloud Console.")
        st.stop()

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
if prompt := st.chat_input("Ask a question about RBI regulations..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# --- LOGIC HANDLER ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with col_main:
        last_prompt = st.session_state.messages[-1]["content"]
        
        with st.chat_message("assistant"):
            with st.spinner("🔍 Analyzing regulations..."):
                # Embed
                try:
                    vector = genai.embed_content(model="models/text-embedding-004", content=last_prompt, task_type="retrieval_query")['embedding']
                except Exception as e:
                    # Fallback embedding model
                    try:
                        vector = genai.embed_content(model="models/embedding-001", content=last_prompt, task_type="retrieval_query")['embedding']
                    except:
                        st.error(f"Embedding failed: {e}")
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
                    except Exception as e:
                        st.error(f"Search failed: {e}")
                
                if not context_text: context_text = "No specific circulars found."

                # Generate (USING AUTO-DETECTED MODEL)
                try:
                    model = genai.GenerativeModel(active_model_name)
                    ai_response = model.generate_content(f"You are an RBI expert. Answer using ONLY this context:\n\n{context_text}\n\nQuestion: {last_prompt}").text
                except Exception as e:
                    ai_response = f"⚠️ AI Error: {e}"

                # Save Response
                st.session_state.messages.append({"role": "assistant", "content": ai_response, "sources": sources})
                st.rerun()
