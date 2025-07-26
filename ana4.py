# import streamlit as st
# import pandas as pd
# import plotly.express as px
# import plotly.graph_objects as go
# from plotly.subplots import make_subplots
# import json
# import logging
# from datetime import datetime, timedelta
# from typing import Dict, List, Optional
# from dataclasses import dataclass
# import time
# from pathlib import Path

# try:
#     from googleapiclient.discovery import build
#     from google.oauth2.credentials import Credentials
#     from google_auth_oauthlib.flow import InstalledAppFlow
#     from google.auth.transport.requests import Request
# except ImportError as e:
#     st.error(f"Missing required libraries. Please install: pip install {e.name}")
#     st.stop()

# # Configure logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# # Channel Configuration - Each channel has its own credentials file
# UPLOAD_CHANNELS = [
#     {
#         "name": "Dental Advisor",
#         "id": "UCsw6IbObS8mtNQqbbZSKvog",
#         "credentials_file": "dental_advisor_credentials.json",
#         "token_file": "dental_advisor_token.json",
#         "description": "Primary channel for MIH educational content",
#         "privacy_status": "public",
#         "category_id": "27",  # Education category
#         "default_language": "en",
#         "tags_prefix": ["#DrGreenwall", "#MIHEducation"],
#         "content_focus": "primary_education"
#     },
#     {
#         "name": "MIH",
#         "id": "UCt56aIAG8gNuKM0hJpWYm9Q",
#         "credentials_file": "mih_credentials.json",
#         "token_file": "mih_token.json",
#         "description": "Specialized MIH treatment and care guidance",
#         "privacy_status": "public",
#         "category_id": "27",
#         "default_language": "en",
#         "tags_prefix": ["#MIHTreatment", "#EnamelCare"],
#         "content_focus": "treatment_focused"
#     },
#     {
#         "name": "Enamel Hypoplasia",
#         "id": "UCnBJEdDIsC7b3oAvaBPje3Q",
#         "credentials_file": "enamel_hypoplasia_credentials.json",
#         "token_file": "enamel_hypoplasia_token.json",
#         "description": "Comprehensive pediatric dental care and whitening",
#         "privacy_status": "public",
#         "category_id": "27",
#         "default_language": "en",
#         "tags_prefix": ["#PediatricDentistry", "#ChildrenTeeth"],
#         "content_focus": "pediatric_care"
#     }
# ]

# @dataclass
# class ChannelAnalytics:
#     """Data class for channel analytics from YouTube Analytics API"""
#     channel_id: str
#     channel_name: str
#     period_views: int
#     period_watch_time_hours: float
#     period_subscribers_gained: int
#     period_likes: int
#     period_comments: int
#     period_shares: int
#     average_view_duration: float
#     estimated_revenue: float
#     cpm: float
#     content_focus: str
#     description: str
#     auth_status: str

# @dataclass 
# class AudienceData:
#     """Data class for audience analytics"""
#     age_gender: List[Dict]
#     device_types: List[Dict]
#     traffic_sources: List[Dict]
#     geography: List[Dict]
#     playback_locations: List[Dict]

# @dataclass
# class TimeSeriesData:
#     """Data class for time series analytics"""
#     dates: List[str]
#     views: List[int]
#     watch_time: List[float]
#     subscribers: List[int]
#     estimated_revenue: List[float]

# @dataclass
# class ChannelAuth:
#     """Data class for channel authentication status"""
#     channel_id: str
#     channel_name: str
#     is_authenticated: bool
#     analytics_service: Optional[object]
#     error_message: Optional[str]

# class YouTubeAnalyticsService:
#     """YouTube Analytics API service with individual channel authentication"""
    
#     SCOPES = ['https://www.googleapis.com/auth/yt-analytics.readonly']
    
#     def __init__(self):
#         self.channels = UPLOAD_CHANNELS
#         self.channel_auth_status = {}
#         self._authenticate_all_channels()
    
#     def _authenticate_channel(self, channel_config: Dict) -> ChannelAuth:
#         """Authenticate a single channel"""
#         channel_id = channel_config['id']
#         channel_name = channel_config['name']
#         credentials_file = channel_config['credentials_file']
#         token_file = channel_config['token_file']
        
#         try:
#             creds = None
            
#             # Load existing token if available
#             if Path(token_file).exists():
#                 try:
#                     creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
#                 except Exception as e:
#                     logger.warning(f"Failed to load existing token for {channel_name}: {e}")
#                     creds = None
            
#             # Refresh or get new credentials
#             if not creds or not creds.valid:
#                 if creds and creds.expired and creds.refresh_token:
#                     try:
#                         creds.refresh(Request())
#                         logger.info(f"Refreshed credentials for {channel_name}")
#                     except Exception as e:
#                         logger.warning(f"Failed to refresh token for {channel_name}: {e}")
#                         creds = None
                
#                 if not creds:
#                     if not Path(credentials_file).exists():
#                         error_msg = f"Credentials file not found: {credentials_file}"
#                         logger.error(error_msg)
#                         return ChannelAuth(
#                             channel_id=channel_id,
#                             channel_name=channel_name,
#                             is_authenticated=False,
#                             analytics_service=None,
#                             error_message=error_msg
#                         )
                    
#                     try:
#                         flow = InstalledAppFlow.from_client_secrets_file(credentials_file, self.SCOPES)
#                         creds = flow.run_local_server(port=0)
#                         logger.info(f"Completed OAuth flow for {channel_name}")
#                     except Exception as e:
#                         error_msg = f"OAuth flow failed for {channel_name}: {e}"
#                         logger.error(error_msg)
#                         return ChannelAuth(
#                             channel_id=channel_id,
#                             channel_name=channel_name,
#                             is_authenticated=False,
#                             analytics_service=None,
#                             error_message=error_msg
#                         )
                
#                 # Save the credentials
#                 try:
#                     with open(token_file, 'w') as token:
#                         token.write(creds.to_json())
#                     logger.info(f"Saved credentials for {channel_name}")
#                 except Exception as e:
#                     logger.warning(f"Failed to save token for {channel_name}: {e}")
            
#             # Build the analytics service
#             try:
#                 analytics_service = build('youtubeAnalytics', 'v2', credentials=creds)
                
#                 # Test the authentication by making a simple query
#                 test_query = analytics_service.reports().query(
#                     ids=f'channel=={channel_id}',
#                     startDate='2023-01-01',
#                     endDate=datetime.now().strftime('%Y-%m-%d'),
#                     metrics='views'
#                 ).execute()
                
#                 logger.info(f"Successfully authenticated {channel_name}")
#                 return ChannelAuth(
#                     channel_id=channel_id,
#                     channel_name=channel_name,
#                     is_authenticated=True,
#                     analytics_service=analytics_service,
#                     error_message=None
#                 )
                
#             except Exception as e:
#                 error_msg = f"Failed to build analytics service or test access for {channel_name}: {e}"
#                 logger.error(error_msg)
#                 return ChannelAuth(
#                     channel_id=channel_id,
#                     channel_name=channel_name,
#                     is_authenticated=False,
#                     analytics_service=None,
#                     error_message=error_msg
#                 )
            
#         except Exception as e:
#             error_msg = f"Unexpected error authenticating {channel_name}: {e}"
#             logger.error(error_msg)
#             return ChannelAuth(
#                 channel_id=channel_id,
#                 channel_name=channel_name,
#                 is_authenticated=False,
#                 analytics_service=None,
#                 error_message=error_msg
#             )
    
#     def _authenticate_all_channels(self):
#         """Authenticate all channels individually"""
#         logger.info("Starting authentication for all channels...")
        
#         for channel_config in self.channels:
#             channel_name = channel_config['name']
#             logger.info(f"Authenticating {channel_name}...")
            
#             auth_result = self._authenticate_channel(channel_config)
#             self.channel_auth_status[channel_config['id']] = auth_result
            
#             if auth_result.is_authenticated:
#                 logger.info(f"✅ {channel_name} authenticated successfully")
#             else:
#                 logger.error(f"❌ {channel_name} authentication failed: {auth_result.error_message}")
        
#         # Summary
#         authenticated_count = sum(1 for auth in self.channel_auth_status.values() if auth.is_authenticated)
#         total_count = len(self.channels)
#         logger.info(f"Authentication complete: {authenticated_count}/{total_count} channels authenticated")
    
#     def get_authenticated_channels(self) -> List[str]:
#         """Get list of successfully authenticated channel IDs"""
#         return [channel_id for channel_id, auth in self.channel_auth_status.items() 
#                 if auth.is_authenticated]
    
#     def get_authentication_status(self) -> Dict[str, ChannelAuth]:
#         """Get authentication status for all channels"""
#         return self.channel_auth_status
    
#     def get_analytics_service(self, channel_id: str) -> Optional[object]:
#         """Get analytics service for a specific channel"""
#         auth_status = self.channel_auth_status.get(channel_id)
#         if auth_status and auth_status.is_authenticated:
#             return auth_status.analytics_service
#         return None
    
#     def get_date_range(self, days: int) -> tuple:
#         """Get start and end dates for analytics queries"""
#         if days == -1:  # All time
#             start_date = '2005-04-23'
#         else:
#             start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
#         end_date = datetime.now().strftime('%Y-%m-%d')
#         return start_date, end_date
    
#     def get_channel_analytics(self, channel_id: str, channel_name: str, days: int = 30) -> Optional[ChannelAnalytics]:
#         """Get channel analytics using YouTube Analytics API"""
#         analytics_service = self.get_analytics_service(channel_id)
#         auth_status = self.channel_auth_status.get(channel_id)
        
#         if not analytics_service:
#             logger.error(f"No authenticated service for {channel_name}")
#             # Return empty analytics with auth status
#             channel_config = next((ch for ch in self.channels if ch['id'] == channel_id), {})
#             return ChannelAnalytics(
#                 channel_id=channel_id,
#                 channel_name=channel_name,
#                 period_views=0,
#                 period_watch_time_hours=0,
#                 period_subscribers_gained=0,
#                 period_likes=0,
#                 period_comments=0,
#                 period_shares=0,
#                 average_view_duration=0,
#                 estimated_revenue=0,
#                 cpm=0,
#                 content_focus=channel_config.get('content_focus', 'general'),
#                 description=channel_config.get('description', 'Dental education content'),
#                 auth_status=f"Authentication failed: {auth_status.error_message if auth_status else 'Unknown error'}"
#             )
        
#         try:
#             start_date, end_date = self.get_date_range(days)
            
#             logger.info(f"Getting analytics for {channel_name} from {start_date} to {end_date}")
            
#             # Get main analytics metrics
#             try:
#                 main_metrics = analytics_service.reports().query(
#                     ids=f'channel=={channel_id}',
#                     startDate=start_date,
#                     endDate=end_date,
#                     metrics='views,estimatedMinutesWatched,subscribersGained,likes,comments,shares,averageViewDuration'
#                 ).execute()
                
#                 analytics_data = main_metrics.get('rows', [[0, 0, 0, 0, 0, 0, 0]])[0]
#             except Exception as e:
#                 logger.warning(f"Some metrics unavailable for {channel_name}: {e}")
#                 # Try with just basic metrics
#                 try:
#                     basic_metrics = analytics_service.reports().query(
#                         ids=f'channel=={channel_id}',
#                         startDate=start_date,
#                         endDate=end_date,
#                         metrics='views,estimatedMinutesWatched,subscribersGained'
#                     ).execute()
                    
