"""
Video generator - creates videos from news articles using ffmpeg.
"""
import os
import json
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

try:
    import ffmpeg
except ImportError:
    ffmpeg = None  # fallback for environments where ffmpeg-python isn't installed
from PIL import Image, ImageDraw, ImageFont

from config import config
from ai_generator import VideoMetadata
from news_fetcher import NewsArticle


@dataclass
class VideoResult:
    """Result of video generation."""
    video_path: str
    thumbnail_path: str
    metadata: VideoMetadata
    article: NewsArticle


class ThumbnailGenerator:
    """Generates thumbnails using Pollinations.ai or local fallback."""
    
    def __init__(self):
        self.session = None
        try:
            import requests
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
        except ImportError:
            pass
    
    def generate_pollinations(self, prompt: str, output_path: Path, seed: int = None) -> bool:
        """Generate image using Pollinations.ai (keyless)."""
        if not self.session:
            return False
        
        try:
            # Add seed for variation
            if seed is not None:
                prompt = f"{prompt}&seed={seed}"
            
            # Pollinations URL
            url = f"https://image.pollinations.ai/prompt/{prompt}"
            params = {
                "width": config.video.width,
                "height": config.video.height,
                "nologo": "true",
                "private": "true",
            }
            
            response = self.session.get(url, params=params, timeout=60, stream=True)
            response.raise_for_status()
            
            # Verify it's an image
            content_type = response.headers.get('content-type', '')
            if 'image' not in content_type:
                print(f"Pollinations returned non-image: {content_type}")
                return False
            
            # Save image
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verify with Pillow
            try:
                with Image.open(output_path) as img:
                    # Check EXIF for Pollinations signature
                    exif = img.getexif()
                    make = exif.get(271, "") if exif else ""
                    if "sana" not in make.lower():
                        print(f"Warning: Image may not be from Pollinations (make={make})")
                    # Check dimensions
                    if img.size != (config.video.width, config.video.height):
                        print(f"Warning: Unexpected dimensions {img.size}")
                return True
            except Exception as e:
                print(f"Image verification failed: {e}")
                return False
                
        except Exception as e:
            print(f"Pollinations generation failed: {e}")
            return False
    
    def generate_local_fallback(self, prompt: str, output_path: Path, article: NewsArticle) -> bool:
        """Generate a local fallback thumbnail."""
        try:
            # Create a gradient background
            img = Image.new('RGB', (config.video.width, config.video.height), color='#1a1a2e')
            draw = ImageDraw.Draw(img)
            
            # Draw gradient
            for y in range(config.video.height):
                r = int(26 + (y / config.video.height) * 30)
                g = int(26 + (y / config.video.height) * 20)
                b = int(46 + (y / config.video.height) * 50)
                draw.line([(0, y), (config.video.width, y)], fill=(r, g, b))
            
            # Add category badge
            cat_colors = {
                "technology": "#00d4ff",
                "business": "#ffd700",
                "science": "#00ff88",
                "health": "#ff6b6b",
                "world": "#ff9500",
            }
            cat_color = cat_colors.get(article.category, "#ffffff")
            
            # Draw category badge
            badge_text = article.category.upper()
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            except:
                font = ImageFont.load_default()
            
            badge_x = 40
            badge_y = 40
            bbox = draw.textbbox((badge_x, badge_y), badge_text, font=font)
            draw.rounded_rectangle(
                [bbox[0]-10, bbox[1]-5, bbox[2]+10, bbox[3]+5],
                radius=8,
                fill=cat_color
            )
            draw.text((badge_x, badge_y), badge_text, font=font, fill="white")
            
            # Add source
            source_text = article.source
            try:
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            except:
                font_small = ImageFont.load_default()
            
            draw.text((40, badge_y + 50), source_text, font=font_small, fill="#cccccc")
            
            # Add "BREAKING" or "LIVE" indicator
            draw.text((config.video.width - 200, 40), "🔴 LIVE", font=font_small, fill="#ff4444")
            
            img.save(output_path, quality=95)
            return True
            
        except Exception as e:
            print(f"Local thumbnail generation failed: {e}")
            return False
    
    def generate(self, prompt: str, output_path: Path, article: NewsArticle, seed: int = None) -> bool:
        """Generate thumbnail, trying Pollinations first then local fallback."""
        # Try Pollinations first
        if self.generate_pollinations(prompt, output_path, seed):
            return True
        
        # Fallback to local
        print("Falling back to local thumbnail generation")
        return self.generate_local_fallback(prompt, output_path, article)


