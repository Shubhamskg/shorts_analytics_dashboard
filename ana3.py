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

# Channel Configuration - Only include channels you have access to
UPLOAD_CHANNELS = [
    {
        "name": "Dental Advisor",
        "id": "UCsw6IbObS8mtNQqbbZSKvog",
        "credentials_file": "youtube_credentials.json",
        "description": "Primary channel for MIH educational content",
        "privacy_status": "public",
        "category_id": "27",  # Education category
        "default_language": "en",
        "tags_prefix": ["#DrGreenwall", "#MIHEducation"],
        "content_focus": "primary_education"
    },
    {
        "name": "MIH",
        "id": "YOUR_ACTUAL_MIH_CHANNEL_ID",
        "credentials_file": "youtube_credentials.json",
        "description": "Specialized MIH treatment and care guidance",
        "privacy_status": "public",
        "category_id": "27",
        "default_language": "en",
        "tags_prefix": ["#MIHTreatment", "#EnamelCare"],
        "content_focus": "treatment_focused"
    },
    {
        "name": "Enamel Hypoplasia",
        "id": "YOUR_ACTUAL_ENAMEL_CHANNEL_ID",
        "credentials_file": "youtube_credentials.json",
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

class YouTubeAnalyticsService:
    """YouTube Analytics API-only service for dental channels"""
    
    SCOPES = ['https://www.googleapis.com/auth/yt-analytics.readonly']
    
    def __init__(self, credentials_file: str = "youtube_credentials.json"):
        self.credentials_file = credentials_file
        self.analytics_service = None
        self.channels = UPLOAD_CHANNELS
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with YouTube Analytics API"""
        try:
            token_file = 'analytics_token.json'
            creds = None
            
            if Path(token_file).exists():
                creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not Path(self.credentials_file).exists():
                        st.error(f"❌ Credentials file not found: {self.credentials_file}")
                        st.info("Please ensure your OAuth 2.0 credentials file is available.")
                        st.stop()
                    
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                
                with open(token_file, 'w') as token:
                    token.write(creds.to_json())
            
            self.analytics_service = build('youtubeAnalytics', 'v2', credentials=creds)
            logger.info("Successfully authenticated with YouTube Analytics API")
            
        except Exception as e:
            st.error(f"❌ Authentication failed: {e}")
            st.info("Please check your credentials file and ensure you have the necessary permissions.")
            st.stop()
    
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
        try:
            start_date, end_date = self.get_date_range(days)
            
            logger.info(f"Getting analytics for {channel_name} from {start_date} to {end_date}")
            
            # Check if user has access to this channel
            try:
                # Test with a simple query first
                test_query = self.analytics_service.reports().query(
                    ids=f'channel=={channel_id}',
                    startDate=start_date,
                    endDate=end_date,
                    metrics='views'
                ).execute()
                
                if not test_query.get('rows'):
                    logger.warning(f"No data available for {channel_name}")
                    return None
                    
            except Exception as e:
                if '403' in str(e) or 'Forbidden' in str(e):
                    logger.error(f"Access denied for {channel_name}. You may not own this channel or lack permissions.")
                    return None
                else:
                    raise e
            
            # Get main analytics metrics (only basic metrics to avoid permission issues)
            try:
                main_metrics = self.analytics_service.reports().query(
                    ids=f'channel=={channel_id}',
                    startDate=start_date,
                    endDate=end_date,
                    metrics='views,estimatedMinutesWatched,subscribersGained,likes,comments,shares,averageViewDuration'
                ).execute()
                
                analytics_data = main_metrics.get('rows', [[0, 0, 0, 0, 0, 0, 0]])[0]
            except Exception as e:
                logger.warning(f"Some metrics unavailable for {channel_name}: {e}")
                # Try with just basic metrics
                try:
                    basic_metrics = self.analytics_service.reports().query(
                        ids=f'channel=={channel_id}',
                        startDate=start_date,
                        endDate=end_date,
                        metrics='views,estimatedMinutesWatched,subscribersGained'
                    ).execute()
                    
                    basic_data = basic_metrics.get('rows', [[0, 0, 0]])[0]
                    analytics_data = basic_data + [0, 0, 0, 0]  # Pad with zeros for missing metrics
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
                description=channel_config.get('description', 'Dental education content')
            )
            
        except Exception as e:
            logger.error(f"Failed to get analytics for {channel_name}: {e}")
            return None
    
    def get_time_series_data(self, channel_id: str, days: int = 30) -> TimeSeriesData:
        """Get time series data for charts"""
        try:
            start_date, end_date = self.get_date_range(days)
            
            # Check access first
            try:
                test_query = self.analytics_service.reports().query(
                    ids=f'channel=={channel_id}',
                    startDate=start_date,
                    endDate=end_date,
                    metrics='views'
                ).execute()
                
                if not test_query.get('rows'):
                    return TimeSeriesData([], [], [], [], [])
                    
            except Exception as e:
                if '403' in str(e) or 'Forbidden' in str(e):
                    logger.warning(f"Access denied for time series data")
                    return TimeSeriesData([], [], [], [], [])
                else:
                    raise e
            
            # Get daily time series data
            time_series = self.analytics_service.reports().query(
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
                watch_time.append((row[2] if len(row) > 2 else 0) / 60)  # Convert to hours
                subscribers.append(row[3] if len(row) > 3 else 0)
                estimated_revenue.append(0)  # Revenue data usually not available daily
            
            return TimeSeriesData(dates, views, watch_time, subscribers, estimated_revenue)
            
        except Exception as e:
            logger.error(f"Failed to get time series data: {e}")
            return TimeSeriesData([], [], [], [], [])
    
    def get_audience_analytics(self, channel_id: str, days: int = 30) -> AudienceData:
        """Get audience analytics using YouTube Analytics API"""
        try:
            start_date, end_date = self.get_date_range(days)
            
            # Check access first
            try:
                test_query = self.analytics_service.reports().query(
                    ids=f'channel=={channel_id}',
                    startDate=start_date,
                    endDate=end_date,
                    metrics='views'
                ).execute()
                
                if not test_query.get('rows'):
                    return AudienceData([], [], [], [], [])
                    
            except Exception as e:
                if '403' in str(e) or 'Forbidden' in str(e):
                    logger.warning(f"Access denied for audience data")
                    return AudienceData([], [], [], [], [])
                else:
                    raise e
            
            age_gender = []
            device_types = []
            traffic_sources = []
            geography = []
            playback_locations = []
            
            # Age and Gender demographics
            try:
                age_gender_response = self.analytics_service.reports().query(
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
                device_response = self.analytics_service.reports().query(
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
            
            # Traffic sources - Updated dimension name
            try:
                traffic_response = self.analytics_service.reports().query(
                    ids=f'channel=={channel_id}',
                    startDate=start_date,
                    endDate=end_date,
                    metrics='views',
                    dimensions='insightTrafficSourceType'  # Updated dimension name
                ).execute()
                
                traffic_sources = [
                    {'source': row[0], 'views': row[1]}
                    for row in traffic_response.get('rows', [])
                ]
            except Exception as e:
                logger.warning(f"Traffic source data unavailable: {e}")
                # Try alternative dimension
                try:
                    traffic_response = self.analytics_service.reports().query(
                        ids=f'channel=={channel_id}',
                        startDate=start_date,
                        endDate=end_date,
                        metrics='views',
                        dimensions='trafficSourceDetail'
                    ).execute()
                    
                    traffic_sources = [
                        {'source': row[0], 'views': row[1]}
                        for row in traffic_response.get('rows', [])
                    ]
                except Exception as e2:
                    logger.warning(f"Alternative traffic source dimension also failed: {e2}")
            
            # Geography
            try:
                geo_response = self.analytics_service.reports().query(
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
            
            # Playback locations
            try:
                playback_response = self.analytics_service.reports().query(
                    ids=f'channel=={channel_id}',
                    startDate=start_date,
                    endDate=end_date,
                    metrics='views',
                    dimensions='insightPlaybackLocationType'
                ).execute()
                
                playback_locations = [
                    {'location': row[0], 'views': row[1]}
                    for row in playback_response.get('rows', [])
                ]
            except Exception as e:
                logger.warning(f"Playback location data unavailable: {e}")
            
            return AudienceData(age_gender, device_types, traffic_sources, geography, playback_locations)
            
        except Exception as e:
            logger.error(f"Failed to get audience analytics: {e}")
            return AudienceData([], [], [], [], [])

class DentalChannelsDashboard:
    """Dashboard for dental education YouTube channels"""
    
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
        
        .dental-metric {
            background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
            padding: 1rem;
            border-radius: 10px;
            text-align: center;
            margin: 0.5rem 0;
        }
        
        .content-focus-badge {
            background: #4facfe;
            color: white;
            padding: 0.3rem 0.8rem;
            border-radius: 15px;
            font-size: 0.8rem;
            font-weight: bold;
        }
        </style>
        """, unsafe_allow_html=True)
    
    def render_header(self):
        """Render dashboard header"""
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
    
    def render_sidebar(self):
        """Render sidebar controls"""
        st.sidebar.markdown("## 🦷 Analytics Controls")
        
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
            index=2,  # Default to 30 days
            help="Analytics data will be filtered for this time period"
        )
        
        days = time_options[selected_period]
        
        # Period indicator
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
        
        # All channels overview button
        if st.sidebar.button("📊 All Channels Overview", type="primary", use_container_width=True):
            st.session_state.selected_channel = None
            st.rerun()
        
        st.sidebar.markdown("#### Individual Channels:")
        
        for channel in UPLOAD_CHANNELS:
            focus_color = {
                'primary_education': '🎓',
                'treatment_focused': '🏥',
                'pediatric_care': '👶'
            }.get(channel['content_focus'], '📺')
            
            if st.sidebar.button(
                f"{focus_color} {channel['name']}",
                key=f"select_{channel['id']}",
                use_container_width=True
            ):
                st.session_state.selected_channel = channel['id']
                st.rerun()
        
        # Refresh button
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🔧 Setup Instructions")
        
        with st.sidebar.expander("📝 How to Add More Channels"):
            st.markdown("""
            **To add more channels:**
            
            1. **Get Channel ID**: Go to your YouTube channel and copy the channel ID from the URL
            
            2. **Verify Access**: Make sure you own the channel or have analytics permissions
            
            3. **Update Code**: Add the channel to the `UPLOAD_CHANNELS` list:
            ```python
            {
                "name": "Your Channel Name",
                "id": "YOUR_CHANNEL_ID",
                "content_focus": "your_focus"
            }
            ```
            
            4. **Restart**: Restart the dashboard to see the new channel
            """)
        
        with st.sidebar.expander("⚠️ Common Issues"):
            st.markdown("""
            **403 Forbidden Error:**
            - You don't own the channel
            - Missing analytics permissions
            - Incorrect channel ID
            
            **No Data Available:**
            - Channel has no recent activity
            - Data may take 24-48 hours to appear
            - Check the selected time period
            """)
        
        st.sidebar.markdown("---")
        if st.sidebar.button("🔄 Refresh Data", type="secondary", use_container_width=True):
            st.success("🔄 Refreshing analytics data...")
            time.sleep(1)
            st.rerun()
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🦷 Channel Focus Areas")
        st.sidebar.info("""
        🎓 **Dental Advisor**: Primary MIH education
        🏥 **MIH**: Treatment & care guidance  
        👶 **Enamel Hypoplasia**: Pediatric dentistry
        """)
        
        return days, period_text
    
    def render_overview_dashboard(self, service, days, period_text):
        """Render overview dashboard for all channels"""
        st.markdown(f"## 📊 All Channels Overview ({period_text})")
        
        # Collect analytics from all channels
        all_analytics = []
        total_views = 0
        total_watch_time = 0
        total_subscribers_gained = 0
        total_likes = 0
        total_comments = 0
        total_revenue = 0
        
        # Progress indicator
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, channel in enumerate(UPLOAD_CHANNELS):
            status_text.text(f"Loading analytics for {channel['name']}...")
            progress_bar.progress((i + 1) / len(UPLOAD_CHANNELS))
            
            analytics = service.get_channel_analytics(channel['id'], channel['name'], days)
            
            if analytics:
                all_analytics.append(analytics)
                total_views += analytics.period_views
                total_watch_time += analytics.period_watch_time_hours
                total_subscribers_gained += analytics.period_subscribers_gained
                total_likes += analytics.period_likes
                total_comments += analytics.period_comments
                total_revenue += analytics.estimated_revenue
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
        
        # Summary metrics
        if all_analytics:
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("👀 Total Views", f"{total_views:,}")
            
            with col2:
                st.metric("⏱️ Watch Time", f"{total_watch_time:.1f}h")
            
            with col3:
                st.metric("👥 New Subscribers", f"+{total_subscribers_gained}")
            
            with col4:
                st.metric("👍 Total Likes", f"{total_likes:,}")
            
            with col5:
                st.metric("💬 Comments", f"{total_comments:,}")
            
            # Show available channels info
            st.info(f"📊 Showing data for {len(all_analytics)} accessible channel(s). " +
                   f"If you have access to additional channels, update the channel IDs in the code.")
        else:
            st.warning("⚠️ No channel data available. Please check:")
            st.markdown("""
            - **Channel Access**: You must own or have analytics access to the channels
            - **API Permissions**: Ensure your credentials have YouTube Analytics API access
            - **Channel IDs**: Verify the channel IDs are correct and accessible
            """)
            return
        
        # Channel comparison charts
        if all_analytics:
            self.render_channel_comparison(all_analytics, period_text)
            self.render_performance_breakdown(all_analytics, period_text)
    
    def render_channel_comparison(self, all_analytics, period_text):
        """Render channel comparison charts"""
        st.markdown(f"### 📈 Channel Performance Comparison ({period_text})")
        
        # Prepare data for charts
        channel_data = []
        for analytics in all_analytics:
            channel_data.append({
                'Channel': analytics.channel_name,
                'Views': analytics.period_views,
                'Watch Time (h)': analytics.period_watch_time_hours,
                'Subscribers Gained': analytics.period_subscribers_gained,
                'Engagement': analytics.period_likes + analytics.period_comments,
                'Avg View Duration (s)': analytics.average_view_duration,
                'Content Focus': analytics.content_focus.replace('_', ' ').title(),
                'Description': analytics.description
            })
        
        df = pd.DataFrame(channel_data)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Views comparison
            fig_views = px.bar(
                df,
                x='Channel',
                y='Views',
                color='Content Focus',
                title="Views by Channel",
                color_discrete_sequence=['#4facfe', '#00f2fe', '#a8edea']
            )
            st.plotly_chart(fig_views, use_container_width=True)
            
            # Subscribers gained
            fig_subs = px.bar(
                df,
                x='Channel',
                y='Subscribers Gained',
                color='Content Focus',
                title="New Subscribers by Channel",
                color_discrete_sequence=['#fed6e3', '#f093fb', '#4facfe']
            )
            st.plotly_chart(fig_subs, use_container_width=True)
        
        with col2:
            # Watch time comparison
            fig_watch = px.bar(
                df,
                x='Channel',
                y='Watch Time (h)',
                color='Content Focus',
                title="Watch Time by Channel (Hours)",
                color_discrete_sequence=['#a8edea', '#4facfe', '#00f2fe']
            )
            st.plotly_chart(fig_watch, use_container_width=True)
            
            # Engagement scatter plot
            fig_engagement = px.scatter(
                df,
                x='Views',
                y='Engagement',
                size='Watch Time (h)',
                color='Content Focus',
                hover_data=['Channel', 'Avg View Duration (s)'],
                title="Views vs Engagement",
                color_discrete_sequence=['#4facfe', '#00f2fe', '#a8edea']
            )
            st.plotly_chart(fig_engagement, use_container_width=True)
    
    def render_performance_breakdown(self, all_analytics, period_text):
        """Render detailed performance breakdown"""
        st.markdown(f"### 🎯 Detailed Performance Breakdown ({period_text})")
        
        # Create detailed table
        detailed_data = []
        for analytics in all_analytics:
            detailed_data.append({
                'Channel': analytics.channel_name,
                'Focus Area': analytics.content_focus.replace('_', ' ').title(),
                'Views': f"{analytics.period_views:,}",
                'Watch Time': f"{analytics.period_watch_time_hours:.1f}h",
                'Avg Duration': f"{analytics.average_view_duration:.0f}s",
                'Subscribers': f"+{analytics.period_subscribers_gained}",
                'Likes': f"{analytics.period_likes:,}",
                'Comments': f"{analytics.period_comments:,}",
                'Shares': f"{analytics.period_shares:,}",
                'Revenue': f"${analytics.estimated_revenue:.2f}" if analytics.estimated_revenue > 0 else "N/A"
            })
        
        df_detailed = pd.DataFrame(detailed_data)
        st.dataframe(df_detailed, use_container_width=True, hide_index=True)
        
        # Performance insights
        st.markdown("### 💡 Performance Insights")
        
        # Find best performing channel
        best_views = max(all_analytics, key=lambda x: x.period_views)
        best_engagement = max(all_analytics, key=lambda x: x.period_likes + x.period_comments)
        best_retention = max(all_analytics, key=lambda x: x.average_view_duration)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.success(f"🏆 **Most Views**: {best_views.channel_name}")
            st.write(f"📊 {best_views.period_views:,} views")
            st.write(f"Focus: {best_views.content_focus.replace('_', ' ').title()}")
        
        with col2:
            st.info(f"💬 **Best Engagement**: {best_engagement.channel_name}")
            total_engagement = best_engagement.period_likes + best_engagement.period_comments
            st.write(f"📊 {total_engagement:,} interactions")
            st.write(f"Focus: {best_engagement.content_focus.replace('_', ' ').title()}")
        
        with col3:
            st.warning(f"⏰ **Best Retention**: {best_retention.channel_name}")
            st.write(f"📊 {best_retention.average_view_duration:.0f}s avg duration")
            st.write(f"Focus: {best_retention.content_focus.replace('_', ' ').title()}")
    
    def render_channel_dashboard(self, service, channel_id, days, period_text):
        """Render detailed dashboard for specific channel"""
        # Find channel config
        channel_config = next((ch for ch in UPLOAD_CHANNELS if ch['id'] == channel_id), None)
        if not channel_config:
            st.error("Channel not found!")
            return
        
        channel_name = channel_config['name']
        
        # Back button
        if st.button("← Back to Overview", key="back_btn", type="secondary"):
            st.session_state.selected_channel = None
            st.rerun()
        
        st.markdown(f"## 🦷 {channel_name} - Detailed Analytics ({period_text})")
        
        # Channel info card
        focus_emoji = {
            'primary_education': '🎓',
            'treatment_focused': '🏥',
            'pediatric_care': '👶'
        }.get(channel_config['content_focus'], '📺')
        
        st.markdown(f"""
        <div class="channel-card">
            <h3>{focus_emoji} {channel_name}</h3>
            <p><strong>Focus:</strong> {channel_config['content_focus'].replace('_', ' ').title()}</p>
            <p><strong>Description:</strong> {channel_config['description']}</p>
            <span class="content-focus-badge">{channel_config['content_focus'].replace('_', ' ').title()}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Get analytics data
        with st.spinner(f"Loading detailed analytics for {channel_name}..."):
            analytics = service.get_channel_analytics(channel_id, channel_name, days)
            time_series = service.get_time_series_data(channel_id, days)
            audience_data = service.get_audience_analytics(channel_id, days)
        
        if not analytics:
            st.error(f"Could not load analytics for {channel_name}")
            return
        
        # Key metrics
        st.markdown("### 📊 Key Performance Metrics")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("👀 Views", f"{analytics.period_views:,}")
        
        with col2:
            st.metric("⏱️ Watch Time", f"{analytics.period_watch_time_hours:.1f}h")
        
        with col3:
            st.metric("👥 Subscribers", f"+{analytics.period_subscribers_gained}")
        
        with col4:
            st.metric("👍 Likes", f"{analytics.period_likes:,}")
        
        with col5:
            st.metric("💬 Comments", f"{analytics.period_comments:,}")
        
        # Additional metrics
        col6, col7, col8 = st.columns(3)
        
        with col6:
            st.metric("📤 Shares", f"{analytics.period_shares:,}")
        
        with col7:
            st.metric("⏰ Avg Duration", f"{analytics.average_view_duration:.0f}s")
        
        with col8:
            if analytics.estimated_revenue > 0:
                st.metric("💰 Revenue", f"${analytics.estimated_revenue:.2f}")
            else:
                engagement_rate = ((analytics.period_likes + analytics.period_comments) / max(analytics.period_views, 1)) * 100
                st.metric("📊 Engagement Rate", f"{engagement_rate:.2f}%")
        
        # Time series charts
        if time_series.dates:
            self.render_time_series_charts(time_series, channel_name, period_text)
        
        # Audience analytics
        self.render_audience_analytics(audience_data, channel_name, period_text)
    
    def render_time_series_charts(self, time_series, channel_name, period_text):
        """Render time series charts"""
        st.markdown(f"### 📈 Performance Trends - {channel_name} ({period_text})")
        
        # Create DataFrame for time series
        df_series = pd.DataFrame({
            'Date': pd.to_datetime(time_series.dates),
            'Views': time_series.views,
            'Watch Time (h)': time_series.watch_time,
            'Subscribers Gained': time_series.subscribers
        })
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Views over time
            fig_views = px.line(
                df_series,
                x='Date',
                y='Views',
                title=f"Daily Views - {channel_name}",
                color_discrete_sequence=['#4facfe']
            )
            fig_views.update_layout(showlegend=False)
            st.plotly_chart(fig_views, use_container_width=True)
            
            # Subscribers gained over time
            fig_subs = px.bar(
                df_series,
                x='Date',
                y='Subscribers Gained',
                title=f"Daily Subscribers Gained - {channel_name}",
                color_discrete_sequence=['#00f2fe']
            )
            st.plotly_chart(fig_subs, use_container_width=True)
        
        with col2:
            # Watch time over time
            fig_watch = px.line(
                df_series,
                x='Date',
                y='Watch Time (h)',
                title=f"Daily Watch Time - {channel_name}",
                color_discrete_sequence=['#a8edea']
            )
            fig_watch.update_layout(showlegend=False)
            st.plotly_chart(fig_watch, use_container_width=True)
            
            # Combined metrics
            fig_combined = make_subplots(
                rows=2, cols=1,
                subplot_titles=('Views', 'Watch Time (h)'),
                vertical_spacing=0.1
            )
            
            fig_combined.add_trace(
                go.Scatter(x=df_series['Date'], y=df_series['Views'], 
                          name='Views', line=dict(color='#4facfe')),
                row=1, col=1
            )
            
            fig_combined.add_trace(
                go.Scatter(x=df_series['Date'], y=df_series['Watch Time (h)'], 
                          name='Watch Time', line=dict(color='#00f2fe')),
                row=2, col=1
            )
            
            fig_combined.update_layout(
                title=f"Combined Metrics - {channel_name}",
                height=400,
                showlegend=False
            )
            st.plotly_chart(fig_combined, use_container_width=True)
    
    def render_audience_analytics(self, audience_data, channel_name, period_text):
        """Render audience analytics"""
        st.markdown(f"### 👥 Audience Analytics - {channel_name} ({period_text})")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Traffic Sources
            st.markdown("#### 🔍 Traffic Sources")
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
                    'PLAYLIST': 'Playlists',
                    'SEARCH': 'Search',
                    'RELATED_VIDEO': 'Related Videos',
                    'SUBSCRIBER': 'Subscriber Feed',
                    'CHANNEL': 'Channel Page',
                    'LIVE': 'Live Streaming'
                }
                
                df_traffic['source'] = df_traffic['source'].map(source_mapping).fillna(df_traffic['source'])
                
                fig_traffic = px.pie(
                    df_traffic,
                    values='views',
                    names='source',
                    title="How Viewers Find Content",
                    color_discrete_sequence=['#4facfe', '#00f2fe', '#a8edea', '#fed6e3', '#f093fb']
                )
                st.plotly_chart(fig_traffic, use_container_width=True)
            else:
                st.info("Traffic source data not available")
            
            # Device Types
            st.markdown("#### 📱 Device Usage")
            if audience_data.device_types:
                df_devices = pd.DataFrame(audience_data.device_types)
                
                device_mapping = {
                    'MOBILE': 'Mobile 📱',
                    'DESKTOP': 'Desktop 💻',
                    'TABLET': 'Tablet 📲',
                    'TV': 'TV/Smart TV 📺'
                }
                
                df_devices['device'] = df_devices['device'].map(device_mapping).fillna(df_devices['device'])
                
                fig_devices = px.bar(
                    df_devices,
                    x='device',
                    y='views',
                    title="Views by Device Type",
                    color='views',
                    color_continuous_scale='Blues'
                )
                st.plotly_chart(fig_devices, use_container_width=True)
            else:
                st.info("Device data not available")
        
        with col2:
            # Geography
            st.markdown("#### 🌍 Geographic Distribution")
            if audience_data.geography:
                df_geo = pd.DataFrame(audience_data.geography)
                
                fig_geo = px.bar(
                    df_geo.head(10),
                    x='views',
                    y='country',
                    orientation='h',
                    title="Top 10 Countries",
                    color='views',
                    color_continuous_scale='Viridis'
                )
                fig_geo.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig_geo, use_container_width=True)
            else:
                st.info("Geographic data not available")
            
            # Demographics
            st.markdown("#### 👫 Demographics")
            if audience_data.age_gender:
                df_demo = pd.DataFrame(audience_data.age_gender)
                
                if not df_demo.empty:
                    # Age group summary
                    df_age_summary = df_demo.groupby('age_group')['percentage'].sum().reset_index()
                    df_age_summary = df_age_summary.sort_values('percentage', ascending=False)
                    
                    fig_demo = px.bar(
                        df_age_summary,
                        x='age_group',
                        y='percentage',
                        title="Audience by Age Group (%)",
                        color='percentage',
                        color_continuous_scale='Plasma'
                    )
                    st.plotly_chart(fig_demo, use_container_width=True)
                else:
                    st.info("Demographic data not available")
            else:
                st.info("Demographic data not available")
            
            # Playback Locations
            if audience_data.playback_locations:
                st.markdown("#### 📍 Playback Locations")
                df_playback = pd.DataFrame(audience_data.playback_locations)
                
                location_mapping = {
                    'WATCH': 'YouTube Watch Page',
                    'EMBEDDED': 'Embedded Players',
                    'MOBILE': 'Mobile App',
                    'CHANNEL': 'Channel Page'
                }
                
                df_playback['location'] = df_playback['location'].map(location_mapping).fillna(df_playback['location'])
                
                fig_playback = px.pie(
                    df_playback,
                    values='views',
                    names='location',
                    title="Where Videos Are Watched",
                    color_discrete_sequence=['#4facfe', '#00f2fe', '#a8edea', '#fed6e3']
                )
                st.plotly_chart(fig_playback, use_container_width=True)
    
    def render_export_options(self, service, days, period_text):
        """Render export options"""
        st.markdown(f"## 📥 Export Analytics Data ({period_text})")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("📊 Export Summary", type="secondary", use_container_width=True):
                export_data = []
                
                for channel in UPLOAD_CHANNELS:
                    analytics = service.get_channel_analytics(channel['id'], channel['name'], days)
                    
                    if analytics:
                        export_data.append({
                            'Channel': analytics.channel_name,
                            'Content Focus': analytics.content_focus.replace('_', ' ').title(),
                            'Time Period': period_text,
                            'Views': analytics.period_views,
                            'Watch Time Hours': analytics.period_watch_time_hours,
                            'Subscribers Gained': analytics.period_subscribers_gained,
                            'Likes': analytics.period_likes,
                            'Comments': analytics.period_comments,
                            'Shares': analytics.period_shares,
                            'Avg View Duration': analytics.average_view_duration,
                            'Estimated Revenue': analytics.estimated_revenue,
                            'CPM': analytics.cpm,
                            'Description': analytics.description
                        })
                
                if export_data:
                    df_export = pd.DataFrame(export_data)
                    csv = df_export.to_csv(index=False)
                    st.download_button(
                        "📥 Download Summary CSV",
                        csv,
                        f"dental_channels_summary_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        "text/csv",
                        key="summary_download"
                    )
        
        with col2:
            if st.button("📈 Export Time Series", type="secondary", use_container_width=True):
                all_time_series = []
                
                for channel in UPLOAD_CHANNELS:
                    time_series = service.get_time_series_data(channel['id'], days)
                    
                    for i, date in enumerate(time_series.dates):
                        all_time_series.append({
                            'Channel': channel['name'],
                            'Content Focus': channel['content_focus'].replace('_', ' ').title(),
                            'Date': date,
                            'Views': time_series.views[i] if i < len(time_series.views) else 0,
                            'Watch Time Hours': time_series.watch_time[i] if i < len(time_series.watch_time) else 0,
                            'Subscribers Gained': time_series.subscribers[i] if i < len(time_series.subscribers) else 0
                        })
                
                if all_time_series:
                    df_series = pd.DataFrame(all_time_series)
                    csv_series = df_series.to_csv(index=False)
                    st.download_button(
                        "📥 Download Time Series CSV",
                        csv_series,
                        f"dental_channels_timeseries_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        "text/csv",
                        key="series_download"
                    )
        
        with col3:
            if st.button("👥 Export Audience Data", type="secondary", use_container_width=True):
                audience_export = []
                
                for channel in UPLOAD_CHANNELS:
                    audience_data = service.get_audience_analytics(channel['id'], days)
                    
                    # Traffic sources
                    for item in audience_data.traffic_sources:
                        audience_export.append({
                            'Channel': channel['name'],
                            'Content Focus': channel['content_focus'].replace('_', ' ').title(),
                            'Data Type': 'Traffic Source',
                            'Category': item['source'],
                            'Value': item['views'],
                            'Metric': 'Views'
                        })
                    
                    # Device types
                    for item in audience_data.device_types:
                        audience_export.append({
                            'Channel': channel['name'],
                            'Content Focus': channel['content_focus'].replace('_', ' ').title(),
                            'Data Type': 'Device Type',
                            'Category': item['device'],
                            'Value': item['views'],
                            'Metric': 'Views'
                        })
                    
                    # Demographics
                    for item in audience_data.age_gender:
                        audience_export.append({
                            'Channel': channel['name'],
                            'Content Focus': channel['content_focus'].replace('_', ' ').title(),
                            'Data Type': 'Demographics',
                            'Category': f"{item['age_group']} - {item['gender']}",
                            'Value': item['percentage'],
                            'Metric': 'Percentage'
                        })
                
                if audience_export:
                    df_audience = pd.DataFrame(audience_export)
                    csv_audience = df_audience.to_csv(index=False)
                    st.download_button(
                        "📥 Download Audience CSV",
                        csv_audience,
                        f"dental_channels_audience_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        "text/csv",
                        key="audience_download"
                    )
        
        with col4:
            if st.button("📋 Export Full Report", type="primary", use_container_width=True):
                # Generate comprehensive report
                report_data = {
                    'report_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'period': period_text,
                    'channels': []
                }
                
                for channel in UPLOAD_CHANNELS:
                    analytics = service.get_channel_analytics(channel['id'], channel['name'], days)
                    time_series = service.get_time_series_data(channel['id'], days)
                    audience_data = service.get_audience_analytics(channel['id'], days)
                    
                    if analytics:
                        channel_report = {
                            'name': analytics.channel_name,
                            'content_focus': analytics.content_focus,
                            'description': analytics.description,
                            'metrics': {
                                'views': analytics.period_views,
                                'watch_time_hours': analytics.period_watch_time_hours,
                                'subscribers_gained': analytics.period_subscribers_gained,
                                'likes': analytics.period_likes,
                                'comments': analytics.period_comments,
                                'shares': analytics.period_shares,
                                'avg_view_duration': analytics.average_view_duration,
                                'estimated_revenue': analytics.estimated_revenue,
                                'cpm': analytics.cpm
                            },
                            'time_series': {
                                'dates': time_series.dates,
                                'views': time_series.views,
                                'watch_time': time_series.watch_time,
                                'subscribers': time_series.subscribers
                            },
                            'audience': {
                                'traffic_sources': audience_data.traffic_sources,
                                'device_types': audience_data.device_types,
                                'geography': audience_data.geography,
                                'demographics': audience_data.age_gender,
                                'playback_locations': audience_data.playback_locations
                            }
                        }
                        report_data['channels'].append(channel_report)
                
                # Convert to JSON
                json_report = json.dumps(report_data, indent=2, default=str)
                st.download_button(
                    "📥 Download Full JSON Report",
                    json_report,
                    f"dental_channels_full_report_{days}days_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    "application/json",
                    key="full_report_download"
                )
    
    def run(self):
        """Main dashboard runner"""
        try:
            # Initialize service
            service = YouTubeAnalyticsService()
            
            # Render header
            self.render_header()
            
            # Render sidebar
            days, period_text = self.render_sidebar()
            
            # Main content routing
            if st.session_state.selected_channel is None:
                # Show overview dashboard
                self.render_overview_dashboard(service, days, period_text)
            else:
                # Show channel-specific dashboard
                self.render_channel_dashboard(service, st.session_state.selected_channel, days, period_text)
            
            st.markdown("---")
            
            # Export options
            self.render_export_options(service, days, period_text)
            
        except Exception as e:
            st.error(f"❌ Error loading dashboard: {e}")
            logger.error(f"Dashboard error: {e}", exc_info=True)
            st.markdown("### 🔧 Troubleshooting:")
            st.markdown("- Ensure `youtube_credentials.json` is in the same directory")
            st.markdown("- Check internet connection")
            st.markdown("- Verify YouTube Analytics API permissions")
            st.markdown("- Check API quota limits")
            st.markdown("- Make sure you have access to the specified channels")
        
        # Footer
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; color: #666; padding: 2rem;">
            <p>🦷 Dental Education YouTube Analytics Dashboard</p>
            <p>Powered by YouTube Analytics API v2 | Specialized for Dental Content</p>
            <p style="font-size: 0.9rem; opacity: 0.7;">
                Dental Advisor • MIH Education • Enamel Hypoplasia Research
            </p>
        </div>
        """, unsafe_allow_html=True)

# Main execution
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