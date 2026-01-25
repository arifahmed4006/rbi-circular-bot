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
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_gemini_embedding(text):
    try:
        return genai.embed_content(model="models/text-embedding-004", content=text, task_type="retrieval_document")['embedding']
    except:
        return []

def generate_summary(text):
    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"Summarize the following RBI circular in 2 simple sentences for a banker:\n\n{text[:2000]}"
        response = model.generate_content(prompt)
        return response.text
    except:
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

    # --- SCENARIO 1: NO NEW CIRCULARS ---
    if not new_circulars:
        msg['Subject'] = "✅ RBI Daily Report: No New Circulars"
        html_content = """
        <html>
          <body style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: #555;">🏦 RBI Daily Status Report</h2>
            <p>Our system scanned the RBI website at 9:00 AM.</p>
            <div style="background-color: #e6fffa; border: 1px solid #b2f5ea; padding: 15px; border-radius: 5px; color: #234e52;">
                <strong>Status:</strong> No new circulars were published in the last 24 hours.
            </div>
            <hr>
            <p style="font-size: 12px; color: #888;">
                <a href="https://rbi-circular-bot.streamlit.app/">Visit Dashboard</a>
            </p>
          </body>
        </html>
        """

    # --- SCENARIO 2: NEW CIRCULARS FOUND ---
    else:
        msg['Subject'] = f"📢 RBI Update: {len(new_circulars)} New Circulars Detected"
        html_content = """
        <html>
          <body style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: #0F52BA;">🏦 New RBI Circulars Detected</h2>
            <p>The following updates were found during the daily scan:</p>
            <hr>
        """
        for item in new_circulars:
            html_content += f"""
            <div style="margin-bottom: 20px;">
                <h3 style="margin: 0;"><a href="{item['url']}" style="color: #0F52BA; text-decoration: none;">{item['title']}</a></h3>
                <p style="font-size: 12px; color: #666; margin-top: 2px;">{item['date']}</p>
                <p style="background-color: #f4f6f9; padding: 10px; border-radius: 5px; font-style: italic;">
                    "{item['summary']}"
                </p>
            </div>
            """
        html_content += """
            <hr>
            <p style="font-size: 12px; color: #888;">
                <a href="https://rbi-circular-bot.streamlit.app/">Visit Dashboard</a>
            </p>
          </body>
        </html>
        """

    msg.set_content("Please view in HTML compatible client.")
    msg.add_alternative(html_content, subtype='html')

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print("✅ Email notification sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def run_scraper():
    print("--- Starting Daily Scraper ---")
    new_items_found = [] 

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        page = browser.new_page()
        page.goto("https://www.rbi.org.in/scripts/bs_circularindexdisplay.aspx", timeout=60000)

        rows = page.query_selector_all("table tr")
        print(f"Found {len(rows)} rows.")

        for i, row in enumerate(rows):
            if i < 2: continue 
            
            cols = row.query_selector_all("td")
            if len(cols) < 4: continue 
            
            date_text = cols[1].inner_text().strip()
            try:
                pub_date = datetime.datetime.strptime(date_text, "%d.%m.%Y").date()
            except:
                continue

            # Only process recent items (last 3 days)
            today = datetime.date.today()
            if (today - pub_date).days > 3: 
                continue

            link_el = cols[0].query_selector("a")
            if not link_el: continue
            href = link_el.get_attribute("href")
            if not href.startswith("http"): href = f"https://www.rbi.org.in/scripts/{href}"
            
            title = cols[3].inner_text().strip()

            # Check Database
            exists = supabase.table("documents").select("id").eq("url", href).execute()
            if exists.data:
                continue # Skip existing

            # New Item Found
            print(f"🆕 NEW FOUND: {title}")
            
            # Save to DB
            data = supabase.table("documents").insert({
                "title": title, "url": href, "published_date": str(pub_date)
            }).execute()
            doc_id = data.data[0]['id']

            # Get Content & Summarize
            circular_page = browser.new_page()
            circular_page.goto(href, timeout=60000)
            try:
                full_text = circular_page.inner_text("body")
            except:
                full_text = ""
            circular_page.close()

            summary = "No content available."
            if full_text:
                summary = generate_summary(full_text)
                chunks = [full_text[i:i+1000] for i in range(0, len(full_text), 1000)]
                for chunk in chunks[:10]:
                    vector = get_gemini_embedding(chunk)
                    if vector:
                        supabase.table("document_chunks").insert({
                            "document_id": doc_id, "content": chunk, "embedding": vector
                        }).execute()
                        time.sleep(0.5)

            new_items_found.append({
                "title": title,
                "url": href,
                "date": str(pub_date),
                "summary": summary
            })

        browser.close()

    # --- FINAL STEP: ALWAYS EMAIL ---
    print(f"🚀 Sending daily report (Items found: {len(new_items_found)})...")
    send_email_notification(new_items_found)

if __name__ == "__main__":
    run_scraper()
