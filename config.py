# config.py - Configuration for MIH Content Automation System
# Enhanced Multi-Channel Configuration with Comprehensive Settings

import os
from typing import List, Dict

# =============================================================================
# API CONFIGURATION
# =============================================================================

# YouTube Data API v3 Key (from Google Cloud Console)
# Get from: https://console.cloud.google.com/ → APIs & Services → Credentials
YOUTUBE_API_KEY = "AIzaSyDxMjS6e_vh-Abb-tWnQUbak-LfKVdZeAM"

# Gemini AI API Key (from Google AI Studio)
# Get from: https://aistudio.google.com/
GEMINI_API_KEY = "AIzaSyBqjvo54BMoRUTR-8PZJOMzgMfKx1kyXH0"
OUTPUT_DIR = "analytics_exports"


# =============================================================================
# MULTI-CHANNEL CONFIGURATION
# =============================================================================

# YouTube Channels Configuration for Upload
# Each channel requires its own OAuth credentials file
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
        "id": "UCt56aIAG8gNuKM0hJpWYm9Q",  # Replace with actual Channel ID
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
        "id": "UCnBJEdDIsC7b3oAvaBPje3Q",  # Replace with actual Channel ID
        "credentials_file": "youtube_credentials.json",
        "description": "Comprehensive pediatric dental care and whitening",
        "privacy_status": "public",
        "category_id": "27",
        "default_language": "en",
        "tags_prefix": ["#PediatricDentistry", "#ChildrenTeeth"],
        "content_focus": "pediatric_care"
    }
]

# =============================================================================
# SEARCH AND CONTENT DISCOVERY
# =============================================================================
# Analytics Settings
ANALYTICS_SETTINGS = {
    "default_time_period_days": 30,
    "max_videos_per_analysis": 50,
    "cache_duration_minutes": 30,
    "auto_refresh_interval_seconds": 30,
    "export_formats": ["csv", "json", "txt"]
}

# Dashboard Customization
DASHBOARD_CONFIG = {
    "brand_colors": {
        "primary": "#2E8B57",
        "secondary": "#4ECDC4", 
        "accent": "#FF6B6B",
        "background": "#f0f2f6"
    },
    "expert_info": {
        "name": "Dr. Linda Greenwall",
        "title": "Global MIH Expert",
        "specialization": "Molar Incisor Hypomineralisation & Pediatric Whitening"
    }
}

# MIH-Specific Keywords for Content Analysis
MIH_KEYWORDS = [
    "MIH", "molar incisor hypomineralisation", "chalky teeth", 
    "white spots", "enamel defects", "ICON treatment",
    "pediatric whitening", "children dental problems",
    "tooth discoloration", "enamel hypoplasia",
    "childhood dental issues", "kids teeth problems"
]

# Performance Thresholds
PERFORMANCE_THRESHOLDS = {
    "high_performing_views": 10000,
    "good_engagement_rate": 5.0,  # percentage
    "excellent_engagement_rate": 10.0,  # percentage
    "viral_threshold_views": 100000,
    "target_subscriber_growth": 2.0  # percentage per month
}

# Notification Settings (for future implementation)
NOTIFICATION_CONFIG = {
    "email_alerts": False,
    "slack_webhook": None,
    "performance_alerts": {
        "viral_video_threshold": 50000,
        "low_performance_alert": True,
        "daily_summary": False
    }
}

# Search Queries for finding Dr. Greenwall videos
SEARCH_QUERIES = [
    # Primary MIH-focused queries
    "Linda Greenwall MIH",
    # "Dr Greenwall molar incisor hypomineralisation", 
    # "Linda Greenwall enamel defects",
    # "Dr Linda Greenwall MIH treatment",
    
    # # Treatment-specific queries
    # "Linda Greenwall ICON treatment",
    # "Dr Greenwall pediatric whitening",
    # "Linda Greenwall enamel care children",
    # "Dr Greenwall teeth whitening kids",
    
    # # Collaborative content
    # "Jaz Gulati Linda Greenwall",
    # "Dentistry Magazine Linda Greenwall",
    # "Protrusive Dental Linda Greenwall",
    
    # # Specialized topics
    # "Linda Greenwall fluorosis children",
    # "Dr Greenwall enamel hypoplasia",
    # "Linda Greenwall demineralization",
    # "Dr Linda Greenwall whitening safety",
    
    # # Conference and educational content
    # "Linda Greenwall dental conference",
    # "Dr Greenwall MIH lecture",
    # "Linda Greenwall enamel development",
    # "Dr Greenwall pediatric cosmetic dentistry"
]