# Wire ffmpeg binary from user's working environment
FFMPEG_BIN = r'C:\Users\ASUS\ai-video\mvenv\lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe'
import os
os.environ['FFMPEG_BINARY'] = FFMPEG_BIN if os.path.exists(FFMPEG_BIN) else 'ffmpeg'
class VideoGenerator:
    """Generates news short videos."""
    
    def __init__(self):
        self.thumbnail_gen = ThumbnailGenerator()
        self.video_count = 0
    
    def create_text_overlay_video(self, text: str, output_path: Path, duration: float = None) -> bool:
        if ffmpeg is None:
            raise ImportError('ffmpeg-python module not installed (requirements.txt needs to resolve properly)')
        """Create a video with text overlay using ffmpeg."""
        if duration is None:
            duration = config.video.duration_seconds
        
        try:
            # Create a simple color background with text using ffmpeg drawtext
            (
                ffmpeg
                .input(f'color=c={config.video.background_color}:size={config.video.width}x{config.video.height}:rate={config.video.fps}', f='lavfi', t=duration)
                .filter('drawtext', 
                    text=text,
                    fontcolor=config.video.font_color,
                    fontsize=config.video.font_size,
                    x='(w-text_w)/2',
                    y='(h-text_h)/2',
                    box=1,
                    boxcolor='0x000000@0.7',
                    boxborderw=20,
                    line_spacing=10
                )
                .output(str(output_path), vcodec='libx264', pix_fmt='yuv420p', r=config.video.fps)
                .overwrite_output()
                .run(quiet=True, capture_stdout=True, capture_stderr=True)
            )
            return True
        except ffmpeg.Error as e:
            print(f"FFmpeg text overlay error: {e.stderr.decode() if e.stderr else e}")
            return False
    
    def create_news_video(self, article: NewsArticle, metadata: VideoMetadata, output_path: Path) -> bool:
        """Create a complete news short video."""
        try:
            # Generate thumbnail
            thumb_path = output_path.with_suffix('.jpg')
            self.thumbnail_gen.generate(
                metadata.thumbnail_prompt, 
                thumb_path, 
                article, 
                seed=self.video_count * 97 + 13
            )
            
            # For now, create a simple video with the script as text overlay
            # In production, this would use TTS + stock footage + dynamic text
            script_text = textwrap.fill(metadata.script, width=40)
            
            # Create video with thumbnail as background and scrolling text
            # This is a simplified version - production would be more sophisticated
            (
                ffmpeg
                .input(str(thumb_path), loop=1, framerate=config.video.fps, t=config.video.duration_seconds)
                .filter('drawtext',
                    text=script_text[:500],  # Limit text length
                    fontcolor=config.video.font_color,
                    fontsize=config.video.font_size - 8,
                    x='(w-text_w)/2',
                    y='(h-text_h)/2',
                    box=1,
                    boxcolor='0x000000@0.8',
                    boxborderw=30,
                    line_spacing=15
                )
                .output(str(output_path), vcodec='libx264', pix_fmt='yuv420p', r=config.video.fps)
                .overwrite_output()
                .run(quiet=True, capture_stdout=True, capture_stderr=True)
            )
            
            self.video_count += 1
            return True
            
        except ffmpeg.Error as e:
            print(f"FFmpeg video creation error: {e.stderr.decode() if e.stderr else e}")
            return False
        except Exception as e:
            print(f"Video creation error: {e}")
            return False
    
    def generate_video(self, article: NewsArticle, metadata: VideoMetadata) -> Optional[VideoResult]:
        """Generate a complete video for an article."""
        # Sanitize filename
        safe_title = "".join(c for c in article.title[:50] if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')
        
        video_path = config.paths.videos_dir / f"{safe_title}_{self.video_count}.mp4"
        thumb_path = config.paths.videos_dir / f"{safe_title}_{self.video_count}.jpg"
        
        print(f"Generating video: {video_path.name}")
        
        if self.create_news_video(article, metadata, video_path):
            return VideoResult(
                video_path=str(video_path),
                thumbnail_path=str(thumb_path),
                metadata=metadata,
                article=article
            )
        
        return None


def main():
    """Test video generation."""
    from news_fetcher import NewsFetcher
    from ai_generator import AIContentGenerator
    
    fetcher = NewsFetcher()
    articles = fetcher.fetch_all_news()
    
    if not articles:
        print("No articles")
        return
    
    generator = AIContentGenerator()
    video_gen = VideoGenerator()
    
    for article in articles[:2]:
        print(f"\nProcessing: {article.title[:60]}...")
        metadata = generator.generate_video_metadata(article)
        if metadata:
            result = video_gen.generate_video(article, metadata)
            if result:
                print(f"  Video: {result.video_path}")
                print(f"  Thumb: {result.thumbnail_path}")


if __name__ == "__main__":
    main()
