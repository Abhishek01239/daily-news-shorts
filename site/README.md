# Daily News Site (Project 2 simplification)

New site at `site/index.html` — reads from `content/news/*.md` articles.
Built as static HTML/CSS (no framework) for zero-cost hosting (Vercel/GitHub Pages).

## What it does
- Fetches news (NewsAPI + RSS) -> writes to `content/news/*.md`
- Site (`site/index.html`) displays articles with images
- No video/YouTube upload (disabled per user direction)

## Build/run
```bash
python src/write_blog_news.py        # writes content/news/*.md
# Site is static: open site/index.html or deploy site/ to Vercel
```

## Articles
Generated in `content/news/` (markdown with frontmatter: title, source, image, date).