#                     basic_data = basic_metrics.get('rows', [[0, 0, 0]])[0]
#                     analytics_data = basic_data + [0, 0, 0, 0]  # Pad with zeros for missing metrics
#                 except Exception as e2:
#                     logger.error(f"Failed to get basic metrics for {channel_name}: {e2}")
#                     analytics_data = [0, 0, 0, 0, 0, 0, 0]
            
#             # Skip revenue metrics as they require special permissions
#             estimated_revenue = 0
#             cpm = 0
            
#             # Find channel config
#             channel_config = next((ch for ch in self.channels if ch['id'] == channel_id), {})
            
#             return ChannelAnalytics(
#                 channel_id=channel_id,
#                 channel_name=channel_name,
#                 period_views=analytics_data[0] if len(analytics_data) > 0 else 0,
#                 period_watch_time_hours=(analytics_data[1] if len(analytics_data) > 1 else 0) / 60,
#                 period_subscribers_gained=analytics_data[2] if len(analytics_data) > 2 else 0,
#                 period_likes=analytics_data[3] if len(analytics_data) > 3 else 0,
#                 period_comments=analytics_data[4] if len(analytics_data) > 4 else 0,
#                 period_shares=analytics_data[5] if len(analytics_data) > 5 else 0,
#                 average_view_duration=analytics_data[6] if len(analytics_data) > 6 else 0,
#                 estimated_revenue=estimated_revenue,
#                 cpm=cpm,
#                 content_focus=channel_config.get('content_focus', 'general'),
#                 description=channel_config.get('description', 'Dental education content'),
#                 auth_status="Authenticated"
#             )
            
#         except Exception as e:
#             logger.error(f"Failed to get analytics for {channel_name}: {e}")
#             return None
    
#     def get_time_series_data(self, channel_id: str, days: int = 30) -> TimeSeriesData:
#         """Get time series data for charts"""
#         analytics_service = self.get_analytics_service(channel_id)
        
#         if not analytics_service:
#             return TimeSeriesData([], [], [], [], [])
        
#         try:
#             start_date, end_date = self.get_date_range(days)
            
#             # Get daily time series data
#             time_series = analytics_service.reports().query(
#                 ids=f'channel=={channel_id}',
#                 startDate=start_date,
#                 endDate=end_date,
#                 metrics='views,estimatedMinutesWatched,subscribersGained',
#                 dimensions='day'
#             ).execute()
            
#             dates = []
#             views = []
#             watch_time = []
#             subscribers = []
#             estimated_revenue = []
            
#             for row in time_series.get('rows', []):
#                 dates.append(row[0])
#                 views.append(row[1] if len(row) > 1 else 0)
#                 watch_time.append((row[2] if len(row) > 2 else 0) / 60)  # Convert to hours
#                 subscribers.append(row[3] if len(row) > 3 else 0)
#                 estimated_revenue.append(0)  # Revenue data usually not available daily
            
#             return TimeSeriesData(dates, views, watch_time, subscribers, estimated_revenue)
            
#         except Exception as e:
#             logger.error(f"Failed to get time series data: {e}")
#             return TimeSeriesData([], [], [], [], [])
    
#     def get_audience_analytics(self, channel_id: str, days: int = 30) -> AudienceData:
#         """Get audience analytics using YouTube Analytics API"""
#         analytics_service = self.get_analytics_service(channel_id)
        
#         if not analytics_service:
#             return AudienceData([], [], [], [], [])
        
#         try:
#             start_date, end_date = self.get_date_range(days)
            
#             age_gender = []
#             device_types = []
#             traffic_sources = []
#             geography = []
#             playback_locations = []
            
#             # Age and Gender demographics
#             try:
#                 age_gender_response = analytics_service.reports().query(
#                     ids=f'channel=={channel_id}',
#                     startDate=start_date,
#                     endDate=end_date,
#                     metrics='viewerPercentage',
#                     dimensions='ageGroup,gender'
#                 ).execute()
                
#                 age_gender = [
#                     {'age_group': row[0], 'gender': row[1], 'percentage': row[2]}
#                     for row in age_gender_response.get('rows', [])
#                 ]
#             except Exception as e:
#                 logger.warning(f"Age/Gender data unavailable: {e}")
            
#             # Device types
#             try:
#                 device_response = analytics_service.reports().query(
#                     ids=f'channel=={channel_id}',
#                     startDate=start_date,
#                     endDate=end_date,
#                     metrics='views',
#                     dimensions='deviceType'
#                 ).execute()
                
#                 device_types = [
#                     {'device': row[0], 'views': row[1]}
#                     for row in device_response.get('rows', [])
#                 ]
#             except Exception as e:
#                 logger.warning(f"Device data unavailable: {e}")
            
#             # Traffic sources
#             try:
#                 traffic_response = analytics_service.reports().query(
#                     ids=f'channel=={channel_id}',
#                     startDate=start_date,
#                     endDate=end_date,
#                     metrics='views',
#                     dimensions='insightTrafficSourceType'
#                 ).execute()
                
#                 traffic_sources = [
#                     {'source': row[0], 'views': row[1]}
#                     for row in traffic_response.get('rows', [])
#                 ]
#             except Exception as e:
#                 logger.warning(f"Traffic source data unavailable: {e}")
#                 # Try alternative dimension
#                 try:
#                     traffic_response = analytics_service.reports().query(
#                         ids=f'channel=={channel_id}',
#                         startDate=start_date,
#                         endDate=end_date,
#                         metrics='views',
#                         dimensions='trafficSourceDetail'
#                     ).execute()
                    
#                     traffic_sources = [
#                         {'source': row[0], 'views': row[1]}
#                         for row in traffic_response.get('rows', [])
#                     ]
#                 except Exception as e2:
#                     logger.warning(f"Alternative traffic source dimension also failed: {e2}")
            
#             # Geography
#             try:
#                 geo_response = analytics_service.reports().query(
#                     ids=f'channel=={channel_id}',
#                     startDate=start_date,
#                     endDate=end_date,
#                     metrics='views',
#                     dimensions='country',
#                     sort='-views',
#                     maxResults=10
#                 ).execute()
                
#                 geography = [
#                     {'country': row[0], 'views': row[1]}
#                     for row in geo_response.get('rows', [])
#                 ]
#             except Exception as e:
#                 logger.warning(f"Geography data unavailable: {e}")
            
#             # Playback locations
#             try:
#                 playback_response = analytics_service.reports().query(
#                     ids=f'channel=={channel_id}',
#                     startDate=start_date,
#                     endDate=end_date,
#                     metrics='views',
#                     dimensions='insightPlaybackLocationType'
#                 ).execute()
                
#                 playback_locations = [
#                     {'location': row[0], 'views': row[1]}
#                     for row in playback_response.get('rows', [])
#                 ]
#             except Exception as e:
#                 logger.warning(f"Playback location data unavailable: {e}")
            
#             return AudienceData(age_gender, device_types, traffic_sources, geography, playback_locations)
            
#         except Exception as e:
#             logger.error(f"Failed to get audience analytics: {e}")
#             return AudienceData([], [], [], [], [])

# class DentalChannelsDashboard:
#     """Dashboard for dental education YouTube channels"""
    
#     def __init__(self):
#         st.set_page_config(
#             page_title="Dental Channels Analytics Dashboard",
#             page_icon="🦷",
#             layout="wide",
#             initial_sidebar_state="expanded"
#         )
        
#         # Initialize session state
#         if 'selected_channel' not in st.session_state:
#             st.session_state.selected_channel = None
        
#         # Custom CSS
#         st.markdown("""
#         <style>
#         .main-header {
#             background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
#             color: white;
#             padding: 2rem;
#             border-radius: 15px;
#             text-align: center;
#             margin-bottom: 2rem;
#             box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
#         }
        
#         .channel-card {
#             background: white;
#             padding: 1.5rem;
#             border-radius: 12px;
#             border-left: 4px solid #4facfe;
#             box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
#             margin-bottom: 1rem;
#             transition: transform 0.2s ease;
#         }
        
#         .channel-card:hover {
#             transform: translateY(-4px);
#         }
        
#         .channel-card.error {
#             border-left-color: #ff4757;
#             background: #fff5f5;
#         }
        
#         .channel-card.success {
#             border-left-color: #2ed573;
#             background: #f0fff4;
#         }
        
#         .dental-metric {
#             background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
#             padding: 1rem;
#             border-radius: 10px;
#             text-align: center;
#             margin: 0.5rem 0;
#         }
        
#         .content-focus-badge {
#             background: #4facfe;
#             color: white;
#             padding: 0.3rem 0.8rem;
#             border-radius: 15px;
#             font-size: 0.8rem;
#             font-weight: bold;
#         }
        
#         .auth-status {
#             padding: 0.3rem 0.8rem;
#             border-radius: 15px;
#             font-size: 0.8rem;
#             font-weight: bold;
#             margin-left: 0.5rem;
#         }
        
#         .auth-success {
#             background: #2ed573;
#             color: white;
#         }
        
#         .auth-error {
#             background: #ff4757;
#             color: white;
#         }
#         </style>
#         """, unsafe_allow_html=True)
    
#     def render_header(self):
#         """Render dashboard header"""
#         st.markdown("""
#         <div class="main-header">
#             <h1>🦷 Dental Education Analytics Dashboard</h1>
#             <p style="font-size: 1.2rem; margin-top: 1rem; opacity: 0.9;">
#                 Comprehensive YouTube Analytics for Dental Education Channels
#             </p>
#             <p style="font-size: 1rem; opacity: 0.8;">
#                 MIH Education • Pediatric Dentistry • Enamel Care
#             </p>
#         </div>
#         """, unsafe_allow_html=True)
    
#     def render_authentication_status(self, service):
#         """Render authentication status for all channels"""
#         st.markdown("### 🔐 Channel Authentication Status")
        
#         auth_status = service.get_authentication_status()
#         authenticated_channels = service.get_authenticated_channels()
        
#         for channel_config in UPLOAD_CHANNELS:
#             channel_id = channel_config['id']
#             channel_name = channel_config['name']
#             auth_info = auth_status.get(channel_id)
            
#             if auth_info and auth_info.is_authenticated:
#                 st.markdown(f"""
#                 <div class="channel-card success">
#                     <h4>✅ {channel_name}</h4>
#                     <p><strong>Status:</strong> <span class="auth-status auth-success">Authenticated</span></p>
#                     <p><strong>Focus:</strong> {channel_config['content_focus'].replace('_', ' ').title()}</p>
#                     <p><strong>Credentials:</strong> {channel_config['credentials_file']}</p>
#                 </div>
#                 """, unsafe_allow_html=True)
#             else:
#                 error_msg = auth_info.error_message if auth_info else "Unknown error"
#                 st.markdown(f"""
#                 <div class="channel-card error">
#                     <h4>❌ {channel_name}</h4>
#                     <p><strong>Status:</strong> <span class="auth-status auth-error">Authentication Failed</span></p>
#                     <p><strong>Error:</strong> {error_msg}</p>
#                     <p><strong>Credentials:</strong> {channel_config['credentials_file']}</p>
#                 </div>
#                 """, unsafe_allow_html=True)
        
