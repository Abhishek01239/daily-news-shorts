"""
AI content generator - uses Groq to generate video metadata.
"""
import json
import os
from typing import List, Optional, Dict
from dataclasses import dataclass
from pathlib import Path

from groq import Groq
from config import config
from news_fetcher import NewsArticle


@dataclass
class VideoMetadata:
    """Metadata for a video."""
    title: str
    description: str
    hashtags: List[str]
    script: str  # Text-to-speech script
    thumbnail_prompt: str


class GroqModelManager:
    """Manages Groq model selection with fallback."""
    
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.available_models: List[str] = []
        self._fetch_models()
    
    def _fetch_models(self):
        """Fetch available models from Groq."""
        try:
            models = self.client.models.list()
            # Filter for chat-capable models
            chat_models = []
            for m in models.data:
                model_id = m.id
                # Skip embedding and other non-chat models
                if any(x in model_id.lower() for x in ['embed', 'whisper', 'tts', 'guard']):
                    continue
                chat_models.append(model_id)
            
            # Prioritize known good models
            priority_order = [
                "groq/compound-mini",
                "groq/compound",
                "qwen/qwen3.6-27b",
                "openai/gpt-oss-120b",
                "openai/gpt-oss-20b",
                "meta-llama/llama-4-scout-17b-16e-instruct",
                "meta-llama/llama-4-maverick-17b-128e-instruct",
                "deepseek-r1-distill-llama-70b",
            ]
            
            # Sort by priority
            self.available_models = sorted(
                chat_models,
                key=lambda x: priority_order.index(x) if x in priority_order else 999
            )
            print(f"Available Groq models: {self.available_models[:10]}")
            
        except Exception as e:
            print(f"Failed to fetch Groq models: {e}")
            # Fallback to config list
            self.available_models = config.ai.preferred_models
    
    def generate(self, prompt: str, system: str = "", temperature: float = 0.7, max_tokens: int = 1000) -> Optional[str]:
        """Generate content with model fallback."""
        for model in self.available_models:
            try:
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                error_msg = str(e).lower()
                if "decommissioned" in error_msg or "not_found" in error_msg or "model_not_found" in error_msg:
                    print(f"Model {model} unavailable: {e}")
                    continue
                elif "rate_limit" in error_msg or "429" in error_msg:
                    print(f"Rate limited on {model}: {e}")
                    continue
                else:
                    print(f"Error with {model}: {e}")
                    continue
        
        print("All models failed!")
        return None


