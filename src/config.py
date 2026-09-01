"""
Configuration module for Daily News Shorts.
Loads settings from environment variables and provides defaults.
"""
import os
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class NewsConfig:
    """News API and RSS configuration."""
    news_api_key: str = os.getenv("NEWS_API_KEY", "")
    rss_feeds: List[str] = field(default_factory=lambda: [
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "https://feeds.reuters.com/reuters/topNews",
        "https://www.theguardian.com/world/rss",
        "https://rss.cnn.com/rss/edition.rss",
    ])
    categories: List[str] = field(default_factory=lambda: [
        "technology", "business", "science", "health", "world"
    ])
    max_articles_per_category: int = 5
    article_age_hours: int = 24


@dataclass
class AIConfig:
    """AI content generation configuration."""
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    # Will be populated dynamically from Groq models list
    preferred_models: List[str] = field(default_factory=lambda: [
        "groq/compound-mini",
        "groq/compound",
        "qwen/qwen3.6-27b",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
    ])
    fallback_title: str = "Daily News Update"
    max_title_length: int = 80
    max_description_length: int = 500


@dataclass
class VideoConfig:
    """Video generation configuration."""
    width: int = 1080
    height: int = 1920
    fps: int = 30
    duration_seconds: int = 50
    background_music_volume: float = 0.1
    font_size: int = 48
    font_color: str = "white"
    background_color: str = "black"
    max_clips: int = 5
    clip_duration: int = 10


@dataclass
class YouTubeConfig:
    """YouTube upload configuration."""
    token_json: str = os.getenv("YOUTUBE_TOKEN_JSON_DAILYNEWS", "")
    channel_name: str = "DailyNewsShorts"
    upload_schedule_hours: float = 1.5
    shorts_per_run: int = 6
    privacy_status: str = "private"  # private, unlisted, public
    category_id: str = "25"  # News & Politics
    tags: List[str] = field(default_factory=lambda: [
        "news", "shorts", "daily", "breaking", "update"
    ])


@dataclass
class SocialConfig:
    """Social media posting configuration."""
    # Telegram
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_channel_id: str = os.getenv("TELEGRAM_CHANNEL_ID", "")
    
    # Reddit
    reddit_client_id: str = os.getenv("REDDIT_CLIENT_ID", "")
    reddit_secret: str = os.getenv("REDDIT_SECRET", "")
    reddit_username: str = os.getenv("REDDIT_USERNAME", "")
    reddit_password: str = os.getenv("REDDIT_PASSWORD", "")
    reddit_subreddits: List[str] = field(default_factory=lambda: [
        "news", "worldnews", "technology", "science"
    ])
    
    # Discord
    discord_webhook: str = os.getenv("DISCORD_WEBHOOK", "")
    
    # General
    site_url: str = os.getenv("SITE_URL", "https://your-site.vercel.app")
    teaser_max_chars: int = 400


@dataclass
class PathsConfig:
    """File paths configuration."""
    base_dir: Path = Path(__file__).parent.parent
    data_dir: Path = field(init=False)
    state_file: Path = field(init=False)
    marketing_dir: Path = field(init=False)
    videos_dir: Path = field(init=False)
    temp_dir: Path = field(init=False)
    
    def __post_init__(self):
        self.data_dir = self.base_dir / "data"
        self.state_file = self.data_dir / "state.json"
        self.marketing_dir = self.base_dir / ".marketing"
        self.videos_dir = self.data_dir / "videos"
        self.temp_dir = self.data_dir / "temp"
        
        # Create directories
        for d in [self.data_dir, self.marketing_dir, self.videos_dir, self.temp_dir]:
            d.mkdir(parents=True, exist_ok=True)


@dataclass
class Config:
    """Main configuration aggregator."""
    news: NewsConfig = field(default_factory=NewsConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)
    social: SocialConfig = field(default_factory=SocialConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    category_filter: Optional[str] = None


# Global config instance
config = Config()
# FFmpeg binary path override (user-confirmed working binary)
import imageio_ffmpeg
CONFIG['ffmpeg_path'] = r'C:\Users\ASUS\ai-video\mvenv\lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe'