#         # Summary
#         total_channels = len(UPLOAD_CHANNELS)
#         authenticated_count = len(authenticated_channels)
        
#         if authenticated_count == 0:
#             st.error(f"⚠️ No channels authenticated ({authenticated_count}/{total_channels})")
#             st.markdown("""
#             ### 🔧 Setup Instructions for Each Channel:
            
#             1. **Create separate OAuth credentials** for each channel:
#                - Go to [Google Cloud Console](https://console.cloud.google.com/)
#                - Create a new project or use existing one
#                - Enable YouTube Analytics API
#                - Create OAuth 2.0 credentials (Desktop Application)
#                - Download the JSON file
            
#             2. **Rename credentials files** according to the channel configuration:
#                - `dental_advisor_credentials.json` for Dental Advisor channel
#                - `mih_credentials.json` for MIH channel  
#                - `enamel_hypoplasia_credentials.json` for Enamel Hypoplasia channel
            
#             3. **Update channel IDs** in the code with your actual channel IDs
            
#             4. **Restart the application** and complete OAuth flow for each channel
#             """)
#         elif authenticated_count < total_channels:
#             st.warning(f"⚠️ Partial authentication ({authenticated_count}/{total_channels} channels)")
#         else:
#             st.success(f"✅ All channels authenticated ({authenticated_count}/{total_channels})")
    
#     def render_sidebar(self, service):
#         """Render sidebar controls"""
#         st.sidebar.markdown("## 🦷 Analytics Controls")
        
#         # Authentication status in sidebar
#         auth_status = service.get_authentication_status()
#         authenticated_count = len(service.get_authenticated_channels())
#         total_count = len(UPLOAD_CHANNELS)
        
#         if authenticated_count == total_count:
#             st.sidebar.success(f"🔐 All channels authenticated ({authenticated_count}/{total_count})")
#         elif authenticated_count > 0:
#             st.sidebar.warning(f"🔐 Partial authentication ({authenticated_count}/{total_count})")
#         else:
#             st.sidebar.error(f"🔐 No channels authenticated ({authenticated_count}/{total_count})")
        
#         # Time period selection
#         time_options = {
#             "7 days": 7,
#             "14 days": 14,
#             "30 days": 30,
#             "60 days": 60,
#             "90 days": 90,
#             "6 months": 180,
#             "1 year": 365,
#             "All time": -1
#         }
        
#         selected_period = st.sidebar.selectbox(
#             "📅 Select Time Period",
#             options=list(time_options.keys()),
#             index=2,  # Default to 30 days
#             help="Analytics data will be filtered for this time period"
#         )
        
#         days = time_options[selected_period]
        
#         # Period indicator
#         period_text = "All Time" if days == -1 else f"Last {days} days"
#         st.sidebar.markdown(f"""
#         <div style="background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); 
#                     color: #333; padding: 0.5rem 1rem; border-radius: 20px; 
#                     font-weight: bold; text-align: center; margin-bottom: 1rem;">
#             📊 Analyzing: {period_text}
#         </div>
#         """, unsafe_allow_html=True)
        
#         # Channel selection
#         st.sidebar.markdown("### 🎯 Channel Selection")
        
#         # All channels overview button
#         if st.sidebar.button("📊 All Channels Overview", type="primary", use_container_width=True):
#             st.session_state.selected_channel = None
#             st.rerun()
        
#         st.sidebar.markdown("#### Individual Channels:")
        
#         for channel in UPLOAD_CHANNELS:
#             channel_id = channel['id']
#             auth_info = auth_status.get(channel_id)
#             is_authenticated = auth_info and auth_info.is_authenticated
            
#             focus_color = {
#                 'primary_education': '🎓',
#                 'treatment_focused': '🏥',
#                 'pediatric_care': '👶'
#             }.get(channel['content_focus'], '📺')
            
#             # Add authentication indicator
#             auth_indicator = "✅" if is_authenticated else "❌"
#             button_type = "secondary" if is_authenticated else "secondary"
            
#             if st.sidebar.button(
#                 f"{auth_indicator} {focus_color} {channel['name']}",
#                 key=f"select_{channel['id']}",
#                 use_container_width=True,
#                 disabled=not is_authenticated,
#                 type=button_type
#             ):
#                 if is_authenticated:
#                     st.session_state.selected_channel = channel['id']
#                     st.rerun()
        
#         # Re-authenticate button
#         st.sidebar.markdown("---")
#         if st.sidebar.button("🔄 Re-authenticate All Channels", type="secondary", use_container_width=True):
#             # Clear all token files to force re-authentication
#             for channel in UPLOAD_CHANNELS:
#                 token_file = channel['token_file']
#                 if Path(token_file).exists():
#                     try:
#                         Path(token_file).unlink()
#                         st.sidebar.success(f"Cleared token for {channel['name']}")
#                     except Exception as e:
#                         st.sidebar.error(f"Failed to clear token for {channel['name']}: {e}")
            
#             st.sidebar.info("🔄 Please restart the application to re-authenticate")
        
#         # Setup instructions
#         st.sidebar.markdown("### 🔧 Setup Instructions")
        
#         with st.sidebar.expander("📝 Channel Setup Guide"):
#             st.markdown("""
#             **Required files for each channel:**
            
#             📁 **Dental Advisor Channel:**
#             - `dental_advisor_credentials.json`
#             - Auto-generated: `dental_advisor_token.json`
            
#             📁 **MIH Channel:**
#             - `mih_credentials.json`
#             - Auto-generated: `mih_token.json`
            
#             📁 **Enamel Hypoplasia Channel:**
#             - `enamel_hypoplasia_credentials.json`
#             - Auto-generated: `enamel_hypoplasia_token.json`
            
#             **Steps:**
#             1. Create separate OAuth 2.0 credentials for each channel
#             2. Download and rename JSON files as shown above
#             3. Update channel IDs in the code
#             4. Restart the application
#             5. Complete OAuth flow for each channel
#             """)
        
#         with st.sidebar.expander("⚠️ Troubleshooting"):
#             st.markdown("""
#             **Authentication Issues:**
            
#             🔴 **403 Forbidden:**
#             - Channel owner mismatch
#             - Missing Analytics API permissions
#             - Incorrect OAuth scope
            
#             🔴 **File Not Found:**
#             - Missing credentials JSON file
#             - Incorrect file naming
#             - Wrong file location
            
#             🔴 **Token Expired:**
#             - Use "Re-authenticate" button
#             - Check refresh token validity
#             - Recreate OAuth credentials if needed
            
#             **Solutions:**
#             - Verify you own/manage the channels
#             - Enable YouTube Analytics API in Google Cloud Console
#             - Use correct OAuth 2.0 credentials (Desktop App)
#             - Ensure files are in the same directory as the script
#             """)
        
#         st.sidebar.markdown("---")
#         if st.sidebar.button("🔄 Refresh Data", type="secondary", use_container_width=True):
#             st.success("🔄 Refreshing analytics data...")
#             time.sleep(1)
#             st.rerun()
        
#         st.sidebar.markdown("---")
#         st.sidebar.markdown("### 🦷 Channel Focus Areas")
#         st.sidebar.info("""
#         🎓 **Dental Advisor**: Primary MIH education
#         🏥 **MIH**: Treatment & care guidance  
#         👶 **Enamel Hypoplasia**: Pediatric dentistry
#         """)
        
#         return days, period_text
    
#     def render_overview_dashboard(self, service, days, period_text):
#         """Render overview dashboard for all channels"""
#         st.markdown(f"## 📊 All Channels Overview ({period_text})")
        
#         # Show authentication status first
#         self.render_authentication_status(service)
        
#         authenticated_channels = service.get_authenticated_channels()
#         if not authenticated_channels:
#             st.warning("⚠️ No authenticated channels available. Please check authentication status above.")
#             return
        
#         # Collect analytics from authenticated channels only
#         all_analytics = []
#         total_views = 0
#         total_watch_time = 0
#         total_subscribers_gained = 0
#         total_likes = 0
#         total_comments = 0
#         total_revenue = 0
        
#         # Progress indicator
#         progress_bar = st.progress(0)
#         status_text = st.empty()
        
#         authenticated_channel_configs = [ch for ch in UPLOAD_CHANNELS if ch['id'] in authenticated_channels]
        
#         for i, channel in enumerate(authenticated_channel_configs):
#             status_text.text(f"Loading analytics for {channel['name']}...")
#             progress_bar.progress((i + 1) / len(authenticated_channel_configs))
            
#             analytics = service.get_channel_analytics(channel['id'], channel['name'], days)
            
#             if analytics and analytics.auth_status == "Authenticated":
#                 all_analytics.append(analytics)
#                 total_views += analytics.period_views
#                 total_watch_time += analytics.period_watch_time_hours
#                 total_subscribers_gained += analytics.period_subscribers_gained
#                 total_likes += analytics.period_likes
#                 total_comments += analytics.period_comments
#                 total_revenue += analytics.estimated_revenue
        
#         # Clear progress indicators
#         progress_bar.empty()
#         status_text.empty()
        
#         # Summary metrics
#         if all_analytics:
#             st.markdown("### 📈 Combined Performance Metrics")
#             col1, col2, col3, col4, col5 = st.columns(5)
            
#             with col1:
#                 st.metric("👀 Total Views", f"{total_views:,}")
            
#             with col2:
#                 st.metric("⏱️ Watch Time", f"{total_watch_time:.1f}h")
            
#             with col3:
#                 st.metric("👥 New Subscribers", f"+{total_subscribers_gained}")
            
#             with col4:
#                 st.metric("👍 Total Likes", f"{total_likes:,}")
            
#             with col5:
#                 st.metric("💬 Comments", f"{total_comments:,}")
            
#             # Show analytics for available channels
#             st.info(f"📊 Showing data for {len(all_analytics)} authenticated channel(s) out of {len(UPLOAD_CHANNELS)} total channels.")
            
#             # Channel comparison charts
#             self.render_channel_comparison(all_analytics, period_text)
#             self.render_performance_breakdown(all_analytics, period_text)
#         else:
#             st.warning("⚠️ No analytics data available from authenticated channels.")
    
#     def render_channel_comparison(self, all_analytics, period_text):
#         """Render channel comparison charts"""
#         st.markdown(f"### 📈 Channel Performance Comparison ({period_text})")
        
#         # Prepare data for charts
#         channel_data = []
#         for analytics in all_analytics:
#             channel_data.append({
#                 'Channel': analytics.channel_name,
#                 'Views': analytics.period_views,
#                 'Watch Time (h)': analytics.period_watch_time_hours,
#                 'Subscribers Gained': analytics.period_subscribers_gained,
#                 'Engagement': analytics.period_likes + analytics.period_comments,
#                 'Avg View Duration (s)': analytics.average_view_duration,
#                 'Content Focus': analytics.content_focus.replace('_', ' ').title(),
#                 'Description': analytics.description,
#                 'Auth Status': analytics.auth_status
#             })
        
#         df = pd.DataFrame(channel_data)
        
#         col1, col2 = st.columns(2)
        
