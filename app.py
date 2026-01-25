import streamlit as st
import google.generativeai as genai
from supabase import create_client
import os
from dotenv import load_dotenv

# 1. Configuration
load_dotenv()
st.set_page_config(page_title="RBI Smart Assistant", page_icon="🏦", layout="wide")

# Custom CSS for a professional look
st.markdown("""
<style>
    .stChatMessage { padding: 1rem; border-radius: 10px; margin-bottom: 1rem;}
    .stChatMessage[data-testid="stChatMessage"] { background-color: #f0f2f6; }
    h1 { color: #2c3e50; }
</style>
""", unsafe_allow_html=True)

# 2. Sidebar Controls
with st.sidebar:
    st.title("🏦 RBI Assistant")
    st.markdown("---")
    st.markdown("**Status:** 🟢 Online")
    st.markdown("**Data Source:** Official RBI Circulars")
    
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    st.caption("Powered by Gemini Pro & Supabase")

# 3. Setup AI & DB
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"⚠️ Configuration Error: {e}")
    st.stop()

# 4. Auto-Detect Model (Smart Selector)
@st.cache_resource
def get_chat_model_name():
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for preferred in ['models/gemini-1.5-flash', 'models/gemini-pro']:
            if preferred in available_models: return preferred
        return available_models[0] if available_models else "models/gemini-pro"
    except:
        return "models/gemini-pro"

chat_model_name = get_chat_model_name()

# 5. Helper Functions
def get_embedding(text):
    try:
        return genai.embed_content(model="models/text-embedding-004", content=text, task_type="retrieval_query")['embedding']
    except:
        return []

# 6. Main Chat Interface
st.title("🏦 RBI Circular Assistant")
st.caption(f"Ask questions about RBI regulations (Model: {chat_model_name.split('/')[-1]})")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # If this message has sources attached (saved in history), show them
        if "sources" in msg:
            with st.expander("📚 View Sources"):
                for source in msg["sources"]:
                    st.markdown(f"- [{source['title']}]({source['url']}) ({source['date']})")

# Chat Input
if prompt := st.chat_input("Ex: What are the new rules for housing loans?"):
    
    # User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # AI Processing
    with st.chat_message("assistant"):
        with st.spinner("🔍 Searching circulars..."):
            
            # Search
            vector = get_embedding(prompt)
            context_text = ""
            sources = [] # To store metadata for the UI

            if vector:
                try:
                    # Increased match_count to 10 for better context
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
                            
                            # Build Context text for AI
                            context_text += f"\n---\nTitle: {title}\nDate: {date}\nExcerpt: {match.get('content', '')}\n"
                            
                            # Save Source for UI (avoid duplicates)
                            if url not in seen_urls:
                                sources.append({"title": title, "url": url, "date": date})
                                seen_urls.add(url)
                except Exception as e:
                    st.error(f"DB Error: {e}")

            if not context_text:
                context_text = "No specific circulars found."

            # Generate Answer
            try:
                model = genai.GenerativeModel(chat_model_name)
                full_prompt = f"""
                You are a helpful RBI financial assistant. Answer the question using ONLY the context below. 
                If the answer is not in the context, say "I couldn't find specific details in the available circulars."
                Format your answer with clear bullet points.

                QUESTION: {prompt}
                
                CONTEXT:
                {context_text}
                """
                ai_response = model.generate_content(full_prompt)
                answer = ai_response.text
            except Exception as e:
                answer = "I'm having trouble connecting to the AI right now."

            # Display Answer
            st.markdown(answer)
            
            # Display Sources immediately
            if sources:
                with st.expander("📚 View Sources Used"):
                    for source in sources:
                        st.markdown(f"- [{source['title']}]({source['url']}) ({source['date']})")

            # Save to history
            st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
