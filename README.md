# Daily News Shorts (Project 2 of 10)

Automated GitHub Actions pipeline that fetches news, generates AI-powered short videos, and posts to YouTube + social channels.

## What it does
- Fetches news from NewsAPI + RSS feeds (BBC, NYT, Reuters, Guardian, CNN)
- Uses Groq AI to generate titles, descriptions, hashtags, and TTS scripts
- Creates 1080x1920 vertical videos with thumbnails via Pollinations.ai
- Uploads to YouTube Shorts with scheduling
- Posts to Telegram, Discord (Reddit optional)

## Business model: Subscription (₹49-₹299/month)

## Setup (user needs to do)
1. Get NewsAPI key (free tier) → set as `NEWS_API_KEY` secret
2. Get Groq API key → set as `GROQ_API_KEY` secret
3. YouTube OAuth token → `python src/youtube_uploader.py gen_token`
4. Set `YOUTUBE_TOKEN_JSON_DAILYNEWS` secret
5. Telegram bot token + channel ID → `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`
6. Discord webhook URL → `DISCORD_WEBHOOK`

## Workflow
Triggered by `cron: '0 6 * * *'` (daily 6am UTC) + manual dispatch.

## Features
- Dedup via SHA256 content hashes
- Auto-resume after failures
- Keyless image generation (Pollinations)
- Fail-safe: no AI = basic metadata + local thumbnail
- Dry-run mode for testing
