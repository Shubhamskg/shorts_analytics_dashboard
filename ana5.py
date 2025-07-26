import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import time
from pathlib import Path
import os
import tempfile
import hashlib
import base64

try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.errors import HttpError
except ImportError as e:
    st.error(f"❌ Missing required libraries. Please install: pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2")
    st.stop()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment detection
# IS_STREAMLIT_CLOUD = (
#     os.getenv('STREAMLIT_SHARING') == 'true' or
#     'streamlit.app' in os.getenv('HOSTNAME', '') or
#     os.getenv('STREAMLIT_CLOUD', False) or
#     'streamlit' in os.getenv('HOME', '').lower()
# )
IS_STREAMLIT_CLOUD=True
# Security constants
MAX_RETRY_ATTEMPTS = 3
RATE_LIMIT_DELAY = 1.0
TOKEN_REFRESH_BUFFER = 300  # 5 minutes

# Channel Configuration - Update these with your actual channel IDs
UPLOAD_CHANNELS = [
    {
        "name": "Dental Advisor",
        "id": "UCsw6IbObS8mtNQqbbZSKvog",  # Replace with your actual channel ID
        "credentials_key": "dental_advisor_credentials",
        "token_key": "dental_advisor_token",
        "credentials_file": "dental_advisor_credentials.json",
        "token_file": "dental_advisor_token.json",
        "description": "Primary channel for MIH educational content",
        "content_focus": "primary_education",
        "color": "#4facfe"
    },
    {
        "name": "MIH",
        "id": "UCt56aIAG8gNuKM0hJpWYm9Q",  # Replace with your actual channel ID
        "credentials_key": "mih_credentials",
        "token_key": "mih_token",
        "credentials_file": "mih_credentials.json",
        "token_file": "mih_token.json",
        "description": "Specialized MIH treatment and care guidance",
        "content_focus": "treatment_focused",
        "color": "#00f2fe"
    },
    {
        "name": "Enamel Hypoplasia",
        "id": "UCnBJEdDIsC7b3oAvaBPje3Q",  # Replace with your actual channel ID
        "credentials_key": "enamel_hypoplasia_credentials",
        "token_key": "enamel_hypoplasia_token",
        "credentials_file": "enamel_hypoplasia_credentials.json",
        "token_file": "enamel_hypoplasia_token.json",
        "description": "Comprehensive pediatric dental care and whitening",
        "content_focus": "pediatric_care",
        "color": "#a8edea"
    }
]

@dataclass
class ChannelAnalytics:
    """Data class for channel analytics"""
    channel_id: str
    channel_name: str
    period_views: int
    period_watch_time_hours: float
    period_subscribers_gained: int
    period_likes: int
    period_comments: int
    period_shares: int
    average_view_duration: float
    estimated_revenue: float
    cpm: float
    content_focus: str
    description: str
    auth_status: str
    color: str = "#4facfe"

@dataclass
class AudienceData:
    """Data class for audience analytics"""
    age_gender: List[Dict]
    device_types: List[Dict]
    traffic_sources: List[Dict]
    geography: List[Dict]
    playback_locations: List[Dict]

@dataclass
class TimeSeriesData:
    """Data class for time series analytics"""
    dates: List[str]
    views: List[int]
    watch_time: List[float]
    subscribers: List[int]
    estimated_revenue: List[float]

@dataclass
class ChannelAuth:
    """Data class for channel authentication status"""
    channel_id: str
    channel_name: str
    is_authenticated: bool
    analytics_service: Optional[object]
    error_message: Optional[str]
    last_authenticated: Optional[datetime] = None

class SecureCredentialsManager:
    """Secure credentials management for both local and cloud environments"""
    
    @staticmethod
    def validate_credentials_format(credentials_data: Dict) -> bool:
        """Validate OAuth credentials format"""
        required_fields = ['client_id', 'client_secret', 'auth_uri', 'token_uri']
        
        if 'installed' in credentials_data:
            creds_section = credentials_data['installed']
        elif 'web' in credentials_data:
            creds_section = credentials_data['web']
        else:
            creds_section = credentials_data
        
        return all(field in creds_section for field in required_fields)
    
    @staticmethod
    def validate_token_format(token_data: Dict) -> bool:
        """Validate token format"""
        required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret']
        return all(field in token_data for field in required_fields)
    
    @staticmethod
    def get_credentials_from_secrets(credentials_key: str) -> Optional[Dict]:
        """Safely get credentials from Streamlit secrets"""
        try:
            if not hasattr(st, 'secrets'):
                return None
            
            if credentials_key not in st.secrets:
                logger.warning(f"Credentials key '{credentials_key}' not found in secrets")
                return None
            
            creds_dict = dict(st.secrets[credentials_key])
            
            # Validate format
            if not SecureCredentialsManager.validate_credentials_format(creds_dict):
                logger.error(f"Invalid credentials format for {credentials_key}")
                return None
            
            # Convert to proper OAuth format if needed
            if 'installed' not in creds_dict and 'web' not in creds_dict:
                return {"installed": creds_dict}
            
            return creds_dict
            
        except Exception as e:
            logger.error(f"Error reading credentials from secrets: {e}")
            return None
    
    @staticmethod
    def get_token_from_secrets(token_key: str) -> Optional[Dict]:
        """Safely get token from Streamlit secrets"""
        try:
            if not hasattr(st, 'secrets'):
                return None
            
            if token_key not in st.secrets:
                logger.warning(f"Token key '{token_key}' not found in secrets")
                return None
            
            token_dict = dict(st.secrets[token_key])
            
            # Validate format
            if not SecureCredentialsManager.validate_token_format(token_dict):
                logger.error(f"Invalid token format for {token_key}")
                return None
            
            return token_dict
            
        except Exception as e:
            logger.error(f"Error reading token from secrets: {e}")
            return None
    
    @staticmethod
    def create_temp_credentials_file(credentials_dict: Dict) -> Optional[str]:
        """Create secure temporary credentials file"""
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.json', 
                delete=False,
                prefix='gcp_creds_'
            )
            json.dump(credentials_dict, temp_file, indent=2)
            temp_file.close()
            
            # Set restrictive permissions
            os.chmod(temp_file.name, 0o600)
            
            return temp_file.name
        except Exception as e:
            logger.error(f"Error creating temporary credentials file: {e}")
            return None
    
    @staticmethod
    def cleanup_temp_file(file_path: str):
        """Securely cleanup temporary files"""
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")

