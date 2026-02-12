import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client
import os
from dotenv import load_dotenv

# ==============================
# CONFIG
# ==============================

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

client = genai.Client(api_key=GOOGLE_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="RBI Smart Assistant", layout="wide")
st.title("🏦 RBI Circular Assistant")

# ==============================
# CHAT STATE
# ==============================

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==============================
# USER INPUT
# ==============================

if prompt := st.chat_input("Ask about RBI Circulars..."):

    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):

        # --------------------------
        # EMBED QUERY
        # --------------------------
        embed_response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=[prompt],
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=3072
            )
        )

        query_embedding = embed_response.embeddings[0].values

        # --------------------------
        # VECTOR SEARCH
        # --------------------------
        search_response = supabase.rpc("match_rbi_circulars", {
            "query_embedding": query_embedding,
            "match_threshold": 0.65,
            "match_count": 5
        }).execute()

        matches = search_response.data

        # --------------------------
        # BUILD CONTEXT
        # --------------------------
        context_text = ""
        sources = []

        if matches:
            for m in matches:
                context_text += f"""
--------------------------------
Title: {m['title']}
Date: {m['published_date']}
Content:
{m['content']}
"""
                sources.append(f"[{m['title']}]({m['url']})")

        system_prompt = """
You are an RBI regulatory assistant.

Rules:
1. Answer ONLY using the provided RBI circular context.
2. If information is not present, say:
   "This information is not available in the RBI circular database."
3. Do NOT hallucinate regulatory details.
4. Cite circular titles clearly.
"""

        model = genai.GenerativeModel("gemini-1.5-flash")

        response = model.generate_content(
            f"{system_prompt}\n\nContext:\n{context_text}\n\nQuestion:\n{prompt}"
        )

        st.markdown(response.text)

        if sources:
            st.markdown("### Sources")
            for s in list(set(sources)):
                st.markdown(f"- {s}")

        st.session_state.messages.append({
            "role": "assistant",
            "content": response.text
        })
