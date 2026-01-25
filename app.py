import streamlit as st
import google.generativeai as genai
from supabase import create_client
import os
from dotenv import load_dotenv

# 1. Configuration & Secrets
load_dotenv()
st.set_page_config(
    page_title="RBI Circular Intelligence",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL CSS STYLING ---
st.markdown("""
<style>
    /* Main Background adjustments */
    .stApp {
        background-color: #F4F6F9;
    }
    
    /* Header Styling */
    .main-header {
        background: linear-gradient(90deg, #0F52BA 0%, #1E3A8A 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .main-header h1 {
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 700;
        margin: 0;
        font-size: 2rem;
        color: white !important;
    }
    .main-header p {
        margin: 0;
        opacity: 0.9;
        font-size: 1rem;
    }

    /* Chat Message Styling */
    .stChatMessage {
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        border: 1px solid #E5E7EB;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    /* User Message Background */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #EBF8FF; /* Light Blue tint */
    }
    /* AI Message Background */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(even) {
        background-color: #FFFFFF; /* Pure White */
    }

    /* Source Card Styling */
    .source-card {
        background-color: #FFFFFF;
        border-left: 4px solid #0F52BA;
        padding: 15px;
        border-radius: 5px;
        margin-top: 10px;
        font-size: 0.9em;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E5E7EB;
    }
</style>
""", unsafe_allow_html=True)
# --------------------------------

# 2. Setup Connections
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"⚠️ System Error: {e}")
    st.stop()

# 3. Model Selector
@st.cache_resource
def get_chat_model_name():
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Prefer the newest, fastest models
        for preferred in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']:
            if preferred in available_models: return preferred
        return available_models[0] if available_models else "models/gemini-pro"
    except:
        return "models/gemini-pro"

chat_model_name = get_chat_model_name()

# 4. Sidebar Interface
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/RBI_Logo.svg/1200px-RBI_Logo.svg.png", width=100)
    st.title("Control Center")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Status", "Online", delta_color="normal")
    with col2:
        st.metric("Model", "Gemini", delta_color="off")
    
    st.info(f"**Current Engine:**\n`{chat_model_name}`")
    
    st.markdown("---")
    st.markdown("### 🛠️ Utilities")
    if st.button("🧹 Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    st.caption("© 2026 RBI Intelligence Bot\nPowered by RAG Architecture")

# 5. Header Section
st.markdown("""
<div class="main-header">
    <h1>🏛️ RBI Regulatory Intelligence</h1>
    <p>Real-time semantic search across Reserve Bank of India circulars and notifications.</p>
</div>
""", unsafe_allow_html=True)

# 6. Chat Logic
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # Render Sources if available
        if "sources" in msg and msg["sources"]:
            with st.expander("📚 Verified References"):
                for source in msg["sources"]:
                    st.markdown(
                        f"""
                        <div class="source-card">
                            <b>Document:</b> <a href="{source['url']}" target="_blank">{source['title']}</a><br>
                            <b>Date:</b> {source['date']}
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )

# Input
if prompt := st.chat_input("Ask about KYC, Loans, Cyber Security, etc..."):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        with st.spinner("Analyzing regulatory framework..."):
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
                1. Be professional, concise, and accurate.
                2. Use bullet points for lists.
                3. If the answer is not in the circulars, clearly state that.
                
                USER QUESTION: {prompt}
                CONTEXT: {context_text}
                """
                ai_response = model.generate_content(full_prompt)
                answer = ai_response.text
            except:
                answer = "System is experiencing high load. Please try again."

            # D. Render
            message_placeholder.markdown(answer)
            
            # Show sources in a nice card
            if sources:
                with st.expander("📚 Verified References", expanded=False):
                    for source in sources:
                        st.markdown(
                            f"""
                            <div class="source-card">
                                <b>Document:</b> <a href="{source['url']}" target="_blank">{source['title']}</a><br>
                                <b>Date:</b> {source['date']}
                            </div>
                            """, 
                            unsafe_allow_html=True
                        )

            # Save
            st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
