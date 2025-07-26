# config.py - Configuration for MIH Content Automation

# YouTube Data API v3 Key (from Google Cloud Console)
YOUTUBE_API_KEY = "AIzaSyDvnNE4cp5kJuFn1xMxBB4APamd7saFofQ"

# Gemini AI API Key (from Google AI Studio)
GEMINI_API_KEY = "AIzaSyBqjvo54BMoRUTR-8PZJOMzgMfKx1kyXH0"

# YouTube OAuth Credentials File (downloaded from Google Cloud Console)
YOUTUBE_CREDENTIALS_FILE = "youtube_credentials.json"

# Output Directory for processed videos
OUTPUT_DIR = "processed_videos"

# YouTube Channels for Upload (replace with your actual channel IDs)
UPLOAD_CHANNELS = [
    {"name": "Shubham Kumar", "id": "UCvOZdrm6eoIuOx4R3Uikt3g"},
]

# Search Queries for finding Dr. Greenwall videos
SEARCH_QUERIES = [
    "Linda Greenwall MIH",
    "Dr Greenwall molar incisor hypomineralisation",
    "Linda Greenwall enamel defects",
    "Dr Greenwall pediatric whitening", 
    "Linda Greenwall ICON treatment",
    "Jaz Gulati Linda Greenwall",
    "Dentistry Magazine Linda Greenwall"
]

# Processing Settings
MIN_CLIP_DURATION = 15  # seconds
MAX_CLIP_DURATION = 60  # seconds
MAX_CLIPS_PER_VIDEO = 12
AUTOMATION_INTERVAL_HOURS = 1

# Video Quality Settings
TARGET_RESOLUTION = (720, 1280)  # 9:16 aspect ratio
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"

# MIH Keywords for content detection
MIH_KEYWORDS = [
    'mih', 'molar incisor hypomineralisation', 'hypomineralization',
    'enamel defect', 'white spots', 'brown spots', 'enamel hypoplasia',
    'demineralization', 'remineralization', 'icon', 'whitening',
    'sensitive teeth', 'enamel care', 'pediatric whitening',
    'fluorosis', 'enamel development', 'childhood enamel problems'
]

# Security Note: For production, consider using environment variables:
# import os
# YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', YOUTUBE_API_KEY)
# GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', GEMINI_API_KEY)