import streamlit as st
import google.generativeai as genai
from supabase import create_client
import os
from dotenv import load_dotenv

# 1. Setup
load_dotenv()
st.set_page_config(page_title="RBI Intelligence", layout="wide")

try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    st.error(f"Connection Error: {e}")
    st.stop()

# --- NEW: SYSTEM AWARENESS FETCH ---
def get_system_context():
    """Fetches real-time stats and titles to make the AI smart about the whole DB."""
    try:
        # Get total count
        res = supabase.table("documents").select("id", count="exact").execute()
        total = res.count if res.count else 0
        
        # Get all titles (for summarization awareness)
        titles_res = supabase.table("documents").select("title").execute()
        titles_list = [row['title'] for row in titles_res.data]
        return total, titles_list
    except:
        return 0, []

total_count, all_titles = get_system_context()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🎛️ Control Center")
    st.success(f"📊 **Total Circulars Indexed: {total_count}**")
    
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    with st.expander("⚙️ System Architecture"):
        st.caption("Scraper: Playwright | DB: Supabase | Brain: Gemini 1.5")
    
    st.markdown("---")
    st.caption(f"Created by **Shaik Arif Ahmed**")

# --- MAIN UI ---
st.markdown("🏛️ **RBI Regulatory Intelligence**")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- CHAT LOGIC ---
if prompt := st.chat_input("Ask about circulars..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            # 1. Search
            vector = genai.embed_content(model="models/text-embedding-004", content=prompt, task_type="retrieval_query")['embedding']
            search_res = supabase.rpc("match_documents", {"query_embedding": vector, "match_threshold": 0.1, "match_count": 10}).execute()
            
            context_text = ""
            sources = []
            for match in search_res.data:
                context_text += f"\n- {match['title']}: {match['content']}\n"
                if match['url'] not in [s['url'] for s in sources]:
                    sources.append({"title": match['title'], "url": match['url'], "date": match['published_date']})

            # 2. AI Synthesis (Updated with Global Awareness)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # This prompt tells the AI EXACTLY what is in the DB
            system_instruction = f"""
            You are a Senior RBI Consultant. 
            DATABASE STATUS: You have {total_count} total circulars in your database.
            TITLES INDEXED: {", ".join(all_titles)}
            
            INSTRUCTIONS:
            - If the user asks for a count, use the DATABASE STATUS above ({total_count}).
            - If the user asks for a summary of everything, refer to the TITLES INDEXED.
            - For detailed technical questions, use the CONTEXT provided below.
            """
            
            full_prompt = f"{system_instruction}\n\nUSER QUESTION: {prompt}\n\nCONTEXT SNIPPETS:\n{context_text}"
            
            ai_response = model.generate_content(full_prompt).text
            st.markdown(ai_response)
            
            if sources:
                with st.expander("📚 Sources"):
                    for s in sources: st.markdown(f"[{s['title']}]({s['url']}) ({s['date']})")

            st.session_state.messages.append({"role": "assistant", "content": ai_response, "sources": sources})
