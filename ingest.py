import os
import datetime
import time
import warnings
from playwright.sync_api import sync_playwright
from supabase import create_client
import google.generativeai as genai
from dotenv import load_dotenv

warnings.filterwarnings("ignore")
load_dotenv()

# Setup Keys
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_gemini_embedding(text):
    try:
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']
    except:
        return []

def run_scraper(days_back=1800):
    print(f"--- Starting Scraper (Web Page Mode) ---")
    cutoff_date = datetime.date.today() - datetime.timedelta(days=days_back)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        
        # Main page (The List)
        page = browser.new_page()
        print("Navigating to RBI List...")
        page.goto("https://www.rbi.org.in/scripts/bs_circularindexdisplay.aspx", timeout=60000)
        time.sleep(5)

        rows = page.query_selector_all("table tr")
        print(f"Found {len(rows)} rows.")

        count = 0
        for i, row in enumerate(rows):
            if i < 2: continue 
            
            cols = row.query_selector_all("td")
            if len(cols) < 4: continue 
            
            # 1. GET DATE (Column 1)
            date_text = cols[1].inner_text().strip()
            try:
                pub_date = datetime.datetime.strptime(date_text, "%d.%m.%Y").date()
            except:
                continue

            if pub_date < cutoff_date:
                continue

            # 2. GET LINK (Column 0)
            link_col = cols[0]
            link_el = link_col.query_selector("a")
            if not link_el: continue
            
            href = link_el.get_attribute("href")
            if not href.startswith("http"):
                href = f"https://www.rbi.org.in/scripts/{href}"

            # 3. GET TITLE (Column 3)
            title = cols[3].inner_text().strip()

            print(f"MATCH! Date: {pub_date} | Title: {title[:40]}...")
            
            # 4. SAVE METADATA TO DB
            try:
                exists = supabase.table("documents").select("id").eq("url", href).execute()
                if exists.data:
                    print("   - Already in DB.")
                    continue

                data = supabase.table("documents").insert({
                    "title": title, "url": href, "published_date": str(pub_date)
                }).execute()
                doc_id = data.data[0]['id']
            except Exception as e:
                print(f"   - DB Error: {e}")
                continue

            # 5. READ THE WEBPAGE CONTENT (The Fix)
            try:
                print("   - Reading Circular Text...")
                
                # Open a TEMPORARY tab to read the circular
                circular_page = browser.new_page()
                circular_page.goto(href, timeout=60000)
                
                # Wait for text to load
                circular_page.wait_for_selector("body")
                
                # Grab all text from the page body
                full_text = circular_page.inner_text("body")
                
                # Close the temp tab
                circular_page.close()
                
                if full_text:
                    print(f"   - Extracted {len(full_text)} characters.")
                    print("   - Creating AI Embeddings...")
                    
                    # Chunk and Embed
                    chunks = [full_text[i:i+1000] for i in range(0, len(full_text), 1000)]
                    
                    # Process first 5 chunks (Giving you more context now)
                    for chunk in chunks[:5]: 
                        vector = get_gemini_embedding(chunk)
                        if vector:
                            supabase.table("document_chunks").insert({
                                "document_id": doc_id, "content": chunk, "embedding": vector
                            }).execute()
                            time.sleep(1) # Be nice to Google API
            except Exception as e:
                print(f"   - Error reading page: {e}")
                try:
                    circular_page.close() # Ensure it closes if error
                except:
                    pass

                    
        browser.close()

if __name__ == "__main__":

    run_scraper()

