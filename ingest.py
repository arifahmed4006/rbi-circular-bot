import os
import datetime
import time
import re
from playwright.sync_api import sync_playwright
from supabase import create_client
from google import genai
from google.genai import types
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


# ==============================
# EMBEDDING (Batch)
# ==============================

def get_embeddings_batch(text_chunks):
    try:
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text_chunks,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=3072
            )
        )
        return [e.values for e in result.embeddings]
    except Exception as e:
        print(f"❌ Batch Embedding Error: {e}")
        return []


# ==============================
# SEMANTIC CHUNKING
# ==============================

def semantic_chunk(text, max_chars=1200):
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) < max_chars:
            current += "\n" + para
        else:
            chunks.append(current.strip())
            current = para

    if current:
        chunks.append(current.strip())

    return chunks


# ==============================
# SCRAPER
# ==============================

def run_scraper():
    print("\n--- RBI Circular Ingestion Started ---")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context()
        page = context.new_page()

        print("Opening RBI Circular Index...")
        page.goto("https://www.rbi.org.in/scripts/bs_circularindexdisplay.aspx")

        print("\n" + "!"*50)
        print("ACTION REQUIRED:")
        print("Navigate manually to desired year/page.")
        input("👉 Once correct circular list is visible, press ENTER...")
        print("!"*50 + "\n")

        rows = page.query_selector_all("tr")
        processed = 0

        for row in rows:
            cols = row.query_selector_all("td")
            if len(cols) < 4:
                continue

            date_text = cols[1].inner_text().strip()
            try:
                pub_date = datetime.datetime.strptime(date_text, "%d.%m.%Y").date()
            except:
                continue

            link_el = cols[0].query_selector("a")
            if not link_el:
                continue

            href = link_el.get_attribute("href")
            if not href.startswith("http"):
                href = f"https://www.rbi.org.in/scripts/{href}"

            title = cols[3].inner_text().strip()

            # ------------------------------
            # DOCUMENT UPSERT
            # ------------------------------
            existing = supabase.table("documents").select("id").eq("url", href).execute().data

            if existing:
                doc_id = existing[0]["id"]
                print(f"🔄 Updating existing: {title[:60]}")
                supabase.table("document_chunks").delete().eq("document_id", doc_id).execute()
            else:
                result = supabase.table("documents").insert({
                    "title": title,
                    "url": href,
                    "published_date": str(pub_date)
                }).execute()
                doc_id = result.data[0]["id"]
                print(f"🆕 New: {title[:60]}")

            # ------------------------------
            # SCRAPE CONTENT
            # ------------------------------
            cp = context.new_page()
            try:
                cp.goto(href, timeout=60000)
                time.sleep(1)
                full_text = cp.inner_text("body")
            except:
                full_text = ""
            cp.close()

            if not full_text or len(full_text) < 300:
                continue

            chunks = semantic_chunk(full_text)

            # Batch embeddings
            embeddings = get_embeddings_batch(chunks)

            payload = []
            for idx, (chunk, vector) in enumerate(zip(chunks, embeddings)):
                payload.append({
                    "document_id": doc_id,
                    "content": chunk,
                    "embedding": vector,
                    "chunk_index": idx,
                    "title": title,
                    "url": href,
                    "published_date": str(pub_date)
                })

            if payload:
                supabase.table("document_chunks").insert(payload).execute()
                print(f"   ✅ Saved {len(payload)} chunks.")

            processed += 1

        browser.close()

    print(f"\n--- Ingestion Complete: {processed} documents processed ---")


if __name__ == "__main__":
    run_scraper()
