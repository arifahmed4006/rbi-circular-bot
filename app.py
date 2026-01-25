import streamlit as st
import google.generativeai as genai
from supabase import create_client
import os
from dotenv import load_dotenv

# 1. Load keys
load_dotenv()

# 2. Configure Gemini & Supabase
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"Configuration Error: {e}")
    st.stop()

# 3. Setup Title
st.set_page_config(page_title="RBI Smart Assistant")
st.title("🏦 RBI Circular Assistant")

# --- NEW: AUTO-DETECT MODEL FUNCTION ---
@st.cache_resource # Run this once and remember it
def get_chat_model_name():
    """Finds a working model name automatically."""
    try:
        # Ask Google: "What models do I have?"
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        # Priority list: Try to find these specific ones first
        for preferred in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']:
            if preferred in available_models:
                return preferred
        
        # If none of the preferred ones exist, take the first valid one
        if available_models:
            return available_models[0]
            
        return "models/gemini-1.5-flash" # Absolute fallback
    except Exception as e:
        return "models/gemini-1.5-flash"

# Get the best model
chat_model_name = get_chat_model_name()
# ---------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

def get_embedding(text):
    try:
        # Try the modern embedding model
        return genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_query"
        )['embedding']
    except:
        # Fallback to older model if newer fails
        try:
            return genai.embed_content(
                model="models/embedding-001",
                content=text,
                task_type="retrieval_query"
            )['embedding']
        except Exception as e:
            st.error(f"Embedding failed. Check API Key. Error: {e}")
            return []

if prompt := st.chat_input(f"Ask a question... (Using: {chat_model_name})"):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.spinner("Analyzing circulars..."):
        # A. Embed
        vector = get_embedding(prompt)
        if not vector:
            st.stop()

        # B. Search
        try:
            response = supabase.rpc("match_documents", {
                "query_embedding": vector,
                "match_threshold": 0.3,
                "match_count": 100
            }).execute()
        except Exception as e:
            st.error(f"Database Error: {e}")
            st.stop()
        
        # C. Context
        matches = response.data
        context_text = ""
        if matches:
            for match in matches:
                title = match.get('title', 'Unknown')
                date = match.get('published_date', 'Unknown')
                content = match.get('content', '')
                context_text += f"\n---\nTitle: {title}\nDate: {date}\nExcerpt: {content}\n"
        else:
            context_text = "No specific circulars found."

        # D. Generate Answer
        try:
            model = genai.GenerativeModel(chat_model_name)
            
            full_prompt = f"""
            You are an expert financial analyst. Answer the user's question based ONLY on the RBI circulars provided below.
            
            USER QUESTION: {prompt}

            RBI CIRCULARS CONTEXT:
            {context_text}
            """
            
            ai_response = model.generate_content(full_prompt)
            answer = ai_response.text
            
        except Exception as e:
            st.error(f"Gemini Error ({chat_model_name}): {e}")
            answer = "Sorry, I could not generate an answer."

        st.session_state.messages.append({"role": "assistant", "content": answer})

        st.chat_message("assistant").write(answer)
