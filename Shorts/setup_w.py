#!/usr/bin/env python3
"""
Windows-specific setup script for MIH Content Automation
"""

import os
import sys
import subprocess
import webbrowser
from pathlib import Path

def check_python():
    """Check Python version"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher required")
        print("Current version:", sys.version)
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")
    return True

def check_uv():
    """Check if uv is installed"""
    try:
        result = subprocess.run(['uv', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ uv is installed")
            return True
        else:
            print("❌ uv not working properly")
            return False
    except FileNotFoundError:
        print("❌ uv not found")
        print("Installing uv...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'uv'], check=True)
            print("✅ uv installed successfully")
            return True
        except:
            print("❌ Failed to install uv")
            print("Please install manually: pip install uv")
            return False

def check_ffmpeg():
    """Check if FFmpeg is available"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ FFmpeg is installed")
            return True
    except FileNotFoundError:
        pass
    
    print("❌ FFmpeg not found")
    print("📥 FFmpeg is required for video processing")
    print("Download from: https://ffmpeg.org/download.html#build-windows")
    print("Or use chocolatey: choco install ffmpeg")
    print("Or use winget: winget install ffmpeg")
    
    choice = input("Open FFmpeg download page? (y/n): ").lower()
    if choice == 'y':
        webbrowser.open("https://ffmpeg.org/download.html#build-windows")
    
    return False

def install_dependencies():
    """Install Python dependencies with uv"""
    print("\n📦 Installing Python dependencies...")
    
    packages = [
        "google-api-python-client",
        "google-auth",
        "google-auth-oauthlib", 
        "google-generativeai",
        "youtube-transcript-api",
        "ffmpeg-python",
        "yt-dlp",
        "requests"
    ]
    
    try:
        # Try to install all at once
        cmd = ['uv', 'add'] + packages
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ All packages installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("Installing packages individually...")
        for package in packages:
            try:
                subprocess.run(['uv', 'add', package], check=True, capture_output=True)
                print(f"✅ {package}")
            except subprocess.CalledProcessError:
                print(f"❌ Failed to install {package}")
                return False
    
    return True

def create_config_template():
    """Create config.py template if it doesn't exist"""
    if not os.path.exists('config.py'):
        print("\n📝 Creating config.py template...")
        
        config_content = '''# config.py - Configuration for MIH Content Automation

# YouTube Data API v3 Key (from Google Cloud Console)
YOUTUBE_API_KEY = "YOUR_YOUTUBE_API_KEY_HERE"

# Gemini AI API Key (from Google AI Studio)  
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"

# YouTube OAuth Credentials File (downloaded from Google Cloud Console)
YOUTUBE_CREDENTIALS_FILE = "youtube_credentials.json"

# Output Directory for processed videos
OUTPUT_DIR = "processed_videos"

# YouTube Channels for Upload (replace with your actual channel IDs)
UPLOAD_CHANNELS = [
    {"name": "MIH Education Primary", "id": "YOUR_CHANNEL_ID_1"},
    {"name": "Pediatric Dentistry Tips", "id": "YOUR_CHANNEL_ID_2"}, 
    {"name": "Dr Greenwall Content", "id": "YOUR_CHANNEL_ID_3"}
]
'''
        
        with open('config.py', 'w') as f:
            f.write(config_content)
        
        print("✅ config.py template created")
        print("⚠️  Please edit config.py with your actual API keys!")
    else:
        print("✅ config.py already exists")

def setup_apis():
    """Guide user through API setup"""
    print("\n🔑 API Setup Required:")
    print("1. YouTube Data API v3 Key")
    print("2. YouTube OAuth Credentials") 
    print("3. Gemini AI API Key")
    
    print("\n📋 Setup Guide:")
    print("1. Google Cloud Console: https://console.cloud.google.com/")
    print("   - Create project")
    print("   - Enable YouTube Data API v3")
    print("   - Create API Key & OAuth credentials")
    
    print("\n2. Google AI Studio: https://aistudio.google.com/")
    print("   - Get Gemini API Key")
    
    choice = input("\nOpen setup guides in browser? (y/n): ").lower()
    if choice == 'y':
        webbrowser.open("https://console.cloud.google.com/")
        webbrowser.open("https://aistudio.google.com/")

def create_test_script():
    """Create a simple test script"""
    test_content = '''#!/usr/bin/env python3
"""Simple test to verify setup"""

def test_imports():
    """Test if all packages can be imported"""
    try:
        import googleapiclient.discovery
        print("✅ Google API Client")
        
        import google.generativeai
        print("✅ Gemini AI")
        
        import youtube_transcript_api
        print("✅ YouTube Transcript API")
        
        import ffmpeg
        print("✅ FFmpeg Python")
        
        import yt_dlp
        print("✅ yt-dlp")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_config():
    """Test if config file is properly set up"""
    try:
        from config import YOUTUBE_API_KEY, GEMINI_API_KEY
        
        if YOUTUBE_API_KEY == "YOUR_YOUTUBE_API_KEY_HERE":
            print("❌ YouTube API key not configured")
            return False
        
        if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
            print("❌ Gemini API key not configured")
            return False
        
        print("✅ API keys configured")
        return True
        
    except ImportError:
        print("❌ config.py not found or invalid")
        return False

def main():
    print("Testing MIH Automation Setup...\\n")
    
    import_test = test_imports()
    config_test = test_config()
    
    print("\\n" + "="*40)
    if import_test and config_test:
        print("🎉 Setup looks good!")
        print("\\nNext steps:")
        print("1. Add youtube_credentials.json file")
        print("2. Run: uv run mih_automation.py")
    else:
        print("❌ Setup incomplete. Please fix errors above.")

if __name__ == "__main__":
    main()
'''
    
    with open('test_setup.py', 'w',encoding="utf-8") as f:
        f.write(test_content)
    
    print("✅ test_setup.py created")

def main():
    print("="*60)
    print(" MIH Content Automation - Windows Setup")
    print("="*60)
    
    # Check system requirements
    print("\\n1. Checking System Requirements...")
    if not check_python():
        return
    
    if not check_uv():
        return
    
    ffmpeg_ok = check_ffmpeg()
    
    # Install dependencies
    print("\\n2. Installing Dependencies...")
    if not install_dependencies():
        print("❌ Failed to install dependencies")
        return
    
    # Create configuration files
    print("\\n3. Creating Configuration Files...")
    create_config_template()
    create_test_script()
    
    # API setup guidance
    print("\\n4. API Setup Required...")
    setup_apis()
    
    # Final instructions
    print("\\n" + "="*60)
    print(" Setup Summary")
    print("="*60)
    
    if ffmpeg_ok:
        print("✅ All system dependencies ready")
    else:
        print("⚠️  FFmpeg installation required")
    
    print("✅ Python packages installed")
    print("✅ Configuration template created")
    
    print("\\n📋 Next Steps:")
    print("1. Install FFmpeg if not already installed")
    print("2. Edit config.py with your API keys")
    print("3. Download youtube_credentials.json from Google Cloud")
    print("4. Run test: uv run test_setup.py")
    print("5. Run automation: uv run mih_automation.py")
    
    print("\\n🔒 Security Reminder:")
    print("- Keep your API keys secure")
    print("- Don't commit config.py to version control")
    print("- Use environment variables for production")

if __name__ == "__main__":
    main()