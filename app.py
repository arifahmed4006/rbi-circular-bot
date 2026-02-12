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
        # A. Get Embedding (Using the most direct method)
        query_embedding = None
        try:
            # We use the explicit 'embed_content' call from the genai module directly
            response = genai.embed_content(
                model="models/gemini-embedding-001",
                content=prompt, # Try passing it directly here
                task_type="retrieval_query",
                output_dimensionality=3072
            )
            
            # The library sometimes returns 'embedding' as a list of lists 
            # or a single list depending on the version. This logic handles both:
            raw_embedding = response['embedding']
            if isinstance(raw_embedding[0], list):
                query_embedding = raw_embedding[0]
            else:
                query_embedding = raw_embedding

        except Exception as e:
            # SECOND ATTEMPT: If direct string fails, try forced list
            try:
                response = genai.embed_content(
                    model="models/gemini-embedding-001",
                    content=[prompt],
                    task_type="retrieval_query",
                    output_dimensionality=3072
                )
                query_embedding = response['embedding'][0]
            except Exception as e2:
                st.error(f"Embedding generation failed: {e2}")
                st.stop()

        # B. Search Supabase (Only if embedding succeeded)
        if query_embedding:
            try:
                search_response = supabase.rpc("match_rbi_circulars", {
                    "query_embedding": query_embedding,
                    "match_threshold": 0.2,
                    "match_count": 5
                }).execute()
                matches = search_response.data
            except Exception as e:
                st.error(f"Database Search Failed: {e}")
                st.stop()
        
        # C. Build Context
        context_text = ""
        sources = []
        if matches:
            for m in matches:
                title = m.get('title', 'Unknown Title')
                url = m.get('url', '#')
                content = m.get('content', '')
                context_text += f"\n---\nSource: {title}\nContent: {content}\n"
                sources.append(f"[{title}]({url})")
        else:
            context_text = "No relevant RBI circulars found in the database."

        # D. Generate Answer with Gemini
        try:
            model = genai.GenerativeModel(chat_model_name)
            ai_response = model.generate_content(
                f"Answer the question based ONLY on this context.\n\nContext: {context_text}\n\nQuestion: {prompt}"
            )
            st.markdown(ai_response.text)
            if sources:
                st.markdown("**Sources:**\n" + "\n".join(list(set(sources))))
            
            st.session_state.messages.append({"role": "assistant", "content": ai_response.text})
        except Exception as e:
            st.error(f"AI Generation Error: {e}")
            answer = "Sorry, I encountered an error while analyzing the circulars."

    st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})