# Channels to prioritize in search results
PRIORITY_CHANNELS = [
    "Protrusive Dental Podcast",
    "The Dental Guide", 
    "Dentistry Magazine",
    "British Dental Association",
    "Academy of Cosmetic Dentistry"
]

# =============================================================================
# PROCESSING SETTINGS
# =============================================================================

# Clip Duration Settings
MIN_CLIP_DURATION = 15          # Minimum clip length in seconds
MAX_CLIP_DURATION = 90          # Maximum clip length in seconds
OPTIMAL_CLIP_DURATION = 45      # Target clip length for best engagement

# Video Processing Limits
MAX_CLIPS_PER_VIDEO = 12        # Maximum clips to extract per source video
MAX_VIDEOS_PER_CYCLE = 10        # Maximum videos to process per automation cycle
MIN_RELEVANCE_SCORE = 0.1       # Minimum MIH relevance score (0.0 to 1.0)

# Quality and Performance Settings
PROCESSING_TIMEOUT = 600        # Maximum time to process one video (seconds)
MAX_RETRIES_PER_VIDEO = 3       # Retry attempts for failed video processing
MAX_RETRIES_PER_UPLOAD = 2      # Retry attempts for failed uploads

# =============================================================================
# TIMING AND RATE LIMITING
# =============================================================================

# Core Timing Settings (all in seconds)
DELAY_BETWEEN_CHANNELS = 10     # Wait time between uploading to different channels
DELAY_BETWEEN_CLIPS = 30        # Wait time between publishing different clips
DELAY_BETWEEN_VIDEOS = 60     # Wait time between processing different videos
DELAY_AFTER_SEARCH = 2          # Wait time after each search query

# Automation Intervals
AUTOMATION_INTERVAL_HOURS = 1   # Hours between automation cycles
CONTINUOUS_MODE_INTERVAL = 3600 # Seconds between cycles in continuous mode

# API Rate Limiting
YOUTUBE_API_CALLS_PER_MINUTE = 10    # Limit YouTube API calls
GEMINI_API_CALLS_PER_MINUTE = 20     # Limit Gemini API calls
MAX_CONCURRENT_UPLOADS = 1           # Maximum simultaneous uploads

# =============================================================================
# VIDEO QUALITY AND ENCODING
# =============================================================================

# Video Resolution and Format
TARGET_RESOLUTION = (720, 1280)     # 9:16 aspect ratio for mobile/vertical
FALLBACK_RESOLUTION = (480, 854)    # Fallback resolution if primary fails
VIDEO_CODEC = "libx264"             # H.264 encoding for compatibility
AUDIO_CODEC = "aac"                 # AAC audio encoding
VIDEO_BITRATE = "1000k"             # Video bitrate
AUDIO_BITRATE = "128k"              # Audio bitrate

# Video Download Settings
DOWNLOAD_FORMAT = "best[height<=720]/best"  # yt-dlp format selector
DOWNLOAD_TIMEOUT = 300              # Download timeout in seconds
EXTRACT_TIMEOUT = 120               # Clip extraction timeout in seconds

# =============================================================================
# CONTENT DETECTION AND AI SETTINGS
# =============================================================================