#         with col1:
#             # Views comparison
#             fig_views = px.bar(
#                 df,
#                 x='Channel',
#                 y='Views',
#                 color='Content Focus',
#                 title="Views by Channel",
#                 color_discrete_sequence=['#4facfe', '#00f2fe', '#a8edea'],
#                 hover_data=['Auth Status']
#             )
#             st.plotly_chart(fig_views, use_container_width=True)
            
#             # Subscribers gained
#             fig_subs = px.bar(
#                 df,
#                 x='Channel',
#                 y='Subscribers Gained',
#                 color='Content Focus',
#                 title="New Subscribers by Channel",
#                 color_discrete_sequence=['#fed6e3', '#f093fb', '#4facfe'],
#                 hover_data=['Auth Status']
#             )
#             st.plotly_chart(fig_subs, use_container_width=True)
        
#         with col2:
#             # Watch time comparison
#             fig_watch = px.bar(
#                 df,
#                 x='Channel',
#                 y='Watch Time (h)',
#                 color='Content Focus',
#                 title="Watch Time by Channel (Hours)",
#                 color_discrete_sequence=['#a8edea', '#4facfe', '#00f2fe'],
#                 hover_data=['Auth Status']
#             )
#             st.plotly_chart(fig_watch, use_container_width=True)
            
#             # Engagement scatter plot
#             fig_engagement = px.scatter(
#                 df,
#                 x='Views',
#                 y='Engagement',
#                 size='Watch Time (h)',
#                 color='Content Focus',
#                 hover_data=['Channel', 'Avg View Duration (s)', 'Auth Status'],
#                 title="Views vs Engagement",
#                 color_discrete_sequence=['#4facfe', '#00f2fe', '#a8edea']
#             )
#             st.plotly_chart(fig_engagement, use_container_width=True)
    
#     def render_performance_breakdown(self, all_analytics, period_text):
#         """Render detailed performance breakdown"""
#         st.markdown(f"### 🎯 Detailed Performance Breakdown ({period_text})")
        
#         # Create detailed table
#         detailed_data = []
#         for analytics in all_analytics:
#             detailed_data.append({
#                 'Channel': analytics.channel_name,
#                 'Auth Status': analytics.auth_status,
#                 'Focus Area': analytics.content_focus.replace('_', ' ').title(),
#                 'Views': f"{analytics.period_views:,}",
#                 'Watch Time': f"{analytics.period_watch_time_hours:.1f}h",
#                 'Avg Duration': f"{analytics.average_view_duration:.0f}s",
#                 'Subscribers': f"+{analytics.period_subscribers_gained}",
#                 'Likes': f"{analytics.period_likes:,}",
#                 'Comments': f"{analytics.period_comments:,}",
#                 'Shares': f"{analytics.period_shares:,}",
#                 'Revenue': f"${analytics.estimated_revenue:.2f}" if analytics.estimated_revenue > 0 else "N/A"
#             })
        
#         df_detailed = pd.DataFrame(detailed_data)
#         st.dataframe(df_detailed, use_container_width=True, hide_index=True)
        
#         # Performance insights
#         if all_analytics:
#             st.markdown("### 💡 Performance Insights")
            
#             # Find best performing channel
#             best_views = max(all_analytics, key=lambda x: x.period_views)
#             best_engagement = max(all_analytics, key=lambda x: x.period_likes + x.period_comments)
#             best_retention = max(all_analytics, key=lambda x: x.average_view_duration)
            
#             col1, col2, col3 = st.columns(3)
            
#             with col1:
#                 st.success(f"🏆 **Most Views**: {best_views.channel_name}")
#                 st.write(f"📊 {best_views.period_views:,} views")
#                 st.write(f"Focus: {best_views.content_focus.replace('_', ' ').title()}")
            
#             with col2:
#                 st.info(f"💬 **Best Engagement**: {best_engagement.channel_name}")
#                 total_engagement = best_engagement.period_likes + best_engagement.period_comments
#                 st.write(f"📊 {total_engagement:,} interactions")
#                 st.write(f"Focus: {best_engagement.content_focus.replace('_', ' ').title()}")
            
#             with col3:
#                 st.warning(f"⏰ **Best Retention**: {best_retention.channel_name}")
#                 st.write(f"📊 {best_retention.average_view_duration:.0f}s avg duration")
#                 st.write(f"Focus: {best_retention.content_focus.replace('_', ' ').title()}")
    
#     def render_channel_dashboard(self, service, channel_id, days, period_text):
#         """Render detailed dashboard for specific channel"""
#         # Check if channel is authenticated
#         if channel_id not in service.get_authenticated_channels():
#             st.error("❌ This channel is not authenticated. Please check the authentication status.")
#             if st.button("← Back to Overview", key="back_btn_error", type="secondary"):
#                 st.session_state.selected_channel = None
#                 st.rerun()
#             return
        
#         # Find channel config
#         channel_config = next((ch for ch in UPLOAD_CHANNELS if ch['id'] == channel_id), None)
#         if not channel_config:
#             st.error("Channel not found!")
#             return
        
#         channel_name = channel_config['name']
        
#         # Back button
#         if st.button("← Back to Overview", key="back_btn", type="secondary"):
#             st.session_state.selected_channel = None
#             st.rerun()
        
#         st.markdown(f"## 🦷 {channel_name} - Detailed Analytics ({period_text})")
        
#         # Channel info card with auth status
#         focus_emoji = {
#             'primary_education': '🎓',
#             'treatment_focused': '🏥',
#             'pediatric_care': '👶'
#         }.get(channel_config['content_focus'], '📺')
        
#         st.markdown(f"""
#         <div class="channel-card success">
#             <h3>✅ {focus_emoji} {channel_name}</h3>
#             <p><strong>Status:</strong> <span class="auth-status auth-success">Authenticated</span></p>
#             <p><strong>Focus:</strong> {channel_config['content_focus'].replace('_', ' ').title()}</p>
#             <p><strong>Description:</strong> {channel_config['description']}</p>
#             <p><strong>Credentials:</strong> {channel_config['credentials_file']}</p>
#             <span class="content-focus-badge">{channel_config['content_focus'].replace('_', ' ').title()}</span>
#         </div>
#         """, unsafe_allow_html=True)
        
#         # Get analytics data
#         with st.spinner(f"Loading detailed analytics for {channel_name}..."):
#             analytics = service.get_channel_analytics(channel_id, channel_name, days)
#             time_series = service.get_time_series_data(channel_id, days)
#             audience_data = service.get_audience_analytics(channel_id, days)
        
#         if not analytics or analytics.auth_status != "Authenticated":
#             st.error(f"Could not load analytics for {channel_name}")
#             return
        
#         # Key metrics
#         st.markdown("### 📊 Key Performance Metrics")
        
#         col1, col2, col3, col4, col5 = st.columns(5)
        
#         with col1:
#             st.metric("👀 Views", f"{analytics.period_views:,}")
        
#         with col2:
#             st.metric("⏱️ Watch Time", f"{analytics.period_watch_time_hours:.1f}h")
        
#         with col3:
#             st.metric("👥 Subscribers", f"+{analytics.period_subscribers_gained}")
        
#         with col4:
#             st.metric("👍 Likes", f"{analytics.period_likes:,}")
        
#         with col5:
#             st.metric("💬 Comments", f"{analytics.period_comments:,}")
        
#         # Additional metrics
#         col6, col7, col8 = st.columns(3)
        
#         with col6:
#             st.metric("📤 Shares", f"{analytics.period_shares:,}")
        
#         with col7:
#             st.metric("⏰ Avg Duration", f"{analytics.average_view_duration:.0f}s")
        
#         with col8:
#             if analytics.estimated_revenue > 0:
#                 st.metric("💰 Revenue", f"${analytics.estimated_revenue:.2f}")
#             else:
#                 engagement_rate = ((analytics.period_likes + analytics.period_comments) / max(analytics.period_views, 1)) * 100
#                 st.metric("📊 Engagement Rate", f"{engagement_rate:.2f}%")
        
#         # Time series charts
#         if time_series.dates:
#             self.render_time_series_charts(time_series, channel_name, period_text)
        
#         # Audience analytics
#         self.render_audience_analytics(audience_data, channel_name, period_text)
    
#     def render_time_series_charts(self, time_series, channel_name, period_text):
#         """Render time series charts"""
#         st.markdown(f"### 📈 Performance Trends - {channel_name} ({period_text})")
        
#         # Create DataFrame for time series
#         df_series = pd.DataFrame({
#             'Date': pd.to_datetime(time_series.dates),
#             'Views': time_series.views,
#             'Watch Time (h)': time_series.watch_time,
#             'Subscribers Gained': time_series.subscribers
#         })
        
#         col1, col2 = st.columns(2)
        
#         with col1:
#             # Views over time
#             fig_views = px.line(
#                 df_series,
#                 x='Date',
#                 y='Views',
#                 title=f"Daily Views - {channel_name}",
#                 color_discrete_sequence=['#4facfe']
#             )
#             fig_views.update_layout(showlegend=False)
#             st.plotly_chart(fig_views, use_container_width=True)
            
#             # Subscribers gained over time
#             fig_subs = px.bar(
#                 df_series,
#                 x='Date',
#                 y='Subscribers Gained',
#                 title=f"Daily Subscribers Gained - {channel_name}",
#                 color_discrete_sequence=['#00f2fe']
#             )
#             st.plotly_chart(fig_subs, use_container_width=True)
        
#         with col2:
#             # Watch time over time
#             fig_watch = px.line(
#                 df_series,
#                 x='Date',
#                 y='Watch Time (h)',
#                 title=f"Daily Watch Time - {channel_name}",
#                 color_discrete_sequence=['#a8edea']
#             )
#             fig_watch.update_layout(showlegend=False)
#             st.plotly_chart(fig_watch, use_container_width=True)
            
#             # Combined metrics
#             fig_combined = make_subplots(
#                 rows=2, cols=1,
#                 subplot_titles=('Views', 'Watch Time (h)'),
#                 vertical_spacing=0.1
#             )
            
#             fig_combined.add_trace(
#                 go.Scatter(x=df_series['Date'], y=df_series['Views'], 
#                           name='Views', line=dict(color='#4facfe')),
#                 row=1, col=1
#             )
            
#             fig_combined.add_trace(
#                 go.Scatter(x=df_series['Date'], y=df_series['Watch Time (h)'], 
#                           name='Watch Time', line=dict(color='#00f2fe')),
#                 row=2, col=1
#             )
            
#             fig_combined.update_layout(
#                 title=f"Combined Metrics - {channel_name}",
#                 height=400,
#                 showlegend=False
#             )
#             st.plotly_chart(fig_combined, use_container_width=True)
    
#     def render_audience_analytics(self, audience_data, channel_name, period_text):
#         """Render audience analytics"""
#         st.markdown(f"### 👥 Audience Analytics - {channel_name} ({period_text})")
        
#         col1, col2 = st.columns(2)
        
#         with col1:
#             # Traffic Sources
#             st.markdown("#### 🔍 Traffic Sources")
#             if audience_data.traffic_sources:
#                 df_traffic = pd.DataFrame(audience_data.traffic_sources)
                
