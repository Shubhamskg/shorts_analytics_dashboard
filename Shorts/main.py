"""
Dr. Linda Greenwall MIH Content Automation System - Enhanced Version
Automatically finds, processes, and publishes educational MIH content from YouTube videos
Supports multiple channels with detailed CSV logging and configurable timing
UPDATED with enhanced multi-channel support and channel-specific customization
"""

import os
import re
import json
import time
import logging
import subprocess
import csv
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

import requests
import google.generativeai as genai
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from youtube_transcript_api import YouTubeTranscriptApi
import ffmpeg

# Configure logging with Windows-compatible encoding
import sys
import codecs

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mih_automation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class VideoClip:
    """Represents a processed video clip with all metadata"""
    clip_id: str
    start_time: float
    end_time: float
    transcript: str
    relevance_score: float
    source_video_id: str
    source_title: str
    source_url: str
    title: str
    description: str
    captions: List[str]
    hashtags: List[str]
    thumbnail_suggestion: str
    file_path: Optional[str] = None
    published_channels: List[str] = None
    failed_channels: List[str] = None
    created_at: str = None
    duration: float = 0.0
    
    def __post_init__(self):
        if self.published_channels is None:
            self.published_channels = []
        if self.failed_channels is None:
            self.failed_channels = []
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.duration == 0.0:
            self.duration = self.end_time - self.start_time

@dataclass
class ProcessedVideo:
    """Represents a processed source video with metadata"""
    video_id: str
    title: str
    description: str
    url: str
    channel_title: str
    published_at: str
    transcript: str
    clips_extracted: int
    clips_published: int
    processing_status: str
    processing_date: str
    error_message: str = ""
    
    def __post_init__(self):
        if self.processing_date is None:
            self.processing_date = datetime.now().isoformat()