# MIH Keywords for content detection and relevance scoring
MIH_KEYWORDS = [
    # Core MIH terms
    'mih', 'molar incisor hypomineralisation', 'molar incisor hypomineralization',
    'hypomineralisation', 'hypomineralization',
    
    # Enamel defects and conditions
    'enamel defect', 'enamel defects', 'white spots', 'brown spots', 
    'enamel hypoplasia', 'enamel opacity', 'enamel discoloration',
    'chalky teeth', 'crumbly enamel', 'weak enamel',
    
    # Treatment and care terms
    'demineralization', 'remineralization', 'icon treatment', 'icon resin',
    'microabrasion', 'enamel infiltration', 'resin infiltration',
    
    # Whitening and cosmetic terms
    'whitening', 'bleaching', 'tooth whitening', 'pediatric whitening',
    'children whitening', 'safe whitening', 'whitening children',
    'cosmetic dentistry children', 'aesthetic dentistry pediatric',
    
    # Clinical and diagnostic terms
    'sensitive teeth', 'tooth sensitivity', 'enamel care', 'enamel protection',
    'fluorosis', 'dental fluorosis', 'enamel development', 'amelogenesis',
    'childhood enamel problems', 'developmental enamel defects',
    
    # Pediatric dentistry terms
    'pediatric dentistry', 'paediatric dentistry', 'children dentistry',
    'kids dental care', 'child dental health', 'young patient care',
    
    # Professional terms
    'enamel formation', 'tooth development', 'mineralization defects',
    'post-eruptive breakdown', 'atypical restorations'
]

# Content Classification Keywords
TREATMENT_KEYWORDS = ['icon', 'treatment', 'therapy', 'restoration', 'filling']
PREVENTION_KEYWORDS = ['prevention', 'care', 'protection', 'maintenance', 'hygiene']
DIAGNOSIS_KEYWORDS = ['diagnosis', 'identification', 'assessment', 'examination', 'signs']

# AI Content Generation Settings
GEMINI_MODEL = "gemini-2.0-flash-001"
AI_CONTENT_TEMPERATURE = 0.7        # Creativity level (0.0 to 1.0)
AI_MAX_TOKENS = 1000                # Maximum tokens per AI response
AI_TIMEOUT = 30                     # AI request timeout in seconds

# =============================================================================
# CONTENT TEMPLATES AND FORMATTING
# =============================================================================

# Title Templates (topic will be replaced dynamically)
TITLE_TEMPLATES = [
    "Dr Greenwall: {topic} - MIH Expert Advice",
    "MIH Treatment: {topic} with Dr Linda Greenwall",
    "Expert Guide: {topic} for Children's Enamel Care",
    "Pediatric Dentistry: {topic} - Dr Greenwall Explains",
    "Enamel Care: {topic} - Professional Tips from Dr Greenwall",
    "Dr Linda Greenwall on {topic} - MIH Education",
    "Children's Teeth: {topic} - Expert Guidance",
    "MIH Solutions: {topic} with Dr Greenwall"
]

# Description Templates
DESCRIPTION_TEMPLATES = [
    "Expert advice from Dr Linda Greenwall on {topic}. Essential guidance for parents dealing with Molar Incisor Hypomineralisation (MIH) in children. Learn evidence-based approaches to enamel care and treatment.",
    
    "Dr Linda Greenwall explains {topic} with practical tips for managing enamel defects and MIH in children. Professional pediatric dental guidance you can trust.",
    
    "Discover {topic} insights from leading MIH expert Dr Linda Greenwall. Comprehensive guidance for parents, dental professionals, and anyone interested in children's dental health.",
    
    "Learn about {topic} from renowned pediatric cosmetic dentist Dr Linda Greenwall. Expert advice on MIH management, enamel care, and safe treatment options for children."
]

# Required Hashtags (always included)
REQUIRED_HASHTAGS = [
    "#MIH", 
    "#EnamelCare", 
    "#PediatricDentistry", 
    "#DrGreenwall",
    "#TeethWhitening",
    "#EnamelDefects",
    "#ChildrenDentistry"
]

# Additional Hashtag Pool (selected based on content)
HASHTAG_POOL = [
    "#MolarIncisorsHypomineralisation",
    "#IconTreatment", 
    "#DentalHealth",
    "#KidsTeeth",
    "#EnamelHypoplasia",
    "#ToothWhitening",
    "#DentalCare",
    "#OralHealth",
    "#PediatricCosmetics",
    "#EnamelProtection",
    "#DentistryEducation",
    "#ParentGuidance",
    "#DentalTips",
    "#HealthyTeeth",
    "#DentalAdvice"
]

