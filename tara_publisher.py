#!/usr/bin/env python3
"""Contact intake only. Article publishing and the legacy CMS are retired."""
import os
import re
import json
import time
import html
import ipaddress
import tempfile
import threading
import urllib.request
import urllib.parse
import smtplib
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid

PORT = 8099
STATE_DIR = os.path.realpath(os.environ.get("AH_EISA_STATE_DIR", "/var/lib/ah-eisa-contact"))
if STATE_DIR == "/var/www" or STATE_DIR.startswith("/var/www/"):
    raise RuntimeError("Contact state must be outside the public web root")
LEADS_FILE = os.path.join(STATE_DIR, "leads.json")

# Provisioned by the root-owned systemd EnvironmentFile, never tracked source.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
CONTACT_RECIPIENT_EMAIL = "Ahmed.eisa.2009@gmail.com"
CONTACT_FROM_EMAIL = "contact@ah-eisa.com"

MAX_NAME_LEN = 120
MAX_EMAIL_LEN = 254
MAX_SUBJECT_LEN = 200
MAX_MESSAGE_LEN = 5000
MIN_MESSAGE_LEN = 5
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

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

            self.ip_records = {key: [t for t in values if t > cutoff]
                               for key, values in self.ip_records.items()
                               if any(t > cutoff for t in values)}

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

def send_telegram_alert(name, email, subject, message, client_ip="", country="", lead_id=""):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "telegram not configured"

    def _post(payload):
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10):
            return True

    try:
        now_str = datetime.now(ZoneInfo("Asia/Dubai")).strftime("%Y-%m-%d %H:%M")
        shown_msg = message if len(message) <= 2500 else message[:2500] + "\n[... truncated - full text in email]"
        where = client_ip + (f" \u00b7 {country}" if country else "")

        tg_text = (
            f"\U0001F514 <b>New inquiry \u2014 ah-eisa.com</b>\n\n"
            f"\U0001F464 <b>{html.escape(name)}</b>\n"
            f"\u2709\uFE0F {html.escape(email)}\n"
            f"\U0001F4CC <b>{html.escape(subject) or '(no subject)'}</b>\n\n"
            f"<blockquote>{html.escape(shown_msg)}</blockquote>\n"
            f"\U0001F552 {now_str} (UAE)\n"
            f"\U0001F30D {html.escape(where)}\n"
            f"\U0001F194 <code>{html.escape(lead_id)}</code>"
        )
        try:
            _post({"chat_id": TELEGRAM_CHAT_ID, "text": tg_text, "parse_mode": "HTML",
                   "disable_web_page_preview": True})
        except Exception:
            # Fallback: plain text so the alert is never lost on a formatting error
            plain = (
                f"\U0001F514 New inquiry - ah-eisa.com\n\n"
                f"Name: {name}\nEmail: {email}\nSubject: {subject}\n\n{shown_msg}\n\n"
                f"{now_str} (UAE) | {where} | {lead_id}"
            )
            _post({"chat_id": TELEGRAM_CHAT_ID, "text": plain})
        return True, "Telegram sent"
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram alert: {type(e).__name__}")
        return False, "telegram failed"

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

        timestamp_str = datetime.now(ZoneInfo("Asia/Dubai")).strftime("%Y-%m-%d %H:%M:%S") + " (UAE)"

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
        print(f"[ERROR] Failed to send email alert: {type(e).__name__}")
        return False, "email failed"

def save_lead_record(lead_data):
    """Keep private records durable; never truncate them on a failed read/write."""
    temporary = None
    try:
        os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
        leads = []
        if os.path.exists(LEADS_FILE):
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(LEADS_FILE, flags), "r", encoding="utf-8") as existing:
                leads = json.load(existing)
            if not isinstance(leads, list):
                raise ValueError("Invalid private record store")
        leads.append(lead_data)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=STATE_DIR,
                                         prefix=".leads-", delete=False) as output:
            temporary = output.name
            os.chmod(temporary, 0o600)
            json.dump(leads, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, LEADS_FILE)
        temporary = None
        return True
    except Exception as error:
        print(f"[ERROR] Private inquiry persistence failed: {type(error).__name__}")
        return False
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass

class TaraPublishHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def canonical_client_ip(self):
        peer = ipaddress.ip_address(self.client_address[0])
        # Only the local reverse proxy can provide the canonical client header.
        # Nginx overwrites this header using its trusted real-IP processing.
        if peer.is_loopback:
            forwarded = self.headers.get("X-Ah-Eisa-Client-IP", "")
            try:
                return str(ipaddress.ip_address(forwarded))
            except ValueError:
                pass
        return str(peer)

    def log_message(self, format, *args):
        route = self.path.split("?", 1)[0].rstrip("/")
        safe_route = route if route in ("/health", "/contact", "/api/contact") else "unknown-route"
        print(f"[{datetime.now(timezone.utc).isoformat()}] {self.command} {safe_route}")

    def send_json(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
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
        route = self.path.split("?", 1)[0].rstrip("/")
        if route in ("/health", "/contact", "/api/contact"):
            self.send_json(200, {"status": "ok", "service": "Inquiry API", "site": "ah-eisa.com"})
        elif route in ("/publish", "/api/publish"):
            self.send_json(410, {"error": "Publishing API retired."})
        else:
            self.send_json(404, {"error": "Not Found"})

    def do_POST(self):
        route = self.path.split("?", 1)[0].rstrip("/")
        if route in ("/contact", "/api/contact"):
            self.handle_contact()
        elif route in ("/publish", "/api/publish"):
            self.send_json(410, {"error": "Publishing API retired."})
        else:
            self.send_json(404, {"error": "Not Found"})

    def handle_contact(self):
        client_ip = self.canonical_client_ip()
        user_agent = self.headers.get("User-Agent", "")[:250]
        country = re.sub(r"[^A-Za-z]", "", self.headers.get("CF-IPCountry", ""))[:2].upper()
        content_type = self.headers.get("Content-Type", "")

        # 1. Rate Limiting Check
        allowed, rate_err = rate_limiter.check_and_record(client_ip)
        if not allowed:
            self.send_json(429, {"ok": False, "error": rate_err})
            return

        # 2. Read Request Body with Limit (max 32KB)
        try:
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,8}", lengths[0]):
                self.send_json(400, {"ok": False, "error": "Invalid request length."})
                return
            content_len = int(lengths[0])
            if content_len < 1:
                self.send_json(400, {"ok": False, "error": "Request body is required."})
                return
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

        if not isinstance(data, dict):
            self.send_json(400, {"ok": False, "error": "Expected a form object."})
            return
        for field in ("name", "email", "subject", "message", "_hp_company", "company_hp", "website"):
            if field in data and not isinstance(data[field], str):
                self.send_json(400, {"ok": False, "error": "Form fields must be text."})
                return

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
            "id": f"lead_{int(time.time())}",
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "name": name,
            "email": email,
            "subject": subject,
            "message": message,
            "ip": client_ip,
            "user_agent": user_agent
        }

        # 7. Persistent Local Storage
        if not save_lead_record(lead_record):
            self.send_json(503, {"ok": False, "error": "Unable to save your inquiry. Please email directly."})
            return

        # 8. Dispatch Notifications
        send_telegram_alert(name, email, subject, message, client_ip, country, lead_record["id"])
        send_email_alert(name, email, subject, message, client_ip + (f" ({country})" if country else ""))

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


def run():
    server = HTTPServer(("127.0.0.1", PORT), TaraPublishHandler)
    print(f"Contact API listening on loopback port {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    run()
