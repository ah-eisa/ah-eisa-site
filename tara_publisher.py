import os
import re
import json
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

PORT = 8099
SECRET_TOKEN = "tara_sec_89d31fbe61c9443db489e29a8a70659e"
WEB_ROOT = "/var/www/ah-eisa.com"
CONTENT_DIR = os.path.join(WEB_ROOT, "content", "insights")

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

class TaraPublishHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Clean custom logging
        print(f"[{datetime.now().isoformat()}] {self.address_string()} - {format % args}")

    def send_json(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ["/health", "/publish", "/api/publish"]:
            self.send_json(200, {"status": "ok", "service": "Tara Publishing API", "site": "ah-eisa.com"})
        else:
            self.send_json(404, {"error": "Not Found"})

    def do_POST(self):
        if self.path not in ["/publish", "/api/publish"]:
            self.send_json(404, {"error": "Not Found"})
            return

        # Check authentication token
        auth_header = self.headers.get("X-Tara-Secret", "")
        if not auth_header:
            bearer = self.headers.get("Authorization", "")
            if bearer.startswith("Bearer "):
                auth_header = bearer[7:].strip()

        if auth_header != SECRET_TOKEN:
            self.send_json(401, {"error": "Unauthorized. Invalid or missing X-Tara-Secret header."})
            return

        # Parse request body
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            body_raw = self.rfile.read(content_len).decode("utf-8")
            data = json.loads(body_raw)
        except Exception as e:
            self.send_json(400, {"error": f"Invalid JSON payload: {str(e)}"})
            return

        title = data.get("title", "").strip()
        body = data.get("body", "").strip()

        if not title:
            self.send_json(400, {"error": "Missing 'title' field."})
            return
        if not body:
            self.send_json(400, {"error": "Missing 'body' field."})
            return

        # Auto-compute fields if omitted
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
            # Extract first non-empty paragraph
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

        # Prepare Markdown file with Frontmatter
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
            self.send_json(500, {"error": f"Failed to write article file: {str(e)}"})
            return

        # Trigger build_insights.py
        try:
            build_res = subprocess.run(
                ["python3", "build_insights.py"],
                cwd=WEB_ROOT,
                capture_output=True,
                text=True,
                timeout=30
            )
            if build_res.returncode != 0:
                print("build_insights.py error:", build_res.stderr)
        except Exception as e:
            print("Failed to run build_insights.py:", e)

        # Commit and push to GitHub asynchronously
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
            "message": "Article successfully compiled and published live to ah-eisa.com"
        })

def run():
    server = HTTPServer(("127.0.0.1", PORT), TaraPublishHandler)
    print(f"Tara Publishing API running on http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    run()
