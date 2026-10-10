#!/usr/bin/env python3
import os
import re
import json
import time
import html
import threading
import subprocess
import urllib.request
import urllib.parse
import smtplib
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid

PORT = 8099
SECRET_TOKEN = "tara_sec_89d31fbe61c9443db489e29a8a70659e"
WEB_ROOT = "/var/www/ah-eisa.com"
CONTENT_DIR = os.path.join(WEB_ROOT, "content", "insights")
LEADS_FILE = os.path.join(WEB_ROOT, "content", "leads.json")

# Notifications Configuration
TELEGRAM_BOT_TOKEN = "8609026379:AAGYLDU3Nk0tCSZN1zD9-jDRoie-BrImiaE"
TELEGRAM_CHAT_ID = 933252341
CONTACT_RECIPIENT_EMAIL = "Ahmed.eisa.2009@gmail.com"
CONTACT_FROM_EMAIL = "contact@ah-eisa.com"

# Input Constraints
MAX_NAME_LEN = 120
MAX_EMAIL_LEN = 254
MAX_SUBJECT_LEN = 200
MAX_MESSAGE_LEN = 5000
MIN_MESSAGE_LEN = 5
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

VALID_CATEGORIES = [
    "Portfolio Strategy",
    "Wealth Management",
    "Asset Allocation",
    "Digital Assets",
    "Tokenization & RWA",
    "Islamic Finance",
    "Markets & Macro",
    "Investment Technology"
]

class RateLimiter:
    """Thread-safe in-memory rate limiter for contact form abuse protection."""
    def __init__(self, ip_limit=5, global_limit=30, window_seconds=3600):
        self.ip_limit = ip_limit
        self.global_limit = global_limit
        self.window = window_seconds
        self.lock = threading.Lock()
        self.ip_records = {}
        self.global_records = []

    def check_and_record(self, ip):
        now = time.time()
        cutoff = now - self.window
        with self.lock:
            # Clean expired global records
            self.global_records = [t for t in self.global_records if t > cutoff]
            if len(self.global_records) >= self.global_limit:
                return False, "Global inquiry threshold reached. Please email directly."

            # Clean expired IP records
            records = [t for t in self.ip_records.get(ip, []) if t > cutoff]
            if len(records) >= self.ip_limit:
                return False, "Too many requests from your IP. Please try again later or email directly."

            records.append(now)
            self.ip_records[ip] = records
            self.global_records.append(now)
            return True, None

# Singleton Rate Limiter
rate_limiter = RateLimiter(ip_limit=5, global_limit=30, window_seconds=3600)

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")

def calc_reading_time(text):
    words = len(re.findall(r"\w+", text))
    minutes = max(1, round(words / 200))
    return f"{minutes} min read"

def infer_category(text, default="Portfolio Strategy"):
    text_lower = text.lower()
    if any(k in text_lower for k in ["token", "rwa", "real-world asset", "smart contract"]):
        return "Tokenization & RWA"
    if any(k in text_lower for k in ["islamic", "sukuk", "sharia", "takaful", "mudaraba"]):
        return "Islamic Finance"
    if any(k in text_lower for k in ["crypto", "digital asset", "vara", "sca", "web3"]):
        return "Digital Assets"
    if any(k in text_lower for k in ["macro", "inflation", "fed", "interest rate", "gdp", "market outlook"]):
        return "Markets & Macro"
    if any(k in text_lower for k in ["fintech", "ai", "algorithm", "trading platform", "technology"]):
        return "Investment Technology"
    if any(k in text_lower for k in ["wealth", "family office", "estate", "hnw", "private bank"]):
        return "Wealth Management"
    if any(k in text_lower for k in ["allocation", "diversification", "etf", "bond", "equity"]):
        return "Asset Allocation"
    return default

def send_telegram_alert(name, email, subject, message, client_ip=""):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # HTML Escape for safe Telegram rendering
        h_name = html.escape(name)
        h_email = html.escape(email)
        h_subj = html.escape(subject)
        h_msg = html.escape(message)
        h_ip = html.escape(client_ip)

        tg_text = (
            f"?? <b>New Inquiry on ah-eisa.com</b>\n\n"
            f"?? <b>Name:</b> {h_name}\n"
            f"?? <b>Email:</b> {h_email}\n"
            f"?? <b>Subject:</b> {h_subj}\n\n"
            f"?? <b>Message:</b>\n{h_msg}\n\n"
            f"?? <i>{timestamp_str} (GST/UAE)</i>\n"
            f"?? <i>IP: {h_ip}</i>"
        )
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": tg_text,
            "parse_mode": "HTML"
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, "Telegram sent"
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram alert: {e}")
        return False, str(e)

