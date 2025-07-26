#!/usr/bin/env python3
"""
Setup Wizard for MIH Content Automation System
Helps configure three YouTube channels with proper authentication
"""

import os
import json
import sys
import subprocess
from pathlib import Path
from typing import Dict, List

def print_header():
    """Print setup wizard header"""
    print("=" * 80)
    print("  MIH CONTENT AUTOMATION - SETUP WIZARD")
    print("  Three Channel Configuration")
    print("=" * 80)
    print()

def check_dependencies():
    """Check if required tools are installed"""
    print("🔍 Checking dependencies...")
    
    required_tools = {
        'yt-dlp': 'pip install yt-dlp',
        # 'ffmpeg': 'Download from https://ffmpeg.org/ and add to PATH'
    }
    
    missing = []
    for tool, install_cmd in required_tools.items():
        try:
            result = subprocess.run([tool, '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"  ✅ {tool} - Found")
            else:
                missing.append((tool, install_cmd))
        except:
            missing.append((tool, install_cmd))
    
    if missing:
        print("\n❌ Missing dependencies:")
        for tool, install_cmd in missing:
            print(f"  - {tool}: {install_cmd}")
        print("\nPlease install missing dependencies and run setup again.")
        return False
    
    print("✅ All dependencies found!")
    return True

def get_api_keys():
    """Get API keys from user"""
    print("\n📋 API CONFIGURATION")
    print("-" * 50)
    
    print("\n1. YouTube Data API v3 Key:")
    print("   - Go to: https://console.cloud.google.com/")
    print("   - Create/select project → Enable YouTube Data API v3")
    print("   - Create credentials (API Key)")
    
    youtube_key = input("\nEnter YouTube API Key: ").strip()
    while not youtube_key:
        print("❌ YouTube API key is required!")
        youtube_key = input("Enter YouTube API Key: ").strip()
    
    print("\n2. Gemini AI API Key:")
    print("   - Go to: https://aistudio.google.com/")
    print("   - Get API key")
    
    gemini_key = input("\nEnter Gemini API Key: ").strip()
    while not gemini_key:
        print("❌ Gemini API key is required!")
        gemini_key = input("Enter Gemini API Key: ").strip()
    
    return youtube_key, gemini_key

def get_channel_info():
    """Get information for three YouTube channels"""
    print("\n📺 CHANNEL CONFIGURATION")
    print("-" * 50)
    print("You need to configure 3 YouTube channels for upload.")
    print("Each channel needs its own OAuth credentials file.")
    
    channels = []
    
    for i in range(3):
        print(f"\n--- CHANNEL {i+1} ---")
        
        name = input(f"Channel {i+1} Name: ").strip()
        while not name:
            name = input(f"Channel {i+1} Name (required): ").strip()
        
        print("\nTo find your Channel ID:")
        print("  1. Go to YouTube Studio")
        print("  2. Settings → Channel → Advanced settings")
        print("  3. Copy the Channel ID (starts with UC...)")
        
        channel_id = input(f"Channel {i+1} ID (UC...): ").strip()
        while not channel_id or not channel_id.startswith('UC'):
            print("❌ Please enter a valid Channel ID (starts with UC...)")
            channel_id = input(f"Channel {i+1} ID (UC...): ").strip()
        
        description = input(f"Channel {i+1} Description (optional): ").strip() or f"MIH content channel {i+1}"
        
        credentials_file = f"youtube_credentials_channel{i+1}.json"
        
        channels.append({
            "name": name,
            "id": channel_id, 
            "credentials_file": credentials_file,
            "description": description
        })
        
        print(f"✅ Channel {i+1} configured: {name}")
    
    return channels

def setup_oauth_credentials():
    """Guide user through OAuth setup"""
    print("\n🔐 OAUTH CREDENTIALS SETUP")
    print("-" * 50)
    print("For each channel, you need to download OAuth credentials:")
    print()
    print("1. Go to Google Cloud Console → APIs & Services → Credentials")
    print("2. Create OAuth 2.0 Client ID (Desktop Application)")
    print("3. Download the JSON file")
    print("4. Rename and place in project folder as instructed")
    print()
    
    for i in range(3):
        credentials_file = f"youtube_credentials_channel{i+1}.json"
        print(f"\nChannel {i+1}: Save OAuth JSON as '{credentials_file}'")
        
        while True:
            response = input(f"Have you placed {credentials_file}? (y/n): ").lower()
            if response == 'y':
                if os.path.exists(credentials_file):
                    print(f"✅ Found {credentials_file}")
                    break
                else:
                    print(f"❌ File {credentials_file} not found in current directory")
            elif response == 'n':
                print(f"Please download and place {credentials_file} before continuing")
            else:
                print("Please enter 'y' or 'n'")

def create_config_file(youtube_key: str, gemini_key: str, channels: List[Dict]):
    """Create the config.py file"""
    print("\n📄 CREATING CONFIG FILE")
    print("-" * 50)
    
    config_content = f'''# config.py - Configuration for MIH Content Automation System
# Generated by Setup Wizard

# API Keys
YOUTUBE_API_KEY = "{youtube_key}"
GEMINI_API_KEY = "{gemini_key}"

# Output Directory
OUTPUT_DIR = "processed_videos"

# YouTube Channels Configuration
UPLOAD_CHANNELS = ['''
    
    for i, channel in enumerate(channels):
        config_content += f'''
    {{
        "name": "{channel['name']}",
        "id": "{channel['id']}",
        "credentials_file": "{channel['credentials_file']}",
        "description": "{channel['description']}"
    }}{"," if i < len(channels)-1 else ""}'''
    
    config_content += '''
]

# Search Queries for finding Dr. Greenwall videos
SEARCH_QUERIES = [
    "Linda Greenwall MIH",
    "Dr Greenwall molar incisor hypomineralisation",
    "Linda Greenwall enamel defects",
    "Dr Greenwall pediatric whitening",
    "Linda Greenwall ICON treatment",
    "Jaz Gulati Linda Greenwall",
    "Dentistry Magazine Linda Greenwall",
    "Linda Greenwall teeth whitening children",
    "Dr Linda Greenwall enamel care",
    "Linda Greenwall dental fluorosis"
]

# Processing Settings
MIN_CLIP_DURATION = 15  # seconds
MAX_CLIP_DURATION = 60  # seconds
MAX_CLIPS_PER_VIDEO = 12
AUTOMATION_INTERVAL_HOURS = 1

# Timing Settings (delays between operations)
DELAY_BETWEEN_CHANNELS = 30    # seconds between uploading to different channels
DELAY_BETWEEN_CLIPS = 45       # seconds between publishing different clips
DELAY_BETWEEN_VIDEOS = 120     # seconds between processing different videos

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
    'fluorosis', 'enamel development', 'childhood enamel problems',
    'tooth discoloration', 'enamel defects children', 'mih treatment',
    'pediatric dentistry', 'children teeth whitening', 'safe whitening kids'
]

# CSV Logging Settings
CSV_OUTPUT_DIR = "logs"
ENABLE_DETAILED_LOGGING = True
LOG_TRANSCRIPT_PREVIEW_LENGTH = 500

# Rate Limiting
YOUTUBE_API_CALLS_PER_MINUTE = 10
GEMINI_API_CALLS_PER_MINUTE = 20

# File Management
AUTO_CLEANUP_TEMP_FILES = True
KEEP_ORIGINAL_VIDEOS = False
KEEP_EXTRACTED_CLIPS = False
MAX_TEMP_STORAGE_GB = 10

# Development Settings
DEBUG_MODE = False
TEST_MODE = False
DRY_RUN = False
VERBOSE_LOGGING = True
'''
    
    # Write config file
    with open('config.py', 'w') as f:
        f.write(config_content)
    
    print("✅ Created config.py")

def install_python_packages():
    """Install required Python packages"""
    print("\n📦 INSTALLING PYTHON PACKAGES")
    print("-" * 50)
    
    packages = [
        # 'google-api-python-client',
        # 'google-auth',
        # 'google-auth-oauthlib', 
        # 'google-auth-httplib2',
        # 'google-generativeai',
        # 'youtube-transcript-api',
        # 'yt-dlp'
    ]
    
    print("Installing required packages...")
    for package in packages:
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', package], 
                         check=True, capture_output=True)
            print(f"  ✅ {package}")
        except subprocess.CalledProcessError:
            print(f"  ❌ Failed to install {package}")
            print(f"     Try manually: pip install {package}")

def create_directory_structure():
    """Create necessary directories"""
    print("\n📁 CREATING DIRECTORIES")
    print("-" * 50)
    
    directories = [
        'processed_videos',
        'logs',
        'temp'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created directory: {directory}")

def test_configuration():
    """Test the configuration"""
    print("\n🧪 TESTING CONFIGURATION")
    print("-" * 50)
    
    try:
        # Test config import
        print("Testing config file...")
        import config
        print("✅ Config file loads successfully")
        
        # Test API keys
        if config.YOUTUBE_API_KEY and config.GEMINI_API_KEY:
            print("✅ API keys configured")
        else:
            print("❌ API keys missing")
            return False
        
        # Test channel configuration
        if len(config.UPLOAD_CHANNELS) == 3:
            print("✅ Three channels configured")
        else:
            print(f"❌ Expected 3 channels, found {len(config.UPLOAD_CHANNELS)}")
            return False
        
        # Test credentials files
        all_files_exist = True
        for channel in config.UPLOAD_CHANNELS:
            if os.path.exists(channel['credentials_file']):
                print(f"✅ Found {channel['credentials_file']}")
            else:
                print(f"❌ Missing {channel['credentials_file']}")
                all_files_exist = False
        
        return all_files_exist
        
    except ImportError as e:
        print(f"❌ Error importing config: {e}")
        return False

def print_next_steps():
    """Print next steps for user"""
    print("\n🎉 SETUP COMPLETE!")
    print("=" * 50)
    print()
    print("Next Steps:")
    print()
    print("1. Test the automation:")
    print("   python automation.py --test VIDEO_ID")
    print("   (Replace VIDEO_ID with actual Dr. Greenwall video ID)")
    print()
    print("2. Run single automation cycle:")
    print("   python automation.py")
    print()
    print("3. Run continuous automation:")
    print("   python automation.py --continuous")
    print()
    print("4. Generate reports:")
    print("   python automation.py --report")
    print()
    print("📊 Monitor Progress:")
    print("   - Check logs/processed_videos.csv for video processing")
    print("   - Check logs/published_clips.csv for clip uploads")
    print("   - Watch console output for real-time updates")
    print()
    print("⏱️  Timing Configuration:")
    print("   - 30 seconds between channel uploads")
    print("   - 45 seconds between different clips")
    print("   - 2 minutes between different videos")
    print()
    print("🔧 If you need to make changes:")
    print("   - Edit config.py for settings")
    print("   - Re-run setup wizard: python setup_wizard.py")

def main():
    """Main setup wizard function"""
    print_header()
    
    try:
        # Step 1: Check dependencies
        if not check_dependencies():
            return
        
        # Step 2: Install Python packages
        install_python_packages()
        
        # Step 3: Get API keys
        youtube_key, gemini_key = get_api_keys()
        
        # Step 4: Get channel information
        channels = get_channel_info()
        
        # Step 5: Setup OAuth credentials
        setup_oauth_credentials()
        
        # Step 6: Create directories
        create_directory_structure()
        
        # Step 7: Create config file
        create_config_file(youtube_key, gemini_key, channels)
        
        # Step 8: Test configuration
        if test_configuration():
            print_next_steps()
        else:
            print("\n❌ Configuration test failed. Please check the errors above.")
            
    except KeyboardInterrupt:
        print("\n\n❌ Setup interrupted by user")
    except Exception as e:
        print(f"\n❌ Setup error: {e}")
        print("Please check the error and try again")

if __name__ == "__main__":
    main()