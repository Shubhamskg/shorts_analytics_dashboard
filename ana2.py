import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import time
from pathlib import Path

try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
except ImportError as e:
    st.error(f"Missing required libraries. Please install: pip install {e.name}")
    st.stop()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class VideoAnalytics:
    """Data class for video analytics from YouTube Analytics API"""
    video_id: str
    title: str
    published_at: str
    duration: str
    views: int
    watch_time_minutes: float
    average_view_duration: float
    likes: int
    comments: int
    shares: int
    subscribers_gained: int
    thumbnail_url: str
    channel_name: str
    video_type: str  # 'short' or 'video'

@dataclass
class ChannelAnalytics:
    """Data class for channel analytics from YouTube Analytics API"""
    channel_id: str
    channel_name: str
    total_subscribers: int
    period_views: int
    period_watch_time_hours: float
    period_subscribers_gained: int
    period_likes: int
    period_comments: int
    period_shares: int
    total_videos_count: int
    total_shorts_count: int
    avg_views_per_video: float
    avg_views_per_short: float
    avg_view_duration: float

@dataclass 
class AudienceData:
    """Data class for audience analytics"""
    age_gender: List[Dict]
    device_types: List[Dict]
    traffic_sources: List[Dict]
    geography: List[Dict]

class YouTubeAnalyticsService:
    """YouTube Analytics API-focused service with minimal Data API usage"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/youtube.readonly',
        'https://www.googleapis.com/auth/yt-analytics.readonly'
    ]
    
    def __init__(self, api_key: str, channel_configs: List[Dict]):
        self.api_key = api_key
        self.channel_configs = channel_configs
        self.youtube_services = {}
        self.analytics_services = {}
        self._authenticate_channels()
    
    def _authenticate_channels(self):
        """Authenticate all configured channels"""
        for i, config in enumerate(self.channel_configs):
            channel_key = f"channel_{i+1}"
            creds_file = config.get('credentials_file')
            channel_name = config.get('name', channel_key)
            
            if not creds_file or not Path(creds_file).exists():
                logger.error(f"Missing credentials file for {channel_name}: {creds_file}")
                continue
            
            try:
                token_file = f'analytics_token_{channel_key}.json'
                creds = None
                
                if Path(token_file).exists():
                    creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
                
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        flow = InstalledAppFlow.from_client_secrets_file(creds_file, self.SCOPES)
                        creds = flow.run_local_server(port=0)
                    
                    with open(token_file, 'w') as token:
                        token.write(creds.to_json())
                
                # Initialize both Analytics API and Data API
                analytics_service = build('youtubeAnalytics', 'v2', credentials=creds)
                youtube_service = build('youtube', 'v3', credentials=creds)
                
                self.analytics_services[channel_key] = {
                    'service': analytics_service,
                    'config': config
                }
                self.youtube_services[channel_key] = {
                    'service': youtube_service,
                    'config': config
                }
                
                logger.info(f"Successfully authenticated: {channel_name}")
            except Exception as e:
                logger.error(f"Authentication failed for {channel_name}: {e}")
                continue
    
    def get_channel_id(self, channel_key: str) -> Optional[str]:
        """Get channel ID - minimal Data API usage"""
        try:
            service = self.youtube_services[channel_key]['service']
            request = service.channels().list(part="id,snippet", mine=True)
            response = request.execute()
            
            if response.get("items"):
                return response["items"][0]["id"]
        except Exception as e:
            logger.error(f"Failed to get channel ID for {channel_key}: {e}")
        return None
    
    def get_date_range(self, days: int) -> tuple:
        """Get start and end dates for analytics queries"""
        if days == -1:  # All time
            start_date = '2005-04-23'
        else:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        return start_date, end_date
    
    def get_channel_analytics_pure(self, channel_key: str, days: int = 30) -> Optional[ChannelAnalytics]:
        """Get channel analytics using ONLY Analytics API where possible"""
        try:
            channel_id = self.get_channel_id(channel_key)
            if not channel_id:
                return None
            
            analytics_service = self.analytics_services[channel_key]['service']
            config = self.analytics_services[channel_key]['config']
            channel_name = config.get('name', 'Unknown')
            
            start_date, end_date = self.get_date_range(days)
            
            logger.info(f"Getting pure analytics for {channel_name} from {start_date} to {end_date}")
            
            # Get main analytics metrics for the period
            try:
                main_analytics = analytics_service.reports().query(
                    ids=f'channel=={channel_id}',
                    startDate=start_date,
                    endDate=end_date,
                    metrics='views,estimatedMinutesWatched,subscribersGained,likes,comments,shares,averageViewDuration'
                ).execute()
                
                analytics_data = main_analytics.get('rows', [[0, 0, 0, 0, 0, 0, 0]])[0]
                
                period_views = analytics_data[0] if len(analytics_data) > 0 else 0
                period_watch_time = analytics_data[1] if len(analytics_data) > 1 else 0
                period_subscribers = analytics_data[2] if len(analytics_data) > 2 else 0
                period_likes = analytics_data[3] if len(analytics_data) > 3 else 0
                period_comments = analytics_data[4] if len(analytics_data) > 4 else 0
                period_shares = analytics_data[5] if len(analytics_data) > 5 else 0
                avg_view_duration = analytics_data[6] if len(analytics_data) > 6 else 0
                
                logger.info(f"Analytics API returned: {period_views} views, {period_watch_time} minutes")
                
            except Exception as e:
                logger.warning(f"Main analytics failed for {channel_name}: {e}")
                period_views = period_watch_time = period_subscribers = 0
                period_likes = period_comments = period_shares = avg_view_duration = 0
            
            # Get video count breakdown using Analytics API
            video_counts = self.get_video_counts_from_analytics(channel_key, days)
            
            # Get subscriber count - minimal Data API usage
            total_subscribers = self.get_subscriber_count_minimal(channel_key)
            
            # Calculate averages from analytics data
            avg_views_per_video = video_counts['avg_views_per_video']
            avg_views_per_short = video_counts['avg_views_per_short']
            
            return ChannelAnalytics(
                channel_id=channel_id,
                channel_name=channel_name,
                total_subscribers=total_subscribers,
                period_views=period_views,
                period_watch_time_hours=period_watch_time / 60,
                period_subscribers_gained=period_subscribers,
                period_likes=period_likes,
                period_comments=period_comments,
                period_shares=period_shares,
                total_videos_count=video_counts['regular_videos'],
                total_shorts_count=video_counts['shorts'],
                avg_views_per_video=avg_views_per_video,
                avg_views_per_short=avg_views_per_short,
                avg_view_duration=avg_view_duration
            )
            
        except Exception as e:
            logger.error(f"Failed to get pure analytics for {channel_key}: {e}")
            return None
    
    def get_video_counts_from_analytics(self, channel_key: str, days: int = 30) -> Dict:
        """Get video counts using Data API since Analytics API video dimension is not supported"""
        try:
            channel_id = self.get_channel_id(channel_key)
            if not channel_id:
                return {'regular_videos': 0, 'shorts': 0, 'avg_views_per_video': 0, 'avg_views_per_short': 0}
            
            youtube_service = self.youtube_services[channel_key]['service']
            start_date, end_date = self.get_date_range(days)
            
            # Use Data API to get videos for the period since Analytics API video dimension is not supported
            if days == -1:  # All time
                published_after = '2005-04-23T00:00:00Z'
            else:
                published_after = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
            
            try:
                # Get videos published in the time range
                all_video_ids = []
                next_page_token = None
                max_results = 500
                
                while len(all_video_ids) < max_results:
                    search_params = {
                        'part': 'id',
                        'channelId': channel_id,
                        'maxResults': min(50, max_results - len(all_video_ids)),
                        'order': 'date',
                        'type': 'video',
                        'publishedAfter': published_after
                    }
                    
                    if next_page_token:
                        search_params['pageToken'] = next_page_token
                    
                    search_response = youtube_service.search().list(**search_params).execute()
                    
                    batch_video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
                    all_video_ids.extend(batch_video_ids)
                    
                    next_page_token = search_response.get('nextPageToken')
                    if not next_page_token or not batch_video_ids:
                        break
                
                if all_video_ids:
                    # Get video details to determine shorts vs regular videos
                    video_metadata = self.get_minimal_video_metadata(channel_key, all_video_ids)
                    
                    shorts = []
                    regular_videos = []
                    
                    for video_id in all_video_ids:
                        duration = video_metadata.get(video_id, {}).get('duration', 'PT0S')
                        is_short = self._is_short_video(duration)
                        
                        if is_short:
                            shorts.append(video_id)
                        else:
                            regular_videos.append(video_id)
                    
                    # Estimate average views (since we can't get exact analytics per video)
                    total_videos = len(all_video_ids)
                    if total_videos > 0:
                        # Use channel total views as approximation
                        try:
                            analytics_service = self.analytics_services[channel_key]['service']
                            main_analytics = analytics_service.reports().query(
                                ids=f'channel=={channel_id}',
                                startDate=start_date,
                                endDate=end_date,
                                metrics='views'
                            ).execute()
                            
                            total_period_views = main_analytics.get('rows', [[0]])[0][0]
                            avg_views_all = total_period_views / total_videos if total_videos > 0 else 0
                            
                            # Estimate based on typical shorts vs video performance ratios
                            avg_views_per_video = avg_views_all * 1.2 if regular_videos else 0  # Videos typically get slightly more
                            avg_views_per_short = avg_views_all * 0.8 if shorts else 0  # Shorts typically get slightly less
                            
                        except Exception as e:
                            logger.warning(f"Could not get view estimates: {e}")
                            avg_views_per_video = avg_views_per_short = 0
                    else:
                        avg_views_per_video = avg_views_per_short = 0
                    
                    return {
                        'regular_videos': len(regular_videos),
                        'shorts': len(shorts),
                        'avg_views_per_video': avg_views_per_video,
                        'avg_views_per_short': avg_views_per_short
                    }
                
            except Exception as e:
                logger.warning(f"Video count search failed: {e}")
            
            return {'regular_videos': 0, 'shorts': 0, 'avg_views_per_video': 0, 'avg_views_per_short': 0}
            
        except Exception as e:
            logger.error(f"Failed to get video counts: {e}")
            return {'regular_videos': 0, 'shorts': 0, 'avg_views_per_video': 0, 'avg_views_per_short': 0}
    
    def get_minimal_video_metadata(self, channel_key: str, video_ids: List[str]) -> Dict:
        """Minimal Data API usage - only get essential metadata"""
        try:
            youtube_service = self.youtube_services[channel_key]['service']
            metadata = {}
            
            # Process in batches of 50
            for i in range(0, len(video_ids), 50):
                batch_ids = video_ids[i:i+50]
                
                try:
                    response = youtube_service.videos().list(
                        part='contentDetails',
                        id=','.join(batch_ids)
                    ).execute()
                    
                    for video in response.get('items', []):
                        video_id = video['id']
                        duration = video.get('contentDetails', {}).get('duration', 'PT0S')
                        metadata[video_id] = {'duration': duration}
                        
                except Exception as e:
                    logger.warning(f"Failed to get metadata for batch: {e}")
                    continue
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to get minimal metadata: {e}")
            return {}
    
    def get_subscriber_count_minimal(self, channel_key: str) -> int:
        """Minimal Data API usage - only get subscriber count"""
        try:
            channel_id = self.get_channel_id(channel_key)
            if not channel_id:
                return 0
                
            youtube_service = self.youtube_services[channel_key]['service']
            
            response = youtube_service.channels().list(
                part="statistics",
                id=channel_id
            ).execute()
            
            if response.get("items"):
                return int(response["items"][0]["statistics"].get('subscriberCount', 0))
                
        except Exception as e:
            logger.warning(f"Failed to get subscriber count: {e}")
        
        return 0
    
    def get_videos_analytics_pure(self, channel_key: str, days: int = 30) -> List[VideoAnalytics]:
        """Get video analytics using Data API since Analytics API video dimension is not supported"""
        video_analytics = []
        
        try:
            channel_id = self.get_channel_id(channel_key)
            if not channel_id:
                return video_analytics
            
            youtube_service = self.youtube_services[channel_key]['service']
            analytics_service = self.analytics_services[channel_key]['service']
            config = self.analytics_services[channel_key]['config']
            channel_name = config.get('name', 'Unknown')
            
            start_date, end_date = self.get_date_range(days)
            
            logger.info(f"Getting video analytics for {channel_name} from {start_date} (using Data API)")
            
            # Get published videos in the time range using Data API
            if days == -1:  # All time
                published_after = '2005-04-23T00:00:00Z'
            else:
                published_after = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # Get videos with pagination
            all_video_ids = []
            next_page_token = None
            max_results = 500
            
            while len(all_video_ids) < max_results:
                search_params = {
                    'part': 'id,snippet',
                    'channelId': channel_id,
                    'maxResults': min(50, max_results - len(all_video_ids)),
                    'order': 'date',
                    'type': 'video',
                    'publishedAfter': published_after
                }
                
                if next_page_token:
                    search_params['pageToken'] = next_page_token
                
                try:
                    search_response = youtube_service.search().list(**search_params).execute()
                    
                    batch_video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
                    all_video_ids.extend(batch_video_ids)
                    
                    next_page_token = search_response.get('nextPageToken')
                    if not next_page_token or not batch_video_ids:
                        break
                        
                except Exception as e:
                    logger.warning(f"Search API error: {e}")
                    break
            
            if not all_video_ids:
                logger.warning(f"No videos found for {channel_name}")
                return video_analytics
            
            logger.info(f"Processing {len(all_video_ids)} videos for analytics")
            
            # Process videos in batches and get their analytics
            for i in range(0, len(all_video_ids), 50):
                batch_ids = all_video_ids[i:i+50]
                
                try:
                    # Get video details from Data API
                    videos_response = youtube_service.videos().list(
                        part='snippet,contentDetails,statistics',
                        id=','.join(batch_ids)
                    ).execute()
                    
                    for video in videos_response.get('items', []):
                        try:
                            video_id = video['id']
                            snippet = video['snippet']
                            content_details = video['contentDetails']
                            statistics = video.get('statistics', {})
                            
                            # Determine if it's a short
                            duration = content_details.get('duration', 'PT0S')
                            is_short = self._is_short_video(duration)
                            
                            # Try to get analytics data for this specific video
                            # Note: Individual video analytics may not be available for all metrics
                            try:
                                video_analytics_response = analytics_service.reports().query(
                                    ids=f'channel=={channel_id}',
                                    startDate=start_date,
                                    endDate=end_date,
                                    metrics='views,estimatedMinutesWatched,subscribersGained',
                                    filters=f'video=={video_id}'
                                ).execute()
                                
                                video_data = video_analytics_response.get('rows', [[0, 0, 0]])[0]
                                
                                analytics_views = video_data[0] if len(video_data) > 0 else int(statistics.get('viewCount', 0))
                                analytics_watch_time = video_data[1] if len(video_data) > 1 else 0
                                analytics_subscribers = video_data[2] if len(video_data) > 2 else 0
                                
                                # Other metrics from statistics (these are lifetime, not period-specific)
                                analytics_likes = int(statistics.get('likeCount', 0))
                                analytics_comments = int(statistics.get('commentCount', 0))
                                
                            except Exception as e:
                                logger.warning(f"Analytics failed for video {video_id}, using basic stats: {e}")
                                # Fall back to basic statistics
                                analytics_views = int(statistics.get('viewCount', 0))
                                analytics_watch_time = 0
                                analytics_likes = int(statistics.get('likeCount', 0))
                                analytics_comments = int(statistics.get('commentCount', 0))
                                analytics_subscribers = 0
                            
                            video_analytic = VideoAnalytics(
                                video_id=video_id,
                                title=snippet.get('title', 'Unknown'),
                                published_at=snippet.get('publishedAt', ''),
                                duration=duration,
                                views=analytics_views,
                                watch_time_minutes=analytics_watch_time,
                                average_view_duration=0,  # Not available through individual video queries
                                likes=analytics_likes,
                                comments=analytics_comments,
                                shares=0,  # Not available in basic statistics
                                subscribers_gained=analytics_subscribers,
                                thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                                channel_name=channel_name,
                                video_type='short' if is_short else 'video'
                            )
                            
                            video_analytics.append(video_analytic)
                            
                        except Exception as e:
                            logger.error(f"Error processing video {video_id}: {e}")
                            continue
                            
                except Exception as e:
                    logger.error(f"Error processing batch: {e}")
                    continue
            
            logger.info(f"Successfully processed {len(video_analytics)} videos")
                
        except Exception as e:
            logger.error(f"Failed to get video analytics: {e}")
        
        return video_analytics
    
    def get_essential_video_metadata(self, channel_key: str, video_ids: List[str]) -> Dict:
        """Get only essential metadata from Data API"""
        try:
            youtube_service = self.youtube_services[channel_key]['service']
            metadata = {}
            
            # Process in batches of 50
            for i in range(0, len(video_ids), 50):
                batch_ids = video_ids[i:i+50]
                
                try:
                    response = youtube_service.videos().list(
                        part='snippet,contentDetails',
                        id=','.join(batch_ids)
                    ).execute()
                    
                    for video in response.get('items', []):
                        video_id = video['id']
                        snippet = video.get('snippet', {})
                        content_details = video.get('contentDetails', {})
                        
                        metadata[video_id] = {
                            'title': snippet.get('title', f'Video {video_id}'),
                            'published_at': snippet.get('publishedAt', ''),
                            'duration': content_details.get('duration', 'PT0S'),
                            'thumbnail_url': snippet.get('thumbnails', {}).get('high', {}).get('url', '')
                        }
                        
                except Exception as e:
                    logger.warning(f"Failed to get essential metadata for batch: {e}")
                    continue
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to get essential metadata: {e}")
            return {}
    
    def get_audience_analytics(self, channel_key: str, days: int = 30) -> AudienceData:
        """Get audience analytics using ONLY YouTube Analytics API"""
        try:
            channel_id = self.get_channel_id(channel_key)
            if not channel_id:
                return AudienceData([], [], [], [])
            
            analytics_service = self.analytics_services[channel_key]['service']
            start_date, end_date = self.get_date_range(days)
            
            age_gender = []
            device_types = []
            traffic_sources = []
            geography = []
            
            # Age and Gender demographics
            try:
                age_gender_response = analytics_service.reports().query(
                    ids=f'channel=={channel_id}',
                    startDate=start_date,
                    endDate=end_date,
                    metrics='viewerPercentage',
                    dimensions='ageGroup,gender'
                ).execute()
                
                age_gender = [
                    {'age_group': row[0], 'gender': row[1], 'percentage': row[2]}
                    for row in age_gender_response.get('rows', [])
                ]
            except Exception as e:
                logger.warning(f"Age/Gender data unavailable: {e}")
            
            # Device types
            try:
                device_response = analytics_service.reports().query(
                    ids=f'channel=={channel_id}',
                    startDate=start_date,
                    endDate=end_date,
                    metrics='views',
                    dimensions='deviceType'
                ).execute()
                
                device_types = [
                    {'device': row[0], 'views': row[1]}
                    for row in device_response.get('rows', [])
                ]
            except Exception as e:
                logger.warning(f"Device data unavailable: {e}")
            
            # Traffic sources
            try:
                traffic_response = analytics_service.reports().query(
                    ids=f'channel=={channel_id}',
                    startDate=start_date,
                    endDate=end_date,
                    metrics='views',
                    dimensions='trafficSourceType'
                ).execute()
                
                traffic_sources = [
                    {'source': row[0], 'views': row[1]}
                    for row in traffic_response.get('rows', [])
                ]
            except Exception as e:
                logger.warning(f"Traffic source data unavailable: {e}")
            
            # Geography
            try:
                geo_response = analytics_service.reports().query(
                    ids=f'channel=={channel_id}',
                    startDate=start_date,
                    endDate=end_date,
                    metrics='views',
                    dimensions='country',
                    sort='-views',
                    maxResults=10
                ).execute()
                
                geography = [
                    {'country': row[0], 'views': row[1]}
                    for row in geo_response.get('rows', [])
                ]
            except Exception as e:
                logger.warning(f"Geography data unavailable: {e}")
            
            return AudienceData(age_gender, device_types, traffic_sources, geography)
            
        except Exception as e:
            logger.error(f"Failed to get audience analytics: {e}")
            return AudienceData([], [], [], [])
    
    def _is_short_video(self, duration: str) -> bool:
        """Check if video is a YouTube Short (<=60 seconds)"""
        try:
            duration = duration.replace('PT', '')
            
            total_seconds = 0
            if 'H' in duration:
                hours, duration = duration.split('H')
                total_seconds += int(hours) * 3600
            if 'M' in duration:
                minutes, duration = duration.split('M')
                total_seconds += int(minutes) * 60
            if 'S' in duration:
                seconds = duration.replace('S', '')
                total_seconds += int(seconds) if seconds else 0
            
            return total_seconds <= 60
        except:
            return False
    
    # Add legacy methods for backward compatibility
    def get_channel_analytics(self, channel_key: str, days: int = 30) -> Optional[ChannelAnalytics]:
        """Legacy method that calls the pure analytics version"""
        return self.get_channel_analytics_pure(channel_key, days)
    
    def get_videos_analytics(self, channel_key: str, days: int = 30) -> List[VideoAnalytics]:
        """Legacy method that calls the pure analytics version"""
        return self.get_videos_analytics_pure(channel_key, days)

class YouTubeDashboard:
    """Main dashboard class"""
    
    def __init__(self):
        st.set_page_config(
            page_title="YouTube Analytics Dashboard",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Initialize session state
        if 'selected_channel' not in st.session_state:
            st.session_state.selected_channel = None
        
        # Custom CSS
        st.markdown("""
        <style>
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 15px;
            text-align: center;
            margin-bottom: 2rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        
        .metric-card {
            background: white;
            padding: 1.5rem;
            border-radius: 12px;
            border-left: 4px solid #667eea;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            margin-bottom: 1rem;
            transition: transform 0.2s ease;
        }
        
        .metric-card:hover {
            transform: translateY(-4px);
        }
        
        .channel-button {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            border: none;
            padding: 1rem 2rem;
            border-radius: 25px;
            font-weight: bold;
            margin: 0.5rem;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .stSelectbox > div > div {
            background-color: #f8f9fa;
            border-radius: 10px;
        }
        
        .period-indicator {
            background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
            color: #333;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-weight: bold;
            display: inline-block;
            margin-bottom: 1rem;
        }
        </style>
        """, unsafe_allow_html=True)
    
    def load_config(self):
        """Load configuration"""
        try:
            import config
            return {
                'youtube_api_key': config.YOUTUBE_API_KEY,
                'upload_channels': config.UPLOAD_CHANNELS
            }
        except ImportError:
            st.error("❌ Configuration file not found! Please ensure config.py exists.")
            st.stop()
    
    def initialize_service(self, system_config):
        """Initialize YouTube Analytics Service"""
        try:
            return YouTubeAnalyticsService(
                system_config['youtube_api_key'],
                system_config['upload_channels']
            )
        except Exception as e:
            st.error(f"❌ Failed to initialize YouTube Analytics Service: {e}")
            st.stop()
    
    def render_header(self):
        """Render dashboard header"""
        st.markdown("""
        <div class="main-header">
            <h1>📊 YouTube Analytics Dashboard</h1>
            <p style="font-size: 1.2rem; margin-top: 1rem; opacity: 0.9;">
                Powered by YouTube Analytics API - Real-time Performance Insights
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    def render_sidebar(self):
        """Render sidebar controls"""
        st.sidebar.markdown("## 🔧 Dashboard Controls")
        
        # Time period selection
        time_options = {
            "2 days": 2,
            "7 days": 7,
            "14 days": 14,
            "30 days": 30,
            "60 days": 60,
            "90 days": 90,
            "All time": -1
        }
        
        selected_period = st.sidebar.selectbox(
            "📅 Select Time Period",
            options=list(time_options.keys()),
            index=3,
            help="Analytics data will be filtered for this time period"
        )
        
        days = time_options[selected_period]
        
        # Period indicator
        period_text = "All Time" if days == -1 else f"Last {days} days"
        st.sidebar.markdown(f"""
        <div class="period-indicator">
            📊 Analyzing: {period_text}
        </div>
        """, unsafe_allow_html=True)
        
        # Refresh button
        if st.sidebar.button("🔄 Refresh Analytics", type="primary", use_container_width=True):
            st.success("🔄 Refreshing analytics data...")
            time.sleep(1)
            st.rerun()
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📈 Analytics Features")
        st.sidebar.info("""
        ✅ Real-time YouTube Analytics API
        ✅ Time-period filtered metrics  
        ✅ Views & Watch Time Analytics
        ✅ Audience Demographics
        ✅ Traffic Source Analysis
        ✅ Device Usage Breakdown
        """)
        
        return days, period_text
    
    def render_summary_dashboard(self, service, days, period_text):
        """Render main summary dashboard"""
        st.markdown(f"## 📊 Performance Overview ({period_text})")
        
        # Collect analytics from all channels
        all_channel_analytics = []
        total_views = 0
        total_videos = 0
        total_shorts = 0
        total_watch_time = 0
        total_likes = 0
        total_comments = 0
        total_subscribers_gained = 0
        
        # Progress indicator
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        channel_count = len(service.youtube_services)
        
        for i, channel_key in enumerate(service.youtube_services.keys()):
            config = service.youtube_services[channel_key]['config']
            channel_name = config.get('name', f'Channel {channel_key}')
            
            status_text.text(f"Loading analytics for {channel_name}...")
            progress_bar.progress((i + 1) / channel_count)
            
            # Get channel analytics
            channel_analytics = service.get_channel_analytics(channel_key, days)
            
            if channel_analytics:
                all_channel_analytics.append({
                    'Channel': channel_name,
                    'Videos': channel_analytics.total_videos_count,
                    'Shorts': channel_analytics.total_shorts_count,
                    'Views': channel_analytics.period_views,
                    'Watch Time (h)': f"{channel_analytics.period_watch_time_hours:.1f}",
                    'Avg Views/Video': f"{channel_analytics.avg_views_per_video:.0f}",
                    'Avg Views/Short': f"{channel_analytics.avg_views_per_short:.0f}",
                    'Subscribers': f"{channel_analytics.total_subscribers:,}",
                    'Gained': f"+{channel_analytics.period_subscribers_gained}",
                    'channel_key': channel_key
                })
                
                total_views += channel_analytics.period_views
                total_videos += channel_analytics.total_videos_count
                total_shorts += channel_analytics.total_shorts_count
                total_watch_time += channel_analytics.period_watch_time_hours
                total_likes += channel_analytics.period_likes
                total_comments += channel_analytics.period_comments
                total_subscribers_gained += channel_analytics.period_subscribers_gained
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
        
        # Overview metrics
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            st.metric("🎬 Videos", f"{total_videos:,}")
        
        with col2:
            st.metric("🎵 Shorts", f"{total_shorts:,}")
        
        with col3:
            st.metric("👀 Views", f"{total_views:,}", delta=f"{period_text}")
        
        with col4:
            st.metric("⏱️ Watch Time", f"{total_watch_time:.1f}h")
        
        with col5:
            st.metric("👍 Likes", f"{total_likes:,}")
        
        with col6:
            st.metric("👥 Subscribers", f"+{total_subscribers_gained}")
        
        # Channel Performance Summary Table
        if all_channel_analytics:
            st.markdown("### 📈 Channel Performance Summary")
            df_summary = pd.DataFrame(all_channel_analytics)
            df_display = df_summary.drop('channel_key', axis=1)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # Channel selection buttons
            st.markdown("### 🎯 Select Channel for Detailed Analysis")
            
            cols = st.columns(len(all_channel_analytics))
            for i, channel_data in enumerate(all_channel_analytics):
                with cols[i]:
                    if st.button(
                        f"📺 {channel_data['Channel']}",
                        key=f"btn_{channel_data['channel_key']}",
                        type="primary",
                        use_container_width=True
                    ):
                        st.session_state.selected_channel = channel_data['channel_key']
                        st.rerun()
        
        # Top content overview
        self.render_top_content_overview(service, days, period_text)
    
    def render_top_content_overview(self, service, days, period_text):
        """Render top performing content overview"""
        st.markdown(f"### 🏆 Top Performing Content ({period_text})")
        
        all_videos = []
        
        # Get videos from all channels
        for channel_key in service.youtube_services.keys():
            video_analytics = service.get_videos_analytics_pure(channel_key, days)
            all_videos.extend(video_analytics)
        
        if all_videos:
            # Sort by views
            all_videos.sort(key=lambda x: x.views, reverse=True)
            top_videos = all_videos[:10]
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Top Videos Chart
                df_top = pd.DataFrame([
                    {
                        'Title': v.title[:40] + '...' if len(v.title) > 40 else v.title,
                        'Views': v.views,
                        'Type': v.video_type.title(),
                        'Channel': v.channel_name
                    }
                    for v in top_videos
                ])
                
                fig = px.bar(
                    df_top,
                    x='Views',
                    y='Title',
                    color='Type',
                    title=f"📊 Top 10 Videos by Views ({period_text})",
                    orientation='h',
                    height=500,
                    color_discrete_map={'Video': '#667eea', 'Short': '#f093fb'}
                )
                fig.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Views vs Watch Time Analysis
                df_performance = pd.DataFrame([
                    {
                        'Title': v.title[:25] + '...' if len(v.title) > 25 else v.title,
                        'Views': v.views,
                        'Watch Time (min)': v.watch_time_minutes,
                        'Type': v.video_type.title(),
                        'Channel': v.channel_name
                    }
                    for v in all_videos[:50] if v.watch_time_minutes > 0
                ])
                
                if not df_performance.empty:
                    fig_scatter = px.scatter(
                        df_performance,
                        x='Views',
                        y='Watch Time (min)',
                        color='Type',
                        size='Views',
                        hover_data=['Title', 'Channel'],
                        title=f"📈 Views vs Watch Time ({period_text})",
                        height=500,
                        color_discrete_map={'Video': '#667eea', 'Short': '#f093fb'}
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)
                else:
                    st.info("Watch time data not available for visualization")
        else:
            st.warning(f"No content found for the selected time period: {period_text}")
    
    def render_channel_dashboard(self, service, channel_key, days, period_text):
        """Render detailed channel dashboard"""
        config = service.youtube_services[channel_key]['config']
        channel_name = config.get('name', f'Channel {channel_key}')
        
        # Back button
        if st.button("← Back to Summary", key="back_btn", type="secondary"):
            st.session_state.selected_channel = None
            st.rerun()
        
        st.markdown(f"## 📺 {channel_name} - Detailed Analytics ({period_text})")
        
        # Get comprehensive analytics using Analytics API as primary source
        with st.spinner(f"Loading detailed analytics for {channel_name}..."):
            channel_analytics = service.get_channel_analytics_pure(channel_key, days)
            video_analytics = service.get_videos_analytics_pure(channel_key, days)
            audience_data = service.get_audience_analytics(channel_key, days)
        
        if not channel_analytics:
            st.error(f"Could not load analytics for {channel_name}")
            return
        
        # Key Metrics Dashboard
        st.markdown("### 📊 Key Performance Metrics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🎬 Videos", f"{channel_analytics.total_videos_count:,}")
            st.metric("🎵 Shorts", f"{channel_analytics.total_shorts_count:,}")
        
        with col2:
            st.metric("👀 Views", f"{channel_analytics.period_views:,}", 
                     help=f"Total views in {period_text}")
            st.metric("⏱️ Watch Time", f"{channel_analytics.period_watch_time_hours:.1f}h")
        
        with col3:
            st.metric("📊 Avg Views/Video", f"{channel_analytics.avg_views_per_video:.0f}")
            st.metric("📊 Avg Views/Short", f"{channel_analytics.avg_views_per_short:.0f}")
        
        with col4:
            st.metric("👥 Subscribers", f"{channel_analytics.total_subscribers:,}")
            st.metric("📈 Gained", f"+{channel_analytics.period_subscribers_gained}", 
                     delta=f"in {period_text}")
        
        # Additional metrics
        col5, col6, col7 = st.columns(3)
        with col5:
            st.metric("👍 Likes", f"{channel_analytics.period_likes:,}")
        with col6:
            st.metric("💬 Comments", f"{channel_analytics.period_comments:,}")
        with col7:
            avg_duration_seconds = channel_analytics.avg_view_duration
            st.metric("⏰ Avg View Duration", f"{avg_duration_seconds:.0f}s")
        
        # Video Performance Analysis
        if video_analytics:
            self.render_video_performance_charts(video_analytics, channel_name, period_text)
            self.render_top_videos_table(video_analytics[:10], channel_name, period_text)
        
        # Audience Analytics
        self.render_audience_analytics(audience_data, channel_name, period_text)
    
    def render_video_performance_charts(self, video_analytics, channel_name, period_text):
        """Render video performance charts"""
        st.markdown(f"### 📈 Content Performance Analysis ({period_text})")
        
        # Sort by views
        top_videos = sorted(video_analytics, key=lambda x: x.views, reverse=True)[:15]
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Top performing videos
            df_top = pd.DataFrame([
                {
                    'Title': v.title[:30] + '...' if len(v.title) > 30 else v.title,
                    'Views': v.views,
                    'Type': v.video_type.title()
                }
                for v in top_videos
            ])
            
            fig_views = px.bar(
                df_top,
                x='Views',
                y='Title',
                color='Type',
                title=f"📊 Top 15 Videos - {channel_name}",
                orientation='h',
                height=600,
                color_discrete_map={'Video': '#667eea', 'Short': '#f093fb'}
            )
            fig_views.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_views, use_container_width=True)
        
        with col2:
            # Performance metrics comparison
            df_metrics = pd.DataFrame([
                {
                    'Title': v.title[:20] + '...' if len(v.title) > 20 else v.title,
                    'Views': v.views,
                    'Watch Time': v.watch_time_minutes,
                    'Likes': v.likes,
                    'Comments': v.comments,
                    'Type': v.video_type.title()
                }
                for v in top_videos if v.watch_time_minutes > 0
            ])
            
            if not df_metrics.empty:
                fig_metrics = px.scatter(
                    df_metrics,
                    x='Views',
                    y='Watch Time',
                    size='Likes',
                    color='Type',
                    hover_data=['Title', 'Comments'],
                    title=f"📈 Performance Correlation - {channel_name}",
                    height=600,
                    color_discrete_map={'Video': '#667eea', 'Short': '#f093fb'}
                )
                st.plotly_chart(fig_metrics, use_container_width=True)
            else:
                st.info("Detailed metrics data not available")
        
        # Timeline analysis
        st.markdown(f"### 📅 Content Timeline ({period_text})")
        
        timeline_data = []
        for v in video_analytics:
            try:
                if v.published_at:
                    date_str = v.published_at.split('T')[0] if 'T' in v.published_at else v.published_at[:10]
                    video_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    timeline_data.append({
                        'Date': video_date,
                        'Views': v.views,
                        'Type': v.video_type.title(),
                        'Title': v.title
                    })
            except Exception as e:
                logger.warning(f"Error parsing date: {e}")
                continue
        
        if timeline_data:
            df_timeline = pd.DataFrame(timeline_data)
            df_timeline_agg = df_timeline.groupby(['Date', 'Type'])['Views'].sum().reset_index()
            
            fig_timeline = px.line(
                df_timeline_agg,
                x='Date',
                y='Views',
                color='Type',
                title=f"📊 Views Over Time - {channel_name}",
                height=400,
                color_discrete_map={'Video': '#667eea', 'Short': '#f093fb'}
            )
            st.plotly_chart(fig_timeline, use_container_width=True)
        else:
            st.info("Timeline data not available")
    
    def render_top_videos_table(self, videos, channel_name, period_text):
        """Render detailed top videos table"""
        st.markdown(f"### 🏅 Top 10 Performing Videos - {channel_name} ({period_text})")
        
        for i, video in enumerate(videos, 1):
            with st.container():
                col1, col2, col3 = st.columns([1, 4, 2])
                
                with col1:
                    if video.thumbnail_url:
                        st.image(video.thumbnail_url, width=120)
                    else:
                        st.markdown(f"**#{i}**")
                
                with col2:
                    st.markdown(f"""
                    **{video.title}**
                    
                    🎬 Type: **{video.video_type.title()}**  
                    📅 Published: **{video.published_at[:10] if video.published_at else 'Unknown'}**  
                    🔗 [Watch Video](https://youtube.com/watch?v={video.video_id})
                    """)
                
                with col3:
                    # Calculate performance metrics
                    try:
                        if video.published_at:
                            date_str = video.published_at.split('T')[0] if 'T' in video.published_at else video.published_at[:10]
                            published_dt = datetime.strptime(date_str, '%Y-%m-%d')
                            days_since = max(1, (datetime.now() - published_dt).days)
                            views_per_day = video.views / days_since
                        else:
                            views_per_day = 0
                    except:
                        views_per_day = 0
                    
                    engagement_rate = ((video.likes + video.comments) / max(video.views, 1)) * 100 if video.views > 0 else 0
                    
                    st.markdown(f"""
                    **📊 Analytics:**  
                    👀 **{video.views:,}** views  
                    📈 **{views_per_day:.0f}** views/day  
                    💬 **{engagement_rate:.2f}%** engagement  
                    ⏱️ **{video.watch_time_minutes:.0f}** min watched  
                    👍 **{video.likes:,}** likes  
                    💬 **{video.comments:,}** comments
                    """)
                
                st.markdown("---")
    
    def render_audience_analytics(self, audience_data, channel_name, period_text):
        """Render comprehensive audience analytics"""
        st.markdown(f"### 👥 Audience Analytics - {channel_name} ({period_text})")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Traffic Sources
            st.markdown("#### 🔍 How Viewers Find Your Content")
            if audience_data.traffic_sources:
                df_traffic = pd.DataFrame(audience_data.traffic_sources)
                
                # Map source types to readable names
                source_mapping = {
                    'YT_SEARCH': 'YouTube Search',
                    'SUGGESTED_VIDEO': 'Suggested Videos',
                    'BROWSE': 'Browse Features',
                    'EXTERNAL': 'External Sources',
                    'DIRECT': 'Direct Traffic',
                    'NOTIFICATION': 'Notifications',
                    'PLAYLIST': 'Playlists'
                }
                
                df_traffic['source'] = df_traffic['source'].map(source_mapping).fillna(df_traffic['source'])
                
                fig_traffic = px.pie(
                    df_traffic,
                    values='views',
                    names='source',
                    title="Traffic Sources",
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                st.plotly_chart(fig_traffic, use_container_width=True)
            else:
                st.info("Traffic source data not available")
            
            # Geography
            st.markdown("#### 🌍 Top Countries")
            if audience_data.geography:
                df_geo = pd.DataFrame(audience_data.geography)
                
                fig_geo = px.bar(
                    df_geo.head(10),
                    x='views',
                    y='country',
                    orientation='h',
                    title="Top 10 Countries by Views",
                    color='views',
                    color_continuous_scale='Blues'
                )
                fig_geo.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig_geo, use_container_width=True)
            else:
                st.info("Geographic data not available")
        
        with col2:
            # Device Types
            st.markdown("#### 📱 Device Usage")
            if audience_data.device_types:
                df_devices = pd.DataFrame(audience_data.device_types)
                
                # Map device types
                device_mapping = {
                    'MOBILE': 'Mobile',
                    'DESKTOP': 'Desktop',
                    'TABLET': 'Tablet',
                    'TV': 'TV/Smart TV'
                }
                
                df_devices['device'] = df_devices['device'].map(device_mapping).fillna(df_devices['device'])
                
                fig_devices = px.pie(
                    df_devices,
                    values='views',
                    names='device',
                    title="Device Distribution",
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                st.plotly_chart(fig_devices, use_container_width=True)
            else:
                st.info("Device data not available")
            
            # Age and Gender
            st.markdown("#### 👫 Demographics")
            if audience_data.age_gender:
                df_demo = pd.DataFrame(audience_data.age_gender)
                
                if not df_demo.empty:
                    # Create summary by age group
                    df_age_summary = df_demo.groupby('age_group')['percentage'].sum().reset_index()
                    df_age_summary = df_age_summary.sort_values('percentage', ascending=False)
                    
                    fig_demo = px.bar(
                        df_age_summary,
                        x='age_group',
                        y='percentage',
                        title="Audience by Age Group (%)",
                        color='percentage',
                        color_continuous_scale='Viridis'
                    )
                    st.plotly_chart(fig_demo, use_container_width=True)
                else:
                    st.info("Demographic data not available")
            else:
                st.info("Demographic data not available")
    
    def render_export_options(self, service, days, period_text):
        """Render comprehensive export options"""
        st.markdown(f"## 📥 Export Analytics Data ({period_text})")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("📊 Export Summary", type="secondary", use_container_width=True):
                export_data = []
                
                for channel_key in service.youtube_services.keys():
                    config = service.youtube_services[channel_key]['config']
                    channel_name = config.get('name', f'Channel {channel_key}')
                    
                    channel_analytics = service.get_channel_analytics(channel_key, days)
                    
                    if channel_analytics:
                        export_data.append({
                            'Channel': channel_name,
                            'Time Period': period_text,
                            'Videos': channel_analytics.total_videos_count,
                            'Shorts': channel_analytics.total_shorts_count,
                            'Views': channel_analytics.period_views,
                            'Watch Time Hours': channel_analytics.period_watch_time_hours,
                            'Likes': channel_analytics.period_likes,
                            'Comments': channel_analytics.period_comments,
                            'Subscribers': channel_analytics.total_subscribers,
                            'Subscribers Gained': channel_analytics.period_subscribers_gained,
                            'Avg Views per Video': channel_analytics.avg_views_per_video,
                            'Avg Views per Short': channel_analytics.avg_views_per_short,
                            'Avg View Duration': channel_analytics.avg_view_duration
                        })
                
                if export_data:
                    df_export = pd.DataFrame(export_data)
                    csv = df_export.to_csv(index=False)
                    st.download_button(
                        "📥 Download Summary CSV",
                        csv,
                        f"youtube_analytics_summary_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        "text/csv",
                        key="summary_download"
                    )
        
        with col2:
            if st.button("🎬 Export Videos", type="secondary", use_container_width=True):
                all_videos_data = []
                
                for channel_key in service.youtube_services.keys():
                    config = service.youtube_services[channel_key]['config']
                    channel_name = config.get('name', f'Channel {channel_key}')
                    
                    video_analytics = service.get_videos_analytics(channel_key, days)
                    
                    for video in video_analytics:
                        all_videos_data.append({
                            'Channel': channel_name,
                            'Time Period': period_text,
                            'Video ID': video.video_id,
                            'Title': video.title,
                            'Type': video.video_type.title(),
                            'Published Date': video.published_at[:10] if video.published_at else 'Unknown',
                            'Views': video.views,
                            'Watch Time Minutes': video.watch_time_minutes,
                            'Average View Duration': video.average_view_duration,
                            'Likes': video.likes,
                            'Comments': video.comments,
                            'Shares': video.shares,
                            'Subscribers Gained': video.subscribers_gained,
                            'URL': f"https://youtube.com/watch?v={video.video_id}"
                        })
                
                if all_videos_data:
                    df_videos = pd.DataFrame(all_videos_data)
                    csv_videos = df_videos.to_csv(index=False)
                    st.download_button(
                        "📥 Download Videos CSV",
                        csv_videos,
                        f"youtube_videos_analytics_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        "text/csv",
                        key="videos_download"
                    )
        
        with col3:
            if st.button("🏆 Export Top Content", type="secondary", use_container_width=True):
                all_videos = []
                
                for channel_key in service.youtube_services.keys():
                    video_analytics = service.get_videos_analytics(channel_key, days)
                    all_videos.extend(video_analytics)
                
                # Sort by views and get top 50
                all_videos.sort(key=lambda x: x.views, reverse=True)
                top_videos = all_videos[:50]
                
                top_content_data = []
                for i, video in enumerate(top_videos, 1):
                    try:
                        if video.published_at:
                            date_str = video.published_at.split('T')[0] if 'T' in video.published_at else video.published_at[:10]
                            published_dt = datetime.strptime(date_str, '%Y-%m-%d')
                            days_since = max(1, (datetime.now() - published_dt).days)
                            views_per_day = round(video.views / days_since, 0)
                        else:
                            views_per_day = 0
                    except:
                        views_per_day = 0
                    
                    engagement_rate = ((video.likes + video.comments) / max(video.views, 1)) * 100 if video.views > 0 else 0
                    
                    top_content_data.append({
                        'Rank': i,
                        'Time Period': period_text,
                        'Channel': video.channel_name,
                        'Title': video.title,
                        'Type': video.video_type.title(),
                        'Views': video.views,
                        'Views per Day': views_per_day,
                        'Watch Time Minutes': video.watch_time_minutes,
                        'Engagement Rate %': round(engagement_rate, 2),
                        'Likes': video.likes,
                        'Comments': video.comments,
                        'Published': video.published_at[:10] if video.published_at else 'Unknown',
                        'URL': f"https://youtube.com/watch?v={video.video_id}"
                    })
                
                if top_content_data:
                    df_top = pd.DataFrame(top_content_data)
                    csv_top = df_top.to_csv(index=False)
                    st.download_button(
                        "📥 Download Top Content CSV",
                        csv_top,
                        f"youtube_top_content_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        "text/csv",
                        key="top_download"
                    )
        
        with col4:
            if st.button("📊 Export Audience Data", type="secondary", use_container_width=True):
                audience_export_data = []
                
                for channel_key in service.youtube_services.keys():
                    config = service.youtube_services[channel_key]['config']
                    channel_name = config.get('name', f'Channel {channel_key}')
                    
                    audience_data = service.get_audience_analytics(channel_key, days)
                    
                    # Traffic sources
                    for item in audience_data.traffic_sources:
                        audience_export_data.append({
                            'Channel': channel_name,
                            'Time Period': period_text,
                            'Data Type': 'Traffic Source',
                            'Category': item['source'],
                            'Value': item['views'],
                            'Metric': 'Views'
                        })
                    
                    # Device types
                    for item in audience_data.device_types:
                        audience_export_data.append({
                            'Channel': channel_name,
                            'Time Period': period_text,
                            'Data Type': 'Device Type',
                            'Category': item['device'],
                            'Value': item['views'],
                            'Metric': 'Views'
                        })
                    
                    # Demographics
                    for item in audience_data.age_gender:
                        audience_export_data.append({
                            'Channel': channel_name,
                            'Time Period': period_text,
                            'Data Type': 'Demographics',
                            'Category': f"{item['age_group']} - {item['gender']}",
                            'Value': item['percentage'],
                            'Metric': 'Percentage'
                        })
                
                if audience_export_data:
                    df_audience = pd.DataFrame(audience_export_data)
                    csv_audience = df_audience.to_csv(index=False)
                    st.download_button(
                        "📥 Download Audience CSV",
                        csv_audience,
                        f"youtube_audience_analytics_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        "text/csv",
                        key="audience_download"
                    )
    
    def run(self):
        """Main dashboard runner"""
        # Load configuration
        system_config = self.load_config()
        
        # Initialize service
        service = self.initialize_service(system_config)
        
        # Check authentication
        if not service.youtube_services:
            st.error("❌ No channels authenticated! Please check your credentials.")
            st.stop()
        
        # Render header
        self.render_header()
        
        # Render sidebar
        days, period_text = self.render_sidebar()
        
        # Main content routing
        try:
            if st.session_state.selected_channel is None:
                # Show summary dashboard
                self.render_summary_dashboard(service, days, period_text)
                
                st.markdown("---")
                
                # Export options
                self.render_export_options(service, days, period_text)
            else:
                # Show channel-specific dashboard
                self.render_channel_dashboard(
                    service, 
                    st.session_state.selected_channel, 
                    days, 
                    period_text
                )
                
                st.markdown("---")
                
                # Export options
                self.render_export_options(service, days, period_text)
        
        except Exception as e:
            st.error(f"❌ Error loading analytics data: {e}")
            logger.error(f"Dashboard error: {e}", exc_info=True)
            st.markdown("### 🔧 Troubleshooting:")
            st.markdown("- Check internet connection")
            st.markdown("- Verify YouTube Analytics API permissions")
            st.markdown("- Ensure proper channel authentication")
            st.markdown("- Check API quota limits")
        
        # Footer
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; color: #666; padding: 2rem;">
            <p>📊 YouTube Analytics Dashboard - Powered by YouTube Analytics API v2</p>
            <p>Real-time performance insights with comprehensive audience analytics</p>
        </div>
        """, unsafe_allow_html=True)

# Main execution
if __name__ == "__main__":
    import sys
    import subprocess
    
    # Check if running with streamlit
    if 'streamlit' not in sys.modules:
        print("This is a Streamlit application. Running with streamlit...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__] + sys.argv[1:])
    else:
        dashboard = YouTubeDashboard()
        dashboard.run()