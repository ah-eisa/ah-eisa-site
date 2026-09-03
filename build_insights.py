import os
import re
import json
import yaml
import markdown
from datetime import datetime

SITE_URL = "https://ah-eisa.com"
AUTHOR_NAME = "Ahmed Eisa"
AUTHOR_ROLE = "UAE CMA-Accredited Investment Portfolio Manager"
AUTHOR_IMG = "https://res.cloudinary.com/dfh3erwx1/image/upload/v1760280190/IMG_0073_vzkxvd.png"
AUTHOR_LINKEDIN = "https://linkedin.com/in/ahmedeisa85"
AUTHOR_BIO = "Over 16 years across regulated banking, multi-asset portfolio advisory, digital wealth platforms, and Islamic finance. Founder of EisaX Intelligence and Investment Portfolio Manager at Emirates Coin Investment, based in Abu Dhabi, UAE."

CATEGORIES = [
    "Portfolio Strategy",
    "Wealth Management",
    "Asset Allocation",
    "Digital Assets",
    "Tokenization & RWA",
    "Islamic Finance",
    "Markets & Macro",
    "Investment Technology"
]

def parse_frontmatter(content):
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) >= 3:
        fm = yaml.safe_load(parts[1]) or {}
        body = parts[2].strip()
        return fm, body
    return {}, content

def format_date(d_val):
    if isinstance(d_val, datetime):
        return d_val.strftime("%B %d, %Y")
    if isinstance(d_val, str):
        try:
            dt = datetime.fromisoformat(d_val.replace("Z", "+00:00"))
            return dt.strftime("%B %d, %Y")
        except Exception:
            try:
                dt = datetime.strptime(d_val, "%Y-%m-%d")
                return dt.strftime("%B %d, %Y")
            except Exception:
                return d_val
    return str(d_val)

def iso_date(d_val):
    if isinstance(d_val, datetime):
        return d_val.isoformat()
    if isinstance(d_val, str):
        return d_val
    return str(d_val)

def calc_reading_time(text):
    words = len(re.findall(r"\w+", text))
    minutes = max(1, round(words / 200))
    return f"{minutes} min read"

def get_articles():
    content_dir = "content/insights"
    if not os.path.exists(content_dir):
        return []
    articles = []
    for fname in os.listdir(content_dir):
        if not fname.endswith(".md"):
            continue
        filepath = os.path.join(content_dir, fname)
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
        fm, body = parse_frontmatter(raw)
        slug = fm.get("slug") or os.path.splitext(fname)[0]
        title = fm.get("title", slug.replace("-", " ").title())
        date_raw = fm.get("date", datetime.now().strftime("%Y-%m-%d"))
        category = fm.get("category", "Portfolio Strategy")
        tags = fm.get("tags", ["Investment Insights"])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        author = fm.get("author", AUTHOR_NAME)
        hero_image = fm.get("hero_image") or AUTHOR_IMG
        excerpt = fm.get("excerpt", "")
        if not excerpt:
            # First non-empty paragraph
            for p in body.split("\n\n"):
                clean = re.sub(r"[#*`_\[\]]", "", p).strip()
                if clean:
                    excerpt = clean[:180] + "..."
                    break
        reading_time = fm.get("reading_time") or calc_reading_time(body)
        seo_title = fm.get("seo_title") or f"{title} | Ahmed Eisa"
        meta_description = fm.get("meta_description") or excerpt

        articles.append({
            "filename": fname,
            "slug": slug,
            "title": title,
            "date": str(date_raw),
            "formatted_date": format_date(date_raw),
            "iso_date": iso_date(date_raw),
            "category": category,
            "tags": tags,
            "author": author,
            "hero_image": hero_image,
            "excerpt": excerpt,
            "reading_time": reading_time,
            "seo_title": seo_title,
            "meta_description": meta_description,
            "body_md": body,
            "body_html": markdown.markdown(body, extensions=["fenced_code", "tables", "toc"])
        })
    # Sort newest first
    articles.sort(key=lambda a: a["date"], reverse=True)
    return articles