#                 # Map source types to readable names
#                 source_mapping = {
#                     'YT_SEARCH': 'YouTube Search',
#                     'SUGGESTED_VIDEO': 'Suggested Videos', 
#                     'BROWSE': 'Browse Features',
#                     'EXTERNAL': 'External Sources',
#                     'DIRECT': 'Direct Traffic',
#                     'NOTIFICATION': 'Notifications',
#                     'PLAYLIST': 'Playlists',
#                     'SEARCH': 'Search',
#                     'RELATED_VIDEO': 'Related Videos',
#                     'SUBSCRIBER': 'Subscriber Feed',
#                     'CHANNEL': 'Channel Page',
#                     'LIVE': 'Live Streaming'
#                 }
                
#                 df_traffic['source'] = df_traffic['source'].map(source_mapping).fillna(df_traffic['source'])
                
#                 fig_traffic = px.pie(
#                     df_traffic,
#                     values='views',
#                     names='source',
#                     title="How Viewers Find Content",
#                     color_discrete_sequence=['#4facfe', '#00f2fe', '#a8edea', '#fed6e3', '#f093fb']
#                 )
#                 st.plotly_chart(fig_traffic, use_container_width=True)
#             else:
#                 st.info("Traffic source data not available")
            
#             # Device Types
#             st.markdown("#### 📱 Device Usage")
#             if audience_data.device_types:
#                 df_devices = pd.DataFrame(audience_data.device_types)
                
#                 device_mapping = {
#                     'MOBILE': 'Mobile 📱',
#                     'DESKTOP': 'Desktop 💻',
#                     'TABLET': 'Tablet 📲',
#                     'TV': 'TV/Smart TV 📺'
#                 }
                
#                 df_devices['device'] = df_devices['device'].map(device_mapping).fillna(df_devices['device'])
                
#                 fig_devices = px.bar(
#                     df_devices,
#                     x='device',
#                     y='views',
#                     title="Views by Device Type",
#                     color='views',
#                     color_continuous_scale='Blues'
#                 )
#                 st.plotly_chart(fig_devices, use_container_width=True)
#             else:
#                 st.info("Device data not available")
        
#         with col2:
#             # Geography
#             st.markdown("#### 🌍 Geographic Distribution")
#             if audience_data.geography:
#                 df_geo = pd.DataFrame(audience_data.geography)
                
#                 fig_geo = px.bar(
#                     df_geo.head(10),
#                     x='views',
#                     y='country',
#                     orientation='h',
#                     title="Top 10 Countries",
#                     color='views',
#                     color_continuous_scale='Viridis'
#                 )
#                 fig_geo.update_layout(yaxis={'categoryorder': 'total ascending'})
#                 st.plotly_chart(fig_geo, use_container_width=True)
#             else:
#                 st.info("Geographic data not available")
            
#             # Demographics
#             st.markdown("#### 👫 Demographics")
#             if audience_data.age_gender:
#                 df_demo = pd.DataFrame(audience_data.age_gender)
                
#                 if not df_demo.empty:
#                     # Age group summary
#                     df_age_summary = df_demo.groupby('age_group')['percentage'].sum().reset_index()
#                     df_age_summary = df_age_summary.sort_values('percentage', ascending=False)
                    
#                     fig_demo = px.bar(
#                         df_age_summary,
#                         x='age_group',
#                         y='percentage',
#                         title="Audience by Age Group (%)",
#                         color='percentage',
#                         color_continuous_scale='Plasma'
#                     )
#                     st.plotly_chart(fig_demo, use_container_width=True)
#                 else:
#                     st.info("Demographic data not available")
#             else:
#                 st.info("Demographic data not available")
            
#             # Playback Locations
#             if audience_data.playback_locations:
#                 st.markdown("#### 📍 Playback Locations")
#                 df_playback = pd.DataFrame(audience_data.playback_locations)
                
#                 location_mapping = {
#                     'WATCH': 'YouTube Watch Page',
#                     'EMBEDDED': 'Embedded Players',
#                     'MOBILE': 'Mobile App',
#                     'CHANNEL': 'Channel Page'
#                 }
                
#                 df_playback['location'] = df_playback['location'].map(location_mapping).fillna(df_playback['location'])
                
#                 fig_playback = px.pie(
#                     df_playback,
#                     values='views',
#                     names='location',
#                     title="Where Videos Are Watched",
#                     color_discrete_sequence=['#4facfe', '#00f2fe', '#a8edea', '#fed6e3']
#                 )
#                 st.plotly_chart(fig_playback, use_container_width=True)
    
#     def render_export_options(self, service, days, period_text):
#         """Render export options"""
#         st.markdown(f"## 📥 Export Analytics Data ({period_text})")
        
#         authenticated_channels = service.get_authenticated_channels()
#         authenticated_channel_configs = [ch for ch in UPLOAD_CHANNELS if ch['id'] in authenticated_channels]
        
#         if not authenticated_channels:
#             st.warning("⚠️ No authenticated channels available for export.")
#             return
        
#         col1, col2, col3, col4 = st.columns(4)
        
#         with col1:
#             if st.button("📊 Export Summary", type="secondary", use_container_width=True):
#                 export_data = []
                
#                 for channel in authenticated_channel_configs:
#                     analytics = service.get_channel_analytics(channel['id'], channel['name'], days)
                    
#                     if analytics and analytics.auth_status == "Authenticated":
#                         export_data.append({
#                             'Channel': analytics.channel_name,
#                             'Auth Status': analytics.auth_status,
#                             'Content Focus': analytics.content_focus.replace('_', ' ').title(),
#                             'Time Period': period_text,
#                             'Views': analytics.period_views,
#                             'Watch Time Hours': analytics.period_watch_time_hours,
#                             'Subscribers Gained': analytics.period_subscribers_gained,
#                             'Likes': analytics.period_likes,
#                             'Comments': analytics.period_comments,
#                             'Shares': analytics.period_shares,
#                             'Avg View Duration': analytics.average_view_duration,
#                             'Estimated Revenue': analytics.estimated_revenue,
#                             'CPM': analytics.cpm,
#                             'Description': analytics.description
#                         })
                
#                 if export_data:
#                     df_export = pd.DataFrame(export_data)
#                     csv = df_export.to_csv(index=False)
#                     st.download_button(
#                         "📥 Download Summary CSV",
#                         csv,
#                         f"dental_channels_summary_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
#                         "text/csv",
#                         key="summary_download"
#                     )
        
#         with col2:
#             if st.button("📈 Export Time Series", type="secondary", use_container_width=True):
#                 all_time_series = []
                
#                 for channel in authenticated_channel_configs:
#                     time_series = service.get_time_series_data(channel['id'], days)
                    
#                     for i, date in enumerate(time_series.dates):
#                         all_time_series.append({
#                             'Channel': channel['name'],
#                             'Content Focus': channel['content_focus'].replace('_', ' ').title(),
#                             'Date': date,
#                             'Views': time_series.views[i] if i < len(time_series.views) else 0,
#                             'Watch Time Hours': time_series.watch_time[i] if i < len(time_series.watch_time) else 0,
#                             'Subscribers Gained': time_series.subscribers[i] if i < len(time_series.subscribers) else 0
#                         })
                
#                 if all_time_series:
#                     df_series = pd.DataFrame(all_time_series)
#                     csv_series = df_series.to_csv(index=False)
#                     st.download_button(
#                         "📥 Download Time Series CSV",
#                         csv_series,
#                         f"dental_channels_timeseries_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
#                         "text/csv",
#                         key="series_download"
#                     )
        
#         with col3:
#             if st.button("👥 Export Audience Data", type="secondary", use_container_width=True):
#                 audience_export = []
                
#                 for channel in authenticated_channel_configs:
#                     audience_data = service.get_audience_analytics(channel['id'], days)
                    
#                     # Traffic sources
#                     for item in audience_data.traffic_sources:
#                         audience_export.append({
#                             'Channel': channel['name'],
#                             'Content Focus': channel['content_focus'].replace('_', ' ').title(),
#                             'Data Type': 'Traffic Source',
#                             'Category': item['source'],
#                             'Value': item['views'],
#                             'Metric': 'Views'
#                         })
                    
#                     # Device types
#                     for item in audience_data.device_types:
#                         audience_export.append({
#                             'Channel': channel['name'],
#                             'Content Focus': channel['content_focus'].replace('_', ' ').title(),
#                             'Data Type': 'Device Type',
#                             'Category': item['device'],
#                             'Value': item['views'],
#                             'Metric': 'Views'
#                         })
                    
#                     # Demographics
#                     for item in audience_data.age_gender:
#                         audience_export.append({
#                             'Channel': channel['name'],
#                             'Content Focus': channel['content_focus'].replace('_', ' ').title(),
#                             'Data Type': 'Demographics',
#                             'Category': f"{item['age_group']} - {item['gender']}",
#                             'Value': item['percentage'],
#                             'Metric': 'Percentage'
#                         })
                
#                 if audience_export:
#                     df_audience = pd.DataFrame(audience_export)
#                     csv_audience = df_audience.to_csv(index=False)
#                     st.download_button(
#                         "📥 Download Audience CSV",
#                         csv_audience,
#                         f"dental_channels_audience_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
#                         "text/csv",
#                         key="audience_download"
#                     )
        
#         with col4:
#             if st.button("📋 Export Full Report", type="primary", use_container_width=True):
#                 # Generate comprehensive report
#                 report_data = {
#                     'report_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
#                     'period': period_text,
#                     'authentication_summary': {
#                         'total_channels': len(UPLOAD_CHANNELS),
#                         'authenticated_channels': len(authenticated_channels),
#                         'authentication_rate': f"{len(authenticated_channels)/len(UPLOAD_CHANNELS)*100:.1f}%"
#                     },
#                     'channels': []
#                 }
                
#                 for channel in authenticated_channel_configs:
#                     analytics = service.get_channel_analytics(channel['id'], channel['name'], days)
#                     time_series = service.get_time_series_data(channel['id'], days)
#                     audience_data = service.get_audience_analytics(channel['id'], days)
                    
#                     if analytics and analytics.auth_status == "Authenticated":
#                         channel_report = {
#                             'name': analytics.channel_name,
#                             'content_focus': analytics.content_focus,
#                             'description': analytics.description,
#                             'auth_status': analytics.auth_status,
#                             'credentials_file': channel['credentials_file'],
#                             'metrics': {
#                                 'views': analytics.period_views,
#                                 'watch_time_hours': analytics.period_watch_time_hours,
#                                 'subscribers_gained': analytics.period_subscribers_gained,
#                                 'likes': analytics.period_likes,
#                                 'comments': analytics.period_comments,
#                                 'shares': analytics.period_shares,
#                                 'avg_view_duration': analytics.average_view_duration,
#                                 'estimated_revenue': analytics.estimated_revenue,
#                                 'cpm': analytics.cpm
#                             },
#                             'time_series': {
#                                 'dates': time_series.dates,
#                                 'views': time_series.views,
#                                 'watch_time': time_series.watch_time,
#                                 'subscribers': time_series.subscribers
#                             },
#                             'audience': {
#                                 'traffic_sources': audience_data.traffic_sources,
#                                 'device_types': audience_data.device_types,
#                                 'geography': audience_data.geography,
#                                 'demographics': audience_data.age_gender,
#                                 'playback_locations': audience_data.playback_locations
#                             }
#                         }
#                         report_data['channels'].append(channel_report)
                