class CSVLogger:
    """Handles CSV logging for videos and clips"""
    
    def __init__(self, output_dir: str = "logs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.videos_csv = self.output_dir / "processed_videos.csv"
        self.clips_csv = self.output_dir / "published_clips.csv"
        
        self._initialize_csv_files()
    
    def _initialize_csv_files(self):
        """Initialize CSV files with headers if they don't exist"""
        
        # Videos CSV headers
        videos_headers = [
            'video_id', 'title', 'description', 'url', 'channel_title', 
            'published_at', 'transcript', 'clips_extracted', 'clips_published',
            'processing_status', 'processing_date', 'error_message'
        ]
        
        if not self.videos_csv.exists():
            with open(self.videos_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(videos_headers)
        
        # Clips CSV headers
        clips_headers = [
            'clip_id', 'source_video_id', 'source_title', 'source_url',
            'start_time', 'end_time', 'duration', 'transcript', 'relevance_score',
            'title', 'description', 'captions', 'hashtags', 'thumbnail_suggestion',
            'file_path', 'published_channels', 'failed_channels', 'created_at',
            'channel_1_status', 'channel_1_video_id', 'channel_1_url', 'channel_1_name',
            'channel_2_status', 'channel_2_video_id', 'channel_2_url', 'channel_2_name',
            'channel_3_status', 'channel_3_video_id', 'channel_3_url', 'channel_3_name',
            'total_published', 'total_failed'
        ]
        
        if not self.clips_csv.exists():
            with open(self.clips_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(clips_headers)
    
    def log_video(self, video: ProcessedVideo):
        """Log processed video information"""
        with open(self.videos_csv, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                video.video_id, video.title, video.description, video.url,
                video.channel_title, video.published_at, video.transcript[:500] + "...",
                video.clips_extracted, video.clips_published, video.processing_status,
                video.processing_date, video.error_message
            ])
    
    def log_clip(self, clip: VideoClip, upload_results: Dict[str, Dict]):
        """Log clip information with upload results"""
        
        # Prepare channel-specific data
        channel_data = {}
        for i in range(1, 4):  # Support for 3 channels
            channel_key = f'channel_{i}'
            if channel_key in upload_results:
                result = upload_results[channel_key]
                channel_data[f'channel_{i}_status'] = result.get('status', 'not_attempted')
                channel_data[f'channel_{i}_video_id'] = result.get('video_id', '')
                channel_data[f'channel_{i}_url'] = result.get('url', '')
                channel_data[f'channel_{i}_name'] = result.get('channel_name', '')
            else:
                channel_data[f'channel_{i}_status'] = 'not_configured'
                channel_data[f'channel_{i}_video_id'] = ''
                channel_data[f'channel_{i}_url'] = ''
                channel_data[f'channel_{i}_name'] = ''
        
        total_published = sum(1 for result in upload_results.values() 
                            if result.get('status') == 'success')
        total_failed = sum(1 for result in upload_results.values() 
                         if result.get('status') == 'failed')
        
        with open(self.clips_csv, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                clip.clip_id, clip.source_video_id, clip.source_title, clip.source_url,
                clip.start_time, clip.end_time, clip.duration, clip.transcript[:200] + "...",
                clip.relevance_score, clip.title, clip.description,
                '; '.join(clip.captions), ', '.join(clip.hashtags), clip.thumbnail_suggestion,
                clip.file_path, ', '.join(clip.published_channels), ', '.join(clip.failed_channels),
                clip.created_at,
                channel_data['channel_1_status'], channel_data['channel_1_video_id'], channel_data['channel_1_url'], channel_data['channel_1_name'],
                channel_data['channel_2_status'], channel_data['channel_2_video_id'], channel_data['channel_2_url'], channel_data['channel_2_name'],
                channel_data['channel_3_status'], channel_data['channel_3_video_id'], channel_data['channel_3_url'], channel_data['channel_3_name'],
                total_published, total_failed
            ])

class MultiChannelYouTubeManager:
    """Handles YouTube API operations for multiple channels with enhanced support"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/youtube.readonly',
        'https://www.googleapis.com/auth/youtube.upload'
    ]
    
    def __init__(self, api_key: str, channel_configs: List[Dict]):
        self.api_key = api_key
        self.channel_configs = channel_configs
        self.youtube_read = build('youtube', 'v3', developerKey=api_key)
        self.youtube_services = {}
        self._authenticate_all_channels()
    
    def _authenticate_all_channels(self):
        """Authenticate for all configured channels"""
        logger.info(f"🔐 Authenticating {len(self.channel_configs)} channels...")
        
        for i, channel_config in enumerate(self.channel_configs):
            channel_key = f"channel_{i+1}"
            credentials_file = channel_config.get('credentials_file')
            channel_name = channel_config.get('name', f'Channel {i+1}')
            
            logger.info(f"\n--- Authenticating {channel_key}: {channel_name} ---")
            
            if not credentials_file:
                logger.error(f"❌ No credentials file specified for {channel_key}")
                continue
                
            if not os.path.exists(credentials_file):
                logger.error(f"❌ Credentials file not found for {channel_key}: {credentials_file}")
                logger.info(f"   Please ensure {credentials_file} exists in the current directory")
                continue
            
            try:
                service = self._authenticate_channel(credentials_file, channel_key)
                if service:
                    self.youtube_services[channel_key] = {
                        'service': service,
                        'config': channel_config
                    }
                    logger.info(f"✅ Successfully authenticated {channel_key}: {channel_name}")
                else:
                    logger.error(f"❌ Failed to authenticate {channel_key}: {channel_name}")
            except Exception as e:
                logger.error(f"❌ Authentication error for {channel_key}: {e}")
        
        authenticated_count = len(self.youtube_services)
        logger.info(f"\n🎯 Authentication Summary: {authenticated_count}/{len(self.channel_configs)} channels ready")
        
        if authenticated_count == 0:
            logger.error("❌ No channels authenticated! Please check credential files.")
        elif authenticated_count < len(self.channel_configs):
            logger.warning(f"⚠️  Only {authenticated_count} channels authenticated. Some uploads will fail.")
        else:
            logger.info("✅ All channels authenticated successfully!")
    
    def _authenticate_channel(self, credentials_file: str, channel_key: str):
        """Authenticate a single channel"""
        creds = None
        token_file = f'youtube_token_{channel_key}.json'
        
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info(f"   Refreshing expired token for {channel_key}")
                creds.refresh(Request())
            else:
                logger.info(f"   Starting OAuth flow for {channel_key}")
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_file, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(token_file, 'w') as token:
                token.write(creds.to_json())
            logger.info(f"   Saved token to {token_file}")
        
        return build('youtube', 'v3', credentials=creds)
    
    def search_videos(self, query: str, max_results: int = 50) -> List[Dict]:
        """Search for videos on YouTube"""
        try:
            search_response = self.youtube_read.search().list(
                q=query,
                part='id,snippet',
                maxResults=max_results,
                type='video',
                order='relevance'
            ).execute()
            
            videos = []
            for item in search_response['items']:
                video_data = {
                    'id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'channel_title': item['snippet']['channelTitle'],
                    'published_at': item['snippet']['publishedAt'],
                    'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}"
                }
                videos.append(video_data)
            
            logger.info(f"Found {len(videos)} videos for query: {query}")
            return videos
            
        except Exception as e:
            logger.error(f"Error searching videos: {e}")
            return []
    
    def debug_authentication(self):
        """Debug method to check authentication status"""
        logger.info(f"\n🔍 AUTHENTICATION DEBUG")
        logger.info(f"{'='*50}")
        
        logger.info(f"Total channel configs: {len(self.channel_configs)}")
        logger.info(f"Total authenticated services: {len(self.youtube_services)}")
        
        for i, channel_config in enumerate(self.channel_configs):
            channel_key = f"channel_{i+1}"
            logger.info(f"\nChannel {i+1}:")
            logger.info(f"  Config name: {channel_config.get('name', 'Unknown')}")
            logger.info(f"  Config ID: {channel_config.get('id', 'Unknown')}")
            logger.info(f"  Credentials file: {channel_config.get('credentials_file', 'Unknown')}")
            logger.info(f"  File exists: {os.path.exists(channel_config.get('credentials_file', ''))}")
            logger.info(f"  In youtube_services: {channel_key in self.youtube_services}")
            
            if channel_key in self.youtube_services:
                service_data = self.youtube_services[channel_key]
                logger.info(f"  Service available: {service_data.get('service') is not None}")
                logger.info(f"  Service type: {type(service_data.get('service'))}")
                
                # Try to get channel info
                try:
                    if service_data.get('service'):
                        channel_response = service_data['service'].channels().list(
                            part='snippet',
                            mine=True
                        ).execute()
                        
                        if channel_response['items']:
                            actual_channel_id = channel_response['items'][0]['id']
                            actual_channel_title = channel_response['items'][0]['snippet']['title']
                            logger.info(f"  Actual channel ID: {actual_channel_id}")
                            logger.info(f"  Actual channel title: {actual_channel_title}")
                            
                            expected_id = channel_config.get('id', '')
                            if actual_channel_id == expected_id:
                                logger.info(f"  ✅ Channel ID matches!")
                            else:
                                logger.error(f"  ❌ Channel ID mismatch!")
                                logger.error(f"     Expected: {expected_id}")
                                logger.error(f"     Actual: {actual_channel_id}")
                        else:
                            logger.error(f"  ❌ No channel found for this service")
                except Exception as e:
                    logger.error(f"  ❌ Error getting channel info: {e}")


    def upload_to_all_channels(self, file_path: str, title: str, description: str, 
                            tags: List[str], delay_between_uploads: int = 35) -> Dict[str, Dict]:
        """Upload video to all configured channels with ENHANCED DEBUGGING"""
        
        # =============================================================================
        # DEBUG SECTION 1: Check initial state
        # =============================================================================
        logger.info(f"\n🔍 DEBUG UPLOAD START")
        logger.info(f"🔍 Total channel configs: {len(self.channel_configs)}")
        logger.info(f"🔍 Total authenticated services: {len(self.youtube_services)}")
        logger.info(f"🔍 YouTube services keys: {list(self.youtube_services.keys())}")
        
        for key, data in self.youtube_services.items():
            logger.info(f"🔍 {key}: {data['config']['name']} (ID: {data['config']['id']})")
        
        # =============================================================================
        # DEBUG SECTION 2: Check each channel service
        # =============================================================================
        results = {}
        
        logger.info(f"\n🚀 STARTING MULTI-CHANNEL UPLOAD")
        logger.info(f"File: {os.path.basename(file_path)}")
        logger.info(f"Title: {title}")
        logger.info(f"Channels to upload: {len(self.youtube_services)}")
        logger.info(f"Delay between uploads: {delay_between_uploads} seconds")
        
        if not os.path.exists(file_path):
            logger.error(f"❌ Video file not found: {file_path}")
            return {}
        
        # =============================================================================
        # DEBUG SECTION 3: Channel loop with detailed logging
        # =============================================================================
        
        for channel_index, (channel_key, channel_data) in enumerate(self.youtube_services.items()):
            channel_config = channel_data['config']
            channel_name = channel_config['name']
            channel_id = channel_config.get('id', 'Unknown')
            
            logger.info(f"\n{'='*70}")
            logger.info(f"🔍 DEBUG: PROCESSING CHANNEL {channel_index + 1}/{len(self.youtube_services)}")
            logger.info(f"🔍 Channel Key: {channel_key}")
            logger.info(f"🔍 Channel Name: {channel_name}")
            logger.info(f"🔍 Channel ID: {channel_id}")
            logger.info(f"🔍 Service Object: {type(channel_data.get('service'))}")
            logger.info(f"🔍 Service Available: {channel_data.get('service') is not None}")
            
            # Check if this is actually a different channel
            if hasattr(channel_data.get('service'), '_http'):
                logger.info(f"🔍 Service HTTP object: {id(channel_data['service']._http)}")
            
            logger.info(f"{'='*70}")
            
            try:
                # Check if service is available
                if not channel_data.get('service'):
                    logger.error(f"❌ No authenticated service for {channel_key}")
                    results[channel_key] = {
                        'status': 'failed',
                        'error': 'No authenticated service',
                        'video_id': '',
                        'url': '',
                        'channel_name': channel_name
                    }
                    continue
                
                # =============================================================================
                # DEBUG SECTION 4: Test channel identity
                # =============================================================================
                
                # Get channel info to verify we're uploading to the right channel
                try:
                    logger.info(f"🔍 Testing channel identity for {channel_name}...")
                    
                    # Get the actual channel info from YouTube API
                    channel_response = channel_data['service'].channels().list(
                        part='snippet',
                        mine=True
                    ).execute()
                    
                    if channel_response['items']:
                        actual_channel_id = channel_response['items'][0]['id']
                        actual_channel_title = channel_response['items'][0]['snippet']['title']
                        
                        logger.info(f"🔍 ACTUAL YouTube Channel ID: {actual_channel_id}")
                        logger.info(f"🔍 ACTUAL YouTube Channel Title: {actual_channel_title}")
                        logger.info(f"🔍 EXPECTED Channel ID: {channel_id}")
                        logger.info(f"🔍 EXPECTED Channel Name: {channel_name}")
                        
                        if actual_channel_id != channel_id:
                            logger.error(f"❌ CHANNEL MISMATCH!")
                            logger.error(f"   Expected: {channel_id}")
                            logger.error(f"   Actual: {actual_channel_id}")
                            logger.error(f"   This service is authenticated for wrong channel!")
                            
                            results[channel_key] = {
                                'status': 'failed',
                                'error': f'Channel mismatch: expected {channel_id}, got {actual_channel_id}',
                                'video_id': '',
                                'url': '',
                                'channel_name': channel_name
                            }
                            continue
                        else:
                            logger.info(f"✅ Channel identity confirmed: {actual_channel_title}")
                    
                except Exception as e:
                    logger.error(f"❌ Could not verify channel identity: {e}")
                    # Continue with upload anyway
                
                # =============================================================================
                # DEBUG SECTION 5: Content customization
                # =============================================================================
                
                logger.info(f"🔍 Customizing content for {channel_name}...")
                
                # Customize content for this specific channel
                channel_title, channel_description, channel_tags = self._customize_content_for_channel(
                    title, description, tags, channel_config, channel_key
                )
                
                logger.info(f"🔍 Original title: {title}")
                logger.info(f"🔍 Customized title: {channel_title}")
                logger.info(f"🔍 Content focus: {channel_config.get('content_focus', 'general')}")
                logger.info(f"🔍 Tags prefix: {channel_config.get('tags_prefix', [])}")
                
                # =============================================================================
                # DEBUG SECTION 6: Upload attempt
                # =============================================================================
                
                logger.info(f"🔄 Starting upload to {channel_name}...")
                logger.info(f"   Customized title: {channel_title}")
                logger.info(f"   Channel focus: {channel_config.get('content_focus', 'general')}")
                
                result = self._upload_to_channel(
                    service=channel_data['service'],
                    file_path=file_path,
                    title=channel_title,
                    description=channel_description,
                    tags=channel_tags,
                    channel_config=channel_config,
                    channel_key=channel_key
                )
                
                # =============================================================================
                # DEBUG SECTION 7: Process result
                # =============================================================================
                
                logger.info(f"🔍 Upload result for {channel_name}: {result['status']}")
                
                if result['status'] == 'success':
                    video_url = f"https://www.youtube.com/watch?v={result['video_id']}"
                    result['url'] = video_url
                    result['channel_name'] = channel_name
                    result['channel_id'] = channel_config.get('id', '')
                    
                    logger.info(f"✅ SUCCESS: {channel_name}")
                    logger.info(f"   Video ID: {result['video_id']}")
                    logger.info(f"   URL: {video_url}")
                    logger.info(f"   Uploaded to channel ID: {channel_config.get('id', '')}")
                else:
                    result['channel_name'] = channel_name
                    result['channel_id'] = channel_config.get('id', '')
                    logger.error(f"❌ FAILED: {channel_name}")
                    logger.error(f"   Error: {result['error']}")
                
                results[channel_key] = result
                
            except Exception as e:
                logger.error(f"❌ EXCEPTION uploading to {channel_key}: {e}")
                results[channel_key] = {
                    'status': 'failed',
                    'error': f'Upload exception: {str(e)}',
                    'video_id': '',
                    'url': '',
                    'channel_name': channel_name,
                    'channel_id': channel_config.get('id', '')
                }
            
            # Wait between uploads (except for the last one)
            if channel_index < len(self.youtube_services) - 1:
                logger.info(f"⏱️  Waiting {delay_between_uploads} seconds before next upload...")
                time.sleep(delay_between_uploads)
        
        # =============================================================================
        # DEBUG SECTION 8: Final summary
        # =============================================================================
        
        successful_uploads = sum(1 for result in results.values() if result.get('status') == 'success')
        total_attempts = len(results)
        
        logger.info(f"\n{'='*70}")
        logger.info("🔍 DEBUG UPLOAD SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"Total channels attempted: {total_attempts}")
        logger.info(f"Successful uploads: {successful_uploads}")
        logger.info(f"Failed uploads: {total_attempts - successful_uploads}")
        
        # Log each result with channel details
        for channel_key, result in results.items():
            status = "✅ SUCCESS" if result['status'] == 'success' else "❌ FAILED"
            channel_name = result.get('channel_name', f'Channel {channel_key}')
            channel_id = result.get('channel_id', 'Unknown')
            
            logger.info(f"{channel_name} ({channel_id}): {status}")
            if result['status'] == 'success':
                logger.info(f"  Video URL: {result.get('url', 'Unknown')}")
            else:
                logger.info(f"  Error: {result.get('error', 'Unknown')}")
        
        return results



    def _customize_content_for_channel(self, title: str, description: str, tags: List[str], 
                                      channel_config: Dict, channel_key: str) -> Tuple[str, str, List[str]]:
        """Customize content based on channel-specific settings"""
        try:
            # Import channel-specific settings
            try:
                from config import CHANNEL_SPECIFIC_SETTINGS
                channel_settings = CHANNEL_SPECIFIC_SETTINGS.get(channel_key, {})
            except ImportError:
                channel_settings = {}
            
            content_focus = channel_config.get('content_focus', 'general')
            tags_prefix = channel_config.get('tags_prefix', [])
            
            # Customize title based on channel focus
            customized_title = title
            if content_focus == 'treatment_focused':
                if 'treatment' not in title.lower() and 'mih treatment' not in title.lower():
                    customized_title = f"MIH Treatment: {title}"
            elif content_focus == 'pediatric_care':
                if 'children' not in title.lower() and 'kids' not in title.lower():
                    customized_title = f"Children's Dental Care: {title}"
            
            # Ensure title doesn't exceed YouTube's limit
            customized_title = customized_title[:100]
            
            # Customize description
            customized_description = description
            if content_focus == 'treatment_focused':
                customized_description += "\n\n🔬 Focus: Advanced MIH treatment options and clinical approaches for dental professionals and informed parents."
            elif content_focus == 'pediatric_care':
                customized_description += "\n\n👨‍👩‍👧‍👦 Family-friendly guidance for children's dental health and enamel care from Dr. Linda Greenwall."
            elif content_focus == 'primary_education':
                customized_description += "\n\n📚 Educational content about Molar Incisor Hypomineralisation (MIH) from leading expert Dr. Linda Greenwall."
            
            # Add channel signature
            channel_name = channel_config.get('name', 'Unknown Channel')
            customized_description += f"\n\n📺 {channel_name} - Expert MIH content"
            
            # Ensure description doesn't exceed YouTube's limit
            customized_description = customized_description[:5000]
            
            # Customize tags - add channel-specific prefix tags
            customized_tags = tags.copy()
            for prefix_tag in tags_prefix:
                if prefix_tag not in customized_tags:
                    customized_tags.insert(0, prefix_tag)  # Add at beginning
            
            # Add channel-specific tags based on focus
            focus_tags = {
                'treatment_focused': ['#MIHTreatment', '#IconTreatment', '#DentalTreatment'],
                'pediatric_care': ['#PediatricDentistry', '#ChildrenTeeth', '#FamilyDental'],
                'primary_education': ['#MIHEducation', '#DentalEducation', '#DrGreenwall']
            }
            
            if content_focus in focus_tags:
                for focus_tag in focus_tags[content_focus]:
                    if focus_tag not in customized_tags:
                        customized_tags.append(focus_tag)
            
            # Limit to YouTube's tag limit
            customized_tags = customized_tags[:15]
            
            logger.info(f"   Content customized for: {content_focus}")
            logger.info(f"   Added prefix tags: {tags_prefix}")
            logger.info(f"   Final tag count: {len(customized_tags)}")
            
            return customized_title, customized_description, customized_tags
            
        except Exception as e:
            logger.warning(f"Error customizing content for {channel_key}: {e}")
            return title, description, tags
    
    def _upload_to_channel(self, service, file_path: str, title: str, description: str, 
                          tags: List[str], channel_config: Dict, channel_key: str) -> Dict:
        """Upload video to a specific channel with channel-specific configuration"""
        try:
            # Extract channel-specific settings
            channel_name = channel_config.get('name', 'Unknown Channel')
            category_id = channel_config.get('category_id', '27')
            privacy_status = channel_config.get('privacy_status', 'public')
            default_language = channel_config.get('default_language', 'en')
            
            logger.info(f"📤 Preparing upload for {channel_name}...")
            logger.info(f"   File size: {os.path.getsize(file_path) / 1024 / 1024:.1f} MB")
            logger.info(f"   Category: {category_id}")
            logger.info(f"   Privacy: {privacy_status}")
            logger.info(f"   Language: {default_language}")
            logger.info(f"   Tags: {len(tags)} tags")
            
            # Prepare upload body with channel-specific settings
            body = {
                'snippet': {
                    'title': title[:100],  # YouTube title limit
                    'description': description[:5000],  # YouTube description limit
                    'tags': tags[:15],  # YouTube tag limit
                    'categoryId': category_id,
                    'defaultLanguage': default_language,
                    'defaultAudioLanguage': default_language
                },
                'status': {
                    'privacyStatus': privacy_status,
                    'selfDeclaredMadeForKids': False,
                    'embeddable': True,
                    'publicStatsViewable': True
                }
            }
            
            # Create media upload with optimized settings
            media = MediaFileUpload(
                file_path, 
                chunksize=2*1024*1024,  # 2MB chunks for better performance
                resumable=True,
                mimetype='video/mp4'
            )
            
            logger.info(f"🚀 Starting upload request for {channel_name}...")
            
            # Create upload request 
            insert_request = service.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            # Execute upload with progress tracking and retries
            response = None
            retry_count = 0
            max_retries = 3
            
            while response is None and retry_count < max_retries:
                try:
                    logger.info(f"   Upload attempt {retry_count + 1}/{max_retries} for {channel_name}")
                    status, response = insert_request.next_chunk()
                    
                    if status:
                        progress = int(status.progress() * 100)
                        logger.info(f"   Upload progress: {progress}%")
                        
                except Exception as chunk_error:
                    retry_count += 1
                    if retry_count >= max_retries:
                        raise chunk_error
                    logger.warning(f"   Chunk upload error for {channel_name}, retrying... ({chunk_error})")
                    time.sleep(10)  # Longer wait between retries
            
            if response and 'id' in response:
                video_id = response['id']
                logger.info(f"✅ Upload completed successfully to {channel_name}")
                logger.info(f"   Video ID: {video_id}")
                logger.info(f"   Channel: {channel_name}")
                
                return {
                    'status': 'success',
                    'video_id': video_id,
                    'error': '',
                    'channel_name': channel_name,
                    'channel_key': channel_key,
                    'upload_settings': {
                        'category_id': category_id,
                        'privacy_status': privacy_status,
                        'language': default_language
                    }
                }
            else:
                error_msg = f"Upload failed to {channel_name} - no video ID returned"
                logger.error(f"❌ {error_msg}")
                return {
                    'status': 'failed',
                    'video_id': '',
                    'error': error_msg,
                    'channel_name': channel_name,
                    'channel_key': channel_key
                }
                
        except Exception as e:
            error_msg = f"Upload error to {channel_config.get('name', 'Unknown')}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                'status': 'failed',
                'video_id': '',
                'error': error_msg,
                'channel_name': channel_config.get('name', 'Unknown'),
                'channel_key': channel_key
            }

class AlternativeTranscriptProcessor:
    """Alternative transcript processor that avoids YouTube timedtext API"""
    
    def __init__(self):
        import tempfile
        self.temp_dir = Path(tempfile.gettempdir()) / "mih_transcripts"
        self.temp_dir.mkdir(exist_ok=True)
    
    def get_transcript_yt_dlp(self, video_id: str) -> List[Dict]:
        """Method 1: Use yt-dlp to get auto-generated subtitles (fastest)"""
        try:
            logger.info(f"Trying yt-dlp auto-subs for {video_id}")
            
            srt_file = self.temp_dir / f"{video_id}.en.srt"
            
            cmd = [
                'yt-dlp',
                '--write-auto-subs',
                '--sub-langs', 'en',
                '--sub-format', 'srt',
                '--skip-download',
                '-o', str(self.temp_dir / f"{video_id}.%(ext)s"),
                f'https://www.youtube.com/watch?v={video_id}'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0 and os.path.exists(srt_file):
                transcript = self._parse_srt_file(srt_file)
                os.remove(srt_file)
                logger.info(f"yt-dlp auto-subs successful: {len(transcript)} segments")
                return transcript
            else:
                logger.warning(f"yt-dlp auto-subs failed for {video_id}")
                return []
                
        except Exception as e:
            logger.error(f"yt-dlp method failed: {e}")
            return []
    
    def _parse_srt_file(self, srt_file: Path) -> List[Dict]:
        """Parse SRT subtitle file"""
        transcript = []
        
        try:
            with open(srt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            blocks = content.strip().split('\n\n')
            
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    timestamp_line = lines[1]
                    if ' --> ' in timestamp_line:
                        start_str, end_str = timestamp_line.split(' --> ')
                        
                        start_seconds = self._parse_timestamp(start_str)
                        end_seconds = self._parse_timestamp(end_str)
                        
                        text = ' '.join(lines[2:])
                        import re
                        text = re.sub(r'<[^>]+>', '', text)
                        
                        if text.strip():
                            transcript.append({
                                'text': text.strip(),
                                'start': start_seconds,
                                'duration': end_seconds - start_seconds
                            })
            
            return transcript
            
        except Exception as e:
            logger.error(f"Error parsing SRT: {e}")
            return []
    
    def _parse_timestamp(self, timestamp_str: str) -> float:
        """Parse SRT timestamp to seconds"""
        time_part, ms_part = timestamp_str.split(',')
        h, m, s = map(int, time_part.split(':'))
        ms = int(ms_part)
        return h * 3600 + m * 60 + s + ms / 1000.0

class TranscriptProcessor:
    """Enhanced transcript processor with multiple methods"""
    
    def __init__(self):
        self.alternative_processor = AlternativeTranscriptProcessor()
    
    def get_transcript(self, video_id: str) -> List[Dict]:
        """Get transcript using yt-dlp method"""
        logger.info(f"Getting transcript for {video_id}")
        transcript = self.alternative_processor.get_transcript_yt_dlp(video_id)
        
        if transcript and len(transcript) > 0:
            logger.info(f"✅ Transcript obtained with {len(transcript)} segments")
            return transcript
        else:
            logger.error(f"❌ Failed to get transcript for {video_id}")
            return []
    
    @staticmethod
    def find_mih_segments(transcript: List[Dict], min_duration: int = 15, 
                         max_duration: int = 60) -> List[Tuple[float, float, str, float]]:
        """Find MIH-related segments in transcript"""
        from config import MIH_KEYWORDS
        
        segments = []
        
        for i in range(len(transcript)):
            for duration in range(min_duration, max_duration + 1, 5):
                start_idx = i
                end_time = transcript[i]['start'] + duration
                
                # Find end index
                end_idx = start_idx
                while (end_idx < len(transcript) - 1 and 
                       transcript[end_idx + 1]['start'] <= end_time):
                    end_idx += 1
                
                if end_idx <= start_idx:
                    continue
                
                # Extract text for this segment
                segment_text = ' '.join([
                    item['text'] for item in transcript[start_idx:end_idx + 1]
                ]).lower()
                
                # Calculate relevance score
                keyword_count = sum(1 for keyword in MIH_KEYWORDS 
                                  if keyword in segment_text)
                relevance_score = keyword_count / len(MIH_KEYWORDS)
                
                if relevance_score > 0.1:  # At least 10% keyword match
                    segments.append((
                        transcript[start_idx]['start'],
                        transcript[end_idx]['start'] + transcript[end_idx]['duration'],
                        segment_text,
                        relevance_score
                    ))
        
        # Sort by relevance score and remove duplicates
        segments = sorted(set(segments), key=lambda x: x[3], reverse=True)
        return segments[:5]  # Return top 5 segments

class VideoProcessor:
    """Handles video downloading and processing"""
    
    def __init__(self, output_dir: str = "processed_videos"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def download_video(self, video_id: str) -> str:
        """Download video using yt-dlp with better error handling"""
        output_path = self.output_dir / f"{video_id}.%(ext)s"
        
        try:
            cmd = [
                'yt-dlp',
                '-f', 'best[height<=720]/best',  # Fallback format
                '--no-playlist',
                '-o', str(output_path),
                f'https://www.youtube.com/watch?v={video_id}'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                # Find the actual downloaded file
                for file in self.output_dir.glob(f"{video_id}.*"):
                    if file.suffix in ['.mp4', '.webm', '.mkv', '.avi']:
                        logger.info(f"Successfully downloaded: {file}")
                        return str(file)
            
            logger.error(f"Failed to download video {video_id}: {result.stderr}")
            return ""
            
        except subprocess.TimeoutExpired:
            logger.error(f"Download timeout for video {video_id}")
            return ""
        except Exception as e:
            logger.error(f"Error downloading video {video_id}: {e}")
            return ""
    
    def extract_clip(self, input_file: str, start_time: float, end_time: float, 
                    output_file: str) -> bool:
        """Extract clip from video and convert to 9:16 aspect ratio"""
        try:
            from config import TARGET_RESOLUTION, VIDEO_CODEC, AUDIO_CODEC
            
            duration = end_time - start_time
            if duration < 10 or duration > 65:
                logger.warning(f"Invalid clip duration: {duration}s")
                return False
            
            # FFmpeg command for 9:16 aspect ratio
            cmd = [
                'ffmpeg',
                '-i', input_file,
                '-ss', str(start_time),
                '-t', str(duration),
                '-vf', f'scale={TARGET_RESOLUTION[0]}:{TARGET_RESOLUTION[1]}:force_original_aspect_ratio=decrease,pad={TARGET_RESOLUTION[0]}:{TARGET_RESOLUTION[1]}:(ow-iw)/2:(oh-ih)/2:black',
                '-c:v', VIDEO_CODEC,
                '-c:a', AUDIO_CODEC,
                '-y',  # Overwrite output file
                output_file
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                logger.info(f"Successfully extracted clip: {output_file}")
                return True
            else:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False
            
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timeout - clip too long")
            return False
        except Exception as e:
            logger.error(f"Error extracting clip: {e}")
            return False

class GeminiContentGenerator:
    """Generates content using Google's Gemini AI"""
    
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-001')
    
    def analyze_transcript_for_clips(self, transcript: str, video_metadata: Dict) -> List[Dict]:
        """Use Gemini to identify the best clips from transcript"""
        from config import MAX_CLIPS_PER_VIDEO
        
        prompt = f"""
Analyze this video transcript and identify the best 15-60 second clips that would be most valuable for parents of children with Molar Incisor Hypomineralisation (MIH).

Video Title: {video_metadata.get('title', '')}
Video Description: {video_metadata.get('description', '')}

Transcript: {transcript[:3000]}

Find clips that focus on:
- MIH causes and identification
- Treatment options (especially ICON treatment)
- Pediatric-safe whitening
- Enamel care tips
- Parent guidance and reassurance

For each clip, provide:
1. Start timestamp (in seconds)
2. End timestamp (in seconds) 
3. Reason why this clip is valuable
4. Key topics covered
5. Emotional tone (educational/reassuring/informative)

Return as JSON array with max {MAX_CLIPS_PER_VIDEO} clips. Example format:
[
  {{
    "start_timestamp": 45,
    "end_timestamp": 90,
    "reason": "Explains MIH causes clearly",
    "topics": ["MIH causes", "parent education"],
    "tone": "educational"
  }}
]

IMPORTANT: Return ONLY valid JSON, no markdown formatting, no extra text.
"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # Try to parse JSON
            clips_data = json.loads(response_text)
            logger.info(f"Gemini identified {len(clips_data)} clips")
            return clips_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error from Gemini: {e}")
            return []
        except Exception as e:
            logger.error(f"Error analyzing transcript with Gemini: {e}")
            return []
    
    def generate_content_for_clip(self, transcript: str, video_metadata: Dict, 
                                 clip_duration: float) -> Dict:
        """Generate social media content for a clip"""
        prompt = f"""
        Create engaging social media content for a {clip_duration}-second video clip featuring Dr. Linda Greenwall discussing MIH (Molar Incisor Hypomineralisation).

        Clip transcript: {transcript[:1000]}
        Source video: {video_metadata.get('title', '')}
        Target audience: Parents of children with MIH, empathetic and educational tone

        Generate:
        1. Title (max 100 characters, engaging and informative)
        2. Description (max 300 characters, include key takeaways)
        3. 3 different captions (max 100 characters each, varied styles)
        4. 10 relevant hashtags (include #MIH #EnamelCare #PediatricDentistry)
        5. Thumbnail suggestion (describe ideal visual)

        Ensure MIH-related terms appear in tags. Be empathetic to parent concerns.
        
        Return as JSON with keys: title, description, captions, hashtags, thumbnail_suggestion

        Example format:
        {{
          "title": "Dr Greenwall Explains MIH Treatment",
          "description": "Expert advice on managing Molar Incisor Hypomineralisation in children",
          "captions": ["MIH expert tips", "Enamel care guidance", "Pediatric dentistry"],
          "hashtags": ["#MIH", "#EnamelCare", "#PediatricDentistry"],
          "thumbnail_suggestion": "Dr Greenwall explaining treatment"
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean up response
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            content_data = json.loads(response_text)
            
            # Validate and ensure MIH terms are present
            hashtags = content_data.get('hashtags', [])
            required_tags = ['#MIH', '#EnamelCare', '#PediatricDentistry']
            
            for tag in required_tags:
                if tag not in hashtags:
                    hashtags.append(tag)
            
            content_data['hashtags'] = hashtags[:10]  # Limit to 10 hashtags
            
            return content_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in content generation: {e}")
            return self._create_fallback_content()
        except Exception as e:
            logger.error(f"Error generating content with Gemini: {e}")
            return self._create_fallback_content()
    
    def _create_fallback_content(self) -> Dict:
        """Create fallback content when Gemini fails"""
        return {
            'title': "Dr Greenwall on MIH Treatment",
            'description': "Expert guidance on Molar Incisor Hypomineralisation from Dr Linda Greenwall",
            'captions': ["MIH expert advice", "Enamel care tips", "Pediatric dentistry guidance"],
            'hashtags': ["#MIH", "#EnamelCare", "#PediatricDentistry", "#DrGreenwall", "#TeethWhitening"],
            'thumbnail_suggestion': "Dr Greenwall explaining MIH treatment"
        }

class MIHContentAutomation:
    """Main automation system with multi-channel support and CSV logging"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.youtube_manager = MultiChannelYouTubeManager(
            config['youtube_api_key'], 
            config['upload_channels']
        )
        self.transcript_processor = TranscriptProcessor()
        self.video_processor = VideoProcessor(config.get('output_dir', 'processed_videos'))
        self.content_generator = GeminiContentGenerator(config['gemini_api_key'])
        self.csv_logger = CSVLogger()
        self.processed_videos = set()
        self._load_processed_videos()
    
    def _load_processed_videos(self):
        """Load list of previously processed videos"""
        processed_file = 'processed_videos.json'
        if os.path.exists(processed_file):
            with open(processed_file, 'r') as f:
                self.processed_videos = set(json.load(f))
    
    def _save_processed_videos(self):
        """Save list of processed videos"""
        with open('processed_videos.json', 'w') as f:
            json.dump(list(self.processed_videos), f)
    
    def search_greenwall_videos(self) -> List[Dict]:
        """Search for Dr. Greenwall videos"""
        from config import SEARCH_QUERIES
        
        all_videos = []
        seen_ids = set()
        
        for query in SEARCH_QUERIES:
            videos = self.youtube_manager.search_videos(query, max_results=20)
            for video in videos:
                if (video['id'] not in seen_ids and 
                    video['id'] not in self.processed_videos):
                    all_videos.append(video)
                    seen_ids.add(video['id'])
            
            time.sleep(1)  # Rate limiting
        
        logger.info(f"Found {len(all_videos)} new videos to process")
        return all_videos
    
    def process_video(self, video_data: Dict) -> List[VideoClip]:
        """Process a single video and extract clips"""
        video_id = video_data['id']
        logger.info(f"Processing video: {video_id} - {video_data['title']}")
        
        # Initialize processed video record
        processed_video = ProcessedVideo(
            video_id=video_id,
            title=video_data['title'],
            description=video_data['description'],
            url=video_data['url'],
            channel_title=video_data['channel_title'],
            published_at=video_data['published_at'],
            transcript="",
            clips_extracted=0,
            clips_published=0,
            processing_status="processing",
            processing_date=datetime.now().isoformat()
        )
        
        try:
            # Get transcript
            transcript = self.transcript_processor.get_transcript(video_id)
            if not transcript:
                processed_video.processing_status = "failed"
                processed_video.error_message = "No transcript available"
                self.csv_logger.log_video(processed_video)
                logger.warning(f"No transcript available for {video_id}")
                return []
            
            # Store full transcript
            full_transcript = ' '.join([item['text'] for item in transcript])
            processed_video.transcript = full_transcript
            
            # Use Gemini to identify best clips
            clip_suggestions = self.content_generator.analyze_transcript_for_clips(
                full_transcript, video_data
            )
            
            if not clip_suggestions:
                # Fallback to keyword-based detection
                segments = self.transcript_processor.find_mih_segments(transcript)
                clip_suggestions = [
                    {
                        'start_timestamp': seg[0],
                        'end_timestamp': seg[1],
                        'reason': 'Contains MIH-related keywords',
                        'topics': ['MIH'],
                        'tone': 'educational'
                    }
                    for seg in segments[:3]
                ]
            
            if not clip_suggestions:
                processed_video.processing_status = "completed"
                processed_video.error_message = "No suitable clips found"
                self.csv_logger.log_video(processed_video)
                logger.info(f"No suitable clips found in {video_id}")
                return []
            
            # Download source video
            video_file = self.video_processor.download_video(video_id)
            if not video_file:
                processed_video.processing_status = "failed"
                processed_video.error_message = "Failed to download video"
                self.csv_logger.log_video(processed_video)
                logger.error(f"Failed to download video {video_id}")
                return []
            
            clips = []
            for i, clip_data in enumerate(clip_suggestions):
                try:
                    start_time = float(clip_data['start_timestamp'])
                    end_time = float(clip_data['end_timestamp'])
                    
                    # Validate clip duration
                    duration = end_time - start_time
                    if duration < 15 or duration > 60:
                        logger.warning(f"Skipping clip {i} - invalid duration: {duration}s")
                        continue
                    
                    # Extract transcript for this clip
                    clip_transcript = self._get_clip_transcript(transcript, start_time, end_time)
                    
                    # Generate content for this clip
                    content_data = self.content_generator.generate_content_for_clip(
                        clip_transcript, video_data, duration
                    )
                    
                    # Create clip object
                    clip = VideoClip(
                        clip_id=str(uuid.uuid4()),
                        start_time=start_time,
                        end_time=end_time,
                        transcript=clip_transcript,
                        relevance_score=0.8,  # High score from Gemini analysis
                        source_video_id=video_id,
                        source_title=video_data['title'],
                        source_url=video_data['url'],
                        title=content_data.get('title', 'Dr Greenwall MIH Content'),
                        description=content_data.get('description', 'MIH educational content'),
                        captions=content_data.get('captions', ['MIH education']),
                        hashtags=content_data.get('hashtags', ['#MIH']),
                        thumbnail_suggestion=content_data.get('thumbnail_suggestion', 'MIH content'),
                        duration=duration
                    )
                    
                    # Extract the actual video clip
                    output_file = f"clip_{video_id}_{i}_{int(start_time)}.mp4"
                    output_path = self.video_processor.output_dir / output_file
                    
                    if self.video_processor.extract_clip(
                        video_file, start_time, end_time, str(output_path)
                    ):
                        clip.file_path = str(output_path)
                        clips.append(clip)
                        logger.info(f"Successfully created clip {i}: {duration:.1f}s")
                    else:
                        logger.error(f"Failed to extract clip {i}")
                        
                except (ValueError, KeyError) as e:
                    logger.error(f"Invalid clip data for clip {i}: {e}")
                    continue
            
            # Clean up source video
            try:
                os.remove(video_file)
            except:
                pass
            
            # Update processed video record
            processed_video.clips_extracted = len(clips)
            processed_video.processing_status = "completed" if clips else "no_clips"
            
            logger.info(f"Created {len(clips)} clips from video {video_id}")
            return clips
            
        except Exception as e:
            processed_video.processing_status = "failed"
            processed_video.error_message = str(e)
            self.csv_logger.log_video(processed_video)
            logger.error(f"Error processing video {video_id}: {e}")
            return []
        finally:
            # Always log the video processing result
            self.csv_logger.log_video(processed_video)
    
    def _get_clip_transcript(self, transcript: List[Dict], start_time: float, 
                           end_time: float) -> str:
        """Extract transcript text for a specific time range"""
        clip_text = []
        for item in transcript:
            item_start = item['start']
            item_end = item_start + item['duration']
            
            if item_end >= start_time and item_start <= end_time:
                clip_text.append(item['text'])
        
        return ' '.join(clip_text)
    
    def publish_clips(self, clips: List[VideoClip]):
        """Generate content and publish clips to all YouTube channels with proper timing"""
        if not clips:
            logger.info("No clips to publish")
            return
        
        # Get timing configuration from config
        try:
            from config import DELAY_BETWEEN_CLIPS
            wait_time_between_clips = DELAY_BETWEEN_CLIPS
        except ImportError:
            wait_time_between_clips = 45  # Default fallback
        
        logger.info(f"Publishing {len(clips)} clips to all channels with timing delays...")
        
        for clip_index, clip in enumerate(clips):
            if not clip.file_path or not os.path.exists(clip.file_path):
                logger.warning(f"Clip file not found: {clip.file_path}")
                continue
            
            logger.info(f"\n{'='*60}")
            logger.info(f"PUBLISHING CLIP {clip_index + 1}/{len(clips)}")
            logger.info(f"Clip ID: {clip.clip_id}")
            logger.info(f"Title: {clip.title}")
            logger.info(f"Duration: {clip.duration:.1f}s")
            logger.info(f"{'='*60}")
            
            try:
                # Upload to all configured channels
                upload_results = self.youtube_manager.upload_to_all_channels(
                    file_path=clip.file_path,
                    title=clip.title,
                    description=clip.description,
                    tags=clip.hashtags
                )
                
                # Process upload results
                for channel_key, result in upload_results.items():
                    if result['status'] == 'success':
                        clip.published_channels.append(channel_key)
                        logger.info(f"✅ Published to {channel_key}: {result['url']}")
                    else:
                        clip.failed_channels.append(channel_key)
                        logger.error(f"❌ Failed to publish to {channel_key}: {result['error']}")
                
                # Log clip with upload results
                self.csv_logger.log_clip(clip, upload_results)
                
                successful_uploads = len(clip.published_channels)
                failed_uploads = len(clip.failed_channels)
                
                logger.info(f"Clip {clip_index + 1} summary:")
                logger.info(f"  Successful uploads: {successful_uploads}")
                logger.info(f"  Failed uploads: {failed_uploads}")
                if (successful_uploads + failed_uploads) > 0:
                    logger.info(f"  Success rate: {successful_uploads/(successful_uploads+failed_uploads)*100:.1f}%")
                
            except Exception as e:
                logger.error(f"Error processing clip {clip_index + 1}: {e}")
                # Log failed clip
                failed_results = {f'channel_{i+1}': {'status': 'failed', 'error': str(e), 'video_id': '', 'url': '', 'channel_name': f'Channel {i+1}'} 
                                for i in range(len(self.youtube_manager.channel_configs))}
                self.csv_logger.log_clip(clip, failed_results)
            
            finally:
                # Clean up clip file
                try:
                    if os.path.exists(clip.file_path):
                        os.remove(clip.file_path)
                        logger.info(f"Cleaned up clip file: {os.path.basename(clip.file_path)}")
                except Exception as e:
                    logger.warning(f"Could not clean up clip file: {e}")
            
            # Wait between clip uploads
            if clip_index < len(clips) - 1:
                logger.info(f"⏱️  Waiting {wait_time_between_clips} seconds before publishing next clip...")
                time.sleep(wait_time_between_clips)
        
        logger.info(f"\n{'='*60}")
        logger.info("CLIP PUBLISHING SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Total clips processed: {len(clips)}")
        
        total_successful = sum(len(clip.published_channels) for clip in clips)
        total_attempts = sum(len(clip.published_channels) + len(clip.failed_channels) for clip in clips)
        
        logger.info(f"Total successful uploads: {total_successful}")
        logger.info(f"Total upload attempts: {total_attempts}")
        if total_attempts > 0:
            logger.info(f"Overall success rate: {total_successful/total_attempts*100:.1f}%")
        
        logger.info("All clips published!")
    
    def run_automation_cycle(self):
        """Run one complete automation cycle"""
        logger.info("Starting MIH content automation cycle")
        
        # Search for new videos
        videos = self.search_greenwall_videos()
        
        if not videos:
            logger.info("No new videos found")
            return
        
        total_clips = 0
        processed_count = 0
        
        # Get configuration values
        try:
            from config import MAX_VIDEOS_PER_CYCLE, DELAY_BETWEEN_VIDEOS
            max_videos_per_cycle = MAX_VIDEOS_PER_CYCLE
            wait_time_between_videos = DELAY_BETWEEN_VIDEOS
        except ImportError:
            max_videos_per_cycle = 3
            wait_time_between_videos = 120
        
        logger.info(f"Found {len(videos)} videos. Processing {min(len(videos), max_videos_per_cycle)} videos this cycle")
        
        for video_index, video_data in enumerate(videos[:max_videos_per_cycle]):
            logger.info(f"\n{'='*80}")
            logger.info(f"PROCESSING VIDEO {video_index + 1}/{min(len(videos), max_videos_per_cycle)}")
            logger.info(f"Video: {video_data['title']}")
            logger.info(f"Video ID: {video_data['id']}")
            logger.info(f"Video URL: {video_data['url']}")
            logger.info(f"{'='*80}")
            
            try:
                # Step 1: Process video and extract all clips
                logger.info("Step 1: Extracting clips from video...")
                clips = self.process_video(video_data)
                
                if not clips:
                    logger.info("No clips extracted from this video, moving to next video")
                    self.processed_videos.add(video_data['id'])
                    processed_count += 1
                    continue
                
                logger.info(f"Successfully extracted {len(clips)} clips from video")
                
                # Step 2: Publish all clips from this video sequentially
                logger.info(f"Step 2: Publishing {len(clips)} clips to all channels...")
                self.publish_clips(clips)
                
                total_clips += len(clips)
                
                # Mark video as processed
                self.processed_videos.add(video_data['id'])
                processed_count += 1
                
                logger.info(f"✅ Completed processing video {video_index + 1}")
                logger.info(f"Total clips published so far: {total_clips}")
                
                # Step 3: Wait before processing next video (except for the last video)
                if video_index < min(len(videos), max_videos_per_cycle) - 1:
                    logger.info(f"⏱️  Waiting {wait_time_between_videos} seconds before processing next video...")
                    time.sleep(wait_time_between_videos)
                
            except KeyboardInterrupt:
                logger.info("Automation stopped by user")
                break
            except Exception as e:
                logger.error(f"Error processing video {video_data['id']}: {e}")
                logger.info("Continuing with next video...")
                # Still mark as processed to avoid reprocessing failed videos
                self.processed_videos.add(video_data['id'])
                processed_count += 1
                continue
        
        # Save processed videos list
        self._save_processed_videos()
        
        logger.info(f"\n{'='*80}")
        logger.info("AUTOMATION CYCLE SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Videos processed: {processed_count}")
        logger.info(f"Total clips published: {total_clips}")
        logger.info(f"Average clips per video: {total_clips/max(processed_count, 1):.1f}")
        
        if len(videos) > max_videos_per_cycle:
            remaining = len(videos) - max_videos_per_cycle
            logger.info(f"Videos remaining for next cycle: {remaining}")
            logger.info("Run the automation again to process remaining videos")
        
        logger.info("Check the 'logs' folder for detailed CSV reports:")
        logger.info("  - processed_videos.csv: Video processing details")
        logger.info("  - published_clips.csv: Clip publishing details")
        
        logger.info("Automation cycle complete!")
    
    def run_single_video_test(self, video_id: str):
        """Test processing a single specific video"""
        logger.info(f"Testing single video: {video_id}")
        
        # Get video details
        video_details = self.youtube_manager.youtube_read.videos().list(
            part='snippet,contentDetails,statistics',
            id=video_id
        ).execute()
        
        if not video_details['items']:
            logger.error(f"Could not get details for video {video_id}")
            return
        
        video_item = video_details['items'][0]
        video_data = {
            'id': video_id,
            'title': video_item['snippet']['title'],
            'description': video_item['snippet']['description'],
            'channel_title': video_item['snippet']['channelTitle'],
            'published_at': video_item['snippet']['publishedAt'],
            'url': f"https://www.youtube.com/watch?v={video_id}"
        }
        
        logger.info(f"Processing: {video_data['title']}")
        
        # Process the video
        clips = self.process_video(video_data)
        
        if clips:
            logger.info(f"Found {len(clips)} clips. Publishing...")
            self.publish_clips(clips)
            logger.info("Single video test completed successfully!")
        else:
            logger.info("No clips found in this video")
    
    def run_continuous(self, interval_hours: int = 1):
        """Run automation continuously"""
        try:
            from config import AUTOMATION_INTERVAL_HOURS
            interval = interval_hours or AUTOMATION_INTERVAL_HOURS
        except ImportError:
            interval = interval_hours
            
        logger.info(f"Starting continuous automation (every {interval} hours)")
        
        while True:
            try:
                self.run_automation_cycle()
                logger.info(f"Sleeping for {interval} hours...")
                time.sleep(interval * 3600)
                
            except KeyboardInterrupt:
                logger.info("Automation stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in automation cycle: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying
    
    def generate_report(self):
        """Generate a summary report from CSV logs"""
        try:
            # Read CSV files
            videos_df = []
            clips_df = []
            
            if self.csv_logger.videos_csv.exists():
                with open(self.csv_logger.videos_csv, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    videos_df = list(reader)
            
            if self.csv_logger.clips_csv.exists():
                with open(self.csv_logger.clips_csv, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    clips_df = list(reader)
            
            # Generate summary
            logger.info("\n" + "="*60)
            logger.info("MIH AUTOMATION SUMMARY REPORT")
            logger.info("="*60)
            
            logger.info(f"Total videos processed: {len(videos_df)}")
            if videos_df:
                successful_videos = sum(1 for v in videos_df if v['processing_status'] == 'completed')
                logger.info(f"Successfully processed: {successful_videos}")
                logger.info(f"Success rate: {successful_videos/len(videos_df)*100:.1f}%")
            
            logger.info(f"\nTotal clips generated: {len(clips_df)}")
            if clips_df:
                total_published = sum(int(c['total_published']) for c in clips_df if c['total_published'].isdigit())
                total_failed = sum(int(c['total_failed']) for c in clips_df if c['total_failed'].isdigit())
                
                logger.info(f"Successfully published: {total_published}")
                logger.info(f"Failed uploads: {total_failed}")
                if (total_published + total_failed) > 0:
                    logger.info(f"Upload success rate: {total_published/(total_published+total_failed)*100:.1f}%")
            
            # Channel-specific breakdown
            if clips_df:
                logger.info(f"\nChannel-specific breakdown:")
                for i in range(1, 4):
                    channel_successes = sum(1 for c in clips_df if c.get(f'channel_{i}_status') == 'success')
                    channel_failures = sum(1 for c in clips_df if c.get(f'channel_{i}_status') == 'failed')
                    channel_name = clips_df[0].get(f'channel_{i}_name', f'Channel {i}') if clips_df else f'Channel {i}'
                    
                    if channel_successes + channel_failures > 0:
                        success_rate = channel_successes / (channel_successes + channel_failures) * 100
                        logger.info(f"  {channel_name}: {channel_successes} success, {channel_failures} failed ({success_rate:.1f}%)")
                    else:
                        logger.info(f"  {channel_name}: No upload attempts")
            
            logger.info(f"\nLog files location:")
            logger.info(f"  Videos: {self.csv_logger.videos_csv}")
            logger.info(f"  Clips: {self.csv_logger.clips_csv}")
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")

def check_tool_availability(tool_name):
    """Check if a command-line tool is available (cross-platform)"""
    try:
        result = subprocess.run([tool_name, '--version'], 
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
        try:
            result = subprocess.run([tool_name, '--help'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except:
            return False

def main():
    """Main function to run the automation"""
    
    # Try to import config
    try:
        import config
        automation_config = {
            'youtube_api_key': config.YOUTUBE_API_KEY,
            'upload_channels': config.UPLOAD_CHANNELS,
            'gemini_api_key': config.GEMINI_API_KEY,
            'output_dir': config.OUTPUT_DIR
        }
        automation = MIHContentAutomation(automation_config)
        automation.youtube_manager.debug_authentication()
        # Print configuration summary
        logger.info("📋 Configuration loaded:")
        logger.info(f"   Channels configured: {len(automation_config['upload_channels'])}")
        for i, channel in enumerate(automation_config['upload_channels'], 1):
            logger.info(f"   Channel {i}: {channel.get('name', 'Unknown')}")
            
    except ImportError:
        logger.error("Config file not found. Please create config.py first")
        logger.info("See the example config.py structure in the comments")
        return
    except AttributeError as e:
        logger.error(f"Missing configuration in config.py: {e}")
        return
    
    # Validate API keys
    if not automation_config['youtube_api_key'] or automation_config['youtube_api_key'] == 'YOUR_YOUTUBE_API_KEY':
        logger.error("YouTube API key not configured. Please update config.py")
        return
    
    if not automation_config['gemini_api_key'] or automation_config['gemini_api_key'] == 'YOUR_GEMINI_API_KEY':
        logger.error("Gemini API key not configured. Please update config.py")
        return
    
    # Validate channel configurations
    if not automation_config['upload_channels']:
        logger.error("No upload channels configured. Please update config.py")
        return
    
    # Check for credential files
    missing_credentials = []
    for i, channel in enumerate(automation_config['upload_channels']):
        credentials_file = channel.get('credentials_file')
        if not credentials_file:
            missing_credentials.append(f"Channel {i+1}: No credentials file specified")
        elif not os.path.exists(credentials_file):
            missing_credentials.append(f"Channel {i+1}: {credentials_file} not found")
    
    if missing_credentials:
        logger.error("❌ Missing credential files:")
        for missing in missing_credentials:
            logger.error(f"   {missing}")
        logger.info("Please ensure all OAuth credential files are in the current directory")
        return
    
    # Validate required dependencies
    required_tools = ['yt-dlp']
    missing_tools = []
    
    for tool in required_tools:
        if not check_tool_availability(tool):
            missing_tools.append(tool)
    
    if missing_tools:
        logger.error(f"Required tools not found: {', '.join(missing_tools)}")
        logger.info("Installation instructions:")
        for tool in missing_tools:
            if tool == 'yt-dlp':
                logger.info(f"  {tool}: pip install yt-dlp")
            elif tool == 'ffmpeg':
                logger.info(f"  {tool}: Download from https://ffmpeg.org/ and add to PATH")
        return
    
    logger.info("✅ All dependencies found")
    logger.info(f"✅ All credential files found")
    logger.info(f"✅ Configured for {len(automation_config['upload_channels'])} channels")
    
    # Initialize and run automation
    try:
        logger.info("🚀 Initializing MIH Content Automation...")
        automation = MIHContentAutomation(automation_config)
        
        # Parse command line arguments
        import sys
        if len(sys.argv) > 1:
            if sys.argv[1] == '--continuous':
                automation.run_continuous(interval_hours=1)
            elif sys.argv[1] == '--test' and len(sys.argv) > 2:
                automation.run_single_video_test(sys.argv[2])
            elif sys.argv[1] == '--report':
                automation.generate_report()
            else:
                logger.info("Usage:")
                logger.info("  python automation.py                 # Run single cycle")
                logger.info("  python automation.py --continuous    # Run continuously")
                logger.info("  python automation.py --test VIDEO_ID # Test single video")
                logger.info("  python automation.py --report        # Generate summary report")
        else:
            automation.run_automation_cycle()
            
    except Exception as e:
        logger.error(f"Error running automation: {e}")
        logger.info("Make sure you have:")
        logger.info("1. Valid API keys in config.py")
        logger.info("2. Credentials files for all channels")
        logger.info("3. All required tools installed")
        logger.info("4. Proper internet connection")

if __name__ == "__main__":
    main()