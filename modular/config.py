"""
Enhanced MIH Content Automation System - Configuration Module
Centralized configuration management with validation
"""

import os
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ChannelConfig:
    """Configuration for a YouTube channel"""
    name: str
    credentials_file: str
    brand_color: str = "#FF6B6B"
    intro_template: str = "modern"
    outro_template: str = "subscribe"

@dataclass
class AudioConfig:
    """Audio processing configuration"""
    tts_engine: str = "gTTS"  # gTTS, Azure, AWS
    voice_language: str = "en"
    voice_accent: str = "com.au"  # Australian accent
    intro_volume: float = 0.8
    outro_volume: float = 0.8
    background_music_volume: float = 0.3
    sound_effects_volume: float = 0.6

@dataclass
class VideoConfig:
    """Video processing configuration"""
    resolution: str = "1080x1920"  # Vertical format for Shorts
    frame_rate: int = 30
    quality_preset: str = "medium"
    enable_gpu: bool = True
    max_clip_duration: int = 60
    min_clip_duration: int = 20
    intro_duration: float = 3.0
    outro_duration: float = 3.0

@dataclass
class AIConfig:
    """AI and content generation configuration"""
    gemini_model: str = "gemini-2.0-flash-001"
    temperature: float = 0.7
    max_tokens: int = 1000
    content_style: str = "engaging_educational"
    trending_hashtags_enabled: bool = True