# =============================================================================
# FILE MANAGEMENT AND STORAGE
# =============================================================================

# Directory Configuration
OUTPUT_DIR = "processed_videos"         # Main output directory
TEMP_DIR = "temp"                      # Temporary files directory
LOGS_DIR = "logs"                      # CSV logs directory
BACKUP_DIR = "backups"                 # Backup directory

# File Management Settings
AUTO_CLEANUP_TEMP_FILES = True         # Automatically clean temporary files
KEEP_ORIGINAL_VIDEOS = False           # Keep downloaded source videos
KEEP_EXTRACTED_CLIPS = False           # Keep clip files after upload
MAX_TEMP_STORAGE_GB = 10              # Maximum temporary storage in GB
CLEANUP_OLDER_THAN_DAYS = 7           # Clean files older than N days

# CSV Logging Configuration
CSV_OUTPUT_DIR = "logs"
ENABLE_DETAILED_LOGGING = True
LOG_TRANSCRIPT_PREVIEW_LENGTH = 500    # Characters to preview in CSV
CSV_ENCODING = "utf-8"
CSV_BACKUP_ENABLED = True

# =============================================================================
# MONITORING AND ALERTS
# =============================================================================

# Success Rate Monitoring
ENABLE_SUCCESS_MONITORING = True
ALERT_ON_LOW_SUCCESS_RATE = True
SUCCESS_RATE_THRESHOLD = 70           # Minimum acceptable success rate (%)
MONITOR_WINDOW_HOURS = 24             # Hours to analyze for success rate

# Performance Thresholds
MAX_PROCESSING_TIME_MINUTES = 10      # Alert if video takes longer to process
MIN_CLIPS_PER_SUCCESSFUL_VIDEO = 1    # Minimum clips expected per video
MAX_CONSECUTIVE_FAILURES = 5          # Alert after N consecutive failures

# Health Check Settings
HEALTH_CHECK_INTERVAL_MINUTES = 30    # How often to perform health checks
LOG_ROTATION_DAYS = 30                # Days to keep log files

# =============================================================================
# DEVELOPMENT AND DEBUG SETTINGS
# =============================================================================

# Debug and Testing
DEBUG_MODE = False                    # Enable debug logging
TEST_MODE = False                     # Use test channels instead of production
DRY_RUN = False                      # Process but don't actually upload
VERBOSE_LOGGING = True               # Enable detailed console output

# Development Overrides
DEV_MAX_VIDEOS_PER_CYCLE = 1         # Limit videos in development
DEV_UPLOAD_DELAY = 10                # Reduced delays for testing
DEV_SKIP_DOWNLOAD = False            # Skip video download for testing

# Fallback and Backup Settings
ENABLE_BACKUP_METHODS = True         # Enable fallback transcript methods
BACKUP_TRANSCRIPT_METHOD = "manual_keywords"  # Fallback method
BACKUP_CONTENT_GENERATION = True     # Use templates if AI fails
ENABLE_MANUAL_INTERVENTION = False   # Pause for manual review

# =============================================================================
# SECURITY AND PRIVACY
# =============================================================================

# API Security
ROTATE_API_KEYS_DAYS = 90            # Remind to rotate API keys
MASK_KEYS_IN_LOGS = True             # Hide API keys in log output
SECURE_CREDENTIAL_STORAGE = True     # Use secure credential storage

# Content Privacy
RESPECT_AGE_RESTRICTIONS = True      # Skip age-restricted content
AVOID_PRIVATE_CONTENT = True         # Skip private/unlisted videos
CONTENT_FILTER_ENABLED = True       # Filter inappropriate content

# =============================================================================
# CHANNEL-SPECIFIC CUSTOMIZATION
# =============================================================================

