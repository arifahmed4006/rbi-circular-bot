import os
import datetime
import time
import playwright
from playwright.sync_api import sync_playwright
from supabase import create_client
import google.generativeai as genai

# Configuration
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_gemini_embedding(text):
    try:
        # UPDATED: Using 3072-dimension model
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']
    except Exception as e:
        print(f"Error: {e}")
        return []

def run_scraper():
    print("--- Starting 2026 Full Ingest ---")
    start_of_2026 = datetime.date(2026, 1, 1)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.rbi.org.in/scripts/bs_circularindexdisplay.aspx", timeout=60000)
        rows = page.query_selector_all("table tr")

        for i, row in enumerate(rows[2:]):
            cols = row.query_selector_all("td")
            if len(cols) < 4: continue
            
            date_text = cols[1].inner_text().strip()
            try:
                pub_date = datetime.datetime.strptime(date_text, "%d.%m.%Y").date()
            except: continue

            # STOP if we hit 2025 (since this script is only for 2026 automation)
            if pub_date < start_of_2026:
                continue

            link_el = cols[0].query_selector("a")
            if not link_el: continue
            href = link_el.get_attribute("href")
            if not href.startswith("http"): href = f"https://www.rbi.org.in/scripts/{href}"
            title = cols[3].inner_text().strip()

            # Deduplication
            exists = supabase.table("documents").select("id").eq("url", href).execute()
            if exists.data: continue

            print(f"🆕 Processing 2026: {title[:50]}...")
            data = supabase.table("documents").insert({
                "title": title, "url": href, "published_date": str(pub_date)
            }).execute()
            doc_id = data.data[0]['id']

            # Content Extraction
            cp = browser.new_page()
            cp.goto(href, timeout=60000)
            full_text = cp.inner_text("body")
            cp.close()

            if full_text:
                chunks = [full_text[i:i+1000] for i in range(0, len(full_text), 900)]
                payload = []
                for chunk in chunks[:20]: # Increased depth for better memory
                    vector = get_gemini_embedding(chunk)
                    if vector:
                        payload.append({"document_id": doc_id, "content": chunk, "embedding": vector})
                
                if payload:
                    supabase.table("document_chunks").insert(payload).execute()

        browser.close()
    print("--- 2026 Ingest Complete ---")

if __name__ == "__main__":
    run_scraper()
