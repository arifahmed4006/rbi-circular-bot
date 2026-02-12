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
st.set_page_config(page_title="RBI Smart Assistant", layout="wide")
st.title("🏦 RBI Circular Assistant")

# --- AUTO-DETECT CHAT MODEL ---
@st.cache_resource
def get_chat_model_name():
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for preferred in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']:
            if preferred in available_models:
                return preferred
        return "models/gemini-1.5-flash"
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
        # A. Get Embedding (FIXED FOR BATCH/LIST ERRORS)
        query_embedding = []
        try:
            # We use embed_content with a list [prompt]
            # This version avoids the 'requests[]' and 'null to object' errors
            response = genai.embed_content(
                model="models/gemini-embedding-001",
                content=[prompt],
                task_type="retrieval_query",
                output_dimensionality=3072
            )
            
            # Extracting correctly based on the 'requests[]' structure
            if 'embedding' in response:
                query_embedding = response['embedding'][0]
            else:
                st.error("Embedding key not found in response.")
                st.stop()

        except Exception as e:
            st.error(f"Embedding Error: {e}")
            st.stop()

        # B. Search Supabase
        try:
            search_response = supabase.rpc("match_rbi_circulars", {
                "query_embedding": query_embedding,
                "match_threshold": 0.2,
                "match_count": 5
            }).execute()
        except Exception as e:
            st.error(f"Database Search Failed: {e}")
            st.stop()
        
        # C. Build Context
        matches = search_response.data
        context_text = ""
        sources = []
        if matches:
            for m in matches:
                title = m.get('title', 'Unknown')
                context_text += f"\n---\nTitle: {title}\nContent: {m.get('content')}\n"
                sources.append(f"[{title}]({m.get('url')})")
        else:
            context_text = "No relevant circulars found in the database."

        # D. Generate Answer
        try:
            model = genai.GenerativeModel(chat_model_name)
            ai_response = model.generate_content(
                f"Answer the question based ONLY on this context.\n\nContext: {context_text}\n\nQuestion: {prompt}"
            )
            answer = ai_response.text
            if sources:
                answer += "\n\n**Sources:**\n" + "\n".join(list(set(sources)))
        except Exception as e:
            st.error(f"Gemini Error: {e}")
            answer = "Error generating response."

        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
