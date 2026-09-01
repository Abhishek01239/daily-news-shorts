#!/usr/bin/env python3
"""
Daily News Shorts - Main pipeline.
Fetches news, generates AI content, creates videos, uploads, posts to social.
"""
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config import config, Config
from news_fetcher import NewsFetcher
from ai_generator import AIContentGenerator
from video_generator import VideoGenerator
from youtube_uploader import YouTubeUploader
from social_poster import SocialPoster


class DailyNewsPipeline:
    """Main automation pipeline."""
    
    def __init__(self, category_filter: str = None):
        config.category_filter = category_filter
        self.news_fetcher = NewsFetcher()
        self.ai_generator = None
        self.video_gen = VideoGenerator()
        self.youtube_uploader = YouTubeUploader()
        self.social_poster = SocialPoster()
        
    def initialize_ai(self):
        if config.ai.groq_api_key:
            try:
                self.ai_generator = AIContentGenerator()
                print("AI generator initialized with Groq")
            except Exception as e:
                print(f"Failed to initialize AI: {e}")
                self.ai_generator = None
        else:
            print("No GROQ_API_KEY set, using fallback mode")
            # Fallback: set self.ai_generator to None (used in run() already)
            self.ai_generator = None
    
    def run(self) -> dict:
        """Run the full pipeline."""
        results = {
            "articles_found": 0,
            "videos_generated": 0,
            "videos_uploaded": 0,
            "social_posts": 0,
            "errors": [],
        }
        
        print("=" * 60)
        print("DAILY NEWS SHORTS PIPELINE")
        print(f"Started: {__import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"Category filter: {config.category_filter or 'all'}")
        print("=" * 60)
        
        # Step 1: Fetch news
        print("\n[1/5] Fetching news articles...")
        articles = self.news_fetcher.fetch_all_news(config.category_filter)
        results["articles_found"] = len(articles)
        print(f"  Found {len(articles)} unique articles")
        
        for a in articles[:3]:
            print(f"    - {a.title[:80]} ({a.source})")
        
        # Step 2: Initialize AI
        print("\n[2/5] Initializing AI content generator...")
        self.initialize_ai()
        
        # Step 3: Generate videos
        print("\n[3/5] Generating videos...")
        video_results = []
        
        for i, article in enumerate(articles[:config.youtube.shorts_per_run]):
            print(f"  Processing article {i+1}/{min(len(articles), config.youtube.shorts_per_run)}: {article.title[:60]}...")
            
            try:
                # Generate AI metadata
                if self.ai_generator:
                    metadata = self.ai_generator.generate_video_metadata(article)
                    if not metadata:
                        print(f"    AI generation failed, using fallback")
                        # Create basic metadata
                        from ai_generator import VideoMetadata
                        metadata = VideoMetadata(
                            title=article.title[:70],
                            description=article.description[:200],
                            hashtags=["#shorts", "#news", "#breaking", "#daily"],
                            script=article.title + ". " + (article.description or ""),
                            thumbnail_prompt=f"news thumbnail, {article.category}"
                        )
                else:
                    # No AI - use basic metadata
                    from ai_generator import VideoMetadata
                    metadata = VideoMetadata(
                        title=article.title[:70] + "!",
                        description=f"{article.description[:150]}... Source: {article.source}",
                        hashtags=["#shorts", "#news", "#breaking", "#daily", f"#{article.category}"],
                        script=f"{article.title}. {article.description[:300] if article.description else 'Latest news update from'} {article.source}.",
                        thumbnail_prompt=f"news thumbnail, {article.category} theme, professional"
                    )
                
                # Generate video file
                result = self.video_gen.generate_video(article, metadata)
                if result:
                    video_results.append(result)
                    results["videos_generated"] += 1
                    print(f"    ✓ Video generated: {result.video_path.split('/')[-1]}")
                else:
                    print(f"    ✗ Video generation failed")
                    results["errors"].append(f"Video generation failed for: {article.title}")
                    
            except Exception as e:
                print(f"    ✗ Error processing article: {e}")
                results["errors"].append(f"Article processing error: {str(e)}")
        
        # Step 4: Upload to YouTube
        print(f"\n[4/5] Uploading {len(video_results)} videos to YouTube...")
        if video_results:
            if self.youtube_uploader.authenticate():
                upload_results = self.youtube_uploader.upload_multiple(
                    video_results,
                    interval_hours=config.youtube.upload_schedule_hours
                )
                results["videos_uploaded"] = len(upload_results)
                print(f"  Uploaded {len(upload_results)} videos")
                for r in upload_results:
                    print(f"    ✓ {r.title[:60]} -> {r.url}")
            else:
                print("  YouTube authentication failed - videos staged but not uploaded")
                results["errors"].append("YouTube authentication failed")
        else:
            print("  No videos to upload")
        
        # Step 5: Post to social
        print(f"\n[5/5] Posting to social media...")
        for result in video_results:
            # Generate teaser from metadata
            teaser = result.metadata.description[:300]
            
            # Post to platforms
            social_results = self.social_poster.post_all(
                result,
                teaser
            )
            
            if any(social_results.values()):
                results["social_posts"] += 1
                print(f"  Social posts made for: {result.metadata.title[:60]}...")
        
        # Summary
        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE")
        print(f"Articles: {results['articles_found']}")
        print(f"Videos generated: {results['videos_generated']}")
        print(f"Videos uploaded: {results['videos_uploaded']}")
        print(f"Social posts: {results['social_posts']}")
        if results["errors"]:
            print(f"Errors: {len(results['errors'])}")
            for e in results["errors"]:
                print(f"  - {e}")
        print("=" * 60)
        
        return results


def main():
    parser = argparse.ArgumentParser(description="Daily News Shorts Pipeline")
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Filter by news category (technology, business, science, health, world)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without generating/uploading"
    )
    
    args = parser.parse_args()
    
    pipeline = DailyNewsPipeline(category_filter=args.category)
    
    if args.dry_run:
        print("DRY RUN MODE - No uploads or posts will occur")
        print("This would:")
        print(f"  - Fetch news in category: {args.category or 'all'}")
        print(f"  - Generate up to {config.youtube.shorts_per_run} videos")
        print(f"  - Upload with {config.youtube.upload_schedule_hours}h intervals")
        print(f"  - Post to configured social platforms")
    else:
        pipeline.run()


if __name__ == "__main__":
    main()