def generate_article_page(article, all_articles):
    slug = article["slug"]
    permalink = f"{SITE_URL}/insights/{slug}"
    encoded_url = permalink.replace(":", "%3A").replace("/", "%2F")
    encoded_title = article["title"].replace(" ", "%20").replace("&", "%26")
    linkedin_share_url = f"https://www.linkedin.com/sharing/share-offsite/?url={encoded_url}"

    # Related articles (same category or others)
    related = [a for a in all_articles if a["slug"] != slug and (a["category"] == article["category"] or True)][:2]
    related_html = ""
    if related:
        cards = []
        for r in related:
            cards.append(f"""
            <a class="related-card" href="/insights/{r['slug']}.html">
              <span class="category-pill">{r['category']}</span>
              <h4>{r['title']}</h4>
              <p>{r['excerpt'][:110]}...</p>
              <span class="read-more">Read analysis &rarr;</span>
            </a>""")
        related_html = f"""
        <section class="related-section">
          <h3>Related Investment Insights</h3>
          <div class="related-grid">
            {''.join(cards)}
          </div>
        </section>"""

    tags_html = "".join([f'<span class="tag-pill">#{t}</span>' for t in article["tags"]])

    hero_img_html = ""
    if article.get("hero_image") and article["hero_image"] != AUTHOR_IMG:
        hero_img_html = f"""
        <div class="article-hero-wrap">
          <img src="{article['hero_image']}" alt="{article['title']}" class="article-hero-img" loading="lazy" />
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{article['seo_title']}</title>
  <meta name="description" content="{article['meta_description']}">
  <link rel="canonical" href="{permalink}">

  <!-- Open Graph / LinkedIn Sharing -->
  <meta property="og:type" content="article">
  <meta property="og:title" content="{article['title']}">
  <meta property="og:description" content="{article['excerpt']}">
  <meta property="og:image" content="{article['hero_image']}">
  <meta property="og:url" content="{permalink}">
  <meta property="og:site_name" content="Ahmed Eisa | Investment & Wealth Management">
  <meta property="article:published_time" content="{article['iso_date']}">
  <meta property="article:author" content="{article['author']}">
  <meta property="article:section" content="{article['category']}">

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{article['title']}">
  <meta name="twitter:description" content="{article['excerpt']}">
  <meta name="twitter:image" content="{article['hero_image']}">

  <!-- JSON-LD Structured Data -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "{article['title']}",
    "description": "{article['excerpt']}",
    "image": "{article['hero_image']}",
    "datePublished": "{article['iso_date']}",
    "author": {{
      "@type": "Person",
      "name": "{article['author']}",
      "url": "{SITE_URL}",
      "jobTitle": "{AUTHOR_ROLE}"
    }},
    "publisher": {{
      "@type": "Person",
      "name": "{AUTHOR_NAME}",
      "url": "{SITE_URL}"
    }},
    "mainEntityOfPage": {{
      "@type": "WebPage",
      "@id": "{permalink}"
    }}
  }}
  </script>

  <link rel="icon" href="/assets/icons/ae-logo.svg">
  <link rel="stylesheet" href="/style.css">
  <script src="/main.js" defer></script>
</head>
<body class="article-page">
<header id="site-header"></header>

<main class="container article-layout">

  <!-- Breadcrumbs & Meta -->
  <div class="article-header">
    <nav class="breadcrumbs" aria-label="Breadcrumb">
      <a href="/index.html">Home</a> &rsaquo;
      <a href="/insights.html">Insights</a> &rsaquo;
      <span>{article['category']}</span>
    </nav>
    <div class="article-meta-row">
      <span class="category-pill">{article['category']}</span>
      <span class="article-date">{article['formatted_date']}</span>
      <span class="meta-dot">&middot;</span>
      <span class="article-reading-time">{article['reading_time']}</span>
    </div>
    <h1 class="article-title">{article['title']}</h1>
    <p class="article-lead">{article['excerpt']}</p>
  </div>

  {hero_img_html}

  <!-- Article Body -->
  <article class="article-body">
    {article['body_html']}
  </article>

  <!-- Tags & LinkedIn Share Bar -->
  <div class="article-footer-bar">
    <div class="article-tags">
      {tags_html}
    </div>
    <div class="article-share-actions">
      <span class="share-label">Share:</span>
      <a class="btn-share btn-linkedin" href="{linkedin_share_url}" target="_blank" rel="noopener noreferrer" title="Share on LinkedIn">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.46 10.9v8.37H9.2V10.9H6.46M7.83 6.3a1.64 1.64 0 1 0 0 3.28 1.64 1.64 0 0 0 0-3.28z"/></svg>
        Share on LinkedIn
      </a>
      <button class="btn-share btn-copy" onclick="copyArticleLink('{permalink}')" title="Copy article link">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
        <span id="copyText">Copy Link</span>
      </button>
    </div>
  </div>

  <!-- Author Bio Card -->
  <section class="author-card" aria-label="About the Author">
    <img src="{AUTHOR_IMG}" alt="{AUTHOR_NAME}" class="author-img" loading="lazy" />
    <div class="author-info">
      <div class="author-name-row">
        <h3>{AUTHOR_NAME}</h3>
        <span class="author-badge">{AUTHOR_ROLE}</span>
      </div>
      <p class="author-bio">{AUTHOR_BIO}</p>
      <div class="author-links">
        <a href="{AUTHOR_LINKEDIN}" target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm">Connect on LinkedIn</a>
        <a href="/assets/pdf/Ahmed_Eisa_Investment_CV.pdf" target="_blank" rel="noopener" class="btn btn-outline btn-sm">Download Investment CV</a>
      </div>
    </div>
  </section>

  {related_html}

  <div class="back-to-insights">
    <a href="/insights.html" class="btn btn-outline">&larr; Back to All Investment Insights</a>
  </div>

</main>

<footer id="site-footer"></footer>

<script>
function copyArticleLink(url) {{
  navigator.clipboard.writeText(url).then(function() {{
    const copyText = document.getElementById('copyText');
    const orig = copyText.textContent;
    copyText.textContent = 'Copied!';
    setTimeout(() => {{ copyText.textContent = orig; }}, 2000);
  }}).catch(function() {{
    alert('Link copied: ' + url);
  }});
}}
</script>

</body>
</html>
"""
    return html

