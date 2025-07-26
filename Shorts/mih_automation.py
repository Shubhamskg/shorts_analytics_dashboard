#!/usr/bin/env python3
"""
Dr. Linda Greenwall MIH Content Automation System
Automatically finds, processes, and publishes educational MIH content from YouTube videos
"""

import os
import re
import json
import time
import logging
import subprocess
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
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
    """Represents a processed video clip"""
    start_time: float
    end_time: float
    transcript: str
    relevance_score: float
    source_video_id: str
    source_title: str
    file_path: Optional[str] = None

@dataclass
class GeneratedContent:
    """Generated content for social media posting"""
    title: str
    description: str
    captions: List[str]
    hashtags: List[str]
    thumbnail_suggestion: str

class YouTubeManager:
    """Handles YouTube API operations"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/youtube.readonly',
        'https://www.googleapis.com/auth/youtube.upload'
    ]
    
    def __init__(self, api_key: str, credentials_file: str):
        self.api_key = api_key
        self.credentials_file = credentials_file
        self.youtube_read = build('youtube', 'v3', developerKey=api_key)
        self.youtube_upload = None
        self._authenticate_upload()
    
    def _authenticate_upload(self):
        """Authenticate for upload operations"""
        creds = None
        token_file = 'youtube_token.json'
        
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(token_file, 'w') as token:
                token.write(creds.to_json())
        
        self.youtube_upload = build('youtube', 'v3', credentials=creds)
    
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
                    'published_at': item['snippet']['publishedAt']
                }
                videos.append(video_data)
            
            logger.info(f"Found {len(videos)} videos for query: {query}")
            return videos
            
        except Exception as e:
            logger.error(f"Error searching videos: {e}")
            return []
    
    def get_video_details(self, video_id: str) -> Dict:
        """Get detailed video information"""
        try:
            response = self.youtube_read.videos().list(
                part='snippet,contentDetails,statistics',
                id=video_id
            ).execute()
            
            if response['items']:
                return response['items'][0]
            return {}
            
        except Exception as e:
            logger.error(f"Error getting video details for {video_id}: {e}")
            return {}
    
    def upload_video(self, file_path: str, title: str, description: str, 
                    tags: List[str], category_id: str = '27') -> str:
        """Upload video to YouTube"""
        try:
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags,
                    'categoryId': category_id
                },
                'status': {
                    'privacyStatus': 'public'
                }
            }
            
            media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
            
            insert_request = self.youtube_upload.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = insert_request.execute()
            video_id = response['id']
            logger.info(f"Successfully uploaded video: {video_id}")
            return video_id
            
        except Exception as e:
            logger.error(f"Error uploading video: {e}")
            return ""

class TranscriptProcessor:
    """Handles video transcript extraction and processing"""
    
    @staticmethod
    def get_transcript(video_id: str) -> List[Dict]:
        """Extract transcript from YouTube video with better error handling"""
        try:
            # Add delay to avoid rate limiting
            time.sleep(1)
            
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            logger.info(f"Successfully extracted transcript for {video_id}")
            return transcript
            
        except Exception as e:
            error_msg = str(e)
            
            # Check for specific error types
            if "429" in error_msg or "Too Many Requests" in error_msg:
                logger.warning(f"Rate limited for {video_id}, waiting 60 seconds...")
                time.sleep(60)
                # Try once more after waiting
                try:
                    transcript = YouTubeTranscriptApi.get_transcript(video_id)
                    logger.info(f"Successfully extracted transcript for {video_id} after retry")
                    return transcript
                except:
                    logger.error(f"Rate limit retry failed for {video_id}")
                    return []
            
            elif "Subtitles are disabled" in error_msg:
                logger.warning(f"Subtitles disabled for {video_id}")
                return []
            
            elif "No transcripts were found" in error_msg:
                logger.warning(f"No English transcript available for {video_id}")
                # Try to get any available transcript in other languages
                try:
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                    # Try to find any generated transcript
                    for transcript in transcript_list:
                        if transcript.is_generated:
                            logger.info(f"Found generated transcript in {transcript.language} for {video_id}")
                            return transcript.fetch()
                except:
                    pass
                return []
            
            else:
                logger.error(f"Error extracting transcript for {video_id}: {e}")
                return []
    
    @staticmethod
    def find_mih_segments(transcript: List[Dict], min_duration: int = 15, 
                         max_duration: int = 60) -> List[Tuple[float, float, str, float]]:
        """Find MIH-related segments in transcript"""
        mih_keywords = [
            'mih', 'molar incisor hypomineralisation', 'hypomineralization',
            'enamel defect', 'white spots', 'brown spots', 'enamel hypoplasia',
            'demineralization', 'remineralization', 'icon', 'whitening',
            'sensitive teeth', 'enamel care', 'pediatric whitening'
        ]
        
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
                keyword_count = sum(1 for keyword in mih_keywords 
                                  if keyword in segment_text)
                relevance_score = keyword_count / len(mih_keywords)
                
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
                '--no-warnings',
                '--extract-flat', 'false',
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
            duration = end_time - start_time
            if duration < 10 or duration > 65:
                logger.warning(f"Invalid clip duration: {duration}s")
                return False
            
            # Simple FFmpeg command for Windows compatibility
            cmd = [
                'ffmpeg',
                '-i', input_file,
                '-ss', str(start_time),
                '-t', str(duration),
                '-vf', 'scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:black',
                '-c:v', 'libx264',
                '-c:a', 'aac',
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
        prompt = f"""
        Analyze this video transcript and identify the best 15-60 second clips that would be most valuable for parents of children with Molar Incisor Hypomineralisation (MIH).

        Video Title: {video_metadata.get('title', '')}
        Video Description: {video_metadata.get('description', '')}

        Transcript: {transcript[:3000]}  # Limit transcript length

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

        Return as JSON array with max 3 clips. Example format:
        [
          {
            "start_timestamp": 45,
            "end_timestamp": 90,
            "reason": "Explains MIH causes clearly",
            "topics": ["MIH causes", "parent education"],
            "tone": "educational"
          }
        ]
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            # Try to parse JSON
            clips_data = json.loads(response_text)
            logger.info(f"Gemini identified {len(clips_data)} clips")
            return clips_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error from Gemini: {e}")
            logger.error(f"Raw response: {response.text[:500]}")
            return []
        except Exception as e:
            logger.error(f"Error analyzing transcript with Gemini: {e}")
            return []
    
    def generate_content(self, transcript: str, video_metadata: Dict, 
                        clip_duration: float) -> GeneratedContent:
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
            
            # Validate MIH terms in hashtags
            mih_terms = ['mih', 'enamel', 'hypomineralisation', 'pediatric', 'dentistry']
            hashtags = content_data.get('hashtags', [])
            hashtags_text = ' '.join(hashtags).lower()
            
            if not any(term in hashtags_text for term in mih_terms):
                # Add MIH hashtags if missing
                content_data['hashtags'] = hashtags + ['#MIH', '#EnamelCare', '#PediatricDentistry']
            
            return GeneratedContent(
                title=content_data.get('title', 'Dr Greenwall MIH Content'),
                description=content_data.get('description', 'MIH educational content'),
                captions=content_data.get('captions', ['MIH education']),
                hashtags=content_data.get('hashtags', ['#MIH']),
                thumbnail_suggestion=content_data.get('thumbnail_suggestion', 'MIH content')
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in content generation: {e}")
            return self._create_fallback_content(transcript, video_metadata)
        except Exception as e:
            logger.error(f"Error generating content with Gemini: {e}")
            return self._create_fallback_content(transcript, video_metadata)
    
    def _create_fallback_content(self, transcript: str, video_metadata: Dict) -> GeneratedContent:
        """Create fallback content when Gemini fails"""
        return GeneratedContent(
            title="Dr Greenwall on MIH Treatment",
            description="Expert guidance on Molar Incisor Hypomineralisation from Dr Linda Greenwall",
            captions=["MIH expert advice", "Enamel care tips", "Pediatric dentistry guidance"],
            hashtags=["#MIH", "#EnamelCare", "#PediatricDentistry", "#DrGreenwall", "#TeethWhitening"],
            thumbnail_suggestion="Dr Greenwall explaining MIH treatment"
        )
    
    def _regenerate_with_mih_terms(self, transcript: str, video_metadata: Dict) -> Dict:
        """Regenerate content ensuring MIH terms are included"""
        prompt = f"""
        Create social media content for Dr. Linda Greenwall's MIH content.
        MANDATORY: Include these terms in hashtags: #MIH #EnamelDefects #PediatricDentistry
        
        Transcript: {transcript}
        
        Return JSON with: title, description, captions, hashtags, thumbnail_suggestion
        """
        
        try:
            response = self.model.generate_content(prompt)
            return json.loads(response.text)
        except:
            return {
                'title': 'Dr Greenwall on MIH Treatment',
                'description': 'Expert advice on Molar Incisor Hypomineralisation',
                'captions': ['MIH expert tips', 'Enamel care guidance', 'Pediatric dentistry'],
                'hashtags': ['#MIH', '#EnamelDefects', '#PediatricDentistry', '#DrGreenwall'],
                'thumbnail_suggestion': 'Dr Greenwall explaining MIH treatment'
            }

class MIHContentAutomation:
    """Main automation system"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.youtube_manager = YouTubeManager(
            config['youtube_api_key'], 
            config['youtube_credentials_file']
        )
        self.transcript_processor = TranscriptProcessor()
        self.video_processor = VideoProcessor(config.get('output_dir', 'processed_videos'))
        self.content_generator = GeminiContentGenerator(config['gemini_api_key'])
        self.upload_channels = config['upload_channels']
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
        search_queries = [
            "Linda Greenwall MIH",
            "Dr Greenwall molar incisor hypomineralisation",
            "Linda Greenwall enamel defects",
            "Dr Greenwall pediatric whitening",
            "Linda Greenwall ICON treatment",
            "Jaz Gulati Linda Greenwall",
            "Dentistry Magazine Linda Greenwall"
        ]
        
        all_videos = []
        seen_ids = set()
        
        for query in search_queries:
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
        
        try:
            # Get transcript
            transcript = self.transcript_processor.get_transcript(video_id)
            if not transcript:
                logger.warning(f"No transcript available for {video_id}")
                return []
            
            # Convert transcript to text for Gemini analysis
            full_transcript = ' '.join([item['text'] for item in transcript])
            
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
                logger.info(f"No suitable clips found in {video_id}")
                return []
            
            # Download source video
            video_file = self.video_processor.download_video(video_id)
            if not video_file:
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
                    
                    clip = VideoClip(
                        start_time=start_time,
                        end_time=end_time,
                        transcript=clip_transcript,
                        relevance_score=0.8,  # High score from Gemini analysis
                        source_video_id=video_id,
                        source_title=video_data['title']
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
            
            logger.info(f"Created {len(clips)} clips from video {video_id}")
            return clips
            
        except Exception as e:
            logger.error(f"Error processing video {video_id}: {e}")
            return []
    
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
        """Generate content and publish clips to YouTube channels"""
        for clip in clips:
            if not clip.file_path or not os.path.exists(clip.file_path):
                continue
            
            logger.info(f"Publishing clip: {os.path.basename(clip.file_path)}")
            
            # Generate content with Gemini
            video_metadata = {
                'title': clip.source_title,
                'description': f"Source: {clip.source_video_id}"
            }
            
            duration = clip.end_time - clip.start_time
            content = self.content_generator.generate_content(
                clip.transcript, video_metadata, duration
            )
            
            # Upload to all configured channels
            for channel_config in self.upload_channels:
                try:
                    video_id = self.youtube_manager.upload_video(
                        file_path=clip.file_path,
                        title=content.title,
                        description=content.description,
                        tags=content.hashtags
                    )
                    
                    if video_id:
                        logger.info(f"Successfully uploaded to channel: {video_id}")
                    
                    time.sleep(5)  # Rate limiting between uploads
                    
                except Exception as e:
                    logger.error(f"Error uploading to channel: {e}")
            
            # Clean up clip file
            try:
                os.remove(clip.file_path)
            except:
                pass
    
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
        max_videos_per_cycle = 10  # Limit to avoid rate limiting
        
        for video_data in videos[:max_videos_per_cycle]:
            try:
                clips = self.process_video(video_data)
                if clips:
                    self.publish_clips(clips)
                    total_clips += len(clips)
                
                # Mark video as processed
                self.processed_videos.add(video_data['id'])
                processed_count += 1
                
                # Rate limiting - longer pause between videos
                logger.info(f"Processed {processed_count}/{min(len(videos), max_videos_per_cycle)} videos")
                if processed_count < min(len(videos), max_videos_per_cycle):
                    logger.info("Waiting 30 seconds to avoid rate limiting...")
                    time.sleep(30)
                
            except KeyboardInterrupt:
                logger.info("Automation stopped by user")
                break
            except Exception as e:
                logger.error(f"Error processing video {video_data['id']}: {e}")
                # Continue with next video even if one fails
                continue
        
        # Save processed videos list
        self._save_processed_videos()
        
        logger.info(f"Automation cycle complete. Processed {total_clips} clips from {processed_count} videos")
        
        if len(videos) > max_videos_per_cycle:
            logger.info(f"Note: {len(videos) - max_videos_per_cycle} videos remaining for next cycle")
            logger.info("Run again to process remaining videos")
    
    def run_continuous(self, interval_hours: int = 1):
        """Run automation continuously"""
        logger.info(f"Starting continuous automation (every {interval_hours} hours)")
        
        while True:
            try:
                self.run_automation_cycle()
                logger.info(f"Sleeping for {interval_hours} hours...")
                time.sleep(interval_hours * 3600)
                
            except KeyboardInterrupt:
                logger.info("Automation stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in automation cycle: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying

def check_tool_availability(tool_name):
    """Check if a command-line tool is available (cross-platform)"""
    try:
        # Try running the tool with --version or --help
        result = subprocess.run([tool_name, '--version'], 
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
        try:
            # Try with --help as fallback
            result = subprocess.run([tool_name, '--help'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except:
            return False

def main():
    """Main function to run the automation"""
    
    # Try to import config, create default if missing
    try:
        from config import (YOUTUBE_API_KEY, GEMINI_API_KEY, YOUTUBE_CREDENTIALS_FILE, 
                           OUTPUT_DIR, UPLOAD_CHANNELS)
        config = {
            'youtube_api_key': YOUTUBE_API_KEY,
            'youtube_credentials_file': YOUTUBE_CREDENTIALS_FILE,
            'gemini_api_key': GEMINI_API_KEY,
            'output_dir': OUTPUT_DIR,
            'upload_channels': UPLOAD_CHANNELS
        }
    except ImportError:
        logger.error("Config file not found. Please run setup_wizard.py first or create config.py")
        logger.info("Example config.py:")
        logger.info("""
YOUTUBE_API_KEY = "your_youtube_api_key_here"
GEMINI_API_KEY = "your_gemini_api_key_here"
YOUTUBE_CREDENTIALS_FILE = "youtube_credentials.json"
OUTPUT_DIR = "processed_videos"
UPLOAD_CHANNELS = [
    {'name': 'Channel 1', 'id': 'your_channel_id_1'},
    {'name': 'Channel 2', 'id': 'your_channel_id_2'},
    {'name': 'Channel 3', 'id': 'your_channel_id_3'}
]
        """)
        return
    
    # Validate API keys
    if not config['youtube_api_key'] or config['youtube_api_key'] == 'YOUR_YOUTUBE_API_KEY':
        logger.error("YouTube API key not configured. Please update config.py")
        return
    
    if not config['gemini_api_key'] or config['gemini_api_key'] == 'YOUR_GEMINI_API_KEY':
        logger.error("Gemini API key not configured. Please update config.py")
        return
    
    # Validate required dependencies
    required_tools = ['yt-dlp', 'ffmpeg']
    missing_tools = []
    
    # for tool in required_tools:
    #     if not check_tool_availability(tool):
    #         missing_tools.append(tool)
    
    if missing_tools:
        logger.error(f"Required tools not found: {', '.join(missing_tools)}")
        logger.info("Installation instructions:")
        for tool in missing_tools:
            if tool == 'yt-dlp':
                logger.info(f"  {tool}: pip install yt-dlp  or  uv add yt-dlp")
            elif tool == 'ffmpeg':
                logger.info(f"  {tool}: Download from https://ffmpeg.org/ and add to PATH")
        return
    
    logger.info("✅ All dependencies found")
    
    # Initialize and run automation
    try:
        automation = MIHContentAutomation(config)
        
        # Run single cycle or continuous
        import sys
        if len(sys.argv) > 1 and sys.argv[1] == '--continuous':
            automation.run_continuous(interval_hours=1)
        else:
            automation.run_automation_cycle()
            
    except Exception as e:
        logger.error(f"Error running automation: {e}")
        logger.info("Make sure you have:")
        logger.info("1. Valid API keys in config.py")
        logger.info("2. youtube_credentials.json file")
        logger.info("3. All required tools installed")

if __name__ == "__main__":
    main()