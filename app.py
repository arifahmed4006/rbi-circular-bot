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
st.markdown("Querying RBI Circulars from 2025-2026 using Gemini & Supabase Vector Search.")

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

if prompt := st.chat_input("Ask about 2026 RBI Circulars..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # A. Get Embedding for the query (MUST MATCH INGEST DIMENSIONS: 3072)
        try:
            embedding_response = genai.embed_content(
                model="models/gemini-embedding-001", 
                content=prompt,
                task_type="retrieval_query",
                output_dimensionality=3072
            )
            query_embedding = embedding_response['embedding']
        except Exception as e:
            st.error(f"Embedding Error: {e}")
            st.stop()

        # B. Search Supabase (Vector Search)
        try:
            # This calls the SQL function you created in Supabase
            response = supabase.rpc("match_rbi_circulars", {
                "query_embedding": query_embedding,
                "match_threshold": 0.2, # Adjusted for better recall
                "match_count": 5
            }).execute()
        except Exception as e:
            st.error(f"Database Error: {e}")
            st.stop()
        
        # C. Build Context from Database Matches
        matches = response.data
        context_text = ""
        sources = []
        if matches:
            for match in matches:
                title = match.get('title', 'Unknown Title')
                url = match.get('url', '#')
                content = match.get('content', '')
                context_text += f"\n---\nSource: {title}\nContent: {content}\n"
                sources.append(f"[{title}]({url})")
        else:
            context_text = "No relevant RBI circulars found in the database."

        # D. Generate Final Answer with Gemini
        try:
            model = genai.GenerativeModel(chat_model_name)
            
            full_prompt = f"""
            You are a specialized RBI Circular Assistant. 
            Answer the user's question based ONLY on the following snippets from RBI circulars.
            If the answer isn't in the context, say you don't have that information.
            
            USER QUESTION: {prompt}

            RELEVANT CIRCULAR SNIPPETS:
            {context_text}
            """
            
            ai_response = model.generate_content(full_prompt)
            answer = ai_response.text
            
            if sources:
                answer += "\n\n**Sources:**\n" + "\n".join(list(set(sources)))
            
        except Exception as e:
            st.error(f"AI Generation Error: {e}")
            answer = "Sorry, I encountered an error while analyzing the circulars."

        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
