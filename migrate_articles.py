import os

articles = [
    {
        file: sca-readiness-in-practice.md,
        slug: sca-readiness-in-practice,
        title: Licence-to-Launch: SCA Readiness in Practice,
        date: 2025-10-01,
        category: Digital Assets,
        tags: [SCA, VARA, Regulatory Strategy, Digital Wealth, UAE Fintech],
        excerpt: A practical roadmap from concept to regulatory go-live under the UAE SCA framework, connecting governance design and compliance documentation with real operating controls.,
        seo_title: Licence-to-Launch: SCA Readiness in Practice | Ahmed Eisa,
        meta_description: Navigating the UAE SCA framework for digital asset platforms. Insights from the operational build of EmCoin on entity structuring, governance, and inspection readiness.,
        reading_time: 5 min read,
        source_file: improved_articles_version/insights/sca-readiness-in-practice.md
    },
    {
        file: q4-2025-stock-market-outlook.md,
        slug: q4-2025-stock-market-outlook,
        title: Q4 2025 Stock Market Outlook: No Margin for Error,
        date: 2025-10-06,
        category: Markets & Macro,
        tags: [Market Outlook, Valuations, AI Mega-Caps, Small-Cap Value, Portfolio Strategy],
        excerpt: A valuation and positioning summary focused on mega-cap concentration risk, small-cap opportunities, and the delicate balance between growth leadership and broader market breadth.,
        seo_title: Q4 2025 Stock Market Outlook: No Margin for Error | Ahmed Eisa,
        meta_description: Valuation and positioning summary covering high market concentration in mega-cap AI stocks and actionable portfolio strategies for Q4 2025.,
        reading_time: 6 min read,
        source_file: improved_articles_version/insights/q4-2025-stock-market-outlook.md
    },
    {
        file: 5-common-portfolio-mistakes.md,
        slug: 5-common-portfolio-mistakes,
        title: 5 Common Portfolio Mistakes — And How to Fix Them,
        date: 2025-09-15,
        category: Portfolio Strategy,
        tags: [Portfolio Construction, Asset Allocation, Diversification, Risk Management, Tax Efficiency],
        excerpt: Structural portfolio pitfalls including account sprawl, overlapping fund holdings, stale allocations, and inefficient asset placement — with actionable fixes.,
        seo_title: 5 Common Portfolio Mistakes & Solutions | Ahmed Eisa,
        meta_description: Discover 5 common portfolio construction mistakes that hurt investment returns and how disciplined asset allocation and rebalancing solve them.,
        reading_time: 7 min read,
        source_file: improved_articles_version/insights/5-common-portfolio-mistakes.md
    },
    {
        file: etf-flows-2025.md,
        slug: etf-flows-2025,
        title: ETF Flows 2025: Where Smart Money Moved,
        date: 2025-08-20,
        category: Asset Allocation,
        tags: [ETFs, Capital Flows, Gold, Active Strategies, Fixed Income, Wealth Management],
        excerpt: Analysis of global ETF flows across gold, value, fixed income, and active strategies — and what shifting institutional capital signals for portfolio allocation.,
        seo_title: ETF Flows 2025: Where Smart Money Moved | Ahmed Eisa,
        meta_description: Deep dive into 2025 ETF inflows and institutional capital rotation across gold, fixed income, and active equity strategies.,
        reading_time: 5 min read,
        source_file: improved_articles_version/insights/etf-flows-2025.md
    }
]

out_dir = content/insights
os.makedirs(out_dir, exist_ok=True)

for art in articles:
    body = "
 src = art[source_file]
 if not os.path.exists(src):
 src = os.path.join(insights, art[file])
 if os.path.exists(src):
 with open(src, encoding=utf-8) as f:
 lines = f.readlines()
 start = 0
 for i, l in enumerate(lines):
 if l.startswith(##):
 start = i
 break
 body = .join(lines[start:]).strip()
 
 tags_str = , .join(['' + t + '' for t in art[tags]])
 frontmatter = f"---
title: {art['title']}
slug: {art['slug']}
excerpt: {art['excerpt']}
hero_image: https://res.cloudinary.com/dfh3erwx1/image/upload/v1760280190/IMG_0073_vzkxvd.png
category: {art['category']}
tags: [{tags_str}]
author: {art['author']}
date: {art['date']}
reading_time: {art['reading_time']}
seo_title: {art['seo_title']}
meta_description: {art['meta_description']}
---

{body}
"
 target = os.path.join(out_dir, art[file])
 with open(target, w, encoding=utf-8) as f:
 f.write(frontmatter)
 print(fCreated {target} ({len(frontmatter)} bytes))
