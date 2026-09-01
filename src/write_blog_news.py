#!/usr/bin/env python3
"""Simplified blog writer: fetch news -> write content/news/*.md with images"""
import sys, os
sys.path.insert(0, r"C:\Users\ASUS\daily-news-shorts\src")
from news_fetcher import NewsFetcher

os.makedirs("content/news", exist_ok=True)
fetcher = NewsFetcher()
articles = fetcher.fetch_all_news()
print(f"Fetched {len(articles)} articles")

for i, a in enumerate(articles[:5]):
    slug = a.title.replace(" ", "_")[:50].replace(":", "").replace("?", "").replace("/", "_")
    image_url = getattr(a, "image_url", "") or ""
    md_path = f"content/news/{slug}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(f'title: "{a.title}"\n')
        f.write(f"source: \"{a.source}\"\n")
        f.write(f"date: {a.published_at}\n")
        f.write(f'image: "{image_url}"\n')
        f.write("---\n\n")
        if image_url:
            f.write(f"![Cover]({image_url})\n\n")
        f.write(a.description or "No description available.\n")
        f.write(f"\n\n[Original source]({a.url})\n")
    print(f"Wrote: {md_path}")

print(f"Done. {min(5, len(articles))} articles in content/news/")

# Automation link: generate JSON feed for site/index.html
import json
try:
    feed_data = [{"title": a.title, "slug": (a.title or "").replace(" ", "_")[:40], "source": a.source, "date": a.published_at or "", "desc": (a.description or "")[:200], "img": getattr(a, "image_url", "") or ""} for a in articles[:6]]
    with open("site/news-feed.json", "w", encoding="utf-8") as f:
        json.dump(feed_data, f, indent=2, ensure_ascii=False)
    print("Feed saved: site/news-feed.json")
except Exception as e:
    print(f"Feed generation skipped: {e}")
