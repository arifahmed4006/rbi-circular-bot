import os
import datetime
import time
from playwright.sync_api import sync_playwright
from supabase import create_client
from google import genai
from google.genai import types

# 1. Configuration
# Using the modern google-genai client
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_gemini_embedding(text):
    """Generates 3072-dimension embeddings using the modern text-embedding-004 model."""
    try:
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
    print(f"--- Starting Full 2026 Ingest: {datetime.datetime.now()} ---")
    start_of_2026 = datetime.date(2026, 1, 1)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        page = context.new_page()
        
        try:
            print("Navigating to RBI Index...")
            # Use 'networkidle' to ensure the background data finishes loading
            page.goto("https://www.rbi.org.in/scripts/bs_circularindexdisplay.aspx", timeout=90000, wait_until="networkidle")
            
            # Wait for the main table to be present
            page.wait_for_selector("table", timeout=30000)
            
            # CRITICAL: Scroll down to trigger any lazy-loaded rows in the RBI table
            print("Scrolling to ensure all rows are loaded...")
            for _ in range(3):
                page.mouse.wheel(0, 2000)
                time.sleep(1)

        except Exception as e:
            print(f"❌ Initial Page Load Failed: {e}")
            browser.close()
            return

        rows = page.query_selector_all("table tr")
        print(f"Detected {len(rows)} potential rows in the table.")

        count = 0
        # Start from index 2 to skip headers
        for i, row in enumerate(rows[2:]):
            cols = row.query_selector_all("td")
            if len(cols) < 4: continue
            
            date_text = cols[1].inner_text().strip()
            try:
                pub_date = datetime.datetime.strptime(date_text, "%d.%m.%Y").date()
            except: continue

            # If we hit 2025 data, we stop (Automation is for 2026)
            if pub_date < start_of_2026:
                print(f"Reached 2025 records ({pub_date}). Stopping scraper.")
                break

            link_el = cols[0].query_selector("a")
            if not link_el: continue
            
            href = link_el.get_attribute("href")
            if not href.startswith("http"):
                href = f"https://www.rbi.org.in/scripts/{href}"
            
            title = cols[3].inner_text().strip()

            # Deduplication Check
            exists = supabase.table("documents").select("id").eq("url", href).execute()
            if exists.data:
                continue

            print(f"🆕 [{count+1}] Indexing 2026: {title[:70]}...")
            
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

            # 2. Extract Full Content
            cp = context.new_page()
            try:
                cp.goto(href, timeout=60000)
                # Wait for the main body to render
                cp.wait_for_selector("body")
                full_text = cp.inner_text("body")
            except:
                full_text = ""
            cp.close()

            if full_text:
                # 3. Create Chunks and Embeddings (3072 dims)
                chunks = [full_text[x:x+1000] for x in range(0, len(full_text), 900)]
                chunk_payload = []
                
                # We index more chunks for 2026 to ensure accuracy
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
                    print(f"   ✅ Saved {len(chunk_payload)} chunks for: {title[:30]}")
            
            count += 1
            # Add a small delay to respect the RBI server
            time.sleep(1)

        browser.close()
    print(f"--- 2026 Ingest Successful. Total New Items: {count} ---")

if __name__ == "__main__":
    run_scraper()
