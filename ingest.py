import os
import datetime
import time
import requests
import smtplib
import ssl
from email.message import EmailMessage
from playwright.sync_api import sync_playwright
from supabase import create_client
import google.generativeai as genai

# 1. Configuration
# Note: Use 'gemini-embedding-001' for high-fidelity 3072-dimension vectors.
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_gemini_embedding(text):
    """
    Generates a 3072-dimension embedding using the latest stable model.
    """
    try:
        # Task type 'retrieval_document' is optimized for indexing chunks.
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']
    except Exception as e:
        print(f"❌ Embedding Error: {e}")
        return []

def generate_summary(text):
    """
    Generates a concise 2-sentence summary using Gemini 1.5 Flash.
    """
    try:
        # Switched to 'gemini-1.5-flash' for faster, more efficient summarization.
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Summarize the following RBI circular in 2 crisp sentences for a banking professional:\n\n{text[:3000]}"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Summary Error: {e}")
        return "Summary unavailable."

def send_email_notification(new_circulars):
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    recipients = os.getenv("EMAIL_RECIPIENTS")

    if not (sender and password and recipients):
        print("⚠️ Email credentials missing. Skipping email.")
        return

    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = recipients

    if not new_circulars:
        msg['Subject'] = "✅ RBI Daily Report: No New Circulars"
        html_content = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: #555;">🏦 RBI Daily Status Report</h2>
            <p>Our system scanned the RBI website at {datetime.datetime.now().strftime('%I:%M %p')}.</p>
            <div style="background-color: #e6fffa; border: 1px solid #b2f5ea; padding: 15px; border-radius: 5px; color: #234e52;">
                <strong>Status:</strong> No new circulars were published in the last 24 hours.
            </div>
          </body>
        </html>
        """
    else:
        msg['Subject'] = f"📢 RBI Update: {len(new_circulars)} New Circulars Detected"
        html_content = """<html><body style="font-family: Arial, sans-serif; color: #333;">"""
        html_content += """<h2 style="color: #0F52BA;">🏦 New RBI Circulars Detected</h2>"""
        for item in new_circulars:
            html_content += f"""
            <div style="margin-bottom: 20px; border-left: 4px solid #0F52BA; padding-left: 15px;">
                <h3 style="margin: 0;"><a href="{item['url']}" style="color: #0F52BA; text-decoration: none;">{item['title']}</a></h3>
                <p style="font-size: 11px; color: #888;">{item['date']}</p>
                <p style="background-color: #f8f9fa; padding: 10px; border-radius: 5px;">{item['summary']}</p>
            </div>"""
        html_content += "</body></html>"

    msg.set_content("Please view in HTML compatible client.")
    msg.add_alternative(html_content, subtype='html')

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print("✅ Email notification sent successfully!")
    except Exception as e:
        print(f"❌ Email Failed: {e}")

def run_scraper():
    print(f"--- Starting Daily Scraper: {datetime.datetime.now()} ---")
    new_items_found = [] 

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        page = browser.new_page()
        
        try:
            page.goto("https://www.rbi.org.in/scripts/bs_circularindexdisplay.aspx", timeout=60000)
            rows = page.query_selector_all("table tr")
        except Exception as e:
            print(f"❌ Scraper Failed to load RBI page: {e}")
            browser.close()
            return

        # Start from row 2 (skipping headers)
        for i, row in enumerate(rows[2:]):
            cols = row.query_selector_all("td")
            if len(cols) < 4: continue 
            
            date_text = cols[1].inner_text().strip()
            try:
                pub_date = datetime.datetime.strptime(date_text, "%d.%m.%Y").date()
            except: continue

            # Only process very recent items
            if (datetime.date.today() - pub_date).days > 3: continue

            link_el = cols[0].query_selector("a")
            if not link_el: continue
            href = link_el.get_attribute("href")
            if not href.startswith("http"): 
                href = f"https://www.rbi.org.in/scripts/{href}"
            
            title = cols[3].inner_text().strip()

            # Deduplication Check
            exists = supabase.table("documents").select("id").eq("url", href).execute()
            if exists.data: continue 

            print(f"🆕 NEW CIRCULAR: {title}")
            
            # 1. Insert Metadata
            data = supabase.table("documents").insert({
                "title": title, 
                "url": href, 
                "published_date": str(pub_date)
            }).execute()
            doc_id = data.data[0]['id']

            # 2. Get Full Text
            circular_page = browser.new_page()
            try:
                circular_page.goto(href, timeout=60000)
                full_text = circular_page.inner_text("body")
                circular_page.close()
            except:
                full_text = ""
                circular_page.close()

            summary = "No content available."
            if full_text:
                summary = generate_summary(full_text)
                # Chunking: 1000 characters with 100 overlap for better context
                chunks = [full_text[i:i+1000] for i in range(0, len(full_text), 900)]
                
                # Insert chunks with 3072-dim embeddings
                chunk_payload = []
                for chunk in chunks[:15]: # Processing first 15 chunks
                    vector = get_gemini_embedding(chunk)
                    if vector:
                        chunk_payload.append({
                            "document_id": doc_id, 
                            "content": chunk, 
                            "embedding": vector
                        })
                
                if chunk_payload:
                    supabase.table("document_chunks").insert(chunk_payload).execute()
                    print(f"✅ Indexed {len(chunk_payload)} chunks.")

            new_items_found.append({
                "title": title, "url": href, "date": str(pub_date), "summary": summary
            })

        browser.close()

    print(f"🚀 Scan complete. Found {len(new_items_found)} new updates.")
    send_email_notification(new_items_found)

if __name__ == "__main__":
    run_scraper()