class ConfigManager:
    """Centralized configuration management"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self.load_config()
    
    def load_config(self):
        """Load configuration from file or environment variables"""
        # Try to load from JSON file first
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                self._load_from_dict(config_data)
                return
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")
        
        # Fallback to environment variables and defaults
        self._load_from_env()
    
    def _load_from_dict(self, config_data: Dict):
        """Load configuration from dictionary"""
        # API Keys
        self.youtube_api_key = config_data.get('youtube_api_key', '')
        self.gemini_api_key = config_data.get('gemini_api_key', '')
        self.azure_speech_key = config_data.get('azure_speech_key', '')
        self.azure_speech_region = config_data.get('azure_speech_region', '')
        
        # Channels
        channels_data = config_data.get('upload_channels', [])
        self.upload_channels = [
            ChannelConfig(**channel) for channel in channels_data
        ]
        
        # Configurations
        audio_data = config_data.get('audio', {})
        self.audio = AudioConfig(**audio_data)
        
        video_data = config_data.get('video', {})
        self.video = VideoConfig(**video_data)
        
        ai_data = config_data.get('ai', {})
        self.ai = AIConfig(**ai_data)
        
        # Directories
        self.output_dir = config_data.get('output_dir', 'processed_videos')
        self.assets_dir = config_data.get('assets_dir', 'assets')
        self.temp_dir = config_data.get('temp_dir', 'temp')
        
        # Processing limits
        self.max_processing_time = config_data.get('max_processing_time', 1800)
        self.max_clips_per_video = config_data.get('max_clips_per_video', 2)
    
    def _load_from_env(self):
        """Load configuration from environment variables with defaults"""
        # API Keys
        self.youtube_api_key = os.getenv('YOUTUBE_API_KEY', 'YOUR_YOUTUBE_API_KEY')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY', 'YOUR_GEMINI_API_KEY')
        self.azure_speech_key = os.getenv('AZURE_SPEECH_KEY', '')
        self.azure_speech_region = os.getenv('AZURE_SPEECH_REGION', '')
        
        # Default channels
        self.upload_channels = [
            ChannelConfig(
                name="MIH Treatment Channel",
                credentials_file="channel1_credentials.json",
                brand_color="#4ECDC4",
                intro_template="dental_modern"
            ),
            ChannelConfig(
                name="Kids Dental Care",
                credentials_file="channel2_credentials.json",
                brand_color="#45B7D1",
                intro_template="kids_friendly"
            )
        ]
        
        # Default configurations
        self.audio = AudioConfig()
        self.video = VideoConfig()
        self.ai = AIConfig()
        
        # Directories
        self.output_dir = os.getenv('OUTPUT_DIR', 'processed_videos')
        self.assets_dir = os.getenv('ASSETS_DIR', 'assets')
        self.temp_dir = os.getenv('TEMP_DIR', 'temp')
        
        # Processing limits
        self.max_processing_time = int(os.getenv('MAX_PROCESSING_TIME', '1800'))
        self.max_clips_per_video = int(os.getenv('MAX_CLIPS_PER_VIDEO', '2'))
    
    def save_config(self):
        """Save current configuration to file"""
        config_data = {
            'youtube_api_key': self.youtube_api_key,
            'gemini_api_key': self.gemini_api_key,
            'azure_speech_key': self.azure_speech_key,
            'azure_speech_region': self.azure_speech_region,
            'upload_channels': [
                {
                    'name': channel.name,
                    'credentials_file': channel.credentials_file,
                    'brand_color': channel.brand_color,
                    'intro_template': channel.intro_template,
                    'outro_template': channel.outro_template
                }
                for channel in self.upload_channels
            ],
            'audio': {
                'tts_engine': self.audio.tts_engine,
                'voice_language': self.audio.voice_language,
                'voice_accent': self.audio.voice_accent,
                'intro_volume': self.audio.intro_volume,
                'outro_volume': self.audio.outro_volume,
                'background_music_volume': self.audio.background_music_volume,
                'sound_effects_volume': self.audio.sound_effects_volume
            },
            'video': {
                'resolution': self.video.resolution,
                'frame_rate': self.video.frame_rate,
                'quality_preset': self.video.quality_preset,
                'enable_gpu': self.video.enable_gpu,
                'max_clip_duration': self.video.max_clip_duration,
                'min_clip_duration': self.video.min_clip_duration,
                'intro_duration': self.video.intro_duration,
                'outro_duration': self.video.outro_duration
            },
            'ai': {
                'gemini_model': self.ai.gemini_model,
                'temperature': self.ai.temperature,
                'max_tokens': self.ai.max_tokens,
                'content_style': self.ai.content_style,
                'trending_hashtags_enabled': self.ai.trending_hashtags_enabled
            },
            'output_dir': self.output_dir,
            'assets_dir': self.assets_dir,
            'temp_dir': self.temp_dir,
            'max_processing_time': self.max_processing_time,
            'max_clips_per_video': self.max_clips_per_video
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        # Check API keys
        if not self.youtube_api_key or 'YOUR_' in self.youtube_api_key:
            errors.append("Invalid or missing YouTube API key")
        
        if not self.gemini_api_key or 'YOUR_' in self.gemini_api_key:
            errors.append("Invalid or missing Gemini API key")
        
        # Check channels
        if not self.upload_channels:
            errors.append("No upload channels configured")
        
        for i, channel in enumerate(self.upload_channels):
            if not channel.credentials_file:
                errors.append(f"Channel {i+1}: Missing credentials file")
            elif not Path(channel.credentials_file).exists():
                errors.append(f"Channel {i+1}: Credentials file not found: {channel.credentials_file}")
        
        # Check directories
        for dir_name, dir_path in [
            ('output', self.output_dir),
            ('assets', self.assets_dir),
            ('temp', self.temp_dir)
        ]:
            try:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create {dir_name} directory {dir_path}: {e}")
        
        return errors
    
    def create_sample_config(self):
        """Create a sample configuration file"""
        sample_config = {
            "youtube_api_key": "YOUR_YOUTUBE_API_KEY_HERE",
            "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE",
            "azure_speech_key": "YOUR_AZURE_SPEECH_KEY_HERE (optional)",
            "azure_speech_region": "YOUR_AZURE_REGION_HERE (optional)",
            "upload_channels": [
                {
                    "name": "MIH Treatment Channel",
                    "credentials_file": "channel1_credentials.json",
                    "brand_color": "#4ECDC4",
                    "intro_template": "dental_modern",
                    "outro_template": "subscribe"
                },
                {
                    "name": "Kids Dental Care",
                    "credentials_file": "channel2_credentials.json",
                    "brand_color": "#45B7D1",
                    "intro_template": "kids_friendly",
                    "outro_template": "subscribe"
                }
            ],
            "audio": {
                "tts_engine": "gTTS",
                "voice_language": "en",
                "voice_accent": "com.au",
                "intro_volume": 0.8,
                "outro_volume": 0.8,
                "background_music_volume": 0.3,
                "sound_effects_volume": 0.6
            },
            "video": {
                "resolution": "1080x1920",
                "frame_rate": 30,
                "quality_preset": "medium",
                "enable_gpu": True,
                "max_clip_duration": 60,
                "min_clip_duration": 20,
                "intro_duration": 3.0,
                "outro_duration": 3.0
            },
            "ai": {
                "gemini_model": "gemini-2.0-flash-001",
                "temperature": 0.7,
                "max_tokens": 1000,
                "content_style": "engaging_educational",
                "trending_hashtags_enabled": True
            },
            "output_dir": "processed_videos",
            "assets_dir": "assets",
            "temp_dir": "temp",
            "max_processing_time": 1800,
            "max_clips_per_video": 2
        }
        
        with open('config_sample.json', 'w') as f:
            json.dump(sample_config, f, indent=2)
        
        print("✅ Sample configuration created: config_sample.json")
        print("📝 Edit this file and rename to config.json")

# Global config instance
config = ConfigManager()

if __name__ == "__main__":
    # Create sample config if run directly
    config.create_sample_config()