class AIContentGenerator:
    """Generates video content using AI."""
    
    def __init__(self):
        if not config.ai.groq_api_key:
            raise ValueError("GROQ_API_KEY not configured")
        self.model_manager = GroqModelManager(config.ai.groq_api_key)
        self.used_titles: set = set()
    
    def normalize_title(self, title: str) -> str:
        """Normalize title for deduplication."""
        import re
        t = title.lower()
        t = re.sub(r"[^a-z0-9 ]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t
    
    def is_duplicate_title(self, title: str) -> bool:
        """Check if title is duplicate."""
        norm = self.normalize_title(title)
        return norm in self.used_titles
    
    def mark_title_used(self, title: str):
        """Mark title as used."""
        self.used_titles.add(self.normalize_title(title))
    
    def generate_video_metadata(self, article: NewsArticle) -> Optional[VideoMetadata]:
        """Generate video metadata from a news article."""
        
        # System prompt for news shorts
        system_prompt = """You are a professional news content creator for YouTube Shorts.
Create engaging, concise content for vertical short-form videos (50 seconds max).
Style: Informative, engaging, authoritative but accessible.
Output MUST be valid JSON only."""
        
        user_prompt = f"""Create a YouTube Short video script from this news article:

Title: {article.title}
Description: {article.description}
Source: {article.source}
Category: {article.category}
URL: {article.url}

Generate JSON with these fields:
1. "title": Catchy YouTube Shorts title (max 80 chars, include 1-2 relevant emojis)
2. "description": Video description (2-3 sentences, include source credit)
3. "hashtags": Array of 8-10 relevant hashtags (include #shorts #news #breaking)
3. "script": TTS narration script (~130 words for 50 seconds, conversational tone)
4. "thumbnail_prompt": Pollinations.ai image prompt for 1080x1920 thumbnail (news style, professional, text-safe area)

Example output:
{{
  "title": "🚀 Major AI Breakthrough Changes Everything!",
  "description": "OpenAI unveils GPT-5 with real-time reasoning. This changes how we work. Source: TechCrunch",
  "hashtags": ["#shorts", "#news", "#ai", "#tech", "#breaking", "#gpt5", "#openai", "#innovation", "#future", "#technology"],
  "script": "OpenAI just dropped GPT-5 and it's a game changer. The new model can reason in real-time, solving complex problems step by step. Early demos show it writing code, analyzing data, and even helping with creative tasks. This could transform how millions of people work every day. The rollout starts next week for Plus users. What would you use it for?",
  "thumbnail_prompt": "Professional news thumbnail, breaking news style, AI brain neural network glowing, modern studio lighting, 1080x1920 vertical, space for title text at top, high quality photorealistic"
}}"""
        
        response = self.model_manager.generate(user_prompt, system_prompt, temperature=0.8, max_tokens=1500)
        
        if not response:
            return self._fallback_metadata(article)
        
        try:
            data = json.loads(response)
            
            # Validate required fields
            required = ["title", "description", "hashtags", "script", "thumbnail_prompt"]
            for field in required:
                if field not in data:
                    data[field] = ""
            
            # Check title length
            if len(data["title"]) > config.ai.max_title_length:
                data["title"] = data["title"][:config.ai.max_title_length - 3] + "..."
            
            # Check for duplicate title
            if self.is_duplicate_title(data["title"]):
                print(f"Duplicate title detected, retrying: {data['title']}")
                return None
            
            self.mark_title_used(data["title"])
            
            return VideoMetadata(
                title=data["title"],
                description=data["description"],
                hashtags=data["hashtags"][:10],
                script=data["script"],
                thumbnail_prompt=data["thumbnail_prompt"]
            )
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse AI response: {e}")
            print(f"Response: {response[:200]}")
            return self._fallback_metadata(article)
    
    def _fallback_metadata(self, article: NewsArticle) -> VideoMetadata:
        """Generate fallback metadata without AI."""
        title = article.title[:70] + ("..." if len(article.title) > 70 else "")
        if not title.endswith(("!", "?", ".")):
            title += "!"
        
        # Simple hashtags from category
        cat_tags = {
            "technology": ["#tech", "#ai", "#innovation"],
            "business": ["#business", "#finance", "#markets"],
            "science": ["#science", "#research", "#discovery"],
            "health": ["#health", "#wellness", "#medical"],
            "world": ["#worldnews", "#global", "#international"],
        }
        tags = ["#shorts", "#news", "#breaking", "#daily"] + cat_tags.get(article.category, ["#trending"])
        
        script = f"{article.title}. {article.description[:300]} Source: {article.source}. Stay informed with our daily news shorts."
        
        return VideoMetadata(
            title=title,
            description=f"{article.description[:200]}... Source: {article.source}",
            hashtags=tags[:10],
            script=script,
            thumbnail_prompt=f"Professional news thumbnail, {article.category} theme, breaking news style, modern clean design, 1080x1920 vertical, space for text overlay"
        )


def main():
    """Test the AI content generator."""
    from news_fetcher import NewsFetcher
    
    fetcher = NewsFetcher()
    articles = fetcher.fetch_all_news()
    
    if not articles:
        print("No articles to process")
        return
    
    generator = AIContentGenerator()
    
    for article in articles[:3]:
        print(f"\nProcessing: {article.title[:60]}...")
        metadata = generator.generate_video_metadata(article)
        if metadata:
            print(f"  Title: {metadata.title}")
            print(f"  Hashtags: {metadata.hashtags}")
            print(f"  Script length: {len(metadata.script)} chars")


if __name__ == "__main__":
    main()