def send_email_alert(name, email, subject, message, client_ip=""):
    try:
        # Strip header injection characters
        clean_subject = re.sub(r"[\r\n]", " ", subject).strip()[:MAX_SUBJECT_LEN]
        clean_name = re.sub(r"[\r\n<>\"]", " ", name).strip()[:MAX_NAME_LEN]
        clean_email = re.sub(r"[\r\n]", "", email).strip()[:MAX_EMAIL_LEN]

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[ah-eisa.com Contact] {clean_subject} - {clean_name}"
        msg["From"] = f"Ahmed Eisa Website <{CONTACT_FROM_EMAIL}>"
        msg["To"] = CONTACT_RECIPIENT_EMAIL
        msg["Reply-To"] = f"{clean_name} <{clean_email}>"
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="ah-eisa.com")

        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        plain_text = (
            f"New contact inquiry submitted on ah-eisa.com:\n\n"
            f"Name: {name}\n"
            f"Email: {clean_email}\n"
            f"Subject: {clean_subject}\n"
            f"Date: {timestamp_str}\n"
            f"IP: {client_ip}\n\n"
            f"Message:\n{message}\n"
        )

        h_name = html.escape(name)
        h_email = html.escape(clean_email)
        h_subj = html.escape(clean_subject)
        h_msg = html.escape(message)
        h_ip = html.escape(client_ip)

        html_text = f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1f2937; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px;">
          <div style="background-color: #0b1120; color: #ffffff; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0; font-size: 20px;">New Inquiry on ah-eisa.com</h2>
            <p style="margin: 5px 0 0; color: #94a3b8; font-size: 14px;">Direct opportunity / partnership submission</p>
          </div>
          <div style="border: 1px solid #e2e8f0; border-top: none; padding: 24px; border-radius: 0 0 8px 8px; background: #ffffff;">
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
              <tr><td style="padding: 8px 0; font-weight: bold; width: 100px; color: #64748b;">From:</td><td style="padding: 8px 0;">{h_name}</td></tr>
              <tr><td style="padding: 8px 0; font-weight: bold; color: #64748b;">Email:</td><td style="padding: 8px 0;"><a href="mailto:{h_email}" style="color: #2563eb;">{h_email}</a></td></tr>
              <tr><td style="padding: 8px 0; font-weight: bold; color: #64748b;">Subject:</td><td style="padding: 8px 0;">{h_subj}</td></tr>
              <tr><td style="padding: 8px 0; font-weight: bold; color: #64748b;">Time:</td><td style="padding: 8px 0;">{timestamp_str}</td></tr>
              <tr><td style="padding: 8px 0; font-weight: bold; color: #64748b;">IP:</td><td style="padding: 8px 0; color: #94a3b8; font-size: 12px;">{h_ip}</td></tr>
            </table>
            <div style="background: #f8fafc; border-left: 4px solid #2563eb; padding: 16px; border-radius: 4px; margin-top: 15px;">
              <h4 style="margin: 0 0 8px; color: #334155;">Message Content:</h4>
              <p style="margin: 0; white-space: pre-wrap; font-size: 15px;">{h_msg}</p>
            </div>
            <div style="margin-top: 25px; padding-top: 15px; border-top: 1px solid #f1f5f9; font-size: 13px; color: #64748b;">
              You can reply directly to this email to respond to <b>{h_name}</b> ({h_email}).
            </div>
          </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(plain_text, "plain", "utf-8"))
        msg.attach(MIMEText(html_text, "html", "utf-8"))

        s = smtplib.SMTP("127.0.0.1", 25, timeout=10)
        s.send_message(msg)
        s.quit()
        return True, "Email sent successfully"
    except Exception as e:
        print(f"[ERROR] Failed to send email alert: {e}")
        return False, str(e)