def build():
    articles = get_articles()
    print(f"Loaded {len(articles)} articles from content/insights")

    os.makedirs("insights", exist_ok=True)
    os.makedirs("content", exist_ok=True)

    # 1. Generate static HTML files
    for a in articles:
        html = generate_article_page(a, articles)
        # 1a. Direct file: /insights/[slug].html
        file_path = os.path.join("insights", f"{a['slug']}.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        # 1b. Clean directory: /insights/[slug]/index.html
        slug_dir = os.path.join("insights", a["slug"])
        os.makedirs(slug_dir, exist_ok=True)
        with open(os.path.join(slug_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  Generated /insights/{a['slug']}.html and /insights/{a['slug']}/index.html")

    # 2. Generate JSON manifest
    manifest = [
        {
            "slug": a["slug"],
            "title": a["title"],
            "date": a["date"],
            "formatted_date": a["formatted_date"],
            "category": a["category"],
            "tags": a["tags"],
            "author": a["author"],
            "hero_image": a["hero_image"],
            "excerpt": a["excerpt"],
            "reading_time": a["reading_time"],
            "url": f"insights/{a['slug']}.html"
        }
        for a in articles
    ]
    with open("content/insights.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print("  Generated content/insights.json")

    # 3. Generate updated insights.html (and blog.html mirror)
    generate_insights_index(articles)

    # 4. Update homepage index.html with latest 3 articles
    update_homepage(articles[:3])

    print("Build completed successfully!")

def generate_insights_index(articles):
    # Category pills
    cat_buttons = ['<button class="cat-tab active" data-category="all">All Topics</button>']
    for c in CATEGORIES:
        cat_buttons.append(f'<button class="cat-tab" data-category="{c}">{c}</button>')

    # Article cards
    cards = []
    for a in articles:
        cards.append(f"""
        <article class="post-card" data-category="{a['category']}" data-title="{a['title'].lower()}" data-tags="{','.join(a['tags']).lower()}">
          <div class="post-card-meta">
            <span class="category-pill">{a['category']}</span>
            <span class="post-date">{a['formatted_date']}</span>
            <span class="meta-dot">&middot;</span>
            <span class="reading-time">{a['reading_time']}</span>
          </div>
          <h2 class="post-card-title"><a href="insights/{a['slug']}.html">{a['title']}</a></h2>
          <p class="post-card-excerpt">{a['excerpt']}</p>
          <div class="post-card-footer">
            <a href="insights/{a['slug']}.html" class="read-link">Read analysis &rarr;</a>
          </div>
        </article>""")

    featured = articles[0] if articles else None
    featured_html = ""
    if featured:
        featured_html = f"""
        <section class="featured-insight">
          <div class="featured-badge">Featured Analysis</div>
          <div class="featured-content">
            <div class="featured-meta">
              <span class="category-pill">{featured['category']}</span>
              <span>{featured['formatted_date']}</span>
              <span>&middot;</span>
              <span>{featured['reading_time']}</span>
            </div>
            <h2><a href="insights/{featured['slug']}.html">{featured['title']}</a></h2>
            <p>{featured['excerpt']}</p>
            <a href="insights/{featured['slug']}.html" class="btn btn-primary">Read Full Analysis &rarr;</a>
          </div>
        </section>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Investment Insights | Ahmed Eisa — Wealth & Portfolio Strategy</title>
  <meta name="description" content="Investment and portfolio insights by Ahmed Eisa. Expert analysis on multi-asset allocation, wealth management, UAE regulations, digital assets, and investment technology.">
  <link rel="canonical" href="{SITE_URL}/insights.html">
  <meta property="og:type" content="website">
  <meta property="og:title" content="Investment Insights | Ahmed Eisa">
  <meta property="og:description" content="Curated analysis on portfolio management, asset allocation, digital assets, and wealth advisory by Ahmed Eisa.">
  <meta property="og:image" content="{AUTHOR_IMG}">
  <meta property="og:url" content="{SITE_URL}/insights.html">
  <link rel="icon" href="assets/icons/ae-logo.svg">
  <link rel="stylesheet" href="style.css">
  <script src="main.js" defer></script>
</head>
<body class="insights-index-page">
<header id="site-header"></header>

<main class="container">

  <div class="page-header">
    <div class="page-kicker">Investment Insights</div>
    <h1>Markets, Portfolios &amp; Regulated Assets</h1>
    <p class="lede">Strategic analysis on portfolio construction, institutional asset allocation, ETF dynamics, digital wealth infrastructure, and UAE regulatory readiness.</p>
  </div>

  {featured_html}

  <!-- Search & Category Filters -->
  <div class="insights-filter-bar">
    <div class="search-wrap">
      <input type="text" id="insightSearch" placeholder="Search insights by keyword, topic, or asset class..." aria-label="Search articles" />
    </div>
    <div class="category-tabs" id="categoryTabs">
      {''.join(cat_buttons)}
    </div>
  </div>

  <!-- Articles Grid -->
  <section class="insights-grid" id="insightsGrid">
    {''.join(cards)}
  </section>

  <div class="no-results" id="noResults" style="display:none; text-align:center; padding: 48px 0; color: #a0aec0;">
    <p>No investment insights found matching your filter criteria.</p>
    <button class="btn btn-outline" onclick="resetFilters()">Reset Filters</button>
  </div>

  <section class="section" style="margin-top: 60px; padding: 32px; background: var(--card-bg); border-radius: 12px; border: 1px solid var(--border-color); text-align: center;">
    <div class="section-kicker">Direct Advisory</div>
    <h2 style="font-size: 24px; margin: 8px 0 16px;">Looking for tailored portfolio or product strategy?</h2>
    <p style="max-width: 620px; margin: 0 auto 24px; color: var(--text-muted);">Available for executive advisory, investment product design, regulatory licensing readiness, and institutional consulting.</p>
    <a class="btn btn-primary" href="contact.html">Get in Touch</a>
  </section>

</main>

<footer id="site-footer"></footer>

<script>
document.addEventListener('DOMContentLoaded', function() {{
  const searchInput = document.getElementById('insightSearch');
  const tabs = document.querySelectorAll('.cat-tab');
  const cards = document.querySelectorAll('.post-card');
  const noResults = document.getElementById('noResults');

  let currentCategory = 'all';
  let currentSearch = '';

  function filterPosts() {{
    let visible = 0;
    cards.forEach(card => {{
      const cat = card.getAttribute('data-category');
      const title = card.getAttribute('data-title');
      const tags = card.getAttribute('data-tags');
      const text = card.textContent.toLowerCase();

      const matchesCat = (currentCategory === 'all' || cat === currentCategory);
      const matchesSearch = (!currentSearch || text.includes(currentSearch) || title.includes(currentSearch) || tags.includes(currentSearch));

      if (matchesCat && matchesSearch) {{
        card.style.display = '';
        visible++;
      }} else {{
        card.style.display = 'none';
      }}
    }});

    noResults.style.display = visible === 0 ? 'block' : 'none';
  }}

  tabs.forEach(tab => {{
    tab.addEventListener('click', () => {{
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentCategory = tab.getAttribute('data-category');
      filterPosts();
    }});
  }});

  if (searchInput) {{
    searchInput.addEventListener('input', (e) => {{
      currentSearch = e.target.value.trim().toLowerCase();
      filterPosts();
    }});
  }}

  window.resetFilters = function() {{
    currentCategory = 'all';
    currentSearch = '';
    if (searchInput) searchInput.value = '';
    tabs.forEach(t => t.classList.remove('active'));
    tabs[0].classList.add('active');
    filterPosts();
  }};
}});
</script>
</body>
</html>
"""
    with open("insights.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open("blog.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("  Generated insights.html and blog.html")

def update_homepage(latest_articles):
    if not os.path.exists("index.html"):
        return
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()

    cards = []
    for a in latest_articles:
        cards.append(f"""
      <article class="card insight-home-card">
        <div class="card-meta">
          <span class="category-pill">{a['category']}</span>
          <span class="date">{a['formatted_date']}</span>
        </div>
        <h3><a href="insights/{a['slug']}.html">{a['title']}</a></h3>
        <p>{a['excerpt'][:140]}...</p>
        <a href="insights/{a['slug']}.html" class="read-link">Read analysis &rarr;</a>
      </article>""")

    section_html = f"""
  <!-- LATEST INVESTMENT INSIGHTS -->
  <section class="section insights-home-section" aria-label="Latest Investment Insights">
    <div class="section-head">
      <div>
        <div class="section-kicker">Thought Leadership</div>
        <h2>Latest Investment Insights</h2>
      </div>
      <p>Independent commentary and deep-dives on multi-asset portfolio positioning, institutional asset flows, UAE digital asset regulations, and wealth management.</p>
    </div>
    <div class="cards">
      {''.join(cards)}
    </div>
    <div class="cta-row">
      <a class="btn btn-outline" href="insights.html">View All Investment Insights &rarr;</a>
    </div>
  </section>
"""

    # Check if section already exists
    if 'class="section insights-home-section"' in content:
        # Replace existing section
        content = re.sub(
            r'<!-- LATEST INVESTMENT INSIGHTS -->.*?</section>',
            section_html.strip(),
            content,
            flags=re.DOTALL
        )
    else:
        # Insert before credentials-band
        target = '<section class="section credentials-band"'
        if target in content:
            content = content.replace(target, section_html + "\n  " + target)
        else:
            # Insert before final-cta
            content = content.replace('<section class="final-cta">', section_html + "\n  " + '<section class="final-cta">')

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(content)
    print("  Updated homepage index.html with latest insights")

if __name__ == "__main__":
    build()
