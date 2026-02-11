import os
import datetime
import time
from playwright.sync_api import sync_playwright
from supabase import create_client
from google import genai # Modern library
from google.genai import types

# 1. Configuration
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_gemini_embedding(text):
    try:
        # Using the new library syntax for 3072 dimensions
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
    print("--- Starting 2026 Full Ingest (Stable Mode) ---")
    start_of_2026 = datetime.date(2026, 1, 1)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Increase timeout to 90 seconds for slow RBI servers
        try:
            print("Navigating to RBI Index...")
            page.goto("https://www.rbi.org.in/scripts/bs_circularindexdisplay.aspx", timeout=90000, wait_until="domcontentloaded")
            
            # Use a more generic selector (table) if 'table.table-common' fails
            page.wait_for_selector("table", timeout=30000) 
            time.sleep(5) # Extra buffer for the dynamic table to render
        except Exception as e:
            print(f"❌ Page Load Failed: {e}")
            browser.close()
            return

        rows = page.query_selector_all("table tr")
        print(f"Total rows detected: {len(rows)}")

        for i, row in enumerate(rows):
            if i < 2: continue # Skip headers
            
            cols = row.query_selector_all("td")
            if len(cols) < 4: continue
            
            date_text = cols[1].inner_text().strip()
            try:
                pub_date = datetime.datetime.strptime(date_text, "%d.%m.%Y").date()
            except: continue

            # Only process 2026
            if pub_date < start_of_2026:
                print(f"Reached 2025 records ({pub_date}). Stopping.")
                break

            link_el = cols[0].query_selector("a")
            if not link_el: continue
            href = link_el.get_attribute("href")
            if not href.startswith("http"): href = f"https://www.rbi.org.in/scripts/{href}"
            title = cols[3].inner_text().strip()

            # Check for existing
            exists = supabase.table("documents").select("id").eq("url", href).execute()
            if exists.data: continue

            print(f"🆕 Indexing 2026 Circular: {title[:60]}...")
            
            data = supabase.table("documents").insert({
                "title": title, "url": href, "published_date": str(pub_date)
            }).execute()
            doc_id = data.data[0]['id']

            # Process Content
            cp = browser.new_page()
            try:
                cp.goto(href, timeout=60000)
                full_text = cp.inner_text("body")
            except:
                full_text = ""
            cp.close()

            if full_text:
                chunks = [full_text[x:x+1000] for x in range(0, len(full_text), 900)]
                payload = []
                for chunk in chunks[:25]:
                    vector = get_gemini_embedding(chunk)
                    if vector:
                        payload.append({"document_id": doc_id, "content": chunk, "embedding": vector})
                
                if payload:
                    supabase.table("document_chunks").insert(payload).execute()
                    print(f"   ✅ Stored {len(payload)} chunks.")

        browser.close()
    print("--- 2026 Automation Successful ---")

if __name__ == "__main__":
    run_scraper()