def save_lead_record(lead_data):
    try:
        os.makedirs(os.path.dirname(LEADS_FILE), exist_ok=True)
        leads = []
        if os.path.exists(LEADS_FILE):
            try:
                with open(LEADS_FILE, "r", encoding="utf-8") as f:
                    leads = json.load(f)
                if not isinstance(leads, list):
                    leads = []
            except Exception:
                leads = []
        leads.append(lead_data)
        with open(LEADS_FILE, "w", encoding="utf-8") as f:
            json.dump(leads, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save lead record: {e}")
        return False

class TaraPublishHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Sanitize logs: do not print tokens or query params
        client_ip = self.headers.get("X-Forwarded-For", "").split(",")[0].strip() or self.address_string()
        print(f"[{datetime.now().isoformat()}] {client_ip} - {format % args}")

    def send_json(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "https://ah-eisa.com")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
        self.end_headers()

    def do_GET(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path in ["/health", "/publish", "/api/publish"]:
            self.send_json(200, {"status": "ok", "site": "ah-eisa.com"})
        elif clean_path in ["/contact", "/api/contact"]:
            self.send_json(200, {"status": "ok", "service": "Inquiry API", "site": "ah-eisa.com"})
        else:
            self.send_json(404, {"error": "Not Found"})

    def do_POST(self):
        clean_path = self.path.split("?")[0].rstrip("/")
        if clean_path in ["/contact", "/api/contact"]:
            self.handle_contact()
        elif clean_path in ["/publish", "/api/publish"]:
            self.handle_publish()
        else:
            self.send_json(404, {"error": "Not Found"})

    def handle_contact(self):
        client_ip = (self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                     or self.headers.get("X-Real-IP", "")
                     or self.address_string())
        user_agent = self.headers.get("User-Agent", "")[:250]
        content_type = self.headers.get("Content-Type", "")

        # 1. Rate Limiting Check
        allowed, rate_err = rate_limiter.check_and_record(client_ip)
        if not allowed:
            self.send_json(429, {"ok": False, "error": rate_err})
            return

        # 2. Read Request Body with Limit (max 32KB)
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len > 32768:
                self.send_json(413, {"ok": False, "error": "Request entity too large."})
                return
            body_raw = self.rfile.read(content_len).decode("utf-8", errors="replace")
        except Exception as e:
            self.send_json(400, {"ok": False, "error": "Unable to process payload."})
            return

        is_json = "application/json" in content_type.lower()
        data = {}

        if is_json:
            try:
                data = json.loads(body_raw)
            except Exception:
                self.send_json(400, {"ok": False, "error": "Malformed JSON payload."})
                return
        else:
            parsed = urllib.parse.parse_qs(body_raw)
            data = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}

        # 3. Honeypot Abuse Check
        honeypot = (data.get("_hp_company", "").strip()
                    or data.get("company_hp", "").strip()
                    or data.get("website", "").strip())
        if honeypot:
            # Silent discard for automated bot submissions
            if is_json or "application/json" in self.headers.get("Accept", "").lower():
                self.send_json(200, {"ok": True, "message": "Inquiry received."})
            else:
                self.send_response(303)
                self.send_header("Location", "/thank-you.html")
                self.end_headers()
            return

        # 4. Strict Input Normalization & Trimming
        name = re.sub(r"[\r\n]", " ", str(data.get("name", ""))).strip()
        name = re.sub(r"\s+", " ", name)

        email = re.sub(r"[\r\n]", "", str(data.get("email", ""))).strip().lower()

        subject = re.sub(r"[\r\n]", " ", str(data.get("subject", ""))).strip()
        subject = re.sub(r"\s+", " ", subject) or "Opportunity Discussion"

        message = str(data.get("message", "")).strip()

        # 5. Strict Validation
        if not name:
            self.send_json(400, {"ok": False, "error": "Name is required."})
            return
        if len(name) > MAX_NAME_LEN:
            self.send_json(400, {"ok": False, "error": f"Name must not exceed {MAX_NAME_LEN} characters."})
            return

        if not email:
            self.send_json(400, {"ok": False, "error": "Email address is required."})
            return
        if len(email) > MAX_EMAIL_LEN or not EMAIL_REGEX.match(email):
            self.send_json(400, {"ok": False, "error": "Please provide a valid email address."})
            return

        if len(subject) > MAX_SUBJECT_LEN:
            subject = subject[:MAX_SUBJECT_LEN]

        if not message or len(message) < MIN_MESSAGE_LEN:
            self.send_json(400, {"ok": False, "error": f"Message must be at least {MIN_MESSAGE_LEN} characters."})
            return
        if len(message) > MAX_MESSAGE_LEN:
            self.send_json(400, {"ok": False, "error": f"Message must not exceed {MAX_MESSAGE_LEN} characters."})
            return

        # 6. Safe Record Creation
        lead_record = {
            "id": f"lead_{int(datetime.utcnow().timestamp())}",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "name": name,
            "email": email,
            "subject": subject,
            "message": message,
            "ip": client_ip,
            "user_agent": user_agent
        }

        # 7. Persistent Local Storage
        save_lead_record(lead_record)

        # 8. Dispatch Notifications
        send_telegram_alert(name, email, subject, message, client_ip)
        send_email_alert(name, email, subject, message, client_ip)

        # 9. Return Controlled Response
        accept_header = self.headers.get("Accept", "").lower()
        if is_json or "application/json" in accept_header:
            self.send_json(200, {
                "ok": True,
                "message": "Thank you! Your message has been received successfully."
            })
        else:
            self.send_response(303)
            self.send_header("Location", "/thank-you.html")
            self.end_headers()

    def handle_publish(self):
        auth_header = self.headers.get("X-Tara-Secret", "")
        if not auth_header:
            bearer = self.headers.get("Authorization", "")
            if bearer.startswith("Bearer "):
                auth_header = bearer[7:].strip()

        if auth_header != SECRET_TOKEN:
            self.send_json(401, {"error": "Unauthorized."})
            return

        try:
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len > 1048576: # 1MB max for article
                self.send_json(413, {"error": "Article payload too large."})
                return
            body_raw = self.rfile.read(content_len).decode("utf-8")
            data = json.loads(body_raw)
        except Exception:
            self.send_json(400, {"error": "Invalid payload format."})
            return

        title = str(data.get("title", "")).strip()
        body = str(data.get("body", "")).strip()

        if not title:
            self.send_json(400, {"error": "Missing 'title' field."})
            return
        if not body:
            self.send_json(400, {"error": "Missing 'body' field."})
            return

        slug = data.get("slug") or slugify(title)
        category = data.get("category")
        if not category or category not in VALID_CATEGORIES:
            category = infer_category(f"{title} {body}")

        tags = data.get("tags")
        if not tags:
            tags = [category, "Investment Strategy"]
        elif isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        excerpt = data.get("excerpt", "").strip()
        if not excerpt:
            for p in body.split("\n\n"):
                clean = re.sub(r"[#*`_\[\]]", "", p).strip()
                if clean:
                    excerpt = clean[:180] + ("..." if len(clean) > 180 else "")
                    break

        hero_image = data.get("hero_image") or "https://res.cloudinary.com/dfh3erwx1/image/upload/v1760280190/IMG_0073_vzkxvd.png"
        author = data.get("author") or "Ahmed Eisa"
        date_str = data.get("date") or datetime.now().strftime("%Y-%m-%d")
        reading_time = data.get("reading_time") or calc_reading_time(body)
        seo_title = data.get("seo_title") or f"{title} | Ahmed Eisa"
        meta_description = data.get("meta_description") or excerpt

        tags_json = json.dumps(tags, ensure_ascii=False)
        md_content = f"""---
title: "{title}"
slug: "{slug}"
excerpt: "{excerpt}"
hero_image: "{hero_image}"
category: "{category}"
tags: {tags_json}
author: "{author}"
date: "{date_str}"
reading_time: "{reading_time}"
seo_title: "{seo_title}"
meta_description: "{meta_description}"
---

{body}
"""

        os.makedirs(CONTENT_DIR, exist_ok=True)
        filename = f"{slug}.md"
        filepath = os.path.join(CONTENT_DIR, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(md_content)
        except Exception as e:
            self.send_json(500, {"error": "Failed to persist article."})
            return

        try:
            build_res = subprocess.run(
                ["python3", "build_insights.py"],
                cwd=WEB_ROOT,
                capture_output=True,
                text=True,
                timeout=30
            )
            if build_res.returncode != 0:
                print("build_insights.py notice:", build_res.stderr[:200])
        except Exception as e:
            print("Failed to run build_insights.py:", e)

        try:
            subprocess.run(["git", "add", "."], cwd=WEB_ROOT, capture_output=True)
            subprocess.run(["git", "commit", "-m", f"feat(tara): publish article '{title}'"], cwd=WEB_ROOT, capture_output=True)
            subprocess.Popen(["git", "push", "origin", "main"], cwd=WEB_ROOT)
        except Exception as e:
            print("Git push notice:", e)

        article_url = f"https://ah-eisa.com/insights/{slug}/"
        self.send_json(200, {
            "success": True,
            "url": article_url,
            "slug": slug,
            "title": title,
            "category": category,
            "tags": tags,
            "reading_time": reading_time,
            "published_at": date_str,
            "message": "Article successfully published"
        })

def run():
    server = HTTPServer(("127.0.0.1", PORT), TaraPublishHandler)
    print(f"Hardened Tara API running on http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    run()
