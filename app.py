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

# --- AUTO-DETECT CHAT MODEL ---
@st.cache_resource
def get_chat_model_name():
    try:
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        for preferred in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']:
            if preferred in available_models:
                return preferred
        return "models/gemini-pro"
    except:
        return "models/gemini-1.5-flash"

chat_model_name = get_chat_model_name()

# 4. Chat Interface
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask about RBI Circulars..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # A. Get Embedding for the query (Updated for 3072 dims)
        query_embedding = []
        try:
            embedding_response = genai.embed_content(
                model="models/text-embedding-001", 
                content=prompt,
                task_type="retrieval_query",
                )
            query_embedding = embedding_response['embedding']
        except Exception as e:
            st.error(f"Embedding Error: {e}")
            st.stop()

        # B. Search Supabase (Vector Search)
        try:
            response = supabase.rpc("match_rbi_circulars", {
                "query_embedding": query_embedding,
                "match_threshold": 0.3,
                "match_count": 5
            }).execute()
        except Exception as e:
            st.error(f"Database Error: {e}")
            st.stop()
        
        # C. Build Context
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
            You are an expert financial analyst. Answer the user's question based ONLY on the RBI circulars provided.
            
            USER QUESTION: {prompt}

            RBI CIRCULARS CONTEXT:
            {context_text}
            """
            ai_response = model.generate_content(full_prompt)
            answer = ai_response.text
            
        except Exception as e:
            st.error(f"AI Error: {e}")
            answer = "Sorry, I could not generate an answer."

        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})

