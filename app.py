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

# --- PROFESSIONAL CSS STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #f8fafc; }
    
    /* Hero Header */
    .hero-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 2rem; border-radius: 12px; margin-bottom: 2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); color: white;
    }
    
    /* Custom Sidebar Workflow Flowchart */
    .workflow-container {
        background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin-bottom: 15px;
    }
    .workflow-step {
        background: #f1f5f9; border-left: 4px solid #3b82f6; padding: 8px 12px; margin-bottom: 8px;
        font-size: 0.8rem; border-radius: 0 4px 4px 0; color: #1e293b;
    }
    .step-title { font-weight: 700; display: block; margin-bottom: 2px; }
    .step-tech { font-size: 0.7rem; color: #64748b; font-family: monospace; }
    .workflow-arrow { text-align: center; color: #94a3b8; font-size: 0.8rem; margin: -4px 0 4px 0; }

    .source-box {
        background-color: #f8fafc; border-left: 4px solid #3b82f6;
        padding: 12px 16px; margin-top: 12px; border-radius: 0 4px 4px 0; font-size: 0.9rem;
    }
    .footer-credit {
        margin-top: 20px; font-size: 0.85rem; color: #64748b;
        border-top: 1px solid #e2e8f0; padding-top: 10px;
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

# 3. Model Selectors
@st.cache_resource
def get_active_models():
    try:
        models = [m.name for m in genai.list_models()]
        gen_model = next((m for m in ['models/gemini-1.5-flash', 'models/gemini-pro'] if m in models), 'models/gemini-1.5-flash')
        embed_model = next((m for m in ['models/text-embedding-004', 'models/gemini-embedding-001'] if m in models), 'models/text-embedding-004')
        return gen_model, embed_model
    except:
        return 'models/gemini-1.5-flash', 'models/text-embedding-004'

chat_model_name, embed_model_name = get_active_models()

# 4. Global Context Fetcher
@st.cache_data(ttl=3600)
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

# --- SIDEBAR (RESTORED ARCHITECTURE) ---
with st.sidebar:
    st.markdown("### 🎛️ Control Center")
    st.success(f"📊 **Total Indexed:** {total_indexed} Circulars")
    
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.markdown("**SYSTEM ARCHITECTURE**")
    
    # Custom HTML Workflow (Replaces Mermaid for stability)
    st.markdown(f"""
    <div class="workflow-container">
        <div class="workflow-step">
            <span class="step-title">1. INGESTION</span>
            <span class="step-tech">Daily Scrape &bull; Playwright</span>
        </div>
        <div class="workflow-arrow">▼</div>
        <div class="workflow-step">
            <span class="step-title">2. PROCESSING</span>
            <span class="step-tech">Chunking &bull; Gemini 004</span>
        </div>
        <div class="workflow-arrow">▼</div>
        <div class="workflow-step">
            <span class="step-title">3. STORAGE</span>
            <span class="step-tech">Vector DB &bull; Supabase</span>
        </div>
        <div class="workflow-arrow">▼</div>
        <div class="workflow-step">
            <span class="step-title">4. RETRIEVAL</span>
            <span class="step-tech">Semantic RAG &bull; Gemini 1.5</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="footer-credit">
        <b>v2.7.0</b> &bull; Engine: <code>{chat_model_name.split('/')[-1]}</code><br>
        Created by <b>Shaik Arif Ahmed</b>
    </div>
    """, unsafe_allow_html=True)

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
                
                # 1. EMBED
                vector = []
                try:
                    vector = genai.embed_content(model=embed_model_name, content=last_prompt, task_type="retrieval_query")['embedding']
                except Exception as e:
                    st.error(f"⚠️ Search failed to initialize. Retrying...")
                    vector = []

                # 2. SEARCH (Fixed APIError Handling)
                context_text = ""
                sources = []
                if vector:
                    try:
                        # Direct RPC call with explicit error trapping
                        response = supabase.rpc("match_documents", {
                            "query_embedding": vector, 
                            "match_threshold": 0.05, 
                            "match_count": 12
                        }).execute()
                        
                        if hasattr(response, 'data') and response.data:
                            seen_urls = set()
                            for match in response.data:
                                context_text += f"\n- {match['title']} ({match['published_date']}): {match['content']}\n"
                                if match['url'] not in seen_urls:
                                    sources.append({"title": match['title'], "url": match['url'], "date": match['published_date']})
                                    seen_urls.add(match['url'])
                    except Exception as e:
                        st.error(f"⚠️ Database Error: Function Cache Timeout. Please retry in 5 seconds.")

                # 3. GENERATION
                if not context_text:
                    context_text = "No specific technical content was retrieved for this query."

                model = genai.GenerativeModel(chat_model_name)
                system_context = f"""
                You are a senior banking regulatory expert. 
                DATABASE: {total_indexed} total circulars indexed.
                AVAILABLE TITLES: {', '.join(all_titles_list)}.
                
                INSTRUCTIONS:
                - Use the DATABASE stats for counts/lists.
                - Use the DETAILED CONTEXT for technical analysis.
                - If no context matches, explain using only the titles you see.
                """
                
                try:
                    ai_response = model.generate_content(f"{system_context}\n\nQuestion: {last_prompt}\n\nDETAILED CONTEXT:\n{context_text}").text
                    st.markdown(ai_response)
                    
                    if sources:
                        with st.expander("📚 Verified References"):
                            for s in sources:
                                st.markdown(f"<div class='source-box'><a href='{s['url']}' target='_blank'>📄 {s['title']}</a><br><small>{s['date']}</small></div>", unsafe_allow_html=True)
                    
                    st.session_state.messages.append({"role": "assistant", "content": ai_response, "sources": sources})
                except Exception as e:
                    st.error(f"⚠️ AI Generation Error: {e}")
                
                st.rerun()
