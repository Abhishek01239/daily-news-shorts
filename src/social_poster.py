"""
Social media posting - Telegram, Reddit, Discord, Dev.to.
"""
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import Optional, List
from pathlib import Path

from config import config
from video_generator import VideoResult


class TelegramPoster:
    """Post to Telegram channel."""
    
    def __init__(self):
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        })
    
    def post(self, title: str, teaser: str, link: str, image_path: Optional[str] = None) -> bool:
        if not config.social.telegram_bot_token:
            print("Telegram bot token not set, skipping")
            return False
        
        if not config.social.telegram_channel_id:
            print("Telegram channel ID not set, skipping")
            return False
        
        try:
            # HTML-escape teaser
            teaser_escaped = teaser.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            
            # Create message with teaser and link
            msg_text = f"{title}\n\n{teaser_escaped}\n\n📺 Watch → {link}"
            
            api_url = f"https://api.telegram.org/bot{config.social.telegram_bot_token}/sendMessage"
            
            payload = {
                "chat_id": config.social.telegram_channel_id,
                "text": msg_text,
                "parse_mode": "HTML",
            }
            
            response = self.session.post(api_url, json=payload, timeout=60)
            resp_json = response.json()
            
            if resp_json.get("ok"):
                print(f"Telegram post successful: {msg_text[:60]}...")
                return True
            else:
                print(f"Telegram post failed: {resp_json}")
                return False
                
        except Exception as e:
            print(f"Telegram error: {e}")
            return False


class DiscordPoster:
    """Post to Discord via webhook."""
    
    def __init__(self):
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        })
    
    def post(self, title: str, teaser: str, link: str) -> bool:
        if not config.social.discord_webhook:
            print("Discord webhook not set, skipping")
            return False
        
        try:
            teaser_short = teaser[:1800] if len(teaser) > 1800 else teaser
            
            payload = {
                "content": f"**{title}**\n{teaser_short}\n\n📺 Watch: {link}",
                "username": "Daily News Shorts",
            }
            
            response = self.session.post(
                config.social.discord_webhook,
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 204]:
                print(f"Discord post successful: {title[:60]}...")
                return True
            else:
                print(f"Discord post failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"Discord error: {e}")
            return False


class RedditPoster:
    """Post to Reddit (simplified - just logs for now, needs OAuth auth)."""
    
    def __init__(self):
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"DailyNewsBot/1.0 (by /u/{config.social.reddit_username})",
        })
        self.client_id = config.social.reddit_client_id
        self.secret = config.social.reddit_secret
        self.username = config.social.reddit_username
        self.password = config.social.reddit_password
    
    def get_access_token(self) -> Optional[str]:
        if not all([self.client_id, self.secret, self.username, self.password]):
            return None
        
        try:
            auth = base64.b64encode(f"{self.client_id}:{self.secret}".encode()).decode()
            
            data = urllib.parse.urlencode({
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
            }).encode()
            
            req = urllib.request.Request(
                "https://www.reddit.com/api/v1/access_token",
                data=data,
                headers={
                    "Authorization": f"Basic {auth}",
                    "User-Agent": f"DailyNewsBot/1.0 (by /u/{self.username})",
                }
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read())
                return result.get("access_token")
        except Exception as e:
            print(f"Reddit auth error: {e}")
            return None
    
    def post(self, title: str, teaser: str, link: str, subreddit: str = "news") -> bool:
        token = self.get_access_token()
        if not token:
            print("Reddit token not available, skipping post")
            return False
        
        print(f"Reddit post would go to r/{subreddit}: {title[:60]}...")
        # In production, implement full POST /api/submit
        return False  # Requires full OAuth flow


class SocialPoster:
    """Main social posting coordinator."""
    
    def __init__(self):
        self.telegram = TelegramPoster()
        self.discord = DiscordPoster()
        self.reddit = RedditPoster()
    
    def post_all(self, video_result: VideoResult, teaser: Optional[str] = None) -> Dict[str, bool]:
        if teaser is None:
            teaser = video_result.metadata.description[:300]
        
        results = {
            "telegram": False,
            "discord": False,
            "reddit": False,
        }
        
        link = video_result.video_path  # In production, this would be YouTube URL
        
        # Post to Telegram
        results["telegram"] = self.telegram.post(
            video_result.metadata.title,
            teaser,
            link
        )
        
        # Post to Discord
        results["discord"] = self.discord.post(
            video_result.metadata.title,
            teaser,
            link
        )
        
        # Post to Reddit (requires more setup)
        # results["reddit"] = self.reddit.post(...)
        
        # Log results
        for platform, success in results.items():
            status = "✓" if success else "✗ (skipped/not configured)"
            print(f"  {platform}: {status}")
        
        return results
    
    def check_dedup(self, slug: str, platform: str) -> bool:
        """Check if content was already posted to a platform."""
        registry_path = config.paths.marketing_dir / f"{platform}.json"
        
        if not registry_path.exists():
            return False
        
        try:
            with open(registry_path, 'r') as f:
                data = json.load(f)
                posted_items = data.get("posted", [])
                return slug in posted_items
        except Exception:
            return False
    
    def mark_posted(self, slug: str, platform: str):
        """Mark content as posted on a platform."""
        registry_path = config.paths.marketing_dir / f"{platform}.json"
        
        data = {"posted": []}
        if registry_path.exists():
            try:
                with open(registry_path, 'r') as f:
                    data = json.load(f)
            except Exception:
                pass
        
        if "posted" not in data:
            data["posted"] = []
        
        if slug not in data["posted"]:
            data["posted"].append(slug)
        
        # Keep only last 100 entries
        data["posted"] = data["posted"][-100:]
        
        with open(registry_path, 'w') as f:
            json.dump(data, f, indent=2)