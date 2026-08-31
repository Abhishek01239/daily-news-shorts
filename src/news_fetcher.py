"""
News fetcher module - fetches news from APIs and RSS feeds.
"""
import json
import feedparser
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import re

from config import config


@dataclass
class NewsArticle:
    """Represents a news article."""
    title: str
    description: str
    url: str
    source: str
    category: str
    published_at: str
    image_url: str = ""
    content_hash: str = ""
    
    def __post_init__(self):
        if not self.content_hash:
            # Create a hash for deduplication
            content = f"{self.title}{self.url}{self.source}"
            self.content_hash = hashlib.md5(content.encode()).hexdigest()[:16]


class NewsFetcher:
    """Fetches news from multiple sources."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.seen_hashes: set = set()
        self.load_state()
    
    def load_state(self):
        """Load seen article hashes from state file."""
        if config.paths.state_file.exists():
            try:
                with open(config.paths.state_file, 'r') as f:
                    data = json.load(f)
                    self.seen_hashes = set(data.get("seen_hashes", []))
            except Exception:
                self.seen_hashes = set()
    
    def save_state(self):
        """Save seen article hashes to state file."""
        data = {
            "seen_hashes": list(self.seen_hashes),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        with open(config.paths.state_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def is_duplicate(self, article: NewsArticle) -> bool:
        """Check if article is a duplicate."""
        return article.content_hash in self.seen_hashes
    
    def mark_seen(self, article: NewsArticle):
        """Mark article as seen."""
        self.seen_hashes.add(article.content_hash)
    
    def fetch_from_newsapi(self, category: str = "general") -> List[NewsArticle]:
        """Fetch news from NewsAPI.org."""
        if not config.news.news_api_key:
            return []
        
        articles = []
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "apiKey": config.news.news_api_key,
            "category": category,
            "language": "en",
            "pageSize": config.news.max_articles_per_category,
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            for item in data.get("articles", []):
                if not item.get("title") or item.get("title") == "[Removed]":
                    continue
                    
                article = NewsArticle(
                    title=item.get("title", ""),
                    description=item.get("description", "") or "",
                    url=item.get("url", ""),
                    source=item.get("source", {}).get("name", "NewsAPI"),
                    category=category,
                    published_at=item.get("publishedAt", datetime.now(timezone.utc).isoformat()),
                    image_url=item.get("urlToImage", "") or ""
                )
                articles.append(article)
                
        except Exception as e:
            print(f"NewsAPI error for {category}: {e}")
        
        return articles
    
    def fetch_from_rss(self, feed_url: str, category: str = "general") -> List[NewsArticle]:
        """Fetch news from RSS feed."""
        articles = []
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:config.news.max_articles_per_category]:
                # Parse published date
                published = datetime.now(timezone.utc)
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                
                # Check if article is too old
                if datetime.now(timezone.utc) - published > timedelta(hours=config.news.article_age_hours):
                    continue
                
                # Extract image
                image_url = ""
                if hasattr(entry, 'media_content') and entry.media_content:
                    image_url = entry.media_content[0].get('url', '')
                elif hasattr(entry, 'enclosures') and entry.enclosures:
                    image_url = entry.enclosures[0].get('href', '')
                
                article = NewsArticle(
                    title=entry.get("title", ""),
                    description=entry.get("summary", "") or entry.get("description", ""),
                    url=entry.get("link", ""),
                    source=feed.feed.get("title", "RSS Feed"),
                    category=category,
                    published_at=published.isoformat(),
                    image_url=image_url
                )
                articles.append(article)
                
        except Exception as e:
            print(f"RSS error for {feed_url}: {e}")
        
        return articles
    
    def fetch_all_news(self, category_filter: Optional[str] = None) -> List[NewsArticle]:
        """Fetch news from all sources."""
        all_articles = []
        
        # Determine categories to fetch
        categories = config.news.categories
        if category_filter:
            categories = [category_filter] if category_filter in categories else categories
        
        # Fetch from NewsAPI for each category
        for category in categories:
            articles = self.fetch_from_newsapi(category)
            all_articles.extend(articles)
        
        # Fetch from RSS feeds
        for i, feed_url in enumerate(config.news.rss_feeds):
            # Assign category based on feed index
            cat = categories[i % len(categories)] if categories else "general"
            articles = self.fetch_from_rss(feed_url, cat)
            all_articles.extend(articles)
        
        # Filter duplicates and sort by recency
        unique_articles = []
        for article in all_articles:
            if not self.is_duplicate(article):
                self.mark_seen(article)
                unique_articles.append(article)
        
        # Sort by published date (newest first)
        unique_articles.sort(key=lambda x: x.published_at, reverse=True)
        
        # Save state
        self.save_state()
        
        return unique_articles


def main():
    """Test the news fetcher."""
    fetcher = NewsFetcher()
    articles = fetcher.fetch_all_news()
    
    print(f"Fetched {len(articles)} unique articles")
    for a in articles[:5]:
        print(f"  - [{a.category}] {a.title[:80]}... ({a.source})")


if __name__ == "__main__":
    main()