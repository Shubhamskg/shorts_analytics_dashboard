#!/usr/bin/env python3
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
    print("Testing MIH Automation Setup...\n")
    
    import_test = test_imports()
    config_test = test_config()
    
    print("\n" + "="*40)
    if import_test and config_test:
        print("🎉 Setup looks good!")
        print("\nNext steps:")
        print("1. Add youtube_credentials.json file")
        print("2. Run: uv run mih_automation.py")
    else:
        print("❌ Setup incomplete. Please fix errors above.")

if __name__ == "__main__":
    main()
