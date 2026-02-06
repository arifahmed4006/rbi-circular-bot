import streamlit as st
import google.generativeai as genai
from supabase import create_client
import os
from dotenv import load_dotenv

# 1. Configuration
load_dotenv()
st.set_page_config(page_title="RBI Intelligence", layout="wide", initial_sidebar_state="expanded")

# --- CSS STYLING ---
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

# 2. Connections
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"Connection Error: {e}")
    st.stop()

# 3. SELF-HEALING MODEL SELECTOR
@st.cache_resource
def get_verified_models():
    try:
        models = [m.name for m in genai.list_models()]
        # Updated Priority List for 2026 / v1beta stability
        gen_priority = [
            'models/gemini-1.5-flash-latest', 
            'models/gemini-1.5-flash', 
            'models/gemini-pro',
            'models/gemini-1.0-pro'
        ]
        embed_priority = [
            'models/text-embedding-004', 
            'models/gemini-embedding-001'
        ]
        
        selected_gen = next((m for m in gen_priority if m in models), 'models/gemini-1.5-flash')
        selected_embed = next((m for m in embed_priority if m in models), 'models/text-embedding-004')
        return selected_gen, selected_embed
    except:
        return 'models/gemini-1.5-flash', 'models/text-embedding-004'

chat_model, embed_model = get_verified_models()

# 4. Global Stats
@st.cache_data(ttl=600)
def get_stats():
    try:
        res = supabase.table("documents").select("id", count="exact").execute()
        titles_res = supabase.table("documents").select("title").execute()
        return res.count or 0, [r['title'] for r in titles_res.data]
    except:
        return 0, []

total_docs, all_titles = get_stats()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🎛️ Control Center")
    st.success(f"📊 **Indexed:** {total_docs} Circulars")
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.markdown("---")
    st.markdown("**SYSTEM ARCHITECTURE**")
    st.markdown(f"""<div class="workflow-container"><div class="workflow-step"><b>INGESTION</b><br>Playwright</div><div class="workflow-step"><b>DB</b><br>Supabase (pgvector)</div><div class="workflow-step"><b>AI</b><br>Gemini 1.5</div></div>""", unsafe_allow_html=True)
    st.caption(f"v2.8.0 • {chat_model.split('/')[-1]}<br>Created by **Shaik Arif Ahmed**")

# --- MAIN ---
col_spacer1, col_main, col_spacer2 = st.columns([1, 10, 1])
with col_main:
    st.markdown("""<div class="hero-header"><h2>🏛️ RBI Regulatory Intelligence</h2><span>Semantic search over RBI circulars</span></div>""", unsafe_allow_html=True)
    if "messages" not in st.session_state: st.session_state.messages = []
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

if prompt := st.chat_input("Ask about circulars..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with col_main:
        query = st.session_state.messages[-1]["content"]
        with st.chat_message("assistant"):
            with st.spinner("🔍 Querying Database..."):
                # 1. Embed
                try:
                    vec = genai.embed_content(model=embed_model, content=query, task_type="retrieval_query")['embedding']
                except:
                    vec = []

                # 2. Search (with Warm-up/Retry Logic)
                context = ""
                sources = []
                if vec:
                    try:
                        resp = supabase.rpc("match_documents", {"query_embedding": vec, "match_threshold": 0.05, "match_count": 12}).execute()
                        for m in resp.data:
                            context += f"\n- {m['title']}: {m['content']}\n"
                            if m['url'] not in [s['url'] for s in sources]:
                                sources.append({"title": m['title'], "url": m['url'], "date": m['published_date']})
                    except:
                        # Warm-up Attempt: If RPC fails, touch the table and retry
                        supabase.table("documents").select("id").limit(1).execute()
                        st.warning("🔄 Waking up database connection... please wait.")

                # 3. Generate
                model_engine = genai.GenerativeModel(chat_model)
                sys_instruct = f"Expert RBI Consultant. DB has {total_docs} docs: {', '.join(all_titles)}. Use facts first."
                try:
                    ans = model_engine.generate_content(f"{sys_instruct}\n\nQ: {query}\n\nContext:\n{context}").text
                    st.markdown(ans)
                    if sources:
                        with st.expander("📚 References"):
                            for s in sources: st.markdown(f"[{s['title']}]({s['url']})")
                    st.session_state.messages.append({"role": "assistant", "content": ans, "sources": sources})
                except Exception as e:
                    st.error(f"AI Generation Failed: {e}")
                st.rerun()
