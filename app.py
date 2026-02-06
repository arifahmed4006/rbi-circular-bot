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

# --- UI STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #f8fafc; }
    .hero-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 2rem; border-radius: 12px; margin-bottom: 2rem; color: white;
    }
    .workflow-container { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; }
    .workflow-step { background: #f1f5f9; border-left: 4px solid #3b82f6; padding: 8px; margin-bottom: 8px; font-size: 0.8rem; border-radius: 0 4px 4px 0; }
</style>
""", unsafe_allow_html=True)

# 2. Setup Connections
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"Setup Error: {e}")
    st.stop()

# 3. GLOBAL STATS (FETCH ONCE)
@st.cache_data(ttl=600)
def get_db_stats():
    try:
        res = supabase.table("documents").select("id", count="exact").execute()
        titles_res = supabase.table("documents").select("title").execute()
        return res.count or 0, [r['title'] for r in titles_res.data]
    except:
        return 0, []

total_docs, all_titles = get_db_stats()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🎛️ Control Center")
    st.success(f"📊 **Indexed:** {total_docs} Circulars")
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.markdown("---")
    st.markdown("**SYSTEM ARCHITECTURE**")
    st.markdown("""<div class="workflow-container"><div class="workflow-step"><b>INGESTION</b><br>Daily Scrape</div><div class="workflow-step"><b>DB</b><br>Supabase (pgvector)</div><div class="workflow-step"><b>AI</b><br>Gemini 1.5</div></div>""", unsafe_allow_html=True)
    st.caption("v3.1.0 • Stable Release")
    st.caption("Created by **Shaik Arif Ahmed**")

# --- MAIN UI ---
col_spacer1, col_main, col_spacer2 = st.columns([1, 10, 1])
with col_main:
    st.markdown("""<div class="hero-header"><h2>🏛️ RBI Regulatory Intelligence</h2><span>Semantic search & conversational AI</span></div>""", unsafe_allow_html=True)
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# --- CHAT INPUT ---
if prompt := st.chat_input("Ask about KYC, counts, or specific circulars..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# --- RESPONSE GENERATION ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with col_main:
        last_query = st.session_state.messages[-1]["content"]
        with st.chat_message("assistant"):
            with st.spinner("🔍 Processing..."):
                
                # 1. EMBED (Explicit Model Name)
                vector = []
                try:
                    # Using the exact name 'models/embedding-001' which is the universal fallback
                    embed_result = genai.embed_content(
                        model="models/embedding-001", 
                        content=last_query, 
                        task_type="retrieval_query"
                    )
                    vector = embed_result['embedding']
                except Exception as e:
                    # If 001 fails, try text-embedding-004
                    try:
                        embed_result = genai.embed_content(
                            model="models/text-embedding-004", 
                            content=last_query, 
                            task_type="retrieval_query"
                        )
                        vector = embed_result['embedding']
                    except:
                        st.error("⚠️ AI Embedding Service is temporarily unavailable.")

                # 2. SEARCH
                context_text = ""
                sources = []
                if vector:
                    try:
                        response = supabase.rpc("match_documents", {
                            "query_embedding": vector, 
                            "match_threshold": 0.05, 
                            "match_count": 10
                        }).execute()
                        
                        if response.data:
                            seen_urls = set()
                            for m in response.data:
                                context_text += f"\n- {m['title']}: {m['content']}\n"
                                if m['url'] not in seen_urls:
                                    sources.append({"title": m['title'], "url": m['url']})
                                    seen_urls.add(m['url'])
                    except Exception:
                        st.warning("⚠️ Database connection slow, trying again...")

                # 3. GENERATE (Explicit Model Name)
                try:
                    # Hardcoded to 'gemini-1.5-flash' - most robust model for Free Tier
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    sys_prompt = f"Expert RBI Consultant. DB has {total_docs} docs: {', '.join(all_titles)}. Use ONLY provided context."
                    full_prompt = f"{sys_prompt}\n\nQ: {last_query}\n\nContext:\n{context_text}"
                    
                    ai_response = model.generate_content(full_prompt).text
                    st.markdown(ai_response)
                    
                    if sources:
                        with st.expander("📚 References"):
                            for s in sources:
                                st.markdown(f"[{s['title']}]({s['url']})")
                    
                    st.session_state.messages.append({"role": "assistant", "content": ai_response, "sources": sources})
                except Exception as e:
                    st.error(f"⚠️ AI Response Error: {e}")
                
                st.rerun()
