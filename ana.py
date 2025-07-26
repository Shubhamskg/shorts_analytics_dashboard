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
class VideoMetrics:
    """Data class for video metrics"""
    video_id: str
    title: str
    published_at: str
    duration: str
    views: int
    likes: int
    comments: int
    shares: int
    subscribers_gained: int
    watch_time_minutes: float
    average_view_duration: float
    ctr: float  # Click-through rate
    retention_rate: float
    thumbnail_url: str
    channel_name: str

@dataclass
class ChannelMetrics:
    """Data class for channel metrics"""
    channel_id: str
    channel_name: str
    subscribers: int
    total_views: int
    total_videos: int
    total_watch_time: float
    avg_views_per_video: float
    engagement_rate: float
    growth_rate: float

class YouTubeAnalyticsAPI:
    """YouTube Analytics API handler"""
    
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
                
                youtube_service = build('youtube', 'v3', credentials=creds)
                analytics_service = build('youtubeAnalytics', 'v2', credentials=creds)
                
                self.youtube_services[channel_key] = {
                    'service': youtube_service,
                    'config': config
                }
                self.analytics_services[channel_key] = {
                    'service': analytics_service,
                    'config': config
                }
                
                logger.info(f"Successfully authenticated: {channel_name}")
            except Exception as e:
                logger.error(f"Authentication failed for {channel_name}: {e}")
                continue
    
    def get_channel_id(self, channel_key: str) -> Optional[str]:
        """Get channel ID for authenticated channel"""
        try:
            service = self.youtube_services[channel_key]['service']
            request = service.channels().list(part="id,snippet", mine=True)
            response = request.execute()
            
            if response.get("items"):
                return response["items"][0]["id"]
        except Exception as e:
            logger.error(f"Failed to get channel ID for {channel_key}: {e}")
        return None
    
    def get_channel_metrics(self, channel_key: str, days: int = 30) -> Optional[ChannelMetrics]:
        """Get channel-level metrics"""
        try:
            channel_id = self.get_channel_id(channel_key)
            if not channel_id:
                return None
            
            # Get channel statistics
            youtube_service = self.youtube_services[channel_key]['service']
            analytics_service = self.analytics_services[channel_key]['service']
            config = self.youtube_services[channel_key]['config']
            
            # Channel basic info
            channel_request = youtube_service.channels().list(
                part="statistics,snippet",
                id=channel_id
            )
            channel_response = channel_request.execute()
            
            if not channel_response.get("items"):
                return None
            
            channel_data = channel_response["items"][0]
            stats = channel_data["statistics"]
            snippet = channel_data["snippet"]
            
            # Analytics data
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            analytics_request = analytics_service.reports().query(
                ids=f'channel=={channel_id}',
                startDate=start_date,
                endDate=end_date,
                metrics='views,estimatedMinutesWatched,subscribersGained',
                dimensions='day'
            )
            analytics_response = analytics_request.execute()
            
            # Calculate metrics
            total_views = int(stats.get('viewCount', 0))
            subscribers = int(stats.get('subscriberCount', 0))
            total_videos = int(stats.get('videoCount', 0))
            
            # From analytics
            analytics_data = analytics_response.get('rows', [])
            recent_views = sum(row[1] for row in analytics_data)
            recent_watch_time = sum(row[2] for row in analytics_data)
            recent_subscribers = sum(row[3] for row in analytics_data)
            
            avg_views_per_video = total_views / max(total_videos, 1)
            
            return ChannelMetrics(
                channel_id=channel_id,
                channel_name=config.get('name', snippet.get('title', 'Unknown')),
                subscribers=subscribers,
                total_views=total_views,
                total_videos=total_videos,
                total_watch_time=recent_watch_time,
                avg_views_per_video=avg_views_per_video,
                engagement_rate=0.0,  # Will calculate separately
                growth_rate=(recent_subscribers / max(subscribers, 1)) * 100
            )
            
        except Exception as e:
            logger.error(f"Failed to get channel metrics for {channel_key}: {e}")
            return None
    
    def get_video_metrics(self, channel_key: str, days: int = 30, limit: int = 50) -> List[VideoMetrics]:
        """Get video-level metrics"""
        video_metrics = []
        
        try:
            channel_id = self.get_channel_id(channel_key)
            if not channel_id:
                return video_metrics
            
            youtube_service = self.youtube_services[channel_key]['service']
            analytics_service = self.analytics_services[channel_key]['service']
            config = self.youtube_services[channel_key]['config']
            
            # Get recent videos
            search_request = youtube_service.search().list(
                part="id,snippet",
                channelId=channel_id,
                maxResults=limit,
                order="date",
                type="video",
                publishedAfter=(datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
            )
            search_response = search_request.execute()
            
            video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
            
            if not video_ids:
                return video_metrics
            
            # Get video statistics
            videos_request = youtube_service.videos().list(
                part="statistics,snippet,contentDetails",
                id=','.join(video_ids)
            )
            videos_response = videos_request.execute()
            
            # Get analytics for each video
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            for video in videos_response.get('items', []):
                try:
                    video_id = video['id']
                    snippet = video['snippet']
                    stats = video['statistics']
                    content_details = video['contentDetails']
                    
                    # Check if it's a Short (duration <= 60 seconds)
                    duration = content_details.get('duration', 'PT0S')
                    if not self._is_short_video(duration):
                        continue
                    
                    # Get detailed analytics for this video
                    analytics_request = analytics_service.reports().query(
                        ids=f'channel=={channel_id}',
                        startDate=start_date,
                        endDate=end_date,
                        metrics='views,likes,comments,shares,subscribersGained,estimatedMinutesWatched,averageViewDuration',
                        filters=f'video=={video_id}'
                    )
                    analytics_response = analytics_request.execute()
                    
                    analytics_data = analytics_response.get('rows', [[0, 0, 0, 0, 0, 0, 0]])[0]
                    
                    video_metric = VideoMetrics(
                        video_id=video_id,
                        title=snippet.get('title', 'Unknown'),
                        published_at=snippet.get('publishedAt', ''),
                        duration=duration,
                        views=int(stats.get('viewCount', 0)),
                        likes=int(stats.get('likeCount', 0)),
                        comments=int(stats.get('commentCount', 0)),
                        shares=analytics_data[3] if len(analytics_data) > 3 else 0,
                        subscribers_gained=analytics_data[4] if len(analytics_data) > 4 else 0,
                        watch_time_minutes=analytics_data[5] if len(analytics_data) > 5 else 0,
                        average_view_duration=analytics_data[6] if len(analytics_data) > 6 else 0,
                        ctr=0.0,  # Will calculate if impression data available
                        retention_rate=0.0,  # Will calculate separately
                        thumbnail_url=snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                        channel_name=config.get('name', 'Unknown')
                    )
                    
                    video_metrics.append(video_metric)
                    
                except Exception as e:
                    logger.error(f"Error processing video {video_id}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Failed to get video metrics for {channel_key}: {e}")
        
        return video_metrics
    
    def _is_short_video(self, duration: str) -> bool:
        """Check if video is a YouTube Short (<=60 seconds)"""
        try:
            # Parse ISO 8601 duration format (PT1M30S)
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
    
    def get_performance_comparison(self, days: int = 30) -> Dict:
        """Get performance comparison across all channels"""
        comparison_data = {
            'channels': [],
            'total_views': 0,
            'total_subscribers': 0,
            'total_videos': 0,
            'total_watch_time': 0
        }
        
        for channel_key in self.youtube_services.keys():
            metrics = self.get_channel_metrics(channel_key, days)
            if metrics:
                comparison_data['channels'].append(metrics)
                comparison_data['total_views'] += metrics.total_views
                comparison_data['total_subscribers'] += metrics.subscribers
                comparison_data['total_videos'] += metrics.total_videos
                comparison_data['total_watch_time'] += metrics.total_watch_time
        
        return comparison_data

class AnalyticsDashboard:
    """Streamlit dashboard for YouTube analytics"""
    
    def __init__(self):
        st.set_page_config(
            page_title="Dr. Greenwall MIH Shorts Analytics",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Custom CSS
        st.markdown("""
        <style>
        .metric-card {
            background-color: #f0f2f6;
            padding: 1rem;
            border-radius: 10px;
            border-left: 4px solid #2E8B57;
        }
        .top-video-card {
            background-color: #ffffff;
            padding: 1rem;
            border-radius: 10px;
            border: 1px solid #e0e0e0;
            margin-bottom: 1rem;
        }
        .channel-header {
            background: linear-gradient(90deg, #2E8B57, #4ECDC4);
            color: white;
            padding: 1rem;
            border-radius: 10px;
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
    
    def initialize_api(self, system_config):
        """Initialize YouTube Analytics API"""
        try:
            return YouTubeAnalyticsAPI(
                system_config['youtube_api_key'],
                system_config['upload_channels']
            )
        except Exception as e:
            st.error(f"❌ Failed to initialize YouTube API: {e}")
            st.stop()
    
    def render_header(self):
        """Render dashboard header"""
        st.markdown("""
        <div style="text-align: center; padding: 2rem; background: linear-gradient(90deg, #2E8B57, #4ECDC4); color: white; border-radius: 10px; margin-bottom: 2rem;">
            <h1>📊 Dr. Linda Greenwall MIH Shorts Analytics</h1>
            <p style="font-size: 1.2rem;">Comprehensive Performance Dashboard for MIH Expert Content</p>
        </div>
        """, unsafe_allow_html=True)
    
    def render_sidebar(self):
        """Render sidebar controls"""
        st.sidebar.markdown("## 🔧 Dashboard Controls")
        
        # Time period selection
        time_period = st.sidebar.selectbox(
            "📅 Select Time Period",
            options=[7, 14, 30, 60, 90],
            index=2,
            format_func=lambda x: f"Last {x} days"
        )
        
        # Refresh button
        if st.sidebar.button("🔄 Refresh Data", type="primary"):
            st.cache_data.clear()
            st.rerun()
        
        # Auto-refresh toggle
        auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh (30 sec)", value=False)
        
        if auto_refresh:
            time.sleep(30)
            st.rerun()
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📈 Key Metrics")
        st.sidebar.info("All metrics are calculated based on YouTube Shorts content only (videos ≤60 seconds)")
        
        return time_period
    
    def render_overview_metrics(self, analytics_api, days):
        """Render overview metrics section"""
        st.markdown("## 📊 Performance Overview")
        
        # Get comparison data
        comparison_data = analytics_api.get_performance_comparison(days)
        
        # Overview metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "🎬 Total Shorts",
                f"{comparison_data['total_videos']:,}",
                delta=None
            )
        
        with col2:
            st.metric(
                "👀 Total Views",
                f"{comparison_data['total_views']:,}",
                delta=None
            )
        
        with col3:
            st.metric(
                "👥 Total Subscribers",
                f"{comparison_data['total_subscribers']:,}",
                delta=None
            )
        
        with col4:
            watch_time_hours = comparison_data['total_watch_time'] / 60
            st.metric(
                "⏱️ Watch Time (Hours)",
                f"{watch_time_hours:,.1f}",
                delta=None
            )
        
        return comparison_data
    
    def render_channel_performance(self, analytics_api, days):
        """Render individual channel performance"""
        st.markdown("## 🏆 Channel Performance Breakdown")
        
        for channel_key in analytics_api.youtube_services.keys():
            config = analytics_api.youtube_services[channel_key]['config']
            channel_name = config.get('name', f'Channel {channel_key}')
            
            # Channel header
            st.markdown(f"""
            <div class="channel-header">
                <h3>📺 {channel_name}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            # Get channel metrics
            channel_metrics = analytics_api.get_channel_metrics(channel_key, days)
            
            if channel_metrics:
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    st.metric("Subscribers", f"{channel_metrics.subscribers:,}")
                
                with col2:
                    st.metric("Total Views", f"{channel_metrics.total_views:,}")
                
                with col3:
                    st.metric("Videos", f"{channel_metrics.total_videos:,}")
                
                with col4:
                    st.metric("Avg Views/Video", f"{channel_metrics.avg_views_per_video:,.0f}")
                
                with col5:
                    st.metric("Growth Rate", f"{channel_metrics.growth_rate:.2f}%")
                
                # Channel specific charts
                self.render_channel_charts(analytics_api, channel_key, channel_name, days)
            else:
                st.warning(f"❌ Could not load metrics for {channel_name}")
    
    def render_channel_charts(self, analytics_api, channel_key, channel_name, days):
        """Render charts for specific channel"""
        video_metrics = analytics_api.get_video_metrics(channel_key, days, limit=20)
        
        if not video_metrics:
            st.warning(f"No video data available for {channel_name}")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Views distribution
            df_views = pd.DataFrame([
                {
                    'Title': metric.title[:30] + '...' if len(metric.title) > 30 else metric.title,
                    'Views': metric.views,
                    'Likes': metric.likes,
                    'Comments': metric.comments
                }
                for metric in video_metrics[:10]
            ])
            
            if not df_views.empty:
                fig_views = px.bar(
                    df_views,
                    x='Views',
                    y='Title',
                    orientation='h',
                    title=f"📈 Top 10 Videos by Views - {channel_name}",
                    color='Views',
                    color_continuous_scale='Viridis'
                )
                fig_views.update_layout(height=400)
                st.plotly_chart(fig_views, use_container_width=True)
        
        with col2:
            # Engagement metrics
            df_engagement = pd.DataFrame([
                {
                    'Title': metric.title[:20] + '...' if len(metric.title) > 20 else metric.title,
                    'Likes': metric.likes,
                    'Comments': metric.comments,
                    'Engagement Rate': ((metric.likes + metric.comments) / max(metric.views, 1)) * 100
                }
                for metric in video_metrics[:10]
            ])
            
            if not df_engagement.empty:
                fig_engagement = px.scatter(
                    df_engagement,
                    x='Likes',
                    y='Comments',
                    size='Engagement Rate',
                    hover_data=['Title'],
                    title=f"💬 Engagement Analysis - {channel_name}",
                    color='Engagement Rate',
                    color_continuous_scale='Reds'
                )
                fig_engagement.update_layout(height=400)
                st.plotly_chart(fig_engagement, use_container_width=True)
        
        # Top performing videos table
        self.render_top_videos_table(video_metrics[:5], channel_name)
    
    def render_top_videos_table(self, video_metrics, channel_name):
        """Render top performing videos table"""
        st.markdown(f"### 🏅 Top 5 Performing Shorts - {channel_name}")
        
        for i, video in enumerate(video_metrics, 1):
            col1, col2, col3 = st.columns([1, 3, 2])
            
            with col1:
                if video.thumbnail_url:
                    st.image(video.thumbnail_url, width=80)
                else:
                    st.markdown(f"**#{i}**")
            
            with col2:
                st.markdown(f"""
                **{video.title}**
                
                🔗 [Watch Video](https://youtube.com/watch?v={video.video_id})
                
                📅 Published: {video.published_at[:10]}
                """)
            
            with col3:
                st.markdown(f"""
                👀 **{video.views:,}** views
                
                👍 **{video.likes:,}** likes
                
                💬 **{video.comments:,}** comments
                
                📈 **{video.subscribers_gained}** subs gained
                """)
            
            st.markdown("---")
    
    def render_comparative_analysis(self, analytics_api, days):
        """Render comparative analysis across channels"""
        st.markdown("## 📊 Cross-Channel Analysis")
        
        # Collect data from all channels
        all_channel_data = []
        all_video_data = []
        
        for channel_key in analytics_api.youtube_services.keys():
            config = analytics_api.youtube_services[channel_key]['config']
            channel_name = config.get('name', f'Channel {channel_key}')
            
            # Channel metrics
            channel_metrics = analytics_api.get_channel_metrics(channel_key, days)
            if channel_metrics:
                all_channel_data.append({
                    'Channel': channel_name,
                    'Subscribers': channel_metrics.subscribers,
                    'Total Views': channel_metrics.total_views,
                    'Videos': channel_metrics.total_videos,
                    'Avg Views/Video': channel_metrics.avg_views_per_video,
                    'Growth Rate %': channel_metrics.growth_rate,
                    'Watch Time (Hours)': channel_metrics.total_watch_time / 60
                })
            
            # Video metrics
            video_metrics = analytics_api.get_video_metrics(channel_key, days, limit=10)
            for video in video_metrics:
                all_video_data.append({
                    'Channel': channel_name,
                    'Title': video.title,
                    'Views': video.views,
                    'Likes': video.likes,
                    'Comments': video.comments,
                    'Engagement Rate': ((video.likes + video.comments) / max(video.views, 1)) * 100,
                    'Published': video.published_at[:10]
                })
        
        if all_channel_data:
            col1, col2 = st.columns(2)
            
            with col1:
                # Channel comparison chart
                df_channels = pd.DataFrame(all_channel_data)
                fig_comparison = px.bar(
                    df_channels,
                    x='Channel',
                    y='Total Views',
                    title="📊 Total Views by Channel",
                    color='Total Views',
                    color_continuous_scale='Blues'
                )
                st.plotly_chart(fig_comparison, use_container_width=True)
            
            with col2:
                # Growth rate comparison
                fig_growth = px.pie(
                    df_channels,
                    values='Subscribers',
                    names='Channel',
                    title="👥 Subscriber Distribution"
                )
                st.plotly_chart(fig_growth, use_container_width=True)
            
            # Performance table
            st.markdown("### 📈 Channel Performance Summary")
            st.dataframe(df_channels, use_container_width=True)
        
        if all_video_data:
            # Best performing videos across all channels
            df_all_videos = pd.DataFrame(all_video_data)
            df_top_videos = df_all_videos.nlargest(10, 'Views')
            
            st.markdown("### 🏆 Top 10 Videos Across All Channels")
            
            fig_top_videos = px.bar(
                df_top_videos,
                x='Views',
                y='Title',
                color='Channel',
                orientation='h',
                title="🎯 Best Performing Videos (All Channels)",
                height=600
            )
            fig_top_videos.update_yaxes(tickfont=dict(size=10))
            st.plotly_chart(fig_top_videos, use_container_width=True)
    
    def render_insights_recommendations(self, analytics_api, days):
        """Render insights and recommendations"""
        st.markdown("## 💡 Insights & Recommendations")
        
        # Collect performance data
        insights = []
        all_videos = []
        
        for channel_key in analytics_api.youtube_services.keys():
            config = analytics_api.youtube_services[channel_key]['config']
            channel_name = config.get('name', f'Channel {channel_key}')
            
            video_metrics = analytics_api.get_video_metrics(channel_key, days, limit=20)
            for video in video_metrics:
                all_videos.append({
                    'channel': channel_name,
                    'views': video.views,
                    'likes': video.likes,
                    'comments': video.comments,
                    'engagement_rate': ((video.likes + video.comments) / max(video.views, 1)) * 100,
                    'title': video.title
                })
        
        if all_videos:
            df_all = pd.DataFrame(all_videos)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 🎯 Key Insights")
                
                # Best performing channel
                best_channel = df_all.groupby('channel')['views'].mean().idxmax()
                avg_views_best = df_all.groupby('channel')['views'].mean().max()
                
                st.success(f"🏆 **Best Performing Channel**: {best_channel} (Avg: {avg_views_best:,.0f} views)")
                
                # Highest engagement rate
                best_engagement = df_all.loc[df_all['engagement_rate'].idxmax()]
                st.info(f"💬 **Highest Engagement**: {best_engagement['engagement_rate']:.2f}% - '{best_engagement['title'][:50]}...'")
                
                # Average metrics
                avg_views = df_all['views'].mean()
                avg_engagement = df_all['engagement_rate'].mean()
                
                st.metric("📊 Average Views per Short", f"{avg_views:,.0f}")
                st.metric("💬 Average Engagement Rate", f"{avg_engagement:.2f}%")
            
            with col2:
                st.markdown("### 🚀 Recommendations")
                
                # Content recommendations
                top_titles = df_all.nlargest(5, 'views')['title'].tolist()
                
                st.markdown("**🎬 Successful Content Patterns:**")
                for title in top_titles[:3]:
                    st.markdown(f"• {title[:50]}...")
                
                st.markdown("**📈 Optimization Opportunities:**")
                
                low_engagement = df_all[df_all['engagement_rate'] < avg_engagement]
                if not low_engagement.empty:
                    st.markdown(f"• {len(low_engagement)} videos have below-average engagement")
                    st.markdown("• Consider adding more call-to-actions")
                    st.markdown("• Focus on audience retention strategies")
                
                high_performers = df_all[df_all['views'] > avg_views * 1.5]
                if not high_performers.empty:
                    st.markdown(f"• {len(high_performers)} videos are high performers")
                    st.markdown("• Analyze their titles and content for patterns")
                    st.markdown("• Replicate successful formats")
        
        # MIH-specific insights
        st.markdown("### 🦷 MIH Content Performance")
        
        mih_keywords = ['MIH', 'chalky teeth', 'white spots', 'enamel', 'ICON', 'pediatric', 'children']
        
        if all_videos:
            # Analyze MIH content performance
            mih_videos = []
            general_videos = []
            
            for video in all_videos:
                title_lower = video['title'].lower()
                if any(keyword.lower() in title_lower for keyword in mih_keywords):
                    mih_videos.append(video)
                else:
                    general_videos.append(video)
            
            if mih_videos and general_videos:
                mih_avg_views = sum(v['views'] for v in mih_videos) / len(mih_videos)
                general_avg_views = sum(v['views'] for v in general_videos) / len(general_videos)
                
                mih_avg_engagement = sum(v['engagement_rate'] for v in mih_videos) / len(mih_videos)
                general_avg_engagement = sum(v['engagement_rate'] for v in general_videos) / len(general_videos)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("🦷 MIH Content Avg Views", f"{mih_avg_views:,.0f}")
                    st.metric("🦷 MIH Content Engagement", f"{mih_avg_engagement:.2f}%")
                
                with col2:
                    st.metric("📺 General Content Avg Views", f"{general_avg_views:,.0f}")
                    st.metric("📺 General Content Engagement", f"{general_avg_engagement:.2f}%")
                
                # Performance comparison
                if mih_avg_views > general_avg_views:
                    st.success("🎯 MIH-focused content is performing better!")
                else:
                    st.warning("⚠️ Consider optimizing MIH content strategy")
    
    def render_export_options(self, analytics_api, days):
        """Render data export options"""
        st.markdown("## 📥 Export Data")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📊 Export Channel Data", type="secondary"):
                # Collect all channel data
                export_data = []
                for channel_key in analytics_api.youtube_services.keys():
                    config = analytics_api.youtube_services[channel_key]['config']
                    channel_name = config.get('name', f'Channel {channel_key}')
                    
                    channel_metrics = analytics_api.get_channel_metrics(channel_key, days)
                    if channel_metrics:
                        export_data.append({
                            'Channel Name': channel_name,
                            'Subscribers': channel_metrics.subscribers,
                            'Total Views': channel_metrics.total_views,
                            'Total Videos': channel_metrics.total_videos,
                            'Avg Views per Video': channel_metrics.avg_views_per_video,
                            'Growth Rate %': channel_metrics.growth_rate,
                            'Watch Time Hours': channel_metrics.total_watch_time / 60
                        })
                
                if export_data:
                    df_export = pd.DataFrame(export_data)
                    csv = df_export.to_csv(index=False)
                    st.download_button(
                        "📥 Download Channel Data CSV",
                        csv,
                        f"mih_channel_analytics_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv"
                    )
        
        with col2:
            if st.button("🎬 Export Video Data", type="secondary"):
                # Collect all video data
                export_videos = []
                for channel_key in analytics_api.youtube_services.keys():
                    config = analytics_api.youtube_services[channel_key]['config']
                    channel_name = config.get('name', f'Channel {channel_key}')
                    
                    video_metrics = analytics_api.get_video_metrics(channel_key, days, limit=50)
                    for video in video_metrics:
                        export_videos.append({
                            'Channel': channel_name,
                            'Video ID': video.video_id,
                            'Title': video.title,
                            'Published Date': video.published_at[:10],
                            'Views': video.views,
                            'Likes': video.likes,
                            'Comments': video.comments,
                            'Shares': video.shares,
                            'Subscribers Gained': video.subscribers_gained,
                            'Watch Time Minutes': video.watch_time_minutes,
                            'Avg View Duration': video.average_view_duration,
                            'Engagement Rate %': ((video.likes + video.comments) / max(video.views, 1)) * 100,
                            'URL': f"https://youtube.com/watch?v={video.video_id}"
                        })
                
                if export_videos:
                    df_export_videos = pd.DataFrame(export_videos)
                    csv_videos = df_export_videos.to_csv(index=False)
                    st.download_button(
                        "📥 Download Video Data CSV",
                        csv_videos,
                        f"mih_video_analytics_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv"
                    )
        
        with col3:
            if st.button("📈 Generate Report", type="secondary"):
                # Generate comprehensive report
                report_data = self._generate_comprehensive_report(analytics_api, days)
                
                st.download_button(
                    "📥 Download Full Report",
                    report_data,
                    f"mih_analytics_report_{datetime.now().strftime('%Y%m%d')}.txt",
                    "text/plain"
                )
    
    def _generate_comprehensive_report(self, analytics_api, days):
        """Generate a comprehensive text report"""
        report_lines = [
            "=" * 80,
            "DR. LINDA GREENWALL MIH SHORTS ANALYTICS REPORT",
            "=" * 80,
            f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Analysis Period: Last {days} days",
            "",
            "EXECUTIVE SUMMARY",
            "-" * 40
        ]
        
        # Get overview data
        comparison_data = analytics_api.get_performance_comparison(days)
        
        report_lines.extend([
            f"Total Channels Analyzed: {len(comparison_data['channels'])}",
            f"Total YouTube Shorts: {comparison_data['total_videos']:,}",
            f"Total Views: {comparison_data['total_views']:,}",
            f"Total Subscribers: {comparison_data['total_subscribers']:,}",
            f"Total Watch Time: {comparison_data['total_watch_time'] / 60:,.1f} hours",
            "",
            "CHANNEL PERFORMANCE BREAKDOWN",
            "-" * 40
        ])
        
        # Add channel details
        for channel_key in analytics_api.youtube_services.keys():
            config = analytics_api.youtube_services[channel_key]['config']
            channel_name = config.get('name', f'Channel {channel_key}')
            
            channel_metrics = analytics_api.get_channel_metrics(channel_key, days)
            if channel_metrics:
                report_lines.extend([
                    f"\n📺 {channel_name.upper()}",
                    f"   Subscribers: {channel_metrics.subscribers:,}",
                    f"   Total Views: {channel_metrics.total_views:,}",
                    f"   Videos: {channel_metrics.total_videos:,}",
                    f"   Avg Views/Video: {channel_metrics.avg_views_per_video:,.0f}",
                    f"   Growth Rate: {channel_metrics.growth_rate:.2f}%"
                ])
                
                # Top 3 videos for this channel
                video_metrics = analytics_api.get_video_metrics(channel_key, days, limit=3)
                if video_metrics:
                    report_lines.append("   Top 3 Videos:")
                    for i, video in enumerate(video_metrics, 1):
                        report_lines.append(f"   {i}. {video.title} ({video.views:,} views)")
        
        report_lines.extend([
            "",
            "RECOMMENDATIONS",
            "-" * 40,
            "• Focus on high-performing content patterns",
            "• Optimize titles for MIH-related keywords",
            "• Maintain consistent upload schedule",
            "• Engage with audience through comments",
            "• Monitor trending topics in pediatric dentistry",
            "",
            "=" * 80,
            "End of Report"
        ])
        
        return "\n".join(report_lines)
    
    def run(self):
        """Main dashboard runner"""
        # Load configuration
        system_config = self.load_config()
        
        # Initialize API
        analytics_api = self.initialize_api(system_config)
        
        # Check if any channels are authenticated
        if not analytics_api.youtube_services:
            st.error("❌ No channels authenticated! Please check your credentials files.")
            st.markdown("""
            ### 🔧 Setup Instructions:
            1. Ensure your `config.py` file contains valid YouTube API key
            2. Make sure credential JSON files exist for each channel
            3. Run the authentication process for each channel
            """)
            st.stop()
        
        # Render header
        self.render_header()
        
        # Render sidebar
        days = self.render_sidebar()
        
        # Main content area
        try:
            # Overview metrics
            self.render_overview_metrics(analytics_api, days)
            
            st.markdown("---")
            
            # Channel performance
            self.render_channel_performance(analytics_api, days)
            
            st.markdown("---")
            
            # Comparative analysis
            self.render_comparative_analysis(analytics_api, days)
            
            st.markdown("---")
            
            # Insights and recommendations
            self.render_insights_recommendations(analytics_api, days)
            
            st.markdown("---")
            
            # Export options
            self.render_export_options(analytics_api, days)
            
        except Exception as e:
            st.error(f"❌ Error loading analytics data: {e}")
            st.markdown("### 🔧 Troubleshooting:")
            st.markdown("- Check your internet connection")
            st.markdown("- Verify API quotas haven't been exceeded")
            st.markdown("- Ensure all channels have proper permissions")
        
        # Footer
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; color: #666; padding: 1rem;">
            <p>🦷 Dr. Linda Greenwall MIH Analytics Dashboard</p>
            <p>Helping spread MIH awareness through data-driven insights</p>
        </div>
        """, unsafe_allow_html=True)

# Cache functions for better performance
@st.cache_data(ttl=1800)  # Cache for 30 minutes
def get_cached_channel_metrics(api_key, channel_configs, channel_key, days):
    """Cached version of channel metrics retrieval"""
    analytics_api = YouTubeAnalyticsAPI(api_key, channel_configs)
    return analytics_api.get_channel_metrics(channel_key, days)

@st.cache_data(ttl=1800)  # Cache for 30 minutes  
def get_cached_video_metrics(api_key, channel_configs, channel_key, days, limit):
    """Cached version of video metrics retrieval"""
    analytics_api = YouTubeAnalyticsAPI(api_key, channel_configs)
    return analytics_api.get_video_metrics(channel_key, days, limit)

# Main execution
if __name__ == "__main__":
    dashboard = AnalyticsDashboard()
    dashboard.run()