# Channel-specific settings for fine-tuning
CHANNEL_SPECIFIC_SETTINGS = {
    "channel_1": {
        "focus_keywords": ["education", "basics", "understanding"],
        "title_style": "educational",
        "description_length": "medium",
        "hashtag_strategy": "broad_appeal",
        "content_preference": "explanatory"
    },
    "channel_2": {
        "focus_keywords": ["treatment", "solution", "therapy"],
        "title_style": "solution_focused", 
        "description_length": "detailed",
        "hashtag_strategy": "treatment_focused",
        "content_preference": "clinical"
    },
    "channel_3": {
        "focus_keywords": ["children", "kids", "parents", "care"],
        "title_style": "parent_friendly",
        "description_length": "accessible",
        "hashtag_strategy": "family_oriented",
        "content_preference": "approachable"
    }
}

# =============================================================================
# ADVANCED CONFIGURATION
# =============================================================================

# AI Prompt Customization
CUSTOM_AI_PROMPTS = {
    "clip_analysis": """
    Analyze this transcript for Molar Incisor Hypomineralisation (MIH) content.
    Focus on: treatment options, parent guidance, clinical insights, and practical advice.
    Prioritize content that helps parents understand and manage MIH in children.
    """,
    
    "content_generation": """
    Create engaging, educational content for parents of children with MIH.
    Tone: Professional but accessible, empathetic, reassuring.
    Focus: Practical guidance, expert authority, trustworthy information.
    """
}

# Content Quality Filters
QUALITY_FILTERS = {
    "min_video_length_seconds": 60,      # Skip very short videos
    "max_video_length_seconds": 3600,    # Skip very long videos  
    "require_good_audio": True,          # Skip videos with poor audio
    "skip_live_streams": True,           # Skip live stream content
    "min_view_count": 100,               # Minimum views for consideration
}

# Experimental Features
EXPERIMENTAL_FEATURES = {
    "enhanced_transcript_analysis": False,  # Advanced AI transcript analysis
    "automatic_thumbnail_generation": False, # AI-generated thumbnails
    "sentiment_analysis": False,            # Content sentiment scoring
    "multi_language_support": False,       # Support for other languages
}

# =============================================================================
# CONFIGURATION VALIDATION
# =============================================================================

def validate_config() -> tuple[bool, list[str]]:
    """
    Validate configuration settings and return status with any errors
    Returns: (is_valid, list_of_errors)
    """
    errors = []
    
    # Validate API keys
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "YOUR_API_KEY_HERE":
        errors.append("YouTube API key not configured")
    
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_API_KEY_HERE":
        errors.append("Gemini API key not configured")
    
    # Validate channels
    if len(UPLOAD_CHANNELS) == 0:
        errors.append("No upload channels configured")
    
    # Validate each channel
    for i, channel in enumerate(UPLOAD_CHANNELS):
        channel_num = i + 1
        
        if not channel.get('name'):
            errors.append(f"Channel {channel_num} missing name")
        
        if not channel.get('id') or 'REPLACE' in channel.get('id', ''):
            errors.append(f"Channel {channel_num} missing or invalid ID")
        
        if not channel.get('credentials_file'):
            errors.append(f"Channel {channel_num} missing credentials file")
        elif not os.path.exists(channel['credentials_file']):
            errors.append(f"Channel {channel_num} credentials file not found: {channel['credentials_file']}")
    
    # Validate timing settings
    if DELAY_BETWEEN_CHANNELS < 10:
        errors.append("DELAY_BETWEEN_CHANNELS should be at least 10 seconds")
    
    if DELAY_BETWEEN_CLIPS < 15:
        errors.append("DELAY_BETWEEN_CLIPS should be at least 15 seconds")
    
    # Validate clip duration settings
    if MIN_CLIP_DURATION >= MAX_CLIP_DURATION:
        errors.append("MIN_CLIP_DURATION must be less than MAX_CLIP_DURATION")
    
    if MIN_CLIP_DURATION < 10:
        errors.append("MIN_CLIP_DURATION should be at least 10 seconds")
    
    if MAX_CLIP_DURATION > 120:
        errors.append("MAX_CLIP_DURATION should not exceed 120 seconds")
    
    # Validate directories
    required_dirs = [OUTPUT_DIR, LOGS_DIR]
    for directory in required_dirs:
        if not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create directory {directory}: {e}")
    
    return len(errors) == 0, errors

