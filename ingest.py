import os
import datetime
import time
from playwright.sync_api import sync_playwright
from supabase import create_client
from google import genai
from google.genai import types

# 1. Configuration
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_gemini_embedding(text):
    """Generates 3072-dimension embeddings."""
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
    print(f"--- Starting Final 2026 Ingest: {datetime.datetime.now()} ---")
    start_of_2026 = datetime.date(2026, 1, 1)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a real browser context to ensure table rendering
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        
        try:
            print("Navigating to RBI Index...")
            # We wait for 'domcontentloaded' instead of 'networkidle' to act on the preloaded data
            page.goto("https://www.rbi.org.in/scripts/bs_circularindexdisplay.aspx", timeout=90000, wait_until="domcontentloaded")
            
            # No wait_for_selector needed if rows are preloaded. 
            # We simply give the browser a 2-second breath.
            time.sleep(2)

        except Exception as e:
            print(f"❌ Navigation Failed: {e}")
            browser.close()
            return

        # Direct extraction of all table rows on the page
        rows = page.query_selector_all("tr")
        print(f"Total rows detected: {len(rows)}")

        count = 0
        for i, row in enumerate(rows):
            cols = row.query_selector_all("td")
            # We only process rows that have at least 4 columns (Date and Subject)
            if len(cols) < 4: continue
            
            date_text = cols[1].inner_text().strip()
            try:
                # Matches the 11.2.2026 format from the site
                pub_date = datetime.datetime.strptime(date_text, "%d.%m.%Y").date()
            except: continue

            # Filter for 2026
            if pub_date < start_of_2026:
                continue

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

            print(f"🆕 [{count+1}] Processing: {title[:70]}...")
            
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

            # Content Extraction from Circular Link
            cp = context.new_page()
            try:
                cp.goto(href, timeout=60000)
                full_text = cp.inner_text("body")
            except:
                full_text = ""
            cp.close()

            if full_text:
                chunks = [full_text[x:x+1000] for x in range(0, len(full_text), 900)]
                chunk_payload = []
                
                for chunk in chunks[:25]: 
                    vector = get_gemini_embedding(chunk)
                    if vector:
                        chunk_payload.append({
                            "document_id": doc_id, 
                            "content": chunk, 
                            "embedding": vector
                        })
                
                if chunk_payload:
                    supabase.table("document_chunks").insert(chunk_payload).execute()
            
            count += 1
            time.sleep(1) # Rate limiting

        browser.close()
    print(f"--- 2026 Ingest Successful. Total New Items: {count} ---")

if __name__ == "__main__":
    run_scraper()
