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
    .footer-credit {
        margin-top: 20px; font-size: 0.85rem; color: #64748b;
        border-top: 1px solid #e2e8f0; padding-top: 10px;
    }
    .flow-step {
        background-color: #ffffff; padding: 8px 10px; border-radius: 6px;
        font-size: 0.8rem; border: 1px solid #e2e8f0; margin-bottom: 4px;
        display: flex; justify-content: space-between; align-items: center;
    }
    .tech-badge {
        font-size: 0.7rem; background-color: #f1f5f9; padding: 2px 6px;
        border-radius: 4px; color: #475569; font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# 2. Setup Connections
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"⚠️ Connection Error: {e}")
    st.stop()

# 3. Robust Model Selector (Fixes 404 Issues)
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

# 4. Global Context Fetcher (Fixes "Wrong Answers" on counts/summaries)
def get_system_context():
    try:
        # Get actual count of unique documents
        count_res = supabase.table("documents").select("id", count="exact").execute()
        total = count_res.count if count_res.count else 0
        # Get list of all titles for summarization
        titles_res = supabase.table("documents").select("title").execute()
        titles = [row['title'] for row in titles_res.data]
        return total, titles
    except:
        return 0, []

total_indexed, all_titles_list = get_system_context()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🎛️ Control Center")
    st.markdown("**SYSTEM STATUS**")
    st.markdown('<div style="background:#f0fdf4;color:#15803d;padding:4px 12px;border-radius:20px;text-align:center;font-weight:600;font-size:0.85rem;border:1px solid #bbf7d0;">🟢 Online</div>', unsafe_allow_html=True)
    st.markdown(f"📊 **Total Indexed:** {total_indexed} Circulars")
    
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    with st.expander("⚙️ System Architecture"):
        st.markdown("""
        <div class="flow-step"><span>🌐 Browser</span><span class="tech-badge">Playwright</span></div>
        <div class="flow-step"><span>🔢 Embedding</span><span class="tech-badge">Gemini 004</span></div>
        <div class="flow-step"><span>💾 Memory</span><span class="tech-badge">Supabase</span></div>
        <div class="flow-step"><span>🤖 Synthesis</span><span class="tech-badge">Gemini 1.5</span></div>
        """, unsafe_allow_html=True)

    st.markdown(
        f"""<div class="footer-credit"><b>v2.5.0</b> • Engine: <code>{chat_model_name.split('/')[-1]}</code><br>
        Created by <b>Shaik Arif Ahmed</b></div>""", unsafe_allow_html=True
    )

# --- MAIN LAYOUT ---
col_spacer1, col_main, col_spacer2 = st.columns([1, 10, 1])
with col_main:
    st.markdown("""<div class="hero-header"><div class="hero-title">🏛️ RBI Regulatory Intelligence</div>
    <div class="hero-subtitle">Semantic search & conversational intelligence over RBI circulars</div></div>""", unsafe_allow_html=True)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# --- CHAT INPUT (STICKY BOTTOM) ---
if prompt := st.chat_input("Ask about KYC, counts, or specific guidelines..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# --- RESPONSE GENERATION ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with col_main:
        last_prompt = st.session_state.messages[-1]["content"]
        with st.chat_message("assistant"):
            with st.spinner("🔍 Querying regulatory database..."):
                # 1. Embed Query
                try:
                    vector = genai.embed_content(model="models/text-embedding-004", content=last_prompt, task_type="retrieval_query")['embedding']
                except:
                    vector = genai.embed_content(model="models/embedding-001", content=last_prompt, task_type="retrieval_query")['embedding']

                # 2. Semantic Search (Low threshold to catch relevant data)
                context_text = ""
                sources = []
                if vector:
                    response = supabase.rpc("match_documents", {
                        "query_embedding": vector, "match_threshold": 0.1, "match_count": 15
                    }).execute()
                    
                    seen_urls = set()
                    for match in response.data:
                        context_text += f"\n- {match['title']} ({match['published_date']}): {match['content']}\n"
                        if match['url'] not in seen_urls:
                            sources.append({"title": match['title'], "url": match['url'], "date": match['published_date']})
                            seen_urls.add(match['url'])

                # 3. Synthesis with Metadata Awareness
                model = genai.GenerativeModel(chat_model_name)
                
                # We "anchor" the AI's logic to the actual database facts
                system_context = f"""
                You are a senior banking regulatory expert. 
                DATABASE FACTS:
                - There are exactly {total_indexed} RBI circulars indexed.
                - Full list of titles: {', '.join(all_titles_list)}.
                
                INSTRUCTIONS:
                - If the user asks for a count or a list of circulars, refer ONLY to the DATABASE FACTS.
                - For technical questions about rules, use the DETAILED CONTEXT below.
                - If the answer is not present, state that you cannot find it in the current dataset.
                """
                
                try:
                    ai_response = model.generate_content(f"{system_context}\n\nQuestion: {last_prompt}\n\nDETAILED CONTEXT:\n{context_text}").text
                except Exception as e:
                    ai_response = f"⚠️ System Error: {str(e)}"

                st.markdown(ai_response)
                
                if sources:
                    with st.expander("📚 Verified References"):
                        for s in sources:
                            st.markdown(f"<div class='source-box'><a href='{s['url']}' target='_blank'>📄 {s['title']}</a><br><small>{s['date']}</small></div>", unsafe_allow_html=True)

                st.session_state.messages.append({"role": "assistant", "content": ai_response, "sources": sources})
                st.rerun()