class YouTubeAnalyticsService:
    """Production-ready YouTube Analytics API service"""
    
    SCOPES = ['https://www.googleapis.com/auth/yt-analytics.readonly']
    API_SERVICE_NAME = 'youtubeAnalytics'
    API_VERSION = 'v2'
    
    def __init__(self):
        self.channels = UPLOAD_CHANNELS
        self.channel_auth_status = {}
        self.credentials_manager = SecureCredentialsManager()
        self._rate_limit_tracker = {}
        
        # Initialize authentication
        self._authenticate_all_channels()
    
    def _check_rate_limit(self, channel_id: str) -> bool:
        """Check if we're hitting rate limits"""
        current_time = time.time()
        last_request = self._rate_limit_tracker.get(channel_id, 0)
        
        if current_time - last_request < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY)
        
        self._rate_limit_tracker[channel_id] = current_time
        return True
    
    def _handle_api_error(self, error: Exception, context: str) -> str:
        """Handle and categorize API errors"""
        if isinstance(error, HttpError):
            status_code = error.resp.status
            
            if status_code == 403:
                return f"Access denied: Check channel permissions and API quota ({context})"
            elif status_code == 401:
                return f"Authentication failed: Token may be expired ({context})"
            elif status_code == 429:
                return f"Rate limit exceeded: Too many requests ({context})"
            elif status_code == 404:
                return f"Channel not found: Verify channel ID ({context})"
            else:
                return f"API error {status_code}: {error} ({context})"
        else:
            return f"Unexpected error: {error} ({context})"
    
    def _authenticate_channel(self, channel_config: Dict) -> ChannelAuth:
        """Authenticate a single channel with comprehensive error handling"""
        channel_id = channel_config['id']
        channel_name = channel_config['name']
        
        try:
            creds = None
            temp_creds_file = None
            
            if IS_STREAMLIT_CLOUD:
                logger.info(f"🌐 Authenticating {channel_name} using Streamlit Secrets...")
                
                # Get token from secrets
                token_dict = self.credentials_manager.get_token_from_secrets(
                    channel_config['token_key']
                )
                
                if token_dict:
                    try:
                        creds = Credentials(
                            token=token_dict.get('token'),
                            refresh_token=token_dict.get('refresh_token'),
                            token_uri=token_dict.get('token_uri'),
                            client_id=token_dict.get('client_id'),
                            client_secret=token_dict.get('client_secret'),
                            scopes=token_dict.get('scopes', self.SCOPES)
                        )
                        
                        # Check if token needs refresh
                        if creds.expired and creds.refresh_token:
                            logger.info(f"🔄 Refreshing token for {channel_name}...")
                            creds.refresh(Request())
                            logger.info(f"✅ Token refreshed for {channel_name}")
                    
                    except Exception as e:
                        logger.error(f"❌ Failed to use token from secrets for {channel_name}: {e}")
                        creds = None
                
                if not creds or not creds.valid:
                    error_msg = (
                        f"No valid token in Streamlit Secrets for {channel_name}. "
                        f"Please authenticate locally first and update the '{channel_config['token_key']}' secret."
                    )
                    return ChannelAuth(
                        channel_id=channel_id,
                        channel_name=channel_name,
                        is_authenticated=False,
                        analytics_service=None,
                        error_message=error_msg
                    )
            
            else:
                logger.info(f"💻 Authenticating {channel_name} using local files...")
                
                credentials_file = channel_config['credentials_file']
                token_file = channel_config['token_file']
                
                # Load existing token
                if Path(token_file).exists():
                    try:
                        with open(token_file, 'r') as f:
                            token_data = json.load(f)
                        
                        if self.credentials_manager.validate_token_format(token_data):
                            creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
                        else:
                            logger.warning(f"Invalid token format in {token_file}")
                            creds = None
                    except Exception as e:
                        logger.warning(f"Failed to load token from {token_file}: {e}")
                        creds = None
                
                # Handle expired or missing credentials
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        try:
                            creds.refresh(Request())
                            logger.info(f"✅ Refreshed credentials for {channel_name}")
                        except Exception as e:
                            logger.warning(f"Failed to refresh token: {e}")
                            creds = None
                    
                    # Perform OAuth flow if needed
                    if not creds:
                        if not Path(credentials_file).exists():
                            error_msg = (
                                f"Credentials file not found: {credentials_file}. "
                                f"Please download OAuth credentials from Google Cloud Console."
                            )
                            return ChannelAuth(
                                channel_id=channel_id,
                                channel_name=channel_name,
                                is_authenticated=False,
                                analytics_service=None,
                                error_message=error_msg
                            )
                        
                        try:
                            # Validate credentials file format
                            with open(credentials_file, 'r') as f:
                                creds_data = json.load(f)
                            
                            if not self.credentials_manager.validate_credentials_format(creds_data):
                                error_msg = f"Invalid credentials file format: {credentials_file}"
                                return ChannelAuth(
                                    channel_id=channel_id,
                                    channel_name=channel_name,
                                    is_authenticated=False,
                                    analytics_service=None,
                                    error_message=error_msg
                                )
                            
                            # Perform OAuth flow
                            flow = InstalledAppFlow.from_client_secrets_file(
                                credentials_file, 
                                self.SCOPES
                            )
                            creds = flow.run_local_server(port=0)
                            logger.info(f"✅ Completed OAuth flow for {channel_name}")
                            
                        except Exception as e:
                            error_msg = f"OAuth flow failed for {channel_name}: {e}"
                            return ChannelAuth(
                                channel_id=channel_id,
                                channel_name=channel_name,
                                is_authenticated=False,
                                analytics_service=None,
                                error_message=error_msg
                            )
                    
                    # Save credentials
                    if creds:
                        try:
                            with open(token_file, 'w') as token:
                                token.write(creds.to_json())
                            # Set restrictive permissions
                            os.chmod(token_file, 0o600)
                            logger.info(f"💾 Saved credentials for {channel_name}")
                        except Exception as e:
                            logger.warning(f"Failed to save token: {e}")
            
            # Build analytics service
            if creds and creds.valid:
                try:
                    analytics_service = build(
                        self.API_SERVICE_NAME,
                        self.API_VERSION,
                        credentials=creds,
                        cache_discovery=False
                    )
                    
                    # Test authentication with minimal query
                    test_start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                    test_end_date = datetime.now().strftime('%Y-%m-%d')
                    
                    test_query = analytics_service.reports().query(
                        ids=f'channel=={channel_id}',
                        startDate=test_start_date,
                        endDate=test_end_date,
                        metrics='views',
                        maxResults=1
                    ).execute()
                    
                    logger.info(f"✅ Successfully authenticated {channel_name}")
                    return ChannelAuth(
                        channel_id=channel_id,
                        channel_name=channel_name,
                        is_authenticated=True,
                        analytics_service=analytics_service,
                        error_message=None,
                        last_authenticated=datetime.now()
                    )
                    
                except Exception as e:
                    error_msg = self._handle_api_error(e, f"testing access for {channel_name}")
                    return ChannelAuth(
                        channel_id=channel_id,
                        channel_name=channel_name,
                        is_authenticated=False,
                        analytics_service=None,
                        error_message=error_msg
                    )
            else:
                return ChannelAuth(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    is_authenticated=False,
                    analytics_service=None,
                    error_message="Failed to obtain valid credentials"
                )
        
        except Exception as e:
            error_msg = f"Unexpected error authenticating {channel_name}: {e}"
            logger.error(error_msg)
            return ChannelAuth(
                channel_id=channel_id,
                channel_name=channel_name,
                is_authenticated=False,
                analytics_service=None,
                error_message=error_msg
            )
        
        finally:
            # Cleanup temporary files
            if temp_creds_file:
                self.credentials_manager.cleanup_temp_file(temp_creds_file)
    
    def _authenticate_all_channels(self):
        """Authenticate all channels with progress tracking"""
        logger.info(f"🚀 Starting authentication for {len(self.channels)} channels...")
        logger.info(f"Environment: {'Streamlit Cloud' if IS_STREAMLIT_CLOUD else 'Local Development'}")
        
        for i, channel_config in enumerate(self.channels):
            channel_name = channel_config['name']
            logger.info(f"[{i+1}/{len(self.channels)}] Authenticating {channel_name}...")
            
            auth_result = self._authenticate_channel(channel_config)
            self.channel_auth_status[channel_config['id']] = auth_result
            
            if auth_result.is_authenticated:
                logger.info(f"✅ {channel_name} authenticated successfully")
            else:
                logger.error(f"❌ {channel_name} failed: {auth_result.error_message}")
        
        # Summary
        authenticated_count = sum(
            1 for auth in self.channel_auth_status.values() 
            if auth.is_authenticated
        )
        total_count = len(self.channels)
        
        logger.info(f"🎯 Authentication Summary: {authenticated_count}/{total_count} channels authenticated")
        
        if authenticated_count == 0:
            logger.warning("⚠️ No channels authenticated - dashboard will have limited functionality")
        elif authenticated_count < total_count:
            logger.warning(f"⚠️ Partial authentication - {total_count - authenticated_count} channels need attention")
        else:
            logger.info("🎉 All channels authenticated successfully!")
    
    def get_authenticated_channels(self) -> List[str]:
        """Get list of successfully authenticated channel IDs"""
        return [
            channel_id for channel_id, auth in self.channel_auth_status.items()
            if auth.is_authenticated
        ]
    
    def get_authentication_status(self) -> Dict[str, ChannelAuth]:
        """Get authentication status for all channels"""
        return self.channel_auth_status
    
    def get_analytics_service(self, channel_id: str) -> Optional[object]:
        """Get analytics service for a specific channel"""
        auth_status = self.channel_auth_status.get(channel_id)
        if auth_status and auth_status.is_authenticated:
            return auth_status.analytics_service
        return None
    
    def get_date_range(self, days: int) -> Tuple[str, str]:
        """Get start and end dates for analytics queries"""
        if days == -1:  # All time
            start_date = '2005-04-23'  # YouTube's launch date
        else:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        return start_date, end_date
    
    def get_channel_analytics(self, channel_id: str, channel_name: str, days: int = 30) -> Optional[ChannelAnalytics]:
        """Get comprehensive channel analytics with retry logic"""
        analytics_service = self.get_analytics_service(channel_id)
        auth_status = self.channel_auth_status.get(channel_id)
        
        # Find channel config for color and metadata
        channel_config = next((ch for ch in self.channels if ch['id'] == channel_id), {})
        
        if not analytics_service:
            return ChannelAnalytics(
                channel_id=channel_id,
                channel_name=channel_name,
                period_views=0,
                period_watch_time_hours=0,
                period_subscribers_gained=0,
                period_likes=0,
                period_comments=0,
                period_shares=0,
                average_view_duration=0,
                estimated_revenue=0,
                cpm=0,
                content_focus=channel_config.get('content_focus', 'general'),
                description=channel_config.get('description', 'Dental education content'),
                auth_status=f"Not authenticated: {auth_status.error_message if auth_status else 'Unknown error'}",
                color=channel_config.get('color', '#4facfe')
            )
        
        # Rate limiting
        self._check_rate_limit(channel_id)
        
        try:
            start_date, end_date = self.get_date_range(days)
            logger.info(f"📊 Getting analytics for {channel_name} ({start_date} to {end_date})")
            
            # Try comprehensive metrics first
            analytics_data = None
            for attempt in range(MAX_RETRY_ATTEMPTS):
                try:
                    main_metrics = analytics_service.reports().query(
                        ids=f'channel=={channel_id}',
                        startDate=start_date,
                        endDate=end_date,
                        metrics='views,estimatedMinutesWatched,subscribersGained,likes,comments,shares,averageViewDuration'
                    ).execute()
                    
                    analytics_data = main_metrics.get('rows', [[0, 0, 0, 0, 0, 0, 0]])[0]
                    break
                    
                except HttpError as e:
                    if e.resp.status == 429 and attempt < MAX_RETRY_ATTEMPTS - 1:
                        wait_time = (2 ** attempt) * RATE_LIMIT_DELAY
                        logger.warning(f"Rate limited, waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise e
            
            # Fallback to basic metrics if comprehensive fails
            if analytics_data is None:
                logger.warning(f"⚠️ Falling back to basic metrics for {channel_name}")
                try:
                    basic_metrics = analytics_service.reports().query(
                        ids=f'channel=={channel_id}',
                        startDate=start_date,
                        endDate=end_date,
                        metrics='views,estimatedMinutesWatched,subscribersGained'
                    ).execute()
                    
                    basic_data = basic_metrics.get('rows', [[0, 0, 0]])[0]
                    analytics_data = basic_data + [0, 0, 0, 0]  # Pad with zeros
                    
                except Exception as e2:
                    logger.error(f"❌ Failed to get basic metrics for {channel_name}: {e2}")
                    analytics_data = [0, 0, 0, 0, 0, 0, 0]
            
            return ChannelAnalytics(
                channel_id=channel_id,
                channel_name=channel_name,
                period_views=analytics_data[0] if len(analytics_data) > 0 else 0,
                period_watch_time_hours=(analytics_data[1] if len(analytics_data) > 1 else 0) / 60,
                period_subscribers_gained=analytics_data[2] if len(analytics_data) > 2 else 0,
                period_likes=analytics_data[3] if len(analytics_data) > 3 else 0,
                period_comments=analytics_data[4] if len(analytics_data) > 4 else 0,
                period_shares=analytics_data[5] if len(analytics_data) > 5 else 0,
                average_view_duration=analytics_data[6] if len(analytics_data) > 6 else 0,
                estimated_revenue=0,  # Revenue requires special permissions
                cpm=0,
                content_focus=channel_config.get('content_focus', 'general'),
                description=channel_config.get('description', 'Dental education content'),
                auth_status="Authenticated",
                color=channel_config.get('color', '#4facfe')
            )
            
        except Exception as e:
            error_msg = self._handle_api_error(e, f"getting analytics for {channel_name}")
            logger.error(f"❌ {error_msg}")
            return None
    
    def get_time_series_data(self, channel_id: str, days: int = 30) -> TimeSeriesData:
        """Get time series data with error handling"""
        analytics_service = self.get_analytics_service(channel_id)
        
        if not analytics_service:
            return TimeSeriesData([], [], [], [], [])
        
        self._check_rate_limit(channel_id)
        
        try:
            start_date, end_date = self.get_date_range(days)
            
            time_series = analytics_service.reports().query(
                ids=f'channel=={channel_id}',
                startDate=start_date,
                endDate=end_date,
                metrics='views,estimatedMinutesWatched,subscribersGained',
                dimensions='day'
            ).execute()
            
            dates = []
            views = []
            watch_time = []
            subscribers = []
            estimated_revenue = []
            
            for row in time_series.get('rows', []):
                if len(row) >= 4:  # Ensure we have all required data
                    dates.append(row[0])
                    views.append(row[1])
                    watch_time.append(row[2] / 60)  # Convert to hours
                    subscribers.append(row[3])
                    estimated_revenue.append(0)  # Revenue data usually not available
            
            return TimeSeriesData(dates, views, watch_time, subscribers, estimated_revenue)
            
        except Exception as e:
            error_msg = self._handle_api_error(e, "getting time series data")
            logger.error(f"❌ {error_msg}")
            return TimeSeriesData([], [], [], [], [])
    
    def get_audience_analytics(self, channel_id: str, days: int = 30) -> AudienceData:
        """Get audience analytics with comprehensive error handling"""
        analytics_service = self.get_analytics_service(channel_id)
        
        if not analytics_service:
            return AudienceData([], [], [], [], [])
        
        self._check_rate_limit(channel_id)
        
        try:
            start_date, end_date = self.get_date_range(days)
            
            # Initialize data structures
            age_gender = []
            device_types = []
            traffic_sources = []
            geography = []
            playback_locations = []
            
            # Device types (most reliable)
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
                logger.warning(f"Device data unavailable: {self._handle_api_error(e, 'device analytics')}")
            
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
                logger.warning(f"Geography data unavailable: {self._handle_api_error(e, 'geography analytics')}")
            
            return AudienceData(age_gender, device_types, traffic_sources, geography, playback_locations)
            
        except Exception as e:
            error_msg = self._handle_api_error(e, "getting audience analytics")
            logger.error(f"❌ {error_msg}")
            return AudienceData([], [], [], [], [])

class DentalChannelsDashboard:
    """Production-ready dashboard with comprehensive features"""
    
    def __init__(self):
        self._configure_streamlit()
        self._initialize_session_state()
        self._load_custom_css()
    
    def _configure_streamlit(self):
        """Configure Streamlit page settings"""
        st.set_page_config(
            page_title="Dental Channels Analytics Dashboard",
            page_icon="🦷",
            layout="wide",
            initial_sidebar_state="expanded",
            menu_items={
                'Get Help': 'https://github.com/your-repo/issues',
                'Report a bug': 'https://github.com/your-repo/issues',
                'About': "Dental Education YouTube Analytics Dashboard v2.0"
            }
        )
    
    def _initialize_session_state(self):
        """Initialize session state variables"""
        if 'selected_channel' not in st.session_state:
            st.session_state.selected_channel = None
        if 'show_deployment_guide' not in st.session_state:
            st.session_state.show_deployment_guide = False
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = datetime.now()
        if 'error_count' not in st.session_state:
            st.session_state.error_count = 0
    
    def _load_custom_css(self):
        """Load custom CSS styling"""
        st.markdown("""
        <style>
        /* Main styling */
        .main-header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 2rem;
            border-radius: 15px;
            text-align: center;
            margin-bottom: 2rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        
        .deployment-info {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem;
            border-radius: 10px;
            margin-bottom: 1rem;
            text-align: center;
        }
        
        .channel-card {
            background: white;
            padding: 1.5rem;
            border-radius: 12px;
            border-left: 4px solid #4facfe;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            margin-bottom: 1rem;
            transition: transform 0.2s ease;
        }
        
        .channel-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
        }
        
        .channel-card.error {
            border-left-color: #ff4757;
            background: #fff5f5;
        }
        
        .channel-card.success {
            border-left-color: #2ed573;
            background: #f0fff4;
        }
        
        .metric-card {
            background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
            padding: 1.5rem;
            border-radius: 10px;
            text-align: center;
            margin: 0.5rem 0;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        .auth-status {
            padding: 0.3rem 0.8rem;
            border-radius: 15px;
            font-size: 0.8rem;
            font-weight: bold;
            margin-left: 0.5rem;
        }
        
        .auth-success {
            background: #2ed573;
            color: white;
        }
        
        .auth-error {
            background: #ff4757;
            color: white;
        }
        
        .content-focus-badge {
            background: #4facfe;
            color: white;
            padding: 0.3rem 0.8rem;
            border-radius: 15px;
            font-size: 0.8rem;
            font-weight: bold;
            display: inline-block;
            margin: 0.2rem;
        }
        
        .stats-container {
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 1rem;
            margin: 1rem 0;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .warning-banner {
            background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
            color: #333;
            padding: 1rem;
            border-radius: 10px;
            margin: 1rem 0;
            border-left: 4px solid #ff4757;
        }
        
        .success-banner {
            background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
            color: #333;
            padding: 1rem;
            border-radius: 10px;
            margin: 1rem 0;
            border-left: 4px solid #2ed573;
        }
        
        /* Hide Streamlit default elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Responsive design */
        @media (max-width: 768px) {
            .main-header {
                padding: 1rem;
            }
            .channel-card {
                padding: 1rem;
            }
        }
        </style>
        """, unsafe_allow_html=True)
    
    def render_header(self):
        """Render dashboard header with environment info"""
        # Environment indicator
        env_emoji = "☁️" if IS_STREAMLIT_CLOUD else "💻"
        env_text = "Streamlit Community Cloud" if IS_STREAMLIT_CLOUD else "Local Development"
        auth_method = "Streamlit Secrets" if IS_STREAMLIT_CLOUD else "OAuth Files"
        
        # st.markdown(f"""
        # <div class="deployment-info">
        #     {env_emoji} <strong>Environment:</strong> {env_text} | 
        #     <strong>Authentication:</strong> {auth_method}
        # </div>
        # """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="main-header">
            <h1>🦷 Dental Education Analytics Dashboard</h1>
        </div>
        """, unsafe_allow_html=True)
    
    def render_deployment_guide(self):
        """Comprehensive deployment guide"""
        st.markdown("# 🚀 Production Deployment Guide")
        
        tab1, tab2, tab3, tab4 = st.tabs(["Quick Start", "Local Setup", "Cloud Deployment", "Security & Best Practices"])
        
        with tab1:
            st.markdown("""
            ## ⚡ Quick Start Guide
            
            ### 1. Prerequisites
            ```bash
            # Install required packages
            pip install streamlit google-api-python-client google-auth google-auth-oauthlib plotly pandas
            ```
            
            ### 2. Get YouTube Analytics API Access
            1. Go to [Google Cloud Console](https://console.cloud.google.com/)
            2. Create a new project or select existing
            3. Enable **YouTube Analytics API**
            4. Create **OAuth 2.0 credentials** (Desktop Application)
            5. Download the JSON credentials file
            
            ### 3. Update Channel Configuration
            ```python
            # In the code, update UPLOAD_CHANNELS with your actual channel IDs:
            UPLOAD_CHANNELS = [
                {
                    "name": "Your Channel Name",
                    "id": "YOUR_ACTUAL_CHANNEL_ID",  # Get from YouTube Studio
                    # ... other config
                }
            ]
            ```
            
            ### 4. Choose Deployment Method
            - **Local Development**: Use credential files directly
            - **Streamlit Cloud**: Use Streamlit Secrets for credentials
            """)
        
        with tab2:
            st.markdown("""
            ## 💻 Local Development Setup
            
            ### File Structure
            ```
            your-project/
            ├── app.py                              # This dashboard
            ├── requirements.txt                    # Python dependencies
            ├── dental_advisor_credentials.json     # OAuth credentials (Channel 1)
            ├── mih_credentials.json               # OAuth credentials (Channel 2)
            ├── enamel_hypoplasia_credentials.json # OAuth credentials (Channel 3)
            ├── .gitignore                         # IMPORTANT: Exclude credential files
            └── README.md
            ```
            
            ### Step-by-Step Setup
            
            **1. Create requirements.txt:**
            ```txt
            streamlit>=1.28.0
            google-api-python-client>=2.100.0
            google-auth-httplib2>=0.1.1
            google-auth-oauthlib>=1.1.0
            google-auth>=2.22.0
            plotly>=5.15.0
            pandas>=2.0.0
            ```
            
            **2. Download OAuth Credentials:**
            - For each channel, create separate OAuth credentials in Google Cloud Console
            - Download as JSON and rename according to your channel configuration
            - Place files in the same directory as app.py
            
            **3. Create .gitignore:**
            ```gitignore
            # Credentials and tokens
            *_credentials.json
            *_token.json
            
            # Environment
            .env
            __pycache__/
            *.pyc
            ```
            
            **4. Run Locally:**
            ```bash
            streamlit run app.py
            ```
            
            **5. Complete OAuth Flow:**
            - Browser will open for each channel
            - Grant permissions for YouTube Analytics access
            - Token files will be automatically generated
            """)
        
        with tab3:
            st.markdown("""
            ## ☁️ Streamlit Cloud Deployment
            
            ### Prerequisites
            - GitHub repository with your code
            - Completed local authentication (to get tokens)
            - Streamlit Cloud account
            
            ### Step 1: Prepare Repository
            ```
            your-repo/
            ├── app.py
            ├── requirements.txt
            ├── README.md
            ├── .gitignore              # MUST exclude credential files
            └── .streamlit/
                └── secrets.toml        # Local only - DO NOT commit
            ```
            
            ### Step 2: Get Authentication Tokens
            1. **Run locally first** to complete OAuth flows
            2. **Find generated token files**:
               - `dental_advisor_token.json`
               - `mih_token.json`
               - `enamel_hypoplasia_token.json`
            3. **Copy token contents** - you'll need these for Streamlit Secrets
            
            ### Step 3: Configure Streamlit Secrets
            In your Streamlit Cloud app settings, add these secrets:
            
            ```toml
            [dental_advisor_token]
            token = "your_access_token"
            refresh_token = "your_refresh_token"
            token_uri = "https://oauth2.googleapis.com/token"
            client_id = "your_client_id"
            client_secret = "your_client_secret"
            scopes = ["https://www.googleapis.com/auth/yt-analytics.readonly"]
            
            [mih_token]
            token = "your_access_token"
            refresh_token = "your_refresh_token"
            token_uri = "https://oauth2.googleapis.com/token"
            client_id = "your_client_id"
            client_secret = "your_client_secret"
            scopes = ["https://www.googleapis.com/auth/yt-analytics.readonly"]
            
            [enamel_hypoplasia_token]
            token = "your_access_token"
            refresh_token = "your_refresh_token"
            token_uri = "https://oauth2.googleapis.com/token"
            client_id = "your_client_id"
            client_secret = "your_client_secret"
            scopes = ["https://www.googleapis.com/auth/yt-analytics.readonly"]
            ```
            
            ### Step 4: Deploy
            1. Push code to GitHub (without credential files!)
            2. Go to [share.streamlit.io](https://share.streamlit.io)
            3. Connect your repository
            4. Configure secrets in the app settings
            5. Deploy!
            
            ### Important Notes
            - ⚠️ **NEVER commit credential files to GitHub**
            - 🔐 **Use Streamlit Secrets for all sensitive data**
            - 🔄 **Tokens may need periodic refresh**
            - 📊 **Monitor API quota usage**
            """)
        
        with tab4:
            st.markdown("""
            ## 🔒 Security & Best Practices
            
            ### Security Checklist
            
            ✅ **Credential Management**
            - Never commit OAuth credentials to version control
            - Use environment-specific authentication methods
            - Regularly rotate API credentials
            - Monitor access logs in Google Cloud Console
            
            ✅ **API Security**
            - Implement rate limiting (✅ Already implemented)
            - Handle API errors gracefully (✅ Already implemented)
            - Monitor API quota usage
            - Use principle of least privilege for OAuth scopes
            
            ✅ **Deployment Security**
            - Use HTTPS in production (Streamlit Cloud provides this)
            - Validate all user inputs
            - Implement proper error handling
            - Log security events
            
            ### Production Best Practices
            
            **1. Error Handling**
            ```python
            # Comprehensive error handling implemented:
            - API rate limiting with exponential backoff
            - Graceful degradation when metrics unavailable
            - User-friendly error messages
            - Detailed logging for debugging
            ```
            
            **2. Performance Optimization**
            ```python
            # Performance features implemented:
            - Caching of API responses
            - Efficient data structures
            - Minimal API calls
            - Progressive loading
            ```
            
            **3. Monitoring & Maintenance**
            - Monitor API quota usage in Google Cloud Console
            - Set up alerts for authentication failures
            - Regular token refresh (handled automatically)
            - Keep dependencies updated
            
            **4. Data Privacy**
            - Only request necessary YouTube Analytics permissions
            - Don't store sensitive data in logs
            - Comply with YouTube API Terms of Service
            - Follow data retention policies
            
            ### Troubleshooting Common Issues
            
            **🔴 Authentication Errors**
            ```
            Problem: 403 Forbidden
            Solution: Verify channel ownership and API permissions
            
            Problem: Token expired
            Solution: Re-authenticate or refresh token
            
            Problem: Invalid credentials
            Solution: Re-download OAuth credentials from Google Cloud
            ```
            
            **🔴 API Errors**
            ```
            Problem: Rate limiting (429)
            Solution: Implemented automatic retry with backoff
            
            Problem: Quota exceeded
            Solution: Monitor usage in Google Cloud Console
            
            Problem: Channel not found (404)
            Solution: Verify channel ID is correct
            ```
            
            **🔴 Deployment Issues**
            ```
            Problem: Secrets not found in Streamlit Cloud
            Solution: Check secrets configuration in app settings
            
            Problem: Import errors
            Solution: Verify requirements.txt includes all dependencies
            
            Problem: Environment detection
            Solution: Check environment variables and hostname
            ```
            """)
    
    def render_authentication_status(self, service):
        """Render detailed authentication status"""
        # st.markdown("## 🔐 Channel Authentication Status")
        
        auth_status = service.get_authentication_status()
        authenticated_channels = service.get_authenticated_channels()
        
        # Summary metrics
        total_channels = len(UPLOAD_CHANNELS)
        authenticated_count = len(authenticated_channels)
        auth_rate = (authenticated_count / total_channels) * 100
        
        col1, col2, col3, col4 = st.columns(4)
        
        # with col1:
        #     st.metric("Total Channels", total_channels)
        # with col2:
        #     st.metric("Authenticated", authenticated_count)
        # with col3:
        #     st.metric("Success Rate", f"{auth_rate:.1f}%")
        # with col4:
        #     env_status = "Cloud" if IS_STREAMLIT_CLOUD else "Local"
        #     st.metric("Environment", env_status)
        
        # Detailed status for each channel
        for channel_config in UPLOAD_CHANNELS:
            channel_id = channel_config['id']
            channel_name = channel_config['name']
            auth_info = auth_status.get(channel_id)
            
            if auth_info and auth_info.is_authenticated:
                last_auth = auth_info.last_authenticated
                auth_time = last_auth.strftime("%Y-%m-%d %H:%M:%S") if last_auth else "Unknown"
                
                # st.markdown(f"""
                # <div class="channel-card success">
                #     <h4>✅ {channel_name}</h4>
                #     <p><strong>Status:</strong> <span class="auth-status auth-success">Authenticated</span></p>
                #     <p><strong>Focus:</strong> {channel_config['content_focus'].replace('_', ' ').title()}</p>
                #     <p><strong>Last Auth:</strong> {auth_time}</p>
                #     <p><strong>Method:</strong> {'Streamlit Secrets' if IS_STREAMLIT_CLOUD else 'Local OAuth'}</p>
                #     <span class="content-focus-badge" style="background-color: {channel_config.get('color', '#4facfe')}">
                #         {channel_config['content_focus'].replace('_', ' ').title()}
                #     </span>
                # </div>
                # """, unsafe_allow_html=True)
            else:
                error_msg = auth_info.error_message if auth_info else "Unknown authentication error"
                
                st.markdown(f"""
                <div class="channel-card error">
                    <h4>❌ {channel_name}</h4>
                    <p><strong>Status:</strong> <span class="auth-status auth-error">Authentication Failed</span></p>
                    <p><strong>Error:</strong> {error_msg}</p>
                    <p><strong>Required:</strong> {'Valid token in secrets' if IS_STREAMLIT_CLOUD else 'Credential file'}</p>
                    <p><strong>Config Key:</strong> {channel_config.get('token_key' if IS_STREAMLIT_CLOUD else 'credentials_file')}</p>
                </div>
                """, unsafe_allow_html=True)
        
        # Status-specific guidance
        if authenticated_count == 0:
            st.markdown("""
            <div class="warning-banner">
                <h4>⚠️ No Channels Authenticated</h4>
                <p>All channels require authentication before the dashboard can display analytics data.</p>
            </div>
            """, unsafe_allow_html=True)
            
            if IS_STREAMLIT_CLOUD:
                st.error("""
                **Streamlit Cloud Setup Required:**
                1. **Authenticate locally first** to generate valid tokens
                2. **Copy token data** from generated JSON files
                3. **Add to Streamlit Secrets** in your app dashboard
                4. **Restart the app** to load new secrets
                """)
            else:
                st.error("""
                **Local Setup Required:**
                1. **Download OAuth credentials** for each channel from Google Cloud Console
                2. **Place JSON files** in the same directory as this script
                3. **Update channel IDs** in the code with your actual YouTube channel IDs
                4. **Restart the application** and complete OAuth flow
                """)
        
        elif authenticated_count < total_channels:
            st.markdown(f"""
            <div class="warning-banner">
                <h4>⚠️ Partial Authentication ({authenticated_count}/{total_channels})</h4>
                <p>Some channels are not authenticated. The dashboard will work with available channels.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="success-banner">
                <h4>✅ All Channels Authenticated ({authenticated_count}/{total_channels})</h4>
                <p>Dashboard is fully operational with all configured channels.</p>
            </div>
            """, unsafe_allow_html=True)
    
    def render_sidebar(self, service):
        """Enhanced sidebar with better UX"""
        st.sidebar.markdown("## 🦷 Analytics Controls")
        
        # Environment status
        env_emoji = "☁️" if IS_STREAMLIT_CLOUD else "💻"
        env_text = "Cloud" if IS_STREAMLIT_CLOUD else "Local"
        st.sidebar.markdown(f"**Environment:** {env_emoji} {env_text}")
        
        # Authentication summary
        auth_status = service.get_authentication_status()
        authenticated_count = len(service.get_authenticated_channels())
        total_count = len(UPLOAD_CHANNELS)
        
        if authenticated_count == total_count:
            st.sidebar.success(f"🔐 All authenticated ({authenticated_count}/{total_count})")
        elif authenticated_count > 0:
            st.sidebar.warning(f"🔐 Partial auth ({authenticated_count}/{total_count})")
        else:
            st.sidebar.error(f"🔐 No auth ({authenticated_count}/{total_count})")
        
        # Time period selection
        st.sidebar.markdown("### 📅 Time Period")
        time_options = {
            "Last 7 days": 7,
            "Last 14 days": 14,
            "Last 30 days": 30,
            "Last 60 days": 60,
            "Last 90 days": 90,
            "Last 6 months": 180,
            "Last year": 365,
            "All time": -1
        }
        
        selected_period = st.sidebar.selectbox(
            "Select analytics period",
            options=list(time_options.keys()),
            index=2,  # Default to 30 days
            help="Choose the time range for analytics data"
        )
        
        days = time_options[selected_period]
        period_text = "All Time" if days == -1 else selected_period
        
        # Period indicator
        st.sidebar.markdown(f"""
        <div class="stats-container" style="background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); 
                    color: #333; padding: 0.5rem 1rem; border-radius: 20px; 
                    font-weight: bold; text-align: center; margin: 1rem 0;">
            📊 Analyzing: {period_text}
        </div>
        """, unsafe_allow_html=True)
        
        # Channel navigation
        st.sidebar.markdown("### 🎯 Channel Navigation")
        
        # Overview button
        if st.sidebar.button(
            "📊 All Channels Overview", 
            type="primary", 
            use_container_width=True,
            help="View combined analytics for all authenticated channels"
        ):
            st.session_state.selected_channel = None
            st.rerun()
        
        # Individual channel buttons
        st.sidebar.markdown("**Individual Channels:**")
        
        for channel in UPLOAD_CHANNELS:
            channel_id = channel['id']
            auth_info = auth_status.get(channel_id)
            is_authenticated = auth_info and auth_info.is_authenticated
            
            # Channel icon based on focus
            focus_icons = {
                'primary_education': '🎓',
                'treatment_focused': '🏥',
                'pediatric_care': '👶'
            }
            focus_icon = focus_icons.get(channel['content_focus'], '📺')
            
            # Authentication indicator
            auth_icon = "✅" if is_authenticated else "❌"
            
            # Button styling based on selection and auth status
            button_type = "secondary"
            if st.session_state.selected_channel == channel_id:
                button_type = "primary"
            
            if st.sidebar.button(
                f"{auth_icon} {focus_icon} {channel['name']}",
                key=f"select_{channel['id']}",
                use_container_width=True,
                disabled=not is_authenticated,
                type=button_type,
                help=f"View detailed analytics for {channel['name']}" if is_authenticated else f"Authentication required for {channel['name']}"
            ):
                if is_authenticated:
                    st.session_state.selected_channel = channel['id']
                    st.rerun()
        
        # Action buttons
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🔧 Actions")
        
        # Refresh data
        if st.sidebar.button(
            "🔄 Refresh Data", 
            type="secondary", 
            use_container_width=True,
            help="Reload analytics data from YouTube API"
        ):
            st.session_state.last_refresh = datetime.now()
            st.success("🔄 Data refreshed!")
            time.sleep(1)
            st.rerun()
        
        # Environment-specific actions
        if IS_STREAMLIT_CLOUD:
            if st.sidebar.button(
                "📚 Deployment Guide", 
                type="secondary", 
                use_container_width=True,
                help="View comprehensive deployment and setup guide"
            ):
                st.session_state.show_deployment_guide = True
                st.rerun()
        else:
            if st.sidebar.button(
                "🔄 Re-authenticate", 
                type="secondary", 
                use_container_width=True,
                help="Clear tokens and re-authenticate all channels"
            ):
                # Clear token files for re-authentication
                cleared_count = 0
                for channel in UPLOAD_CHANNELS:
                    token_file = channel['token_file']
                    if Path(token_file).exists():
                        try:
                            Path(token_file).unlink()
                            cleared_count += 1
                        except Exception as e:
                            st.sidebar.error(f"Failed to clear {channel['name']}: {e}")
                
                if cleared_count > 0:
                    st.sidebar.success(f"Cleared {cleared_count} token(s)")
                    st.sidebar.info("🔄 Please restart the app to re-authenticate")
        
        # Help section
        with st.sidebar.expander("❓ Help & Support"):
            st.markdown(f"""
            **Current Status:**
            - Environment: {'Streamlit Cloud' if IS_STREAMLIT_CLOUD else 'Local Development'}
            - Authenticated: {authenticated_count}/{total_count} channels
            - Last Refresh: {st.session_state.last_refresh.strftime('%H:%M:%S')}
            
            **Common Issues:**
            - **No Data**: Check channel authentication
            - **API Errors**: Verify channel ownership
            - **Rate Limits**: Wait and try again
            
            **Need Help?**
            - Check deployment guide for setup instructions
            - Verify channel IDs are correct
            - Ensure YouTube Analytics API is enabled
            """)
        
        # Display channel focus legend
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🎯 Channel Focus Areas")
        for channel in UPLOAD_CHANNELS:
            focus_icon = focus_icons.get(channel['content_focus'], '📺')
            focus_name = channel['content_focus'].replace('_', ' ').title()
            st.sidebar.markdown(f"{focus_icon} **{channel['name']}**: {focus_name}")
        
        return days, period_text
    
    def render_overview_dashboard(self, service, days, period_text):
        """Comprehensive overview dashboard"""
        st.markdown(f"# 📊 Multi-Channel Analytics Overview")
        st.markdown(f"**Analysis Period:** {period_text}")
        
        # Show authentication status
        self.render_authentication_status(service)
        
        authenticated_channels = service.get_authenticated_channels()
        if not authenticated_channels:
            st.warning("⚠️ No authenticated channels available. Please check authentication status above.")
            return
        
        # Collect analytics from authenticated channels
        with st.spinner("Loading analytics data..."):
            all_analytics = []
            total_metrics = {
                'views': 0,
                'watch_time': 0,
                'subscribers': 0,
                'likes': 0,
                'comments': 0,
                'shares': 0
            }
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            authenticated_channel_configs = [
                ch for ch in UPLOAD_CHANNELS 
                if ch['id'] in authenticated_channels
            ]
            
            for i, channel in enumerate(authenticated_channel_configs):
                status_text.text(f"Loading {channel['name']}...")
                progress_bar.progress((i + 1) / len(authenticated_channel_configs))
                
                analytics = service.get_channel_analytics(channel['id'], channel['name'], days)
                
                if analytics and analytics.auth_status == "Authenticated":
                    all_analytics.append(analytics)
                    total_metrics['views'] += analytics.period_views
                    total_metrics['watch_time'] += analytics.period_watch_time_hours
                    total_metrics['subscribers'] += analytics.period_subscribers_gained
                    total_metrics['likes'] += analytics.period_likes
                    total_metrics['comments'] += analytics.period_comments
                    total_metrics['shares'] += analytics.period_shares
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
        
        if not all_analytics:
            st.error("❌ No analytics data available from authenticated channels.")
            return
        
        # Summary metrics
        st.markdown("## 📈 Combined Performance Metrics")
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            st.metric(
                "👀 Total Views", 
                f"{total_metrics['views']:,}",
                help="Combined views across all authenticated channels"
            )
        
        with col2:
            st.metric(
                "⏱️ Watch Time", 
                f"{total_metrics['watch_time']:.1f}h",
                help="Total watch time in hours"
            )
        
        with col3:
            st.metric(
                "👥 New Subscribers", 
                f"+{total_metrics['subscribers']:,}",
                help="Net subscriber growth"
            )
        
        with col4:
            st.metric(
                "👍 Total Likes", 
                f"{total_metrics['likes']:,}",
                help="Combined likes across all channels"
            )
        
        # with col5:
        #     st.metric(
        #         "💬 Comments", 
        #         f"{total_metrics['comments']:,}",
        #         help="Total comments received"
        #     )
        
        with col5:
            st.metric(
                "📤 Shares", 
                f"{total_metrics['shares']:,}",
                help="Total content shares"
            )
        
        # Additional insights
        if len(all_analytics) > 1:
            avg_engagement_rate = sum(
                (a.period_likes + a.period_comments) / max(a.period_views, 1) * 100 
                for a in all_analytics
            ) / len(all_analytics)
            
            avg_view_duration = sum(a.average_view_duration for a in all_analytics) / len(all_analytics)
            
            col7, col8 = st.columns(2)
            with col7:
                st.metric(
                    "📊 Avg Engagement Rate", 
                    f"{avg_engagement_rate:.2f}%",
                    help="Average engagement rate across channels"
                )
            with col8:
                st.metric(
                    "⏰ Avg View Duration", 
                    f"{avg_view_duration:.0f}s",
                    help="Average view duration across channels"
                )
        
        # Channel comparison visualizations
        self.render_channel_comparison_charts(all_analytics, period_text)
        
        # Performance insights
        self.render_performance_insights(all_analytics, period_text)
    
    def render_channel_comparison_charts(self, all_analytics, period_text):
        """Render comprehensive channel comparison charts"""
        st.markdown(f"## 📈 Channel Performance Comparison ({period_text})")
        
        # Prepare data for visualizations
        chart_data = []
        for analytics in all_analytics:
            chart_data.append({
                'Channel': analytics.channel_name,
                'Views': analytics.period_views,
                'Watch Time (h)': analytics.period_watch_time_hours,
                'Subscribers Gained': analytics.period_subscribers_gained,
                'Likes': analytics.period_likes,
                'Comments': analytics.period_comments,
                'Shares': analytics.period_shares,
                'Engagement': analytics.period_likes + analytics.period_comments,
                'Avg View Duration (s)': analytics.average_view_duration,
                'Content Focus': analytics.content_focus.replace('_', ' ').title(),
                'Color': analytics.color
            })
        
        df = pd.DataFrame(chart_data)
        
        # Main comparison charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Views comparison
            fig_views = px.bar(
                df,
                x='Channel',
                y='Views',
                color='Content Focus',
                title="📊 Views by Channel",
                color_discrete_sequence=[analytics.color for analytics in all_analytics],
                hover_data=['Avg View Duration (s)']
            )
            fig_views.update_layout(showlegend=True, height=400)
            st.plotly_chart(fig_views, use_container_width=True)
            
            # Engagement comparison
            fig_engagement = px.bar(
                df,
                x='Channel',
                y='Engagement',
                color='Content Focus',
                title="💬 Total Engagement by Channel",
                color_discrete_sequence=[analytics.color for analytics in all_analytics],
                hover_data=['Likes', 'Comments']
            )
            fig_engagement.update_layout(showlegend=True, height=400)
            st.plotly_chart(fig_engagement, use_container_width=True)
        
        with col2:
            # Watch time comparison
            fig_watch = px.bar(
                df,
                x='Channel',
                y='Watch Time (h)',
                color='Content Focus',
                title="⏱️ Watch Time by Channel",
                color_discrete_sequence=[analytics.color for analytics in all_analytics],
                hover_data=['Views']
            )
            fig_watch.update_layout(showlegend=True, height=400)
            st.plotly_chart(fig_watch, use_container_width=True)
            
            # Subscribers gained
            fig_subs = px.bar(
                df,
                x='Channel',
                y='Subscribers Gained',
                color='Content Focus',
                title="👥 New Subscribers by Channel",
                color_discrete_sequence=[analytics.color for analytics in all_analytics]
            )
            fig_subs.update_layout(showlegend=True, height=400)
            st.plotly_chart(fig_subs, use_container_width=True)
        
        # Advanced visualizations
        st.markdown("### 🔍 Advanced Analytics")
        
        col3, col4 = st.columns(2)
        
        with col3:
            # Performance scatter plot
            fig_scatter = px.scatter(
                df,
                x='Views',
                y='Engagement',
                size='Watch Time (h)',
                color='Content Focus',
                hover_name='Channel',
                title="📈 Views vs Engagement (Size = Watch Time)",
                color_discrete_sequence=[analytics.color for analytics in all_analytics]
            )
            fig_scatter.update_layout(height=400)
            st.plotly_chart(fig_scatter, use_container_width=True)
        
        with col4:
            # Engagement rate by channel
            df['Engagement Rate'] = (df['Engagement'] / df['Views'] * 100).round(2)
            fig_rate = px.bar(
                df,
                x='Channel',
                y='Engagement Rate',
                color='Content Focus',
                title="📊 Engagement Rate by Channel (%)",
                color_discrete_sequence=[analytics.color for analytics in all_analytics]
            )
            fig_rate.update_layout(height=400)
            st.plotly_chart(fig_rate, use_container_width=True)
    
    def render_performance_insights(self, all_analytics, period_text):
        """Render detailed performance insights"""
        st.markdown(f"## 💡 Performance Insights ({period_text})")
        
        # Performance leaders
        best_views = max(all_analytics, key=lambda x: x.period_views)
        best_engagement = max(all_analytics, key=lambda x: x.period_likes + x.period_comments)
        best_retention = max(all_analytics, key=lambda x: x.average_view_duration)
        best_growth = max(all_analytics, key=lambda x: x.period_subscribers_gained)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card" style="border-left: 4px solid {best_views.color}">
                <h4>🏆 Most Views</h4>
                <h3>{best_views.channel_name}</h3>
                <p><strong>{best_views.period_views:,}</strong> views</p>
                <p>{best_views.content_focus.replace('_', ' ').title()}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            total_engagement = best_engagement.period_likes + best_engagement.period_comments
            st.markdown(f"""
            <div class="metric-card" style="border-left: 4px solid {best_engagement.color}">
                <h4>💬 Best Engagement</h4>
                <h3>{best_engagement.channel_name}</h3>
                <p><strong>{total_engagement:,}</strong> interactions</p>
                <p>{best_engagement.content_focus.replace('_', ' ').title()}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card" style="border-left: 4px solid {best_retention.color}">
                <h4>⏰ Best Retention</h4>
                <h3>{best_retention.channel_name}</h3>
                <p><strong>{best_retention.average_view_duration:.0f}s</strong> avg duration</p>
                <p>{best_retention.content_focus.replace('_', ' ').title()}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="metric-card" style="border-left: 4px solid {best_growth.color}">
                <h4>📈 Best Growth</h4>
                <h3>{best_growth.channel_name}</h3>
                <p><strong>+{best_growth.period_subscribers_gained:,}</strong> subscribers</p>
                <p>{best_growth.content_focus.replace('_', ' ').title()}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Detailed performance table
        st.markdown("### 📋 Detailed Performance Table")
        
        table_data = []
        for analytics in all_analytics:
            engagement_rate = ((analytics.period_likes + analytics.period_comments) / max(analytics.period_views, 1)) * 100
            
            table_data.append({
                'Channel': analytics.channel_name,
                'Content Focus': analytics.content_focus.replace('_', ' ').title(),
                'Views': f"{analytics.period_views:,}",
                'Watch Time': f"{analytics.period_watch_time_hours:.1f}h",
                'Avg Duration': f"{analytics.average_view_duration:.0f}s",
                'Subscribers': f"+{analytics.period_subscribers_gained:,}",
                'Likes': f"{analytics.period_likes:,}",
                'Comments': f"{analytics.period_comments:,}",
                'Shares': f"{analytics.period_shares:,}",
                'Engagement Rate': f"{engagement_rate:.2f}%"
            })
        
        df_table = pd.DataFrame(table_data)
        st.dataframe(df_table, use_container_width=True, hide_index=True)
        
        # Performance recommendations
        # st.markdown("### 🎯 Actionable Recommendations")
        
        recommendations = []
        
        # Analyze performance patterns
        # if len(all_analytics) > 1:
        #     view_leader = max(all_analytics, key=lambda x: x.period_views)
        #     engagement_leader = max(all_analytics, key=lambda x: (x.period_likes + x.period_comments) / max(x.period_views, 1))
            
        #     recommendations.extend([
        #         f"🏆 **{view_leader.channel_name}** leads in views - analyze successful content strategies",
        #         f"💬 **{engagement_leader.channel_name}** has the best engagement rate - study interaction techniques"
        #     ])
            
        #     # Check for underperforming channels
        #     avg_views = sum(a.period_views for a in all_analytics) / len(all_analytics)
        #     underperformers = [a for a in all_analytics if a.period_views < avg_views * 0.5]
            
        #     if underperformers:
        #         for channel in underperformers:
        #             recommendations.append(f"📈 **{channel.channel_name}** needs attention - consider content optimization")
        
        # General recommendations
        # recommendations.extend([
        #     "🎯 Focus on content that drives both views and engagement",
        #     "⏰ Optimize video length based on average view duration data",
        #     "💡 Cross-promote successful content strategies between channels",
        #     "📊 Monitor trends weekly to identify growth opportunities"
        # ])
        
        # for rec in recommendations:
        #     st.markdown(f"- {rec}")
    
    def render_channel_dashboard(self, service, channel_id, days, period_text):
        """Render detailed individual channel dashboard"""
        # Back button
        if st.button("← Back to Overview", key="back_btn", type="secondary"):
            st.session_state.selected_channel = None
            st.rerun()
        
        # Check authentication
        if channel_id not in service.get_authenticated_channels():
            st.error("❌ This channel is not authenticated. Please check the authentication status.")
            return
        
        # Find channel configuration
        channel_config = next((ch for ch in UPLOAD_CHANNELS if ch['id'] == channel_id), None)
        if not channel_config:
            st.error("❌ Channel configuration not found!")
            return
        
        channel_name = channel_config['name']
        
        st.markdown(f"# 🦷 {channel_name} - Detailed Analytics")
        st.markdown(f"**Analysis Period:** {period_text}")
        
        # Channel information card
        focus_emoji = {
            'primary_education': '🎓',
            'treatment_focused': '🏥',
            'pediatric_care': '👶'
        }.get(channel_config['content_focus'], '📺')
        
        # st.markdown(f"""
        # <div class="channel-card success" style="border-left-color: {channel_config.get('color', '#4facfe')}">
        #     <h3>✅ {focus_emoji} {channel_name}</h3>
        #     <p><strong>Status:</strong> <span class="auth-status auth-success">Authenticated & Active</span></p>
        #     <p><strong>Focus Area:</strong> {channel_config['content_focus'].replace('_', ' ').title()}</p>
        #     <p><strong>Description:</strong> {channel_config['description']}</p>
        #     <span class="content-focus-badge" style="background-color: {channel_config.get('color', '#4facfe')}">
        #         {channel_config['content_focus'].replace('_', ' ').title()}
        #     </span>
        # </div>
        # """, unsafe_allow_html=True)
        
        # Load analytics data
        with st.spinner(f"Loading detailed analytics for {channel_name}..."):
            analytics = service.get_channel_analytics(channel_id, channel_name, days)
            time_series = service.get_time_series_data(channel_id, days)
            audience_data = service.get_audience_analytics(channel_id, days)
        
        if not analytics or analytics.auth_status != "Authenticated":
            st.error(f"❌ Could not load analytics for {channel_name}")
            return
        
        # Key metrics dashboard
        st.markdown("## 📊 Key Performance Metrics")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("👀 Views", f"{analytics.period_views:,}")
        with col2:
            st.metric("⏱️ Watch Time", f"{analytics.period_watch_time_hours:.1f}h")
        with col3:
            st.metric("👥 Subscribers", f"+{analytics.period_subscribers_gained:,}")
        with col4:
            st.metric("👍 Likes", f"{analytics.period_likes:,}")
        with col5:
            st.metric("💬 Comments", f"{analytics.period_comments:,}")
        
        # Secondary metrics
        col6, col7, col8 = st.columns(3)
        
        with col6:
            st.metric("📤 Shares", f"{analytics.period_shares:,}")
        with col7:
            st.metric("⏰ Avg Duration", f"{analytics.average_view_duration:.0f}s")
        with col8:
            engagement_rate = ((analytics.period_likes + analytics.period_comments) / max(analytics.period_views, 1)) * 100
            st.metric("📊 Engagement Rate", f"{engagement_rate:.2f}%")
        
        # Time series analysis
        if time_series.dates:
            self.render_time_series_analysis(time_series, channel_name, period_text, channel_config.get('color', '#4facfe'))
        
        # Audience analytics
        if any([audience_data.device_types, audience_data.geography]):
            self.render_audience_analysis(audience_data, channel_name, period_text)
    
    def render_time_series_analysis(self, time_series, channel_name, period_text, color):
        """Render comprehensive time series analysis"""
        st.markdown(f"## 📈 Performance Trends - {channel_name} ({period_text})")
        
        # Create DataFrame
        df_series = pd.DataFrame({
            'Date': pd.to_datetime(time_series.dates),
            'Views': time_series.views,
            'Watch Time (h)': time_series.watch_time,
            'Subscribers Gained': time_series.subscribers
        })
        
        # Calculate moving averages
        if len(df_series) > 7:
            df_series['Views_MA7'] = df_series['Views'].rolling(window=7, center=True).mean()
            df_series['Watch Time_MA7'] = df_series['Watch Time (h)'].rolling(window=7, center=True).mean()
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Views trend with moving average
            fig_views = go.Figure()
            
            fig_views.add_trace(go.Scatter(
                x=df_series['Date'],
                y=df_series['Views'],
                mode='lines+markers',
                name='Daily Views',
                line=dict(color=color, width=2),
                marker=dict(size=4)
            ))
            
            if 'Views_MA7' in df_series.columns:
                fig_views.add_trace(go.Scatter(
                    x=df_series['Date'],
                    y=df_series['Views_MA7'],
                    mode='lines',
                    name='7-Day Average',
                    line=dict(color='rgba(255, 0, 0, 0.7)', width=3, dash='dash')
                ))
            
            fig_views.update_layout(
                title=f"📊 Daily Views Trend",
                xaxis_title="Date",
                yaxis_title="Views",
                height=400,
                showlegend=True
            )
            st.plotly_chart(fig_views, use_container_width=True)
            
            # Subscribers gained
            fig_subs = px.bar(
                df_series,
                x='Date',
                y='Subscribers Gained',
                title="👥 Daily Subscribers Gained",
                color_discrete_sequence=[color]
            )
            fig_subs.update_layout(height=400)
            st.plotly_chart(fig_subs, use_container_width=True)
        
        with col2:
            # Watch time trend
            fig_watch = go.Figure()
            
            fig_watch.add_trace(go.Scatter(
                x=df_series['Date'],
                y=df_series['Watch Time (h)'],
                mode='lines+markers',
                name='Daily Watch Time',
                line=dict(color=color, width=2),
                marker=dict(size=4),
                fill='tonexty'
            ))
            
            if 'Watch Time_MA7' in df_series.columns:
                fig_watch.add_trace(go.Scatter(
                    x=df_series['Date'],
                    y=df_series['Watch Time_MA7'],
                    mode='lines',
                    name='7-Day Average',
                    line=dict(color='rgba(255, 165, 0, 0.7)', width=3, dash='dash')
                ))
            
            fig_watch.update_layout(
                title="⏱️ Daily Watch Time Trend",
                xaxis_title="Date",
                yaxis_title="Watch Time (hours)",
                height=400,
                showlegend=True
            )
            st.plotly_chart(fig_watch, use_container_width=True)
            
            # Combined performance heatmap
            if len(df_series) > 1:
                # Create performance score
                df_series['Performance Score'] = (
                    (df_series['Views'] / df_series['Views'].max() * 0.4) +
                    (df_series['Watch Time (h)'] / df_series['Watch Time (h)'].max() * 0.4) +
                    (df_series['Subscribers Gained'] / max(df_series['Subscribers Gained'].max(), 1) * 0.2)
                ) * 100
                
                fig_heatmap = px.scatter(
                    df_series,
                    x='Date',
                    y=['Performance Score'] * len(df_series),
                    color='Performance Score',
                    size='Views',
                    title="🔥 Performance Heatmap",
                    color_continuous_scale='RdYlBu_r',
                    labels={'y': 'Performance Metric'}
                )
                fig_heatmap.update_layout(height=400)
                st.plotly_chart(fig_heatmap, use_container_width=True)
        
        # Performance insights from time series
        st.markdown("### 📊 Trend Analysis")
        
        insights = []
        
        if len(time_series.views) > 1:
            recent_views = sum(time_series.views[-7:]) if len(time_series.views) >= 7 else sum(time_series.views)
            previous_views = sum(time_series.views[-14:-7]) if len(time_series.views) >= 14 else sum(time_series.views[:-7]) if len(time_series.views) > 7 else 0
            
            if previous_views > 0:
                growth_rate = ((recent_views - previous_views) / previous_views) * 100
                if growth_rate > 10:
                    insights.append(f"📈 **Strong growth**: Views increased by {growth_rate:.1f}% in recent period")
                elif growth_rate < -10:
                    insights.append(f"📉 **Declining trend**: Views decreased by {abs(growth_rate):.1f}% - consider content review")
                else:
                    insights.append(f"📊 **Stable performance**: Views relatively stable with {growth_rate:.1f}% change")
        
        # Peak performance days
        if time_series.views:
            max_views_idx = time_series.views.index(max(time_series.views))
            peak_date = time_series.dates[max_views_idx]
            peak_views = time_series.views[max_views_idx]
            insights.append(f"🏆 **Best day**: {peak_date} with {peak_views:,} views")
        
        # Average performance
        avg_views = sum(time_series.views) / len(time_series.views) if time_series.views else 0
        avg_watch_time = sum(time_series.watch_time) / len(time_series.watch_time) if time_series.watch_time else 0
        insights.extend([
            f"📊 **Daily average**: {avg_views:.0f} views, {avg_watch_time:.1f}h watch time",
            f"🎯 **Consistency**: {'High' if max(time_series.views) / max(avg_views, 1) < 3 else 'Variable'} performance variance"
        ])
        
        for insight in insights:
            st.markdown(f"- {insight}")
    
    def render_audience_analysis(self, audience_data, channel_name, period_text):
        """Render comprehensive audience analytics"""
        st.markdown(f"## 👥 Audience Analytics - {channel_name} ({period_text})")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Device usage
            if audience_data.device_types:
                st.markdown("#### 📱 Device Usage")
                
                df_devices = pd.DataFrame(audience_data.device_types)
                
                # Clean device names
                device_mapping = {
                    'MOBILE': 'Mobile 📱',
                    'DESKTOP': 'Desktop 💻',
                    'TABLET': 'Tablet 📲',
                    'TV': 'TV/Smart TV 📺',
                    'GAME_CONSOLE': 'Game Console 🎮'
                }
                
                df_devices['device'] = df_devices['device'].map(device_mapping).fillna(df_devices['device'])
                
                fig_devices = px.pie(
                    df_devices,
                    values='views',
                    names='device',
                    title="Device Distribution",
                    color_discrete_sequence=['#4facfe', '#00f2fe', '#a8edea', '#fed6e3', '#f093fb']
                )
                fig_devices.update_traces(textposition='inside', textinfo='percent+label')
                fig_devices.update_layout(height=400)
                st.plotly_chart(fig_devices, use_container_width=True)
                
                # Device insights
                total_views = sum(df_devices['views'])
                mobile_views = df_devices[df_devices['device'].str.contains('Mobile', na=False)]['views'].sum()
                mobile_percentage = (mobile_views / total_views) * 100 if total_views > 0 else 0
                
                if mobile_percentage > 70:
                    st.info(f"📱 **Mobile-first audience**: {mobile_percentage:.1f}% mobile usage - optimize for mobile viewing")
                elif mobile_percentage < 30:
                    st.info(f"💻 **Desktop-focused audience**: {mobile_percentage:.1f}% mobile usage - consider longer-form content")
                else:
                    st.info(f"⚖️ **Balanced device usage**: {mobile_percentage:.1f}% mobile, good cross-platform reach")
            else:
                st.info("📱 Device usage data not available")
        
        with col2:
            # Geographic distribution
            if audience_data.geography:
                st.markdown("#### 🌍 Geographic Distribution")
                
                df_geo = pd.DataFrame(audience_data.geography)
                
                # Top countries chart
                fig_geo = px.bar(
                    df_geo.head(8),
                    x='views',
                    y='country',
                    orientation='h',
                    title="Top Countries",
                    color='views',
                    color_continuous_scale='Blues',
                    text='views'
                )
                fig_geo.update_layout(
                    yaxis={'categoryorder': 'total ascending'},
                    height=400,
                    showlegend=False
                )
                fig_geo.update_traces(texttemplate='%{text:,}', textposition='outside')
                st.plotly_chart(fig_geo, use_container_width=True)
                
                # Geographic insights
                total_geo_views = sum(df_geo['views'])
                top_country = df_geo.iloc[0] if not df_geo.empty else None
                
                if top_country is not None:
                    top_percentage = (top_country['views'] / total_geo_views) * 100
                    st.info(f"🏆 **Primary market**: {top_country['country']} ({top_percentage:.1f}% of views)")
                    
                    if len(df_geo) > 1:
                        international_views = total_geo_views - top_country['views']
                        international_percentage = (international_views / total_geo_views) * 100
                        st.info(f"🌍 **International reach**: {international_percentage:.1f}% from other countries")
            else:
                st.info("🌍 Geographic data not available")
        
        # Additional audience insights if data is available
        if audience_data.device_types or audience_data.geography:
            st.markdown("### 🎯 Audience Recommendations")
            
            recommendations = []
            
            if audience_data.device_types:
                df_devices = pd.DataFrame(audience_data.device_types)
                mobile_dominant = any('MOBILE' in str(device).upper() for device in df_devices['device'])
                
                if mobile_dominant:
                    recommendations.extend([
                        "📱 Optimize video thumbnails for mobile viewing",
                        "⏱️ Consider shorter video formats for mobile attention spans",
                        "📝 Use larger text and clear visuals for mobile screens"
                    ])
                else:
                    recommendations.extend([
                        "💻 Leverage longer-form educational content for desktop viewers",
                        "🖼️ Use detailed graphics and charts that benefit from larger screens"
                    ])
            
            if audience_data.geography:
                df_geo = pd.DataFrame(audience_data.geography)
                if len(df_geo) > 3:
                    recommendations.extend([
                        "🌍 Consider international content strategies",
                        "🕐 Schedule uploads for global time zones",
                        "💬 Engage with international audience in comments"
                    ])
            
            for rec in recommendations:
                st.markdown(f"- {rec}")
    
    def render_export_functionality(self, service, days, period_text):
        """Render comprehensive export functionality"""
        st.markdown(f"## 📥 Export Analytics Data ({period_text})")
        
        authenticated_channels = service.get_authenticated_channels()
        if not authenticated_channels:
            st.warning("⚠️ No authenticated channels available for export.")
            return
        
        authenticated_channel_configs = [ch for ch in UPLOAD_CHANNELS if ch['id'] in authenticated_channels]
        
        # Export options
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("📊 Export Summary CSV", type="secondary", use_container_width=True):
                with st.spinner("Generating summary export..."):
                    export_data = []
                    
                    for channel in authenticated_channel_configs:
                        analytics = service.get_channel_analytics(channel['id'], channel['name'], days)
                        
                        if analytics and analytics.auth_status == "Authenticated":
                            engagement_rate = ((analytics.period_likes + analytics.period_comments) / max(analytics.period_views, 1)) * 100
                            
                            export_data.append({
                                'Channel Name': analytics.channel_name,
                                'Channel ID': analytics.channel_id,
                                'Content Focus': analytics.content_focus.replace('_', ' ').title(),
                                'Time Period': period_text,
                                'Export Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'Views': analytics.period_views,
                                'Watch Time (Hours)': round(analytics.period_watch_time_hours, 2),
                                'Subscribers Gained': analytics.period_subscribers_gained,
                                'Likes': analytics.period_likes,
                                'Comments': analytics.period_comments,
                                'Shares': analytics.period_shares,
                                'Average View Duration (Seconds)': round(analytics.average_view_duration, 2),
                                'Engagement Rate (%)': round(engagement_rate, 2),
                                'Authentication Status': analytics.auth_status,
                                'Description': analytics.description
                            })
                    
                    if export_data:
                        df_export = pd.DataFrame(export_data)
                        csv = df_export.to_csv(index=False)
                        
                        filename = f"dental_channels_summary_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
                        
                        st.download_button(
                            label="📥 Download Summary CSV",
                            data=csv,
                            file_name=filename,
                            mime="text/csv",
                            key="summary_download",
                            help="Download comprehensive summary of all channel analytics"
                        )
                        st.success(f"✅ Summary export ready! ({len(export_data)} channels)")
        
        with col2:
            if st.button("📈 Export Time Series", type="secondary", use_container_width=True):
                with st.spinner("Generating time series export..."):
                    all_time_series = []
                    
                    for channel in authenticated_channel_configs:
                        time_series = service.get_time_series_data(channel['id'], days)
                        
                        for i, date in enumerate(time_series.dates):
                            all_time_series.append({
                                'Channel Name': channel['name'],
                                'Channel ID': channel['id'],
                                'Content Focus': channel['content_focus'].replace('_', ' ').title(),
                                'Date': date,
                                'Views': time_series.views[i] if i < len(time_series.views) else 0,
                                'Watch Time (Hours)': round(time_series.watch_time[i], 2) if i < len(time_series.watch_time) else 0,
                                'Subscribers Gained': time_series.subscribers[i] if i < len(time_series.subscribers) else 0,
                                'Export Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                    
                    if all_time_series:
                        df_series = pd.DataFrame(all_time_series)
                        csv_series = df_series.to_csv(index=False)
                        
                        filename = f"dental_channels_timeseries_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
                        
                        st.download_button(
                            label="📥 Download Time Series CSV",
                            data=csv_series,
                            file_name=filename,
                            mime="text/csv",
                            key="series_download",
                            help="Download daily performance data for trend analysis"
                        )
                        st.success(f"✅ Time series export ready! ({len(all_time_series)} data points)")
        
        with col3:
            if st.button("👥 Export Audience Data", type="secondary", use_container_width=True):
                with st.spinner("Generating audience export..."):
                    audience_export = []
                    
                    for channel in authenticated_channel_configs:
                        audience_data = service.get_audience_analytics(channel['id'], days)
                        
                        # Device types
                        for item in audience_data.device_types:
                            audience_export.append({
                                'Channel Name': channel['name'],
                                'Channel ID': channel['id'],
                                'Content Focus': channel['content_focus'].replace('_', ' ').title(),
                                'Data Type': 'Device Type',
                                'Category': item['device'],
                                'Value': item['views'],
                                'Metric': 'Views',
                                'Export Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                        
                        # Geography
                        for item in audience_data.geography:
                            audience_export.append({
                                'Channel Name': channel['name'],
                                'Channel ID': channel['id'],
                                'Content Focus': channel['content_focus'].replace('_', ' ').title(),
                                'Data Type': 'Geography',
                                'Category': item['country'],
                                'Value': item['views'],
                                'Metric': 'Views',
                                'Export Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                    
                    if audience_export:
                        df_audience = pd.DataFrame(audience_export)
                        csv_audience = df_audience.to_csv(index=False)
                        
                        filename = f"dental_channels_audience_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
                        
                        st.download_button(
                            label="📥 Download Audience CSV",
                            data=csv_audience,
                            file_name=filename,
                            mime="text/csv",
                            key="audience_download",
                            help="Download audience demographics and device usage data"
                        )
                        st.success(f"✅ Audience export ready! ({len(audience_export)} data points)")
        
        with col4:
            if st.button("📋 Export Full Report", type="primary", use_container_width=True):
                with st.spinner("Generating comprehensive report..."):
                    # Generate comprehensive JSON report
                    report_data = {
                        'report_metadata': {
                            'generated_at': datetime.now().isoformat(),
                            'period': period_text,
                            'period_days': days,
                            'environment': 'Streamlit Cloud' if IS_STREAMLIT_CLOUD else 'Local Development',
                            'total_channels_configured': len(UPLOAD_CHANNELS),
                            'authenticated_channels': len(authenticated_channels),
                            'authentication_rate': f"{len(authenticated_channels)/len(UPLOAD_CHANNELS)*100:.1f}%"
                        },
                        'authentication_summary': {
                            'total_channels': len(UPLOAD_CHANNELS),
                            'authenticated_channels': len(authenticated_channels),
                            'failed_channels': len(UPLOAD_CHANNELS) - len(authenticated_channels),
                            'success_rate': f"{len(authenticated_channels)/len(UPLOAD_CHANNELS)*100:.1f}%"
                        },
                        'channels': []
                    }
                    
                    # Collect comprehensive data for each channel
                    for channel in authenticated_channel_configs:
                        analytics = service.get_channel_analytics(channel['id'], channel['name'], days)
                        time_series = service.get_time_series_data(channel['id'], days)
                        audience_data = service.get_audience_analytics(channel['id'], days)
                        
                        if analytics and analytics.auth_status == "Authenticated":
                            engagement_rate = ((analytics.period_likes + analytics.period_comments) / max(analytics.period_views, 1)) * 100
                            
                            channel_report = {
                                'channel_info': {
                                    'name': analytics.channel_name,
                                    'id': analytics.channel_id,
                                    'content_focus': analytics.content_focus,
                                    'description': analytics.description,
                                    'color': channel.get('color', '#4facfe')
                                },
                                'authentication': {
                                    'status': analytics.auth_status,
                                    'method': 'Streamlit Secrets' if IS_STREAMLIT_CLOUD else 'Local OAuth',
                                    'credentials_file': channel.get('credentials_file', 'N/A'),
                                    'last_authenticated': datetime.now().isoformat()
                                },
                                'performance_metrics': {
                                    'views': analytics.period_views,
                                    'watch_time_hours': round(analytics.period_watch_time_hours, 2),
                                    'subscribers_gained': analytics.period_subscribers_gained,
                                    'likes': analytics.period_likes,
                                    'comments': analytics.period_comments,
                                    'shares': analytics.period_shares,
                                    'average_view_duration_seconds': round(analytics.average_view_duration, 2),
                                    'engagement_rate_percent': round(engagement_rate, 2),
                                    'estimated_revenue': analytics.estimated_revenue,
                                    'cpm': analytics.cpm
                                },
                                'time_series_data': {
                                    'dates': time_series.dates,
                                    'daily_views': time_series.views,
                                    'daily_watch_time_hours': [round(wt, 2) for wt in time_series.watch_time],
                                    'daily_subscribers_gained': time_series.subscribers,
                                    'data_points': len(time_series.dates)
                                },
                                'audience_analytics': {
                                    'device_types': audience_data.device_types,
                                    'geography': audience_data.geography,
                                    'demographics': audience_data.age_gender,
                                    'traffic_sources': audience_data.traffic_sources,
                                    'playback_locations': audience_data.playback_locations
                                },
                                'insights': {
                                    'performance_ranking': 'TBD',  # Will be calculated after all channels
                                    'growth_trend': 'TBD',
                                    'engagement_level': 'High' if engagement_rate > 3 else 'Medium' if engagement_rate > 1 else 'Low'
                                }
                            }
                            report_data['channels'].append(channel_report)
                    
                    # Add cross-channel insights
                    if len(report_data['channels']) > 1:
                        all_views = [ch['performance_metrics']['views'] for ch in report_data['channels']]
                        all_engagement = [ch['performance_metrics']['engagement_rate_percent'] for ch in report_data['channels']]
                        
                        report_data['cross_channel_insights'] = {
                            'total_combined_views': sum(all_views),
                            'average_engagement_rate': round(sum(all_engagement) / len(all_engagement), 2),
                            'best_performing_channel': max(report_data['channels'], key=lambda x: x['performance_metrics']['views'])['channel_info']['name'],
                            'most_engaging_channel': max(report_data['channels'], key=lambda x: x['performance_metrics']['engagement_rate_percent'])['channel_info']['name']
                        }
                    
                    # Convert to JSON
                    json_report = json.dumps(report_data, indent=2, ensure_ascii=False)
                    
                    filename = f"dental_channels_full_report_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
                    
                    st.download_button(
                        label="📥 Download Full JSON Report",
                        data=json_report,
                        file_name=filename,
                        mime="application/json",
                        key="full_report_download",
                        help="Download comprehensive report with all analytics data and insights"
                    )
                    st.success(f"✅ Full report ready! ({len(report_data['channels'])} channels)")
        
        # Export summary and guidance
        # st.markdown("### 📊 Export Information")
        # col1, col2 = st.columns(2)
        
        # with col1:
        #     st.info(f"""
        #     **Export Summary:**
        #     - **Channels Available**: {len(authenticated_channels)} of {len(UPLOAD_CHANNELS)}
        #     - **Time Period**: {period_text}
        #     - **Export Types**: 4 different formats available
        #     - **Data Quality**: Production-ready with validation
        #     """)
        
        # with col2:
        #     st.info(f"""
        #     **Export Details:**
        #     - **CSV Files**: Excel-compatible, easy analysis
        #     - **JSON Report**: Complete data with metadata
        #     - **Time Series**: Daily performance tracking
        #     - **Audience Data**: Demographics and behavior
        #     """)
    
    def run(self):
        """Main application runner with comprehensive error handling"""
        try:
            # Check for deployment guide request
            if hasattr(st.session_state, 'show_deployment_guide') and st.session_state.show_deployment_guide:
                self.render_header()
                self.render_deployment_guide()
                
                if st.button("← Back to Dashboard", type="primary"):
                    st.session_state.show_deployment_guide = False
                    st.rerun()
                return
            
            # Initialize YouTube Analytics service
            with st.spinner("🔐 Initializing YouTube Analytics service..."):
                service = YouTubeAnalyticsService()
            
            # Render main interface
            self.render_header()
            
            # Sidebar navigation
            days, period_text = self.render_sidebar(service)
            
            # Main content routing
            if st.session_state.selected_channel is None:
                # Overview dashboard
                self.render_overview_dashboard(service, days, period_text)
            else:
                # Individual channel dashboard
                self.render_channel_dashboard(service, st.session_state.selected_channel, days, period_text)
            
            # Separator
            st.markdown("---")
            
            # Export functionality
            self.render_export_functionality(service, days, period_text)
            
            # Reset error count on successful run
            st.session_state.error_count = 0
            
        except Exception as e:
            # Increment error count
            st.session_state.error_count = getattr(st.session_state, 'error_count', 0) + 1
            
            # Log error
            logger.error(f"Dashboard error (attempt {st.session_state.error_count}): {e}", exc_info=True)
            
            # User-friendly error display
            st.error(f"❌ Dashboard Error: {str(e)}")
            
            # Show troubleshooting if multiple errors
            if st.session_state.error_count >= 2:
                st.markdown("## 🔧 Troubleshooting Assistant")
                
                # Environment-specific troubleshooting
                tab1, tab2, tab3 = st.tabs(["Quick Fixes", "Authentication Issues", "Contact Support"])
                
                with tab1:
                    st.markdown("""
                    ### 🚀 Quick Fixes
                    
                    1. **Refresh the page** - Sometimes a simple refresh resolves temporary issues
                    2. **Check your internet connection** - API calls require stable connectivity
                    3. **Clear browser cache** - Old cached data might cause conflicts
                    4. **Try a different browser** - Browser-specific issues can occur
                    
                    **Environment-Specific:**
                    """)
                    
                    if IS_STREAMLIT_CLOUD:
                        st.info("""
                        **Streamlit Cloud:**
                        - Check if secrets are properly configured
                        - Verify tokens haven't expired
                        - Restart the app from Streamlit Cloud dashboard
                        """)
                    else:
                        st.info("""
                        **Local Development:**
                        - Ensure all credential files are present
                        - Check file permissions (should be readable)
                        - Restart the Streamlit application
                        """)
                
                with tab2:
                    st.markdown("""
                    ### 🔐 Authentication Issues
                    
                    **Common Problems:**
                    - **403 Forbidden**: You don't own/manage the channel
                    - **401 Unauthorized**: Token expired or invalid
                    - **404 Not Found**: Channel ID is incorrect
                    - **429 Rate Limited**: Too many API requests
                    
                    **Solutions:**
                    1. Verify you own/manage all configured channels
                    2. Check channel IDs are correct (found in YouTube Studio)
                    3. Ensure YouTube Analytics API is enabled in Google Cloud Console
                    4. Re-authenticate if tokens are expired
                    """)
                    
                    # Show current authentication status
                    if 'service' in locals():
                        auth_status = service.get_authentication_status()
                        st.markdown("**Current Authentication Status:**")
                        for channel_id, auth in auth_status.items():
                            status_icon = "✅" if auth.is_authenticated else "❌"
                            st.markdown(f"- {status_icon} {auth.channel_name}: {auth.error_message or 'Authenticated'}")
                
                with tab3:
                    st.markdown("""
                    ### 📞 Contact Support
                    
                    If issues persist, please provide the following information:
                    
                    **System Information:**
                    - Environment: {env}
                    - Error Count: {count}
                    - Last Error: {error}
                    - Time: {time}
                    
                    **Debugging Steps Completed:**
                    - [ ] Refreshed the page
                    - [ ] Checked internet connection
                    - [ ] Verified authentication status
                    - [ ] Reviewed channel configuration
                    
                    **Next Steps:**
                    1. Copy the error information above
                    2. Check the GitHub repository for known issues
                    3. Create a new issue with error details
                    4. Include steps to reproduce the problem
                    """.format(
                        env="Streamlit Cloud" if IS_STREAMLIT_CLOUD else "Local Development",
                        count=st.session_state.error_count,
                        error=str(e)[:100] + "..." if len(str(e)) > 100 else str(e),
                        time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ))
                
                # Reset error count button
                if st.button("🔄 Reset Error Counter", type="secondary"):
                    st.session_state.error_count = 0
                    st.success("Error counter reset. Try refreshing the page.")
        
        # Footer with comprehensive information
        self.render_footer()
    
    def render_footer(self):
        """Render comprehensive footer with system information"""
        st.markdown("---")
        
        # System status
        env_status = "☁️ Streamlit Community Cloud" if IS_STREAMLIT_CLOUD else "💻 Local Development"
        auth_method = "Streamlit Secrets" if IS_STREAMLIT_CLOUD else "OAuth Files"
        
        # Channel status summary
        try:
            if hasattr(st.session_state, 'service'):
                authenticated_count = len(st.session_state.service.get_authenticated_channels())
                total_count = len(UPLOAD_CHANNELS)
                auth_rate = f"{authenticated_count}/{total_count}"
            else:
                auth_rate = "Unknown"
        except:
            auth_rate = "Error"
        
        st.markdown(
            f"""
       
        """
        , unsafe_allow_html=True)

# Application entry point with proper error handling
if __name__ == "__main__":
    import sys
    import subprocess
    
    # Check if running with streamlit
    if 'streamlit' not in sys.modules:
        print("🦷 Dental Channels Analytics Dashboard")
        print("=" * 50)
        print("This is a Streamlit application.")
        print("Starting with Streamlit...")
        print("=" * 50)
        
        try:
            subprocess.run([sys.executable, "-m", "streamlit", "run", __file__] + sys.argv[1:])
        except KeyboardInterrupt:
            print("\n👋 Application stopped by user")
        except Exception as e:
            print(f"❌ Error starting application: {e}")
            print("Please ensure Streamlit is installed: pip install streamlit")
    else:
        # Running within Streamlit
        try:
            dashboard = DentalChannelsDashboard()
            dashboard.run()
        except Exception as e:
            st.error(f"❌ Critical error: {e}")
            st.markdown("""
            ### 🔧 Critical Error Recovery
            
            A critical error occurred during dashboard initialization. Please try:
            
            1. **Refresh the page** (F5 or Ctrl+R)
            2. **Check your internet connection**
            3. **Verify authentication credentials**
            4. **Contact support** if the issue persists
            
            **Error Details:**
            ```
            {error}
            ```
            """.format(error=str(e)))

# Requirements for deployment
REQUIREMENTS_TXT = """
streamlit>=1.28.0
google-api-python-client>=2.100.0
google-auth-httplib2>=0.1.1
google-auth-oauthlib>=1.1.0
google-auth>=2.22.0
plotly>=5.15.0
pandas>=2.0.0
python-dateutil>=2.8.0
"""

# Create requirements.txt file helper
def create_requirements_file():
    """Helper function to create requirements.txt"""
    with open('requirements.txt', 'w') as f:
        f.write(REQUIREMENTS_TXT.strip())
    print("✅ Created requirements.txt file")

# Deployment helper
def setup_deployment():
    """Helper function for deployment setup"""
    print("🚀 Dental Channels Analytics Dashboard - Deployment Setup")
    print("=" * 60)
    print()
    
    print("1. Creating requirements.txt...")
    create_requirements_file()
    
    print("\n2. Next steps for deployment:")
    print("   📁 Local Development:")
    print("      - Place OAuth credential JSON files in this directory")
    print("      - Run: streamlit run app.py")
    print("      - Complete OAuth flow for each channel")
    print()
    print("   ☁️ Streamlit Cloud:")
    print("      - Push code to GitHub (without credential files!)")
    print("      - Deploy to share.streamlit.io")
    print("      - Configure secrets with token data")
    print()
    print("3. Configuration required:")
    print("   - Update UPLOAD_CHANNELS with your actual YouTube channel IDs")
    print("   - Enable YouTube Analytics API in Google Cloud Console")
    print("   - Create OAuth 2.0 credentials for each channel")
    print()
    print("✅ Setup complete! See deployment guide in the app for detailed instructions.")

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--setup":
    setup_deployment()