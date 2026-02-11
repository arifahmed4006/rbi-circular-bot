import os
import datetime
import time
from playwright.sync_api import sync_playwright
from supabase import create_client
from google import genai
from google.genai import types

# 1. Configuration
# The client must use the API key from your GitHub Secrets
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_gemini_embedding(text):
    """Generates 3072-dimension embeddings using the verified stable model name."""
    try:
        # VERIFIED: 'text-embedding-004' is the correct model string for the new SDK
        result = client.models.embed_content(
            model="text-embedding-004", 
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
        )
        return result.embeddings[0].values
    except Exception as e:
        print(f"❌ Embedding Error: {e}")
        return []

def run_scraper():
    print(f"--- Starting Verified 2026 Ingest: {datetime.datetime.now()} ---")
    start_of_2026 = datetime.date(2026, 1, 1)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a high-resolution viewport to ensure all table rows are rendered in the DOM
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()
        
        try:
            print("Navigating to RBI Index...")
            # Increased timeout for slow RBI servers
            page.goto("https://www.rbi.org.in/scripts/bs_circularindexdisplay.aspx", timeout=90000, wait_until="networkidle")
            
            # VERIFIED: Wait for the specific table class seen in your image
            page.wait_for_selector("table.table-common", timeout=30000)
            
            # Force a small scroll and wait to ensure the 30+ rows are fully loaded
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3) 

        except Exception as e:
            print(f"❌ Page Load Failed: {e}")
            browser.close()
            return

        # Select all rows specifically within the common table
        rows = page.query_selector_all("table.table-common tr")
        print(f"Verified: Detected {len(rows)} rows in the table.")

        count = 0
        for i, row in enumerate(rows):
            cols = row.query_selector_all("td")
            # RBI rows have 5 columns: Number, Date, Dept, Subject, Meant For
            if len(cols) < 4: continue
            
            date_text = cols[1].inner_text().strip()
            try:
                # Matches '11.2.2026' format seen in your image
                pub_date = datetime.datetime.strptime(date_text, "%d.%m.%Y").date()
            except: continue

            # Filter only for 2026
            if pub_date < start_of_2026:
                continue

            link_el = cols[0].query_selector("a")
            if not link_el: continue
            
            href = link_el.get_attribute("href")
            if not href.startswith("http"):
                href = f"https://www.rbi.org.in/scripts/{href}"
            
            title = cols[3].inner_text().strip()

            # Check if document metadata already exists in Supabase
            exists = supabase.table("documents").select("id").eq("url", href).execute()
            if exists.data:
                continue

            print(f"🆕 [{count+1}] Processing: {title[:70]}...")
            
            # 1. Insert Metadata
            try:
                data = supabase.table("documents").insert({
                    "title": title, 
                    "url": href, 
                    "published_date": str(pub_date)
                }).execute()
                doc_id = data.data[0]['id']
            except Exception as e:
                print(f"   ⚠️ Metadata insertion failed: {e}")
                continue

            # 2. Extract and Chunk Content
            cp = context.new_page()
            try:
                cp.goto(href, timeout=60000)
                full_text = cp.inner_text("body")
                cp.close()
            except:
                full_text = ""
                cp.close()

            if full_text:
                # Create chunks with 10% overlap for context preservation
                chunks = [full_text[x:x+1000] for x in range(0, len(full_text), 900)]
                chunk_payload = []
                
                # Index up to 30 chunks per circular
                for chunk in chunks[:30]: 
                    vector = get_gemini_embedding(chunk)
                    if vector:
                        chunk_payload.append({
                            "document_id": doc_id, 
                            "content": chunk, 
                            "embedding": vector
                        })
                
                if chunk_payload:
                    supabase.table("document_chunks").insert(chunk_payload).execute()
                    print(f"   ✅ Successfully stored {len(chunk_payload)} chunks.")
            
            count += 1
            time.sleep(1) # Safety delay to prevent RBI rate limiting

        browser.close()
    print(f"--- 2026 Ingest Successful. Total New Items: {count} ---")

if __name__ == "__main__":
    run_scraper()
