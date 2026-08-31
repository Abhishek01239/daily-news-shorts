"""
YouTube uploader - uploads videos to YouTube as Shorts.
"""
import os
import json
import time
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from config import config
from video_generator import VideoResult


@dataclass
class UploadResult:
    """Result of a YouTube upload."""
    video_id: str
    url: str
    title: str
    scheduled_time: Optional[str] = None
    status: str = "uploaded"  # uploaded, scheduled, failed


class YouTubeUploader:
    """Handles YouTube video uploads."""
    
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    def __init__(self):
        self.youtube = None
        self.channel_name = config.youtube.channel_name
        self.token_path = config.paths.data_dir / f"{self.channel_name}_token.json"
        self.client_secret_path = config.paths.data_dir / "client_secret.json"
    
    def load_credentials(self) -> Optional[Credentials]:
        """Load OAuth credentials from token file or environment."""
        # First try environment variable (GitHub Actions)
        token_json = config.youtube.token_json
        if token_json:
            try:
                token_data = json.loads(token_json)
                creds = Credentials.from_authorized_user_info(token_data, self.SCOPES)
                if creds and creds.valid:
                    return creds
                elif creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    return creds
            except Exception as e:
                print(f"Failed to load credentials from env: {e}")
        
        # Then try local token file
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), self.SCOPES)
                if creds and creds.valid:
                    return creds
                elif creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    # Save refreshed token
                    self.save_credentials(creds)
                    return creds
            except Exception as e:
                print(f"Failed to load credentials from file: {e}")
        
        return None
    
    def save_credentials(self, creds: Credentials):
        """Save credentials to token file."""
        try:
            with open(self.token_path, 'w') as f:
                f.write(creds.to_json())
            print(f"Saved credentials to {self.token_path}")
        except Exception as e:
            print(f"Failed to save credentials: {e}")
    
    def authenticate(self) -> bool:
        """Authenticate with YouTube API."""
        creds = self.load_credentials()
        
        if not creds or not creds.valid:
            print("No valid credentials found. Run gen_token.py first.")
            return False
        
        try:
            self.youtube = build('youtube', 'v3', credentials=creds)
            # Test the connection
            self.youtube.channels().list(part='id', mine=True).execute()
            print("YouTube authentication successful")
            return True
        except HttpError as e:
            print(f"YouTube authentication failed: {e}")
            return False
        except Exception as e:
            print(f"YouTube authentication error: {e}")
            return False
    
    def upload_short(self, video_result: VideoResult, schedule_hours: float = None) -> Optional[UploadResult]:
        """Upload a video as a YouTube Short."""
        if not self.youtube:
            if not self.authenticate():
                return None
        
        if schedule_hours is None:
            schedule_hours = config.youtube.upload_schedule_hours
        
        # Calculate scheduled time
        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=schedule_hours)
        
        # Prepare metadata
        title = video_result.metadata.title
        description = f"{video_result.metadata.description}\n\n"
        description += f"Source: {video_result.article.source}\n"
        description += f"Original: {video_result.article.url}\n\n"
        description += " ".join(video_result.metadata.hashtags)
        
        # Truncate description if too long
        if len(description) > 5000:
            description = description[:4997] + "..."
        
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': video_result.metadata.hashtags,
                'categoryId': config.youtube.category_id,
                'defaultLanguage': 'en',
                'defaultAudioLanguage': 'en',
            },
            'status': {
                'privacyStatus': config.youtube.privacy_status,
                'selfDeclaredMadeForKids': False,
            }
        }
        
        # Schedule if in future
        if config.youtube.privacy_status == 'private' and schedule_hours > 0:
            body['status']['publishAt'] = scheduled_time.isoformat().replace('+00:00', 'Z')
            body['status']['privacyStatus'] = 'private'
        
        # Upload video
        try:
            print(f"Uploading: {title[:60]}...")
            
            media = MediaFileUpload(
                video_result.video_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/mp4'
            )
            
            request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"  Upload progress: {int(status.progress() * 100)}%")
            
            video_id = response['id']
            video_url = f"https://youtube.com/shorts/{video_id}"
            
            print(f"Uploaded: {video_url}")
            
            return UploadResult(
                video_id=video_id,
                url=video_url,
                title=title,
                scheduled_time=scheduled_time.isoformat() if schedule_hours > 0 else None,
                status="scheduled" if schedule_hours > 0 else "uploaded"
            )
            
        except HttpError as e:
            print(f"YouTube upload failed: {e}")
            if e.resp.status == 401:
                print("Authentication error - token may be expired or revoked")
            return None
        except Exception as e:
            print(f"Upload error: {e}")
            return None
    
    def upload_multiple(self, video_results: List[VideoResult], interval_hours: float = None) -> List[UploadResult]:
        """Upload multiple videos with scheduling intervals."""
        if interval_hours is None:
            interval_hours = config.youtube.upload_schedule_hours
        
        results = []
        base_time = datetime.now(timezone.utc) + timedelta(hours=interval_hours)
        
        for i, video_result in enumerate(video_results):
            schedule_time = base_time + timedelta(hours=i * interval_hours)
            schedule_hours = (schedule_time - datetime.now(timezone.utc)).total_seconds() / 3600
            
            if schedule_hours < 0:
                schedule_hours = 0.1  # Minimum delay
            
            result = self.upload_short(video_result, schedule_hours)
            if result:
                results.append(result)
                # Small delay between uploads to avoid rate limits
                time.sleep(2)
            else:
                print(f"Failed to upload video {i+1}")
        
        return results


def gen_token(channel_name: str = "DailyNewsShorts"):
    """Generate OAuth token for a channel (run locally)."""
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    client_secret_path = config.paths.data_dir / "client_secret.json"
    if not client_secret_path.exists():
        print(f"client_secret.json not found at {client_secret_path}")
        print("Download it from Google Cloud Console and place it there.")
        return
    
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secret_path), SCOPES
    )
    
    # Run local server for OAuth
    creds = flow.run_local_server(port=0)
    
    # Save token
    token_path = config.paths.data_dir / f"{channel_name}_token.json"
    with open(token_path, 'w') as f:
        f.write(creds.to_json())
    
    print(f"Token saved to {token_path}")
    print(f"Add this as GitHub secret: YOUTUBE_TOKEN_JSON_{channel_name.upper()}")


def main():
    """Test YouTube uploader."""
    uploader = YouTubeUploader()
    
    if uploader.authenticate():
        print("Authentication successful!")
        
        # List channel info
        try:
            response = uploader.youtube.channels().list(part='snippet,statistics', mine=True).execute()
            for channel in response.get('items', []):
                print(f"Channel: {channel['snippet']['title']}")
                print(f"Subscribers: {channel['statistics'].get('subscriberCount', 'N/A')}")
        except Exception as e:
            print(f"Error getting channel info: {e}")
    else:
        print("Authentication failed")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "gen_token":
        gen_token(sys.argv[2] if len(sys.argv) > 2 else "DailyNewsShorts")
    else:
        main()