#                 # Convert to JSON
#                 json_report = json.dumps(report_data, indent=2, default=str)
#                 st.download_button(
#                     "📥 Download Full JSON Report",
#                     json_report,
#                     f"dental_channels_full_report_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
#                     "application/json",
#                     key="full_report_download"
#                 )
        
#         # Export summary
#         st.info(f"📊 Export includes data from {len(authenticated_channels)} authenticated channels out of {len(UPLOAD_CHANNELS)} total channels.")
    
#     def run(self):
#         """Main dashboard runner"""
#         try:
#             # Initialize service with individual channel authentication
#             with st.spinner("🔐 Authenticating channels..."):
#                 service = YouTubeAnalyticsService()
            
#             # Render header
#             self.render_header()
            
#             # Render sidebar
#             days, period_text = self.render_sidebar(service)
            
#             # Main content routing
#             if st.session_state.selected_channel is None:
#                 # Show overview dashboard
#                 self.render_overview_dashboard(service, days, period_text)
#             else:
#                 # Show channel-specific dashboard
#                 self.render_channel_dashboard(service, st.session_state.selected_channel, days, period_text)
            
#             st.markdown("---")
            
#             # Export options
#             self.render_export_options(service, days, period_text)
            
#         except Exception as e:
#             st.error(f"❌ Error loading dashboard: {e}")
#             logger.error(f"Dashboard error: {e}", exc_info=True)
            
#             # Enhanced troubleshooting section
#             st.markdown("### 🔧 Troubleshooting:")
            
#             col1, col2 = st.columns(2)
            
#             with col1:
#                 st.markdown("""
#                 **Authentication Issues:**
#                 - Ensure each channel has its own credentials file
#                 - Check file naming matches configuration
#                 - Verify you own or manage the channels
#                 - Complete OAuth flow for each channel separately
#                 """)
                
#                 st.markdown("""
#                 **Required Files:**
#                 - `dental_advisor_credentials.json`
#                 - `mih_credentials.json` 
#                 - `enamel_hypoplasia_credentials.json`
#                 """)
            
#             with col2:
#                 st.markdown("""
#                 **API Setup:**
#                 - Enable YouTube Analytics API in Google Cloud Console
#                 - Create OAuth 2.0 credentials (Desktop Application)
#                 - Set correct scopes: `yt-analytics.readonly`
#                 - Check API quota limits
#                 """)
                
#                 st.markdown("""
#                 **Common Solutions:**
#                 - Update channel IDs with your actual channel IDs
#                 - Use "Re-authenticate All Channels" button
#                 - Check internet connection
#                 - Restart the application after fixing credentials
#                 """)
        
#         # Enhanced footer
#         st.markdown("---")
#         st.markdown("""
#         <div style="text-align: center; color: #666; padding: 2rem;">
#             <p>🦷 <strong>Dental Education YouTube Analytics Dashboard</strong></p>
#             <p>Powered by YouTube Analytics API v2 | Individual Channel Authentication</p>
#             <p style="font-size: 0.9rem; opacity: 0.7;">
#                 <strong>Supported Channels:</strong> Dental Advisor • MIH Education • Enamel Hypoplasia Research
#             </p>
#             <p style="font-size: 0.8rem; opacity: 0.6; margin-top: 1rem;">
#                 📋 <strong>Setup Checklist:</strong><br>
#                 ✅ Separate OAuth credentials for each channel<br>
#                 ✅ Correct file naming and placement<br>
#                 ✅ YouTube Analytics API enabled<br>
#                 ✅ Channel ownership verified
#             </p>
#         </div>
#         """, unsafe_allow_html=True)

# # Main execution
# if __name__ == "__main__":
#     import sys
#     import subprocess
    
#     # Check if running with streamlit
#     if 'streamlit' not in sys.modules:
#         print("🦷 Dental Channels Analytics Dashboard")
#         print("This is a Streamlit application. Running with streamlit...")
#         subprocess.run([sys.executable, "-m", "streamlit", "run", __file__] + sys.argv[1:])
#     else:
#         dashboard = DentalChannelsDashboard()
#         dashboard.run()


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
import os
import tempfile

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

# Check if running on Streamlit Cloud
IS_STREAMLIT_CLOUD = os.getenv('STREAMLIT_SHARING', False) or 'streamlit.app' in os.getenv('HOSTNAME', '')

# Channel Configuration
UPLOAD_CHANNELS = [
    {
        "name": "Dental Advisor",
        "id": "UCsw6IbObS8mtNQqbbZSKvog",
        "credentials_key": "dental_advisor_credentials",
        "token_key": "dental_advisor_token",
        "credentials_file": "dental_advisor_credentials.json",
        "token_file": "dental_advisor_token.json",
        "description": "Primary channel for MIH educational content",
        "privacy_status": "public",
        "category_id": "27",
        "default_language": "en",
        "tags_prefix": ["#DrGreenwall", "#MIHEducation"],
        "content_focus": "primary_education"
    },
    {
        "name": "MIH",
        "id": "UCt56aIAG8gNuKM0hJpWYm9Q",
        "credentials_key": "mih_credentials",
        "token_key": "mih_token",
        "credentials_file": "mih_credentials.json",
        "token_file": "mih_token.json",
        "description": "Specialized MIH treatment and care guidance",
        "privacy_status": "public",
        "category_id": "27",
        "default_language": "en",
        "tags_prefix": ["#MIHTreatment", "#EnamelCare"],
        "content_focus": "treatment_focused"
    },
    {
        "name": "Enamel Hypoplasia",
        "id": "UCnBJEdDIsC7b3oAvaBPje3Q",
        "credentials_key": "enamel_hypoplasia_credentials",
        "token_key": "enamel_hypoplasia_token",
        "credentials_file": "enamel_hypoplasia_credentials.json",
        "token_file": "enamel_hypoplasia_token.json",
        "description": "Comprehensive pediatric dental care and whitening",
        "privacy_status": "public",
        "category_id": "27",
        "default_language": "en",
        "tags_prefix": ["#PediatricDentistry", "#ChildrenTeeth"],
        "content_focus": "pediatric_care"
    }
]

@dataclass
class ChannelAnalytics:
    """Data class for channel analytics from YouTube Analytics API"""
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

