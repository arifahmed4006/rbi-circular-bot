import os
import datetime
import time
from playwright.sync_api import sync_playwright
from supabase import create_client
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 1. Configuration
load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_gemini_embedding(text):
    """
    Generates high-fidelity 3072-dimension embeddings.
    Model: gemini-embedding-001 is the current standard.
    """
    try:
        result = client.models.embed_content(
            model="gemini-embedding-001", 
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=3072
            )
        )
        return result.embeddings[0].values
    except Exception as e:
        print(f"❌ Embedding Error: {e}")
        return []

def run_scraper_2026():
    print(f"--- 2026 Final Ingest (3072-Dim) ---")
    
    with sync_playwright() as p:
        # headless=False so you can watch and navigate
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("Opening RBI Index...")
        page.goto("https://www.rbi.org.in/scripts/bs_circularindexdisplay.aspx", wait_until="load")
        
        print("\n" + "!"*50)
        print("ACTION REQUIRED:")
        print("1. In the browser, navigate so that 2026 circulars are visible.")
        input("👉 Once 2026 data is on screen, press ENTER here...")
        print("!"*50 + "\n")

        rows = page.query_selector_all("tr")
        count = 0
        for i, row in enumerate(rows):
            cols = row.query_selector_all("td")
            if len(cols) < 4: continue
            
            date_text = cols[1].inner_text().strip()
            try:
                pub_date = datetime.datetime.strptime(date_text, "%d.%m.%Y").date()
            except: continue

            # Target 2026 ONLY
            if pub_date.year != 2026: continue

            link_el = cols[0].query_selector("a")
            if not link_el: continue
            
            href = link_el.get_attribute("href")
            if not href.startswith("http"): href = f"https://www.rbi.org.in/scripts/{href}"
            title = cols[3].inner_text().strip()

            # Deduplication
            if supabase.table("documents").select("id").eq("url", href).execute().data:
                continue

            print(f"🆕 Processing: {title[:60]}...")
            
            # Metadata
            data = supabase.table("documents").insert({
                "title": title, "url": href, "published_date": str(pub_date)
            }).execute()
            doc_id = data.data[0]['id']

            # Content
            cp = context.new_page()
            try:
                cp.goto(href, timeout=60000)
                time.sleep(1)
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
                    print(f"   ✅ Saved {len(payload)} chunks.")
            
            count += 1

        browser.close()
    print(f"--- Done! Ingested {count} items. ---")

if __name__ == "__main__":
    run_scraper_2026()