def print_config_summary():
    """Print a summary of current configuration"""
    print("=" * 80)
    print("  MIH AUTOMATION CONFIGURATION SUMMARY")
    print("=" * 80)
    print(f"Configured Channels: {len(UPLOAD_CHANNELS)}")
    for i, channel in enumerate(UPLOAD_CHANNELS, 1):
        print(f"  Channel {i}: {channel['name']}")
    
    print(f"\nTiming Configuration:")
    print(f"  Between channels: {DELAY_BETWEEN_CHANNELS}s")
    print(f"  Between clips: {DELAY_BETWEEN_CLIPS}s") 
    print(f"  Between videos: {DELAY_BETWEEN_VIDEOS}s")
    
    print(f"\nProcessing Limits:")
    print(f"  Clip duration: {MIN_CLIP_DURATION}-{MAX_CLIP_DURATION}s")
    print(f"  Max clips per video: {MAX_CLIPS_PER_VIDEO}")
    print(f"  Max videos per cycle: {MAX_VIDEOS_PER_CYCLE}")
    
    print(f"\nSearch Queries: {len(SEARCH_QUERIES)} configured")
    print(f"MIH Keywords: {len(MIH_KEYWORDS)} configured")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"Logs Directory: {LOGS_DIR}")

# =============================================================================
# ENVIRONMENT VARIABLE OVERRIDES
# =============================================================================

# Allow environment variables to override sensitive settings
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', YOUTUBE_API_KEY)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', GEMINI_API_KEY)

# Environment flags
if os.getenv('MIH_DEBUG_MODE', '').lower() == 'true':
    DEBUG_MODE = True
    VERBOSE_LOGGING = True

if os.getenv('MIH_TEST_MODE', '').lower() == 'true':
    TEST_MODE = True
    MAX_VIDEOS_PER_CYCLE = 1

if os.getenv('MIH_DRY_RUN', '').lower() == 'true':
    DRY_RUN = True

# =============================================================================
# CONFIGURATION HELP AND DOCUMENTATION
# =============================================================================

CONFIG_HELP = """
MIH AUTOMATION CONFIGURATION GUIDE

REQUIRED SETUP:
1. Set YOUTUBE_API_KEY and GEMINI_API_KEY
2. Update channel IDs in UPLOAD_CHANNELS (replace UC_REPLACE_WITH_CHANNEL_*_ID)
3. Place OAuth credential files for each channel
4. Run: python setup_wizard.py for guided setup

TIMING RECOMMENDATIONS:
- DELAY_BETWEEN_CHANNELS: 30s (avoid rate limits)
- DELAY_BETWEEN_CLIPS: 45s (reasonable publishing pace)  
- DELAY_BETWEEN_VIDEOS: 120s (prevent overloading)

PERFORMANCE TUNING:
- Increase MAX_CLIPS_PER_VIDEO for more content per video
- Adjust MIN_RELEVANCE_SCORE to filter content quality
- Modify TARGET_RESOLUTION for different video quality

TROUBLESHOOTING:
- Enable DEBUG_MODE for detailed logging
- Use TEST_MODE to limit processing during setup
- Set DRY_RUN=True to test without uploading

For detailed setup instructions, see README.md
"""

# Automatically validate configuration on import
if __name__ == "__main__":
    print_config_summary()
    print("\nValidating configuration...")
    is_valid, errors = validate_config()
    
    if is_valid:
        print("✅ Configuration is valid!")
    else:
        print("❌ Configuration errors found:")
        for error in errors:
            print(f"  - {error}")
        print("\nPlease fix these errors before running the automation.")
        print("\nFor help, run: python setup_wizard.py")
else:
    # Silent validation when imported
    is_valid, errors = validate_config()
    if not is_valid and not os.getenv('MIH_SKIP_VALIDATION'):
        print("⚠️  Configuration issues detected. Run config.py directly for details.")