class YouTubeAnalyticsService:
    """YouTube Analytics API service with Streamlit Cloud support"""
    
    SCOPES = ['https://www.googleapis.com/auth/yt-analytics.readonly']
    
    def __init__(self):
        self.channels = UPLOAD_CHANNELS
        self.channel_auth_status = {}
        self._authenticate_all_channels()
    
    def _get_credentials_from_secrets(self, credentials_key: str) -> Optional[Dict]:
        """Get credentials from Streamlit secrets"""
        try:
            if hasattr(st, 'secrets') and credentials_key in st.secrets:
                creds_dict = dict(st.secrets[credentials_key])
                # Convert to proper OAuth credentials format
                return {
                    "installed": {
                        "client_id": creds_dict["client_id"],
                        "client_secret": creds_dict["client_secret"],
                        "auth_uri": creds_dict["auth_uri"],
                        "token_uri": creds_dict["token_uri"],
                        "auth_provider_x509_cert_url": creds_dict["auth_provider_x509_cert_url"],
                        "redirect_uris": creds_dict["redirect_uris"]
                    }
                }
            return None
        except Exception as e:
            logger.error(f"Error reading credentials from secrets: {e}")
            return None
    
    def _get_token_from_secrets(self, token_key: str) -> Optional[Dict]:
        """Get token from Streamlit secrets"""
        try:
            if hasattr(st, 'secrets') and token_key in st.secrets:
                return dict(st.secrets[token_key])
            return None
        except Exception as e:
            logger.error(f"Error reading token from secrets: {e}")
            return None
    
    def _create_temp_credentials_file(self, credentials_dict: Dict) -> str:
        """Create temporary credentials file"""
        try:
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            json.dump(credentials_dict, temp_file, indent=2)
            temp_file.close()
            return temp_file.name
        except Exception as e:
            logger.error(f"Error creating temporary credentials file: {e}")
            return None
    
    def _authenticate_channel(self, channel_config: Dict) -> ChannelAuth:
        """Authenticate a single channel with Streamlit Cloud support"""
        channel_id = channel_config['id']
        channel_name = channel_config['name']
        
        try:
            creds = None
            
            if IS_STREAMLIT_CLOUD:
                # Running on Streamlit Cloud - use secrets
                logger.info(f"Authenticating {channel_name} using Streamlit secrets...")
                
                # Try to get existing token from secrets
                token_dict = self._get_token_from_secrets(channel_config['token_key'])
                if token_dict:
                    try:
                        creds = Credentials(
                            token=token_dict.get('token'),
                            refresh_token=token_dict.get('refresh_token'),
                            token_uri=token_dict.get('token_uri'),
                            client_id=token_dict.get('client_id'),
                            client_secret=token_dict.get('client_secret'),
                            scopes=token_dict.get('scopes')
                        )
                        
                        # Refresh if expired
                        if creds.expired and creds.refresh_token:
                            creds.refresh(Request())
                            logger.info(f"Refreshed token for {channel_name}")
                        
                    except Exception as e:
                        logger.warning(f"Failed to use token from secrets for {channel_name}: {e}")
                        creds = None
                
                if not creds or not creds.valid:
                    error_msg = f"No valid token in secrets for {channel_name}. Please authenticate locally first and update secrets."
                    logger.error(error_msg)
                    return ChannelAuth(
                        channel_id=channel_id,
                        channel_name=channel_name,
                        is_authenticated=False,
                        analytics_service=None,
                        error_message=error_msg
                    )
                
            else:
                # Running locally - use file-based authentication
                logger.info(f"Authenticating {channel_name} using local files...")
                
                credentials_file = channel_config['credentials_file']
                token_file = channel_config['token_file']
                
                # Load existing token if available
                if Path(token_file).exists():
                    try:
                        creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
                    except Exception as e:
                        logger.warning(f"Failed to load existing token for {channel_name}: {e}")
                        creds = None
                
                # Refresh or get new credentials
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        try:
                            creds.refresh(Request())
                            logger.info(f"Refreshed credentials for {channel_name}")
                        except Exception as e:
                            logger.warning(f"Failed to refresh token for {channel_name}: {e}")
                            creds = None
                    
                    if not creds:
                        if not Path(credentials_file).exists():
                            error_msg = f"Credentials file not found: {credentials_file}"
                            logger.error(error_msg)
                            return ChannelAuth(
                                channel_id=channel_id,
                                channel_name=channel_name,
                                is_authenticated=False,
                                analytics_service=None,
                                error_message=error_msg
                            )
                        
                        try:
                            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, self.SCOPES)
                            creds = flow.run_local_server(port=0)
                            logger.info(f"Completed OAuth flow for {channel_name}")
                        except Exception as e:
                            error_msg = f"OAuth flow failed for {channel_name}: {e}"
                            logger.error(error_msg)
                            return ChannelAuth(
                                channel_id=channel_id,
                                channel_name=channel_name,
                                is_authenticated=False,
                                analytics_service=None,
                                error_message=error_msg
                            )
                    
                    # Save the credentials locally
                    try:
                        with open(token_file, 'w') as token:
                            token.write(creds.to_json())
                        logger.info(f"Saved credentials for {channel_name}")
                    except Exception as e:
                        logger.warning(f"Failed to save token for {channel_name}: {e}")
            
            # Build the analytics service
            try:
                analytics_service = build('youtubeAnalytics', 'v2', credentials=creds)
                
                # Test the authentication
                test_query = analytics_service.reports().query(
                    ids=f'channel=={channel_id}',
                    startDate='2023-01-01',
                    endDate=datetime.now().strftime('%Y-%m-%d'),
                    metrics='views'
                ).execute()
                
                logger.info(f"Successfully authenticated {channel_name}")
                return ChannelAuth(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    is_authenticated=True,
                    analytics_service=analytics_service,
                    error_message=None
                )
                
            except Exception as e:
                error_msg = f"Failed to build analytics service or test access for {channel_name}: {e}"
                logger.error(error_msg)
                return ChannelAuth(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    is_authenticated=False,
                    analytics_service=None,
                    error_message=error_msg
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
    
    def _authenticate_all_channels(self):
        """Authenticate all channels"""
        logger.info(f"Starting authentication for all channels... (Streamlit Cloud: {IS_STREAMLIT_CLOUD})")
        
        for channel_config in self.channels:
            channel_name = channel_config['name']
            logger.info(f"Authenticating {channel_name}...")
            
            auth_result = self._authenticate_channel(channel_config)
            self.channel_auth_status[channel_config['id']] = auth_result
            
            if auth_result.is_authenticated:
                logger.info(f"✅ {channel_name} authenticated successfully")
            else:
                logger.error(f"❌ {channel_name} authentication failed: {auth_result.error_message}")
        
        # Summary
        authenticated_count = sum(1 for auth in self.channel_auth_status.values() if auth.is_authenticated)
        total_count = len(self.channels)
        logger.info(f"Authentication complete: {authenticated_count}/{total_count} channels authenticated")
    
    def get_authenticated_channels(self) -> List[str]:
        """Get list of successfully authenticated channel IDs"""
        return [channel_id for channel_id, auth in self.channel_auth_status.items() 
                if auth.is_authenticated]
    
    def get_authentication_status(self) -> Dict[str, ChannelAuth]:
        """Get authentication status for all channels"""
        return self.channel_auth_status
    
    def get_analytics_service(self, channel_id: str) -> Optional[object]:
        """Get analytics service for a specific channel"""
        auth_status = self.channel_auth_status.get(channel_id)
        if auth_status and auth_status.is_authenticated:
            return auth_status.analytics_service
        return None
    
    def get_date_range(self, days: int) -> tuple:
        """Get start and end dates for analytics queries"""
        if days == -1:  # All time
            start_date = '2005-04-23'
        else:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        return start_date, end_date
    
    def get_channel_analytics(self, channel_id: str, channel_name: str, days: int = 30) -> Optional[ChannelAnalytics]:
        """Get channel analytics using YouTube Analytics API"""
        analytics_service = self.get_analytics_service(channel_id)
        auth_status = self.channel_auth_status.get(channel_id)
        
        if not analytics_service:
            logger.error(f"No authenticated service for {channel_name}")
            channel_config = next((ch for ch in self.channels if ch['id'] == channel_id), {})
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
                auth_status=f"Authentication failed: {auth_status.error_message if auth_status else 'Unknown error'}"
            )
        
        try:
            start_date, end_date = self.get_date_range(days)
            
            logger.info(f"Getting analytics for {channel_name} from {start_date} to {end_date}")
            
            # Get main analytics metrics
            try:
                main_metrics = analytics_service.reports().query(
                    ids=f'channel=={channel_id}',
                    startDate=start_date,
                    endDate=end_date,
                    metrics='views,estimatedMinutesWatched,subscribersGained,likes,comments,shares,averageViewDuration'
                ).execute()
                
                analytics_data = main_metrics.get('rows', [[0, 0, 0, 0, 0, 0, 0]])[0]
            except Exception as e:
                logger.warning(f"Some metrics unavailable for {channel_name}: {e}")
                try:
                    basic_metrics = analytics_service.reports().query(
                        ids=f'channel=={channel_id}',
                        startDate=start_date,
                        endDate=end_date,
                        metrics='views,estimatedMinutesWatched,subscribersGained'
                    ).execute()
                    
                    basic_data = basic_metrics.get('rows', [[0, 0, 0]])[0]
                    analytics_data = basic_data + [0, 0, 0, 0]
                except Exception as e2:
                    logger.error(f"Failed to get basic metrics for {channel_name}: {e2}")
                    analytics_data = [0, 0, 0, 0, 0, 0, 0]
            
            # Skip revenue metrics as they require special permissions
            estimated_revenue = 0
            cpm = 0
            
            # Find channel config
            channel_config = next((ch for ch in self.channels if ch['id'] == channel_id), {})
            
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
                estimated_revenue=estimated_revenue,
                cpm=cpm,
                content_focus=channel_config.get('content_focus', 'general'),
                description=channel_config.get('description', 'Dental education content'),
                auth_status="Authenticated"
            )
            
        except Exception as e:
            logger.error(f"Failed to get analytics for {channel_name}: {e}")
            return None
    
    def get_time_series_data(self, channel_id: str, days: int = 30) -> TimeSeriesData:
        """Get time series data for charts"""
        analytics_service = self.get_analytics_service(channel_id)
        
        if not analytics_service:
            return TimeSeriesData([], [], [], [], [])
        
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
                dates.append(row[0])
                views.append(row[1] if len(row) > 1 else 0)
                watch_time.append((row[2] if len(row) > 2 else 0) / 60)
                subscribers.append(row[3] if len(row) > 3 else 0)
                estimated_revenue.append(0)
            
            return TimeSeriesData(dates, views, watch_time, subscribers, estimated_revenue)
            
        except Exception as e:
            logger.error(f"Failed to get time series data: {e}")
            return TimeSeriesData([], [], [], [], [])
    
    def get_audience_analytics(self, channel_id: str, days: int = 30) -> AudienceData:
        """Get audience analytics using YouTube Analytics API"""
        analytics_service = self.get_analytics_service(channel_id)
        
        if not analytics_service:
            return AudienceData([], [], [], [], [])
        
        try:
            start_date, end_date = self.get_date_range(days)
            
            age_gender = []
            device_types = []
            traffic_sources = []
            geography = []
            playback_locations = []
            
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
            
            return AudienceData(age_gender, device_types, traffic_sources, geography, playback_locations)
            
        except Exception as e:
            logger.error(f"Failed to get audience analytics: {e}")
            return AudienceData([], [], [], [], [])

class DentalChannelsDashboard:
    """Dashboard for dental education YouTube channels with Streamlit Cloud support"""
    
    def __init__(self):
        st.set_page_config(
            page_title="Dental Channels Analytics Dashboard",
            page_icon="🦷",
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
            transform: translateY(-4px);
        }
        
        .channel-card.error {
            border-left-color: #ff4757;
            background: #fff5f5;
        }
        
        .channel-card.success {
            border-left-color: #2ed573;
            background: #f0fff4;
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
        </style>
        """, unsafe_allow_html=True)
    
    def render_header(self):
        """Render dashboard header"""
        # Show deployment environment
        if IS_STREAMLIT_CLOUD:
            st.markdown("""
            <div class="deployment-info">
                ☁️ <strong>Running on Streamlit Community Cloud</strong><br>
                Using Streamlit Secrets for authentication
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="deployment-info">
                💻 <strong>Running Locally</strong><br>
                Using local credential files for authentication
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="main-header">
            <h1>🦷 Dental Education Analytics Dashboard</h1>
            <p style="font-size: 1.2rem; margin-top: 1rem; opacity: 0.9;">
                Comprehensive YouTube Analytics for Dental Education Channels
            </p>
            <p style="font-size: 1rem; opacity: 0.8;">
                MIH Education • Pediatric Dentistry • Enamel Care
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    def render_deployment_guide(self):
        """Render deployment guide"""
        st.markdown("### 🚀 Deployment Guide")
        
        tab1, tab2, tab3 = st.tabs(["Local Setup", "Streamlit Cloud", "Troubleshooting"])
        
        with tab1:
            st.markdown("""
            #### 💻 Local Development Setup
            
            **1. Install Dependencies:**
            ```bash
            pip install streamlit google-api-python-client google-auth-httplib2 google-auth-oauthlib plotly pandas
            ```
            
            **2. Create OAuth Credentials:**
            - Go to [Google Cloud Console](https://console.cloud.google.com/)
            - Enable YouTube Analytics API
            - Create OAuth 2.0 credentials (Desktop Application)
            - Download JSON files for each channel
            
            **3. File Structure:**
            ```
            your-app/
            ├── app.py
            ├── dental_advisor_credentials.json
            ├── mih_credentials.json
            ├── enamel_hypoplasia_credentials.json
            └── requirements.txt
            ```
            
            **4. Run Locally:**
            ```bash
            streamlit run app.py
            ```
            """)
        
        with tab2:
            st.markdown("""
            #### ☁️ Streamlit Community Cloud Deployment
            
            **Step 1: Prepare Repository**
            ```
            your-repo/
            ├── app.py
            ├── requirements.txt
            ├── .streamlit/
            │   └── secrets.toml (local only - don't commit!)
            └── README.md
            ```
            
            **Step 2: Get Tokens Locally**
            1. Run the app locally first to complete OAuth flow
            2. Find generated token files:
               - `dental_advisor_token.json`
               - `mih_token.json`
               - `enamel_hypoplasia_token.json`
            3. Copy token contents for secrets
            
            **Step 3: Deploy to Streamlit Cloud**
            1. Push code to GitHub (without credential files!)
            2. Go to [share.streamlit.io](https://share.streamlit.io)
            3. Connect your GitHub repo
            4. Add secrets in the Streamlit Cloud dashboard
            
            **Step 4: Configure Secrets**
            In your Streamlit app settings, add all the secrets from the secrets.toml file.
            
            **Important Notes:**
            - ⚠️ Never commit credential files to GitHub
            - 🔐 Use Streamlit Secrets for sensitive data
            - 🔄 Tokens may need periodic refresh
            """)
        
        with tab3:
            st.markdown("""
            #### 🔧 Common Issues & Solutions
            
            **Authentication Errors:**
            - **403 Forbidden**: Check channel ownership and API permissions
            - **Token Expired**: Re-authenticate locally and update secrets
            - **Invalid Scope**: Ensure `yt-analytics.readonly` scope is used
            
            **Deployment Issues:**
            - **Secrets Not Found**: Verify secrets are properly configured in Streamlit Cloud
            - **Token Format Error**: Check JSON formatting in secrets
            - **API Quota Exceeded**: Monitor YouTube API usage limits
            
            **Local vs Cloud:**
            - **Local**: Uses credential files and OAuth flow
            - **Cloud**: Uses pre-authenticated tokens from secrets
            - **Transition**: Authenticate locally first, then copy tokens to secrets
            
            **Security Best Practices:**
            - ✅ Use `.gitignore` to exclude credential files
            - ✅ Store tokens in Streamlit Secrets only
            - ✅ Regularly rotate OAuth credentials
            - ✅ Monitor API usage and access logs
            """)
    
    def render_authentication_status(self, service):
        """Render authentication status with deployment context"""
        st.markdown("### 🔐 Channel Authentication Status")
        
        if IS_STREAMLIT_CLOUD:
            st.info("🌐 **Streamlit Cloud Mode**: Using tokens from Streamlit Secrets")
        else:
            st.info("💻 **Local Mode**: Using OAuth flow with credential files")
        
        auth_status = service.get_authentication_status()
        authenticated_channels = service.get_authenticated_channels()
        
        for channel_config in UPLOAD_CHANNELS:
            channel_id = channel_config['id']
            channel_name = channel_config['name']
            auth_info = auth_status.get(channel_id)
            
            if auth_info and auth_info.is_authenticated:
                st.markdown(f"""
                <div class="channel-card success">
                    <h4>✅ {channel_name}</h4>
                    <p><strong>Status:</strong> <span class="auth-status auth-success">Authenticated</span></p>
                    <p><strong>Focus:</strong> {channel_config['content_focus'].replace('_', ' ').title()}</p>
                    <p><strong>Method:</strong> {'Streamlit Secrets' if IS_STREAMLIT_CLOUD else 'Local OAuth'}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                error_msg = auth_info.error_message if auth_info else "Unknown error"
                st.markdown(f"""
                <div class="channel-card error">
                    <h4>❌ {channel_name}</h4>
                    <p><strong>Status:</strong> <span class="auth-status auth-error">Authentication Failed</span></p>
                    <p><strong>Error:</strong> {error_msg}</p>
                    <p><strong>Required:</strong> {'Valid token in secrets' if IS_STREAMLIT_CLOUD else 'Credential file'}</p>
                </div>
                """, unsafe_allow_html=True)
        
        # Summary and instructions
        total_channels = len(UPLOAD_CHANNELS)
        authenticated_count = len(authenticated_channels)
        
        if authenticated_count == 0:
            st.error(f"⚠️ No channels authenticated ({authenticated_count}/{total_channels})")
            if IS_STREAMLIT_CLOUD:
                st.markdown("""
                ### 🔧 Streamlit Cloud Setup Required:
                1. **Authenticate locally first** to get valid tokens
                2. **Copy token data** from generated JSON files  
                3. **Add to Streamlit Secrets** in your app dashboard
                4. **Restart the app** to load new secrets
                """)
            else:
                st.markdown("""
                ### 🔧 Local Setup Required:
                1. **Download OAuth credentials** for each channel
                2. **Place JSON files** in the same directory as this script
                3. **Update channel IDs** with your actual YouTube channel IDs
                4. **Restart the application** and complete OAuth flow
                """)
        elif authenticated_count < total_channels:
            st.warning(f"⚠️ Partial authentication ({authenticated_count}/{total_channels} channels)")
        else:
            st.success(f"✅ All channels authenticated ({authenticated_count}/{total_channels})")
    
    def render_sidebar(self, service):
        """Render sidebar with deployment-aware controls"""
        st.sidebar.markdown("## 🦷 Analytics Controls")
        
        # Deployment status
        if IS_STREAMLIT_CLOUD:
            st.sidebar.success("☁️ Streamlit Cloud")
        else:
            st.sidebar.info("💻 Local Development")
        
        # Authentication status in sidebar
        auth_status = service.get_authentication_status()
        authenticated_count = len(service.get_authenticated_channels())
        total_count = len(UPLOAD_CHANNELS)
        
        if authenticated_count == total_count:
            st.sidebar.success(f"🔐 All channels authenticated ({authenticated_count}/{total_count})")
        elif authenticated_count > 0:
            st.sidebar.warning(f"🔐 Partial authentication ({authenticated_count}/{total_count})")
        else:
            st.sidebar.error(f"🔐 No channels authenticated ({authenticated_count}/{total_count})")
        
        # Time period selection
        time_options = {
            "7 days": 7,
            "14 days": 14,
            "30 days": 30,
            "60 days": 60,
            "90 days": 90,
            "6 months": 180,
            "1 year": 365,
            "All time": -1
        }
        
        selected_period = st.sidebar.selectbox(
            "📅 Select Time Period",
            options=list(time_options.keys()),
            index=2,
            help="Analytics data will be filtered for this time period"
        )
        
        days = time_options[selected_period]
        period_text = "All Time" if days == -1 else f"Last {days} days"
        
        st.sidebar.markdown(f"""
        <div style="background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); 
                    color: #333; padding: 0.5rem 1rem; border-radius: 20px; 
                    font-weight: bold; text-align: center; margin-bottom: 1rem;">
            📊 Analyzing: {period_text}
        </div>
        """, unsafe_allow_html=True)
        
        # Channel selection
        st.sidebar.markdown("### 🎯 Channel Selection")
        
        if st.sidebar.button("📊 All Channels Overview", type="primary", use_container_width=True):
            st.session_state.selected_channel = None
            st.rerun()
        
        st.sidebar.markdown("#### Individual Channels:")
        
        for channel in UPLOAD_CHANNELS:
            channel_id = channel['id']
            auth_info = auth_status.get(channel_id)
            is_authenticated = auth_info and auth_info.is_authenticated
            
            focus_color = {
                'primary_education': '🎓',
                'treatment_focused': '🏥',
                'pediatric_care': '👶'
            }.get(channel['content_focus'], '📺')
            
            auth_indicator = "✅" if is_authenticated else "❌"
            
            if st.sidebar.button(
                f"{auth_indicator} {focus_color} {channel['name']}",
                key=f"select_{channel['id']}",
                use_container_width=True,
                disabled=not is_authenticated,
                type="secondary"
            ):
                if is_authenticated:
                    st.session_state.selected_channel = channel['id']
                    st.rerun()
        
        # Deployment-specific actions
        st.sidebar.markdown("---")
        if IS_STREAMLIT_CLOUD:
            st.sidebar.markdown("### ☁️ Cloud Actions")
            st.sidebar.info("💡 To re-authenticate: Update secrets and restart app")
            if st.sidebar.button("📚 View Deployment Guide", type="secondary", use_container_width=True):
                st.session_state.show_deployment_guide = True
                st.rerun()
        else:
            st.sidebar.markdown("### 💻 Local Actions")
            if st.sidebar.button("🔄 Re-authenticate Channels", type="secondary", use_container_width=True):
                for channel in UPLOAD_CHANNELS:
                    token_file = channel['token_file']
                    if Path(token_file).exists():
                        try:
                            Path(token_file).unlink()
                            st.sidebar.success(f"Cleared token for {channel['name']}")
                        except Exception as e:
                            st.sidebar.error(f"Failed to clear token for {channel['name']}: {e}")
                st.sidebar.info("🔄 Please restart the application to re-authenticate")
        
        # Help section
        with st.sidebar.expander("❓ Need Help?"):
            st.markdown("""
            **Authentication Issues:**
            - Check channel ownership
            - Verify API permissions
            - Update channel IDs
            
            **Deployment Help:**
            - Local: Use credential files
            - Cloud: Use Streamlit Secrets
            - See deployment guide for details
            """)
        
        return days, period_text
    
    def run(self):
        """Main dashboard runner with deployment support"""
        try:
            # Check if we should show deployment guide
            if hasattr(st.session_state, 'show_deployment_guide') and st.session_state.show_deployment_guide:
                self.render_header()
                self.render_deployment_guide()
                if st.button("← Back to Dashboard"):
                    st.session_state.show_deployment_guide = False
                    st.rerun()
                return
            
            # Initialize service
            with st.spinner("🔐 Authenticating channels..."):
                service = YouTubeAnalyticsService()
            
            # Render header
            self.render_header()
            
            # Render sidebar
            days, period_text = self.render_sidebar(service)
            
            # Main content routing
            if st.session_state.selected_channel is None:
                # Show overview dashboard
                self.render_overview_dashboard(service, days, period_text)
            else:
                # Show channel-specific dashboard
                self.render_channel_dashboard(service, st.session_state.selected_channel, days, period_text)
            
            st.markdown("---")
            
            # Export options (simplified for brevity - same as before)
            authenticated_channels = service.get_authenticated_channels()
            if authenticated_channels:
                st.markdown(f"## 📥 Export Options ({period_text})")
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("📊 Export Summary", type="secondary", use_container_width=True):
                        st.info("Export functionality available - see full code for implementation")
                
                with col2:
                    if st.button("📋 Export Full Report", type="primary", use_container_width=True):
                        st.info("Export functionality available - see full code for implementation")
            
        except Exception as e:
            st.error(f"❌ Error loading dashboard: {e}")
            logger.error(f"Dashboard error: {e}", exc_info=True)
            
            # Enhanced troubleshooting
            st.markdown("### 🔧 Troubleshooting:")
            
            if IS_STREAMLIT_CLOUD:
                st.markdown("""
                **Streamlit Cloud Issues:**
                - Check if secrets are properly configured
                - Verify token format in secrets
                - Ensure tokens haven't expired
                - Try updating secrets and restarting
                """)
            else:
                st.markdown("""
                **Local Development Issues:**
                - Ensure credential files are present
                - Check file naming and location
                - Verify internet connection
                - Try re-authenticating
                """)
        
        # Footer with deployment info
        st.markdown("---")
        deployment_status = "☁️ Streamlit Community Cloud" if IS_STREAMLIT_CLOUD else "💻 Local Development"
        st.markdown(f"""
        <div style="text-align: center; color: #666; padding: 2rem;">
            <p>🦷 <strong>Dental Education YouTube Analytics Dashboard</strong></p>
            <p>Deployment: {deployment_status} | Authentication: {'Secrets' if IS_STREAMLIT_CLOUD else 'OAuth Files'}</p>
            <p style="font-size: 0.9rem; opacity: 0.7;">
                Powered by YouTube Analytics API v2 | Streamlit Cloud Ready
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Add simplified methods for overview and channel dashboards
    def render_overview_dashboard(self, service, days, period_text):
        """Simplified overview dashboard"""
        st.markdown(f"## 📊 All Channels Overview ({period_text})")
        self.render_authentication_status(service)
        
        authenticated_channels = service.get_authenticated_channels()
        if authenticated_channels:
            st.success(f"✅ Dashboard ready with {len(authenticated_channels)} authenticated channels")
            # Add your analytics visualization code here
        else:
            st.warning("⚠️ No authenticated channels available")
    
    def render_channel_dashboard(self, service, channel_id, days, period_text):
        """Simplified channel dashboard"""
        if st.button("← Back to Overview", key="back_btn", type="secondary"):
            st.session_state.selected_channel = None
            st.rerun()
        
        channel_config = next((ch for ch in UPLOAD_CHANNELS if ch['id'] == channel_id), None)
        if channel_config:
            st.markdown(f"## 🦷 {channel_config['name']} - Detailed Analytics ({period_text})")
            st.success("✅ Channel analytics would be displayed here")
            # Add your detailed analytics code here

# Requirements.txt content for easy deployment
REQUIREMENTS_TXT = """
streamlit>=1.28.0
google-api-python-client>=2.100.0
google-auth-httplib2>=0.1.1
google-auth-oauthlib>=1.1.0
google-auth>=2.22.0
plotly>=5.15.0
pandas>=2.0.0
"""

if __name__ == "__main__":
    import sys
    import subprocess
    
    # Check if running with streamlit
    if 'streamlit' not in sys.modules:
        print("🦷 Dental Channels Analytics Dashboard")
        print("This is a Streamlit application. Running with streamlit...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__] + sys.argv[1:])
    else:
        dashboard = DentalChannelsDashboard()
        dashboard.run()