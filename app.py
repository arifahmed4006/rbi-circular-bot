import streamlit as st
import google.generativeai as genai
from supabase import create_client
import os
from dotenv import load_dotenv

# 1. Configuration
load_dotenv()
st.set_page_config(
    page_title="RBI Regulatory Intelligence",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #f8fafc; }
    .hero-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 2rem; border-radius: 12px; margin-bottom: 2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); color: white;
    }
    .source-box {
        background-color: #f8fafc; border-left: 4px solid #3b82f6;
        padding: 12px 16px; margin-top: 12px; border-radius: 0 4px 4px 0; font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# 2. Connections
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"⚠️ Connection Error: {e}")
    st.stop()

# 3. Model Selectors (Updated for 2026 Standards)
@st.cache_resource
def get_active_models():
    """Finds the best available models for this API key."""
    try:
        models = [m.name for m in genai.list_models()]
        # Generation Model
        gen_model = 'models/gemini-1.5-flash' # Default stable
        for m in ['models/gemini-2.0-flash', 'models/gemini-1.5-flash']:
            if m in models: 
                gen_model = m
                break
        
        # Embedding Model
        embed_model = 'models/text-embedding-004' # Default stable
        for m in ['models/text-embedding-004', 'models/gemini-embedding-001']:
            if m in models:
                embed_model = m
                break
                
        return gen_model, embed_model
    except:
        return 'models/gemini-1.5-flash', 'models/text-embedding-004'

chat_model_name, embed_model_name = get_active_models()

# 4. Global Context
def get_system_context():
    try:
        count_res = supabase.table("documents").select("id", count="exact").execute()
        total = count_res.count if count_res.count else 0
        titles_res = supabase.table("documents").select("title").execute()
        titles = [row['title'] for row in titles_res.data]
        return total, titles
    except:
        return 0, []

total_indexed, all_titles_list = get_system_context()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🎛️ Control Center")
    st.success(f"📊 **Total Indexed:** {total_indexed} Circulars")
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.markdown("---")
    st.caption(f"**Engine:** `{chat_model_name.split('/')[-1]}`")
    st.caption(f"Created by **Shaik Arif Ahmed**")

# --- MAIN UI ---
col_spacer1, col_main, col_spacer2 = st.columns([1, 10, 1])
with col_main:
    st.markdown("""<div class="hero-header"><div class="hero-title">🏛️ RBI Regulatory Intelligence</div>
    <div class="hero-subtitle">Semantic search & conversational intelligence over RBI circulars</div></div>""", unsafe_allow_html=True)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# --- CHAT INPUT ---
if prompt := st.chat_input("Ask about KYC, counts, or specific guidelines..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# --- RESPONSE GENERATION ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with col_main:
        last_prompt = st.session_state.messages[-1]["content"]
        with st.chat_message("assistant"):
            with st.spinner("🔍 Querying regulatory database..."):
                
                # 1. EMBED (Using discovered model)
                vector = []
                try:
                    vector = genai.embed_content(model=embed_model_name, content=last_prompt, task_type="retrieval_query")['embedding']
                except Exception as e:
                    st.error(f"⚠️ Search temporary offline. Retrying with backup...")
                    # Force one last try with the most basic name
                    try:
                        vector = genai.embed_content(model="models/text-embedding-004", content=last_prompt, task_type="retrieval_query")['embedding']
                    except:
                        vector = []

                # 2. SEARCH
                context_text = ""
                sources = []
                if vector:
                    response = supabase.rpc("match_documents", {
                        "query_embedding": vector, "match_threshold": 0.05, "match_count": 15
                    }).execute()
                    
                    seen_urls = set()
                    for match in response.data:
                        context_text += f"\n- {match['title']} ({match['published_date']}): {match['content']}\n"
                        if match['url'] not in seen_urls:
                            sources.append({"title": match['title'], "url": match['url'], "date": match['published_date']})
                            seen_urls.add(match['url'])

                # 3. GENERATION
                model = genai.GenerativeModel(chat_model_name)
                system_context = f"""
                You are a senior banking regulatory expert. 
                DATABASE STATUS: {total_indexed} total circulars indexed.
                AVAILABLE TITLES: {', '.join(all_titles_list)}.
                
                INSTRUCTIONS:
                - Use the DATABASE STATUS and TITLES for general counts/lists.
                - Use the DETAILED CONTEXT for technical answers.
                - If the DETAILED CONTEXT is empty, explain that you can see the titles but cannot access the inner content right now due to a search indexing delay.
                """
                
                ai_response = model.generate_content(f"{system_context}\n\nQuestion: {last_prompt}\n\nDETAILED CONTEXT:\n{context_text}").text
                st.markdown(ai_response)
                
                if sources:
                    with st.expander("📚 Verified References"):
                        for s in sources:
                            st.markdown(f"<div class='source-box'><a href='{s['url']}' target='_blank'>📄 {s['title']}</a><br><small>{s['date']}</small></div>", unsafe_allow_html=True)

                st.session_state.messages.append({"role": "assistant", "content": ai_response, "sources": sources})
                st.rerun()
