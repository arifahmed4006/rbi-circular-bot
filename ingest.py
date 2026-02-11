import os
import datetime
import time
from playwright.sync_api import sync_playwright
from supabase import create_client
import google.generativeai as genai

# Configuration
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_gemini_embedding(text):
    try:
        # 3072-dimension model (Option B)
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']
    except Exception as e:
        print(f"❌ Embedding failed: {e}")
        return []

def run_scraper():
    print("--- Starting Full 2026 Automatic Ingest ---")
    start_of_2026 = datetime.date(2026, 1, 1)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Navigate and WAIT for the table to actually exist
        page.goto("https://www.rbi.org.in/scripts/bs_circularindexdisplay.aspx", wait_until="networkidle")
        page.wait_for_selector("table.table-common", timeout=10000) 

        # Extract ALL rows
        rows = page.query_selector_all("table tr")
        print(f"Total rows detected: {len(rows)}")

        for i, row in enumerate(rows):
            if i < 2: continue # Skip header rows
            
            cols = row.query_selector_all("td")
            if len(cols) < 4: continue
            
            date_text = cols[1].inner_text().strip()
            try:
                pub_date = datetime.datetime.strptime(date_text, "%d.%m.%Y").date()
            except: continue

            # If we hit 2025, we stop (Automation is for 2026 only)
            if pub_date < start_of_2026:
                print(f"Reached 2025 data ({pub_date}). Stopping automated run.")
                break

            link_el = cols[0].query_selector("a")
            if not link_el: continue
            href = link_el.get_attribute("href")
            if not href.startswith("http"): href = f"https://www.rbi.org.in/scripts/{href}"
            title = cols[3].inner_text().strip()

            # Skip if already exists
            exists = supabase.table("documents").select("id").eq("url", href).execute()
            if exists.data:
                continue

            print(f"🆕 Ingesting 2026: {title[:60]}...")
            
            # Save Metadata
            data = supabase.table("documents").insert({
                "title": title, "url": href, "published_date": str(pub_date)
            }).execute()
            doc_id = data.data[0]['id']

            # Extract Content
            cp = browser.new_page()
            cp.goto(href, timeout=60000)
            full_text = cp.inner_text("body")
            cp.close()

            if full_text:
                # Chunking and Vectorizing (3072 dims)
                chunks = [full_text[x:x+1000] for x in range(0, len(full_text), 900)]
                payload = []
                for chunk in chunks[:25]: # Increased depth for 2026
                    vector = get_gemini_embedding(chunk)
                    if vector:
                        payload.append({"document_id": doc_id, "content": chunk, "embedding": vector})
                
                if payload:
                    supabase.table("document_chunks").insert(payload).execute()
                    print(f"   ✅ Saved {len(payload)} chunks.")

        browser.close()
    print("--- 2026 Automation Complete ---")

if __name__ == "__main__":
    run_scraper()
