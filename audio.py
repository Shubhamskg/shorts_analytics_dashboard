"""
Enhanced MIH Content Automation System v2.0
============================================
Complete redesign with audio, enhanced visuals, better prompts, and modular architecture
Features: TTS intro/outro, sound effects, animations, catchy graphics, improved AI prompts
"""

import os
import re
import json
import time
import logging
import subprocess
import uuid
import tempfile
import shutil
import signal
import select
import sys
import threading
import queue
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
from abc import ABC, abstractmethod

import google.generativeai as genai
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Configure logging with UTF-8 encoding for Windows compatibility
import sys
import io

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        # Try to set console to UTF-8
        import locale
        locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    except:
        pass
    
    # Ensure stdout can handle Unicode
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Create custom formatter that handles Unicode gracefully
class SafeFormatter(logging.Formatter):
    def format(self, record):
        try:
            return super().format(record)
        except UnicodeEncodeError:
            # Replace problematic Unicode characters with ASCII equivalents
            msg = record.getMessage()
            msg = msg.replace('✅', '[OK]').replace('❌', '[ERROR]').replace('⚠️', '[WARN]')
            msg = msg.replace('🚀', '[INIT]').replace('📝', '[PROC]').replace('🎬', '[VIDEO]')
            msg = msg.replace('📥', '[DOWN]').replace('📤', '[UP]').replace('🧹', '[CLEAN]')
            msg = msg.replace('ℹ️', '[INFO]').replace('🔍', '[DETECT]').replace('💻', '[CPU]')
            record.msg = msg
            return super().format(record)

# Configure logging with safe formatter
safe_formatter = SafeFormatter('%(asctime)s - %(levelname)s - %(message)s')

# File handler
file_handler = logging.FileHandler('mih_automation.log', encoding='utf-8')
file_handler.setFormatter(safe_formatter)

# Console handler with encoding handling
console_handler = logging.StreamHandler()
console_handler.setFormatter(safe_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    """Custom timeout exception"""
    pass

class ProcessingError(Exception):
    """Custom processing exception"""
    pass

def timeout_handler(signum, frame):
    """Handle timeout signals"""
    raise TimeoutError("Operation timed out")

def safe_execute(cmd: List[str], timeout: int = 120, **kwargs) -> subprocess.CompletedProcess:
    """Execute command safely with timeout protection"""
    try:
        kwargs.setdefault('capture_output', True)
        kwargs.setdefault('text', True)
        
        if hasattr(signal, 'SIGALRM'):
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout)
        
        result = subprocess.run(cmd, timeout=timeout, **kwargs)
        
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        
        return result
        
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {' '.join(str(x) for x in cmd[:3])}...")
        raise TimeoutError(f"Command timed out after {timeout}s")
    except Exception as e:
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)
        raise e

@dataclass
class AudioConfig:
    """Audio configuration settings"""
    tts_voice: str = "en-US-Neural2-F"  # Female voice
    tts_speed: float = 1.0
    music_volume: float = 0.3
    sfx_volume: float = 0.5
    master_volume: float = 0.8

@dataclass
class VisualConfig:
    """Visual configuration settings"""
    resolution: Tuple[int, int] = (1080, 1920)  # 9:16 for shorts
    fps: int = 30
    font_family: str = "Arial"
    primary_color: str = "#FF6B6B"
    secondary_color: str = "#4ECDC4"
    accent_color: str = "#45B7D1"
    background_gradient: List[str] = field(default_factory=lambda: ["#667eea", "#764ba2"])

@dataclass
class VideoClip:
    """Enhanced video clip data structure"""
    clip_id: str
    start_time: float
    end_time: float
    transcript: str
    source_video_id: str
    source_title: str
    source_url: str
    title: str
    description: str
    hashtags: List[str]
    keywords: List[str]
    engagement_score: float
    file_path: Optional[str] = None
    duration: float = 0.0
    subtitle_segments: List[Dict] = field(default_factory=list)
    audio_features: Dict = field(default_factory=dict)
    visual_effects: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.duration == 0.0:
            self.duration = self.end_time - self.start_time

class BaseProcessor(ABC):
    """Abstract base class for processors"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.temp_dir = Path(tempfile.gettempdir()) / f"mih_{self.__class__.__name__.lower()}"
        self.temp_dir.mkdir(exist_ok=True)
    
    @abstractmethod
    def process(self, *args, **kwargs):
        pass
    
    def cleanup(self):
        """Clean up temporary files"""
        try:
            for file in self.temp_dir.glob("*"):
                try:
                    file.unlink()
                except:
                    pass
            logger.info(f"[CLEAN] {self.__class__.__name__} cleanup complete")
        except Exception as e:
            logger.warning(f"[WARN] Cleanup error in {self.__class__.__name__}: {e}")

class AudioProcessor(BaseProcessor):
    """Enhanced audio processing with TTS and sound effects"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.audio_config = AudioConfig()
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if required audio tools are available"""
        try:
            safe_execute(['espeak', '--version'], timeout=10)
            self.tts_engine = 'espeak'
            logger.info("[OK] eSpeak TTS engine detected")
        except:
            try:
                safe_execute(['say', '-v', '?'], timeout=10)
                self.tts_engine = 'say'
                logger.info("[OK] macOS say TTS engine detected")
            except:
                try:
                    import pyttsx3
                    self.tts_engine = 'pyttsx3'
                    logger.info("[OK] Windows SAPI TTS engine detected")
                except ImportError:
                    logger.warning("[WARN] No TTS engine found, using silent audio")
                    logger.info("[INFO] Install TTS: pip install pyttsx3 (Windows) or espeak (Linux)")
                    self.tts_engine = None
    
    def create_tts_audio(self, text: str, output_file: str, voice_speed: float = 1.0) -> str:
        """Create TTS audio file"""
        try:
            if not self.tts_engine:
                return self._create_silent_audio(3.0, output_file)
            
            # Clean text for TTS
            clean_text = re.sub(r'[^\w\s\.,!?\-]', '', text)
            clean_text = clean_text[:200]  # Limit length
            
            temp_wav = self.temp_dir / f"tts_{uuid.uuid4().hex[:8]}.wav"
            
            if self.tts_engine == 'espeak':
                cmd = [
                    'espeak', '-w', str(temp_wav),
                    '-s', str(int(140 * voice_speed)),  # Words per minute
                    '-v', 'en+f3',  # Female voice
                    clean_text
                ]
            elif self.tts_engine == 'say':
                cmd = [
                    'say', '-v', 'Samantha',
                    '-r', str(int(200 * voice_speed)),
                    '-o', str(temp_wav),
                    clean_text
                ]
            elif self.tts_engine == 'pyttsx3':
                return self._create_windows_tts(clean_text, output_file)
            else:
                return self._create_silent_audio(3.0, output_file)
            
            result = safe_execute(cmd, timeout=30)
            
            if result.returncode == 0 and temp_wav.exists():
                # Convert to proper format and normalize
                self._normalize_audio(str(temp_wav), output_file)
                temp_wav.unlink()
                logger.info(f"[OK] TTS audio created: {os.path.basename(output_file)}")
                return output_file
            else:
                logger.warning("[WARN] TTS failed, creating silent audio")
                return self._create_silent_audio(3.0, output_file)
                
        except Exception as e:
            logger.warning(f"[WARN] TTS creation failed: {e}")
            return self._create_silent_audio(3.0, output_file)
    
    def _create_windows_tts(self, text: str, output_file: str) -> str:
        """Create TTS using Windows SAPI"""
        try:
            import pyttsx3
            
            engine = pyttsx3.init()
            engine.setProperty('rate', 140)  # Words per minute
            engine.setProperty('volume', 0.9)
            
            # Try to use a female voice
            voices = engine.getProperty('voices')
            for voice in voices:
                if any(word in voice.name.lower() for word in ['zira', 'female', 'hazel', 'susan']):
                    engine.setProperty('voice', voice.id)
                    break
            
            # Save to temporary WAV file
            temp_wav = self.temp_dir / f"tts_temp_{uuid.uuid4().hex[:8]}.wav"
            engine.save_to_file(text, str(temp_wav))
            engine.runAndWait()
            
            # Convert WAV to AAC and normalize
            if temp_wav.exists():
                self._normalize_audio(str(temp_wav), output_file)
                temp_wav.unlink()
                logger.info(f"[OK] Windows TTS audio created: {os.path.basename(output_file)}")
                return output_file
            else:
                logger.warning("[WARN] Windows TTS file creation failed")
                return self._create_silent_audio(3.0, output_file)
                
        except ImportError:
            logger.info("[INFO] pyttsx3 not installed. Install with: pip install pyttsx3")
            return self._create_silent_audio(3.0, output_file)
        except Exception as e:
            logger.warning(f"[WARN] Windows TTS failed: {e}")
            return self._create_silent_audio(3.0, output_file)
    
    def _create_silent_audio(self, duration: float, output_file: str) -> str:
        """Create silent audio as fallback"""
        try:
            cmd = [
                'ffmpeg', '-y', '-f', 'lavfi',
                '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100',
                '-t', str(duration),
                '-c:a', 'aac',
                output_file
            ]
            
            result = safe_execute(cmd, timeout=30)
            if result.returncode == 0:
                return output_file
        except Exception as e:
            logger.error(f"[ERROR] Silent audio creation failed: {e}")
        return ""
    
    def _normalize_audio(self, input_file: str, output_file: str):
        """Normalize audio levels"""
        try:
            cmd = [
                'ffmpeg', '-y', '-i', input_file,
                '-af', f'volume={self.audio_config.master_volume},dynaudnorm=f=75:g=25:r=0.9',
                '-c:a', 'aac', '-b:a', '128k',
                output_file
            ]
            
            result = safe_execute(cmd, timeout=60)
            if result.returncode != 0:
                # Fallback: simple copy
                shutil.copy2(input_file, output_file)
                
        except Exception as e:
            logger.warning(f"[WARN] Audio normalization failed: {e}")
            try:
                shutil.copy2(input_file, output_file)
            except:
                pass
    
    def add_background_music(self, video_file: str, output_file: str, music_type: str = "upbeat") -> str:
        """Add background music to video"""
        try:
            # Create simple background music using tone generation
            music_file = self.temp_dir / f"bg_music_{uuid.uuid4().hex[:8]}.wav"
            
            # Generate pleasant background tone
            if music_type == "upbeat":
                frequencies = "440+554+659"  # A major chord
            else:
                frequencies = "220+277+330"  # A minor chord
            
            cmd = [
                'ffmpeg', '-y', '-f', 'lavfi',
                '-i', f'sine=frequency={frequencies}:duration=60',
                '-af', f'volume={self.audio_config.music_volume}',
                str(music_file)
            ]
            
            music_result = safe_execute(cmd, timeout=30)
            
            if music_result.returncode == 0 and music_file.exists():
                # Mix with video
                cmd = [
                    'ffmpeg', '-y', '-i', video_file,
                    '-i', str(music_file),
                    '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=shortest:dropout_transition=3',
                    '-c:v', 'copy', '-c:a', 'aac',
                    output_file
                ]
                
                result = safe_execute(cmd, timeout=120)
                
                music_file.unlink()
                
                if result.returncode == 0:
                    return output_file
            
            # Fallback: copy original
            shutil.copy2(video_file, output_file)
            return output_file
            
        except Exception as e:
            logger.warning(f"[WARN] Background music failed: {e}")
            try:
                shutil.copy2(video_file, output_file)
                return output_file
            except:
                return video_file

class VisualProcessor(BaseProcessor):
    """Enhanced visual processing with animations and effects"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.visual_config = VisualConfig()
        self.gpu_available = self._detect_gpu()
    
    def _detect_gpu(self) -> Dict[str, bool]:
        """Detect available GPU acceleration"""
        gpu_support = {'nvidia': False, 'intel': False, 'amd': False}
        
        try:
            result = safe_execute(['ffmpeg', '-hide_banner', '-encoders'], timeout=15)
            
            if result.returncode == 0:
                encoders = result.stdout.lower()
                if 'h264_nvenc' in encoders:
                    gpu_support['nvidia'] = True
                    logger.info("[GPU] NVIDIA GPU acceleration available")
                if 'h264_qsv' in encoders:
                    gpu_support['intel'] = True
                    logger.info("[GPU] Intel QuickSync acceleration available")
                if 'h264_amf' in encoders:
                    gpu_support['amd'] = True
                    logger.info("[GPU] AMD GPU acceleration available")
                    
        except Exception as e:
            logger.warning(f"[WARN] GPU detection failed: {e}")
        
        return gpu_support
    
    def create_animated_intro(self, title: str, duration: float = 3.0) -> str:
        """Create animated intro with enhanced graphics"""
        try:
            output_file = self.temp_dir / f"intro_{uuid.uuid4().hex[:8]}.mp4"
            safe_title = self._sanitize_text(title)
            
            # Create complex filter for animated intro
            filters = self._build_intro_filters(safe_title, duration)
            
            encoder, encoder_opts = self._get_encoder_settings()
            
            cmd = [
                'ffmpeg', '-y', '-v', 'error',
                '-f', 'lavfi', '-i', f'color=c=#1a1a2e:size={self.visual_config.resolution[0]}x{self.visual_config.resolution[1]}:duration={duration}',
                '-vf', filters,
                '-c:v', encoder,
                '-r', str(self.visual_config.fps),
                '-pix_fmt', 'yuv420p'
            ]
            
            cmd.extend(encoder_opts)
            cmd.append(str(output_file))
            
            logger.info("[VIDEO] Creating animated intro...")
            result = safe_execute(cmd, timeout=60)
            
            if result.returncode == 0 and output_file.exists():
                logger.info(f"[OK] Animated intro created: {output_file.name}")
                return str(output_file)
            else:
                return self._create_simple_intro(safe_title, duration)
                
        except Exception as e:
            logger.warning(f"[WARN] Animated intro failed: {e}")
            return self._create_simple_intro(title, duration)
    
    def _build_intro_filters(self, title: str, duration: float) -> str:
        """Build complex filter chain for intro animation"""
        w, h = self.visual_config.resolution
        
        # Split title into words for animation
        words = title.split()[:4]  # Max 4 words
        
        filters = []
        
        # Background gradient animation
        filters.append(f"geq=r='255*((W-1)*sin(2*PI*T/{duration})+1)/(2*W)':g='128':b='255'")
        
        # Add animated text elements
        for i, word in enumerate(words):
            delay = i * 0.3
            fade_in = f"fade=t=in:st={delay}:d=0.5:alpha=1"
            
            # Text with shadow and glow effect
            text_filter = (
                f"drawtext=text='{word}':fontfile=/System/Library/Fonts/Arial.ttf:"
                f"fontsize=72:fontcolor=white:x=(w-text_w)/2:"
                f"y={h//2 + i*80 - len(words)*40}:alpha='if(between(t,{delay},{delay+0.5}),(t-{delay})/0.5,1)':"
                f"shadowcolor=black:shadowx=3:shadowy=3"
            )
            filters.append(text_filter)
        
        # Add Dr. Greenwall branding
        branding = (
            f"drawtext=text='Dr. Linda Greenwall - MIH Expert':"
            f"fontsize=32:fontcolor={self.visual_config.accent_color}:"
            f"x=(w-text_w)/2:y=h-150:alpha='if(gt(t,1.5),1,0)'"
        )
        filters.append(branding)
        
        return ','.join(filters)
    
    def _create_simple_intro(self, title: str, duration: float) -> str:
        """Fallback simple intro"""
        try:
            output_file = self.temp_dir / f"simple_intro_{uuid.uuid4().hex[:8]}.mp4"
            
            cmd = [
                'ffmpeg', '-y', '-v', 'error',
                '-f', 'lavfi', '-i', f'color=c=#2C3E50:size=1080x1920:duration={duration}',
                '-vf', f"drawtext=text='{title}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                str(output_file)
            ]
            
            result = safe_execute(cmd, timeout=45)
            
            if result.returncode == 0:
                return str(output_file)
                
        except Exception as e:
            logger.error(f"❌ Simple intro creation failed: {e}")
        
        return ""
    
    def create_animated_outro(self, duration: float = 3.0) -> str:
        """Create animated outro with call-to-action"""
        try:
            output_file = self.temp_dir / f"outro_{uuid.uuid4().hex[:8]}.mp4"
            
            # Complex outro animation
            filters = self._build_outro_filters(duration)
            
            encoder, encoder_opts = self._get_encoder_settings()
            
            cmd = [
                'ffmpeg', '-y', '-v', 'error',
                '-f', 'lavfi', '-i', f'color=c=#34495e:size=1080x1920:duration={duration}',
                '-vf', filters,
                '-c:v', encoder,
                '-r', str(self.visual_config.fps),
                '-pix_fmt', 'yuv420p'
            ]
            
            cmd.extend(encoder_opts)
            cmd.append(str(output_file))
            
            result = safe_execute(cmd, timeout=60)
            
            if result.returncode == 0 and output_file.exists():
                logger.info(f"✅ Animated outro created: {output_file.name}")
                return str(output_file)
            else:
                return self._create_simple_outro(duration)
                
        except Exception as e:
            logger.warning(f"⚠️ Animated outro failed: {e}")
            return self._create_simple_outro(duration)
    
    def _build_outro_filters(self, duration: float) -> str:
        """Build outro animation filters"""
        filters = []
        
        # Animated background
        filters.append("geq=r='255*sin(2*PI*T/3)':g='128':b='255*cos(2*PI*T/4)'")
        
        # Main CTA text with animation
        main_text = (
            "drawtext=text='LIKE & SUBSCRIBE':fontsize=64:fontcolor=white:"
            "x=(w-text_w)/2:y=h/2-100:alpha='if(lt(t,0.5),t*2,1)':"
            "shadowcolor=black:shadowx=2:shadowy=2"
        )
        filters.append(main_text)
        
        # Subscribe icon simulation
        subscribe_button = (
            "drawbox=x=w/2-100:y=h/2+50:w=200:h=60:color=red@0.8:t=fill,"
            "drawtext=text='SUBSCRIBE':fontsize=24:fontcolor=white:"
            "x=(w-text_w)/2:y=h/2+65"
        )
        filters.append(subscribe_button)
        
        # Channel branding
        branding = (
            "drawtext=text='Dr. Linda Greenwall - MIH Expert':"
            "fontsize=28:fontcolor=#FFD700:x=(w-text_w)/2:y=h-100"
        )
        filters.append(branding)
        
        return ','.join(filters)
    
    def _create_simple_outro(self, duration: float) -> str:
        """Fallback simple outro"""
        try:
            output_file = self.temp_dir / f"simple_outro_{uuid.uuid4().hex[:8]}.mp4"
            
            cmd = [
                'ffmpeg', '-y', '-v', 'error',
                '-f', 'lavfi', '-i', f'color=c=#e74c3c:size=1080x1920:duration={duration}',
                '-vf', "drawtext=text='LIKE & SUBSCRIBE':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                str(output_file)
            ]
            
            result = safe_execute(cmd, timeout=45)
            
            if result.returncode == 0:
                return str(output_file)
                
        except Exception as e:
            logger.error(f"❌ Simple outro creation failed: {e}")
        
        return ""
    
    def enhance_clip_visuals(self, input_file: str, output_file: str, 
                           title: str, subtitle_segments: List[Dict]) -> bool:
        """Apply visual enhancements to main clip"""
        try:
            filters = self._build_enhancement_filters(title, subtitle_segments)
            
            encoder, encoder_opts = self._get_encoder_settings()
            
            cmd = [
                'ffmpeg', '-y', '-i', input_file,
                '-vf', filters,
                '-c:v', encoder,
                '-c:a', 'aac', '-b:a', '128k'
            ]
            
            cmd.extend(encoder_opts)
            cmd.append(output_file)
            
            result = safe_execute(cmd, timeout=180)
            
            if result.returncode == 0:
                logger.info("✅ Visual enhancements applied")
                return True
            else:
                logger.warning("⚠️ Visual enhancement failed, copying original")
                shutil.copy2(input_file, output_file)
                return True
                
        except Exception as e:
            logger.error(f"❌ Visual enhancement failed: {e}")
            try:
                shutil.copy2(input_file, output_file)
                return True
            except:
                return False
    
    def _build_enhancement_filters(self, title: str, subtitle_segments: List[Dict]) -> str:
        """Build visual enhancement filter chain"""
        filters = []
        
        # Scale and pad for shorts format
        filters.append('scale=1080:1920:force_original_aspect_ratio=decrease')
        filters.append('pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black')
        
        # Color enhancement
        filters.append('eq=brightness=0.05:contrast=1.15:saturation=1.2:gamma=1.1')
        
        # Sharpening
        filters.append('unsharp=5:5:1.0:3:3:0.5')
        
        # Add progress bar at bottom
        filters.append(
            "drawbox=x=0:y=h-20:w=w*t/duration:h=20:color=#FF6B6B@0.8:t=fill"
        )
        
        # Channel watermark
        watermark = (
            f"drawtext=text='@DrGreenwall':fontsize=24:fontcolor=white@0.7:"
            f"x=50:y=100:shadowcolor=black@0.5:shadowx=1:shadowy=1"
        )
        filters.append(watermark)
        
        # Dynamic subtitle styling
        if subtitle_segments:
            subtitle_filter = self._create_subtitle_filter(subtitle_segments)
            if subtitle_filter:
                filters.append(subtitle_filter)
        
        return ','.join(filters)
    
    def _create_subtitle_filter(self, segments: List[Dict]) -> str:
        """Create animated subtitle filter"""
        # This is a simplified version - in practice, you'd want to create
        # an SRT file and use the subtitles filter
        return (
            "drawtext=text='%{metadata\\:subtitle}':fontsize=32:fontcolor=white:"
            "x=(w-text_w)/2:y=h-200:box=1:boxcolor=black@0.5:boxborderw=5"
        )
    
    def _get_encoder_settings(self) -> Tuple[str, List[str]]:
        """Get optimal encoder settings"""
        if self.gpu_available['nvidia']:
            return 'h264_nvenc', ['-preset', 'medium', '-cq', '23', '-b:v', '3M']
        elif self.gpu_available['intel']:
            return 'h264_qsv', ['-preset', 'medium', '-global_quality', '23']
        else:
            return 'libx264', ['-preset', 'medium', '-crf', '23']
    
    def _sanitize_text(self, text: str) -> str:
        """Sanitize text for video filters"""
        # Remove problematic characters for FFmpeg
        text = re.sub(r'[^\w\s\-\.\!\?\&]', '', text)
        text = text.replace("'", "").replace('"', '').replace('`', '')
        return text[:50].strip()

class EnhancedContentGenerator(BaseProcessor):
    """Enhanced AI content generation with improved prompts"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.model = None
        self._initialize_ai()
    
    def process(self, *args, **kwargs):
        """Implementation of abstract process method"""
        # This can be used for batch processing if needed
        return self.find_viral_clips(*args, **kwargs)
    
    def _initialize_ai(self):
        """Initialize Gemini AI with error handling"""
        try:
            api_key = self.config.get('gemini_api_key')
            if not api_key or 'your_' in api_key.lower():
                logger.warning("[WARN] Invalid Gemini API key")
                return
            
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash-001')
            logger.info("[OK] Enhanced Gemini AI initialized")
        except Exception as e:
            logger.warning(f"[WARN] Failed to initialize Gemini: {e}")
    
    def find_viral_clips(self, transcript: str, video_data: Dict) -> List[Dict]:
        """Find clips with viral potential using enhanced AI prompts"""
        if not self.model:
            return self._fallback_clip_detection(transcript, video_data)
        
        try:
            enhanced_prompt = self._build_clip_analysis_prompt(transcript, video_data)
            
            response = self.model.generate_content(
                enhanced_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=800,
                    top_p=0.8,
                    top_k=40
                )
            )
            
            clips = self._parse_clip_response(response.text)
            
            if clips:
                logger.info(f"[OK] AI found {len(clips)} viral clips")
                return clips
            else:
                logger.warning("[WARN] AI clips invalid, using fallback")
                return self._fallback_clip_detection(transcript, video_data)
                
        except Exception as e:
            logger.warning(f"[WARN] AI clip detection failed: {e}")
            return self._fallback_clip_detection(transcript, video_data)
    
    def _build_clip_analysis_prompt(self, transcript: str, video_data: Dict) -> str:
        """Build enhanced prompt for clip analysis"""
        # Limit transcript length
        transcript_excerpt = transcript[:2000] if len(transcript) > 2000 else transcript
        
        return f"""
**TASK: Find 2 VIRAL-POTENTIAL Short Clips from MIH Dental Video**

**SOURCE VIDEO:**
Title: {video_data.get('title', '')[:150]}
Content Type: Medical/Educational (MIH - Molar Incisor Hypomineralization)
Transcript: {transcript_excerpt}

**FIND CLIPS THAT ARE:**
1. **HOOK-WORTHY** - Start with surprising facts, questions, or statements
2. **EDUCATIONAL VALUE** - Clear, actionable dental advice 
3. **EMOTIONAL RESONANCE** - Parents worry about their kids' teeth
4. **VIRAL ELEMENTS** - Surprising facts, before/after, quick tips
5. **COMPLETENESS** - Self-contained segments that make sense alone

**IDEAL CLIP CHARACTERISTICS:**
- Starts with a hook: "Did you know...", "Here's why...", "The shocking truth..."
- Contains specific, actionable advice
- Addresses common parent concerns
- Has clear beginning, middle, end
- 25-50 seconds duration (sweet spot for engagement)
- Includes visual cues or demonstrations

**ANALYZE FOR:**
- Surprising facts about MIH
- Quick diagnostic tips
- Treatment explanations
- Prevention advice
- Parent guidance moments
- Before/after discussions
- Common misconceptions addressed

**RETURN EXACTLY THIS JSON FORMAT:**
```json
[
  {
    "start_timestamp": 45.2,
    "end_timestamp": 78.5,
    "hook_factor": 9,
    "educational_value": 8,
    "viral_potential": 8,
    "key_topic": "MIH diagnosis signs",
    "target_emotion": "concern_to_relief",
    "clip_type": "educational_hook"
  },
  {
    "start_timestamp": 156.7,
    "end_timestamp": 198.3,
    "hook_factor": 7,
    "educational_value": 9,
    "viral_potential": 7,
    "key_topic": "treatment options",
    "target_emotion": "hope",
    "clip_type": "solution_focused"
  }
]
```

**REQUIREMENTS:**
- EXACTLY 2 clips maximum
- Each clip 25-50 seconds duration
- Start/end timestamps must be realistic for content length
- Hook_factor, educational_value, viral_potential: scale 1-10
- No overlapping timestamps
- Choose the absolute BEST segments only

**FOCUS ON SEGMENTS WHERE DR. GREENWALL:**
- Reveals surprising facts about MIH
- Explains complex concepts simply
- Addresses parent fears directly
- Provides actionable advice
- Shows diagnostic techniques
- Discusses treatment outcomes

ANALYZE CAREFULLY and select only the most engaging, educational segments.
"""
    
    def _parse_clip_response(self, response_text: str) -> List[Dict]:
        """Parse and validate AI response for clips"""
        try:
            # Clean JSON response
            clean_text = response_text.strip()
            if '```json' in clean_text:
                clean_text = clean_text.split('```json')[1].split('```')[0]
            elif '```' in clean_text:
                clean_text = clean_text.split('```')[1].split('```')[0]
            
            clips = json.loads(clean_text)
            
            # Validate and enhance clips
            valid_clips = []
            for clip in clips:
                if self._validate_clip_data(clip):
                    enhanced_clip = self._enhance_clip_data(clip)
                    valid_clips.append(enhanced_clip)
            
            return valid_clips[:2]  # Max 2 clips
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse clip response: {e}")
            return []
    
    def _validate_clip_data(self, clip: Dict) -> bool:
        """Validate clip data structure"""
        required_fields = ['start_timestamp', 'end_timestamp']
        
        if not all(field in clip for field in required_fields):
            return False
        
        start = float(clip['start_timestamp'])
        end = float(clip['end_timestamp'])
        duration = end - start
        
        return 20 <= duration <= 60 and start >= 0
    
    def _enhance_clip_data(self, clip: Dict) -> Dict:
        """Add calculated fields to clip data"""
        start = float(clip['start_timestamp'])
        end = float(clip['end_timestamp'])
        
        # Calculate engagement score based on AI ratings
        hook_factor = clip.get('hook_factor', 5)
        educational_value = clip.get('educational_value', 5)
        viral_potential = clip.get('viral_potential', 5)
        
        engagement_score = (hook_factor * 0.4 + educational_value * 0.3 + viral_potential * 0.3)
        
        return {
            'start_timestamp': start,
            'end_timestamp': end,
            'engagement_score': engagement_score,
            'key_topic': clip.get('key_topic', 'MIH advice'),
            'target_emotion': clip.get('target_emotion', 'educational'),
            'clip_type': clip.get('clip_type', 'educational')
        }
    
    def generate_viral_content(self, transcript: str, duration: float, clip_data: Dict) -> Dict:
        """Generate viral-optimized content with enhanced prompts"""
        if not self.model:
            return self._fallback_content_generation(transcript, duration, clip_data)
        
        try:
            enhanced_prompt = self._build_content_generation_prompt(transcript, duration, clip_data)
            
            response = self.model.generate_content(
                enhanced_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.4,
                    max_output_tokens=600,
                    top_p=0.9,
                    top_k=40
                )
            )
            
            content = self._parse_content_response(response.text)
            
            if content:
                logger.info(f"[OK] Generated viral content: {content['title'][:30]}...")
                return content
            else:
                logger.warning("[WARN] AI content invalid, using fallback")
                return self._fallback_content_generation(transcript, duration, clip_data)
                
        except Exception as e:
            logger.warning(f"[WARN] AI content generation failed: {e}")
            return self._fallback_content_generation(transcript, duration, clip_data)
    
    def _build_content_generation_prompt(self, transcript: str, duration: float, clip_data: Dict) -> str:
        """Build enhanced prompt for content generation"""
        transcript_excerpt = transcript[:800] if len(transcript) > 800 else transcript
        
        key_topic = clip_data.get('key_topic', 'MIH advice')
        target_emotion = clip_data.get('target_emotion', 'educational')
        clip_type = clip_data.get('clip_type', 'educational')
        
        return f"""
**TASK: Create VIRAL YouTube Shorts Content for MIH Dental Clip**

**CLIP DETAILS:**
Duration: {duration:.0f} seconds
Key Topic: {key_topic}
Target Emotion: {target_emotion}
Clip Type: {clip_type}
Content: {transcript_excerpt}

**CREATE CONTENT THAT:**
1. **STOPS THE SCROLL** - Immediate attention grabber
2. **BUILDS AUTHORITY** - Establishes Dr. Greenwall as THE MIH expert
3. **DRIVES ENGAGEMENT** - Encourages likes, comments, shares
4. **TARGETS PARENTS** - Worried parents of kids with dental issues
5. **OPTIMIZES FOR ALGORITHM** - Uses trending formats and keywords

**TITLE FORMULAS TO USE:**
- "The MIH Truth Dentists Don't Tell You"
- "Why Your Child's Teeth Look Like This"
- "I'm a Dentist and This Shocked Me"
- "Stop Doing This to Your Kid's Teeth"
- "The Real Reason Behind White Spots"
- "MIH: What Every Parent Must Know"
- "This Could Save Your Child's Smile"

**DESCRIPTION MUST INCLUDE:**
- Hook question or shocking fact
- Clear value proposition
- Call to action
- Relevant emojis (dental, medical, parenting)
- Authority builder about Dr. Greenwall
- Urgency or importance indicator

**HASHTAG STRATEGY:**
- Mix trending dental hashtags
- Include MIH-specific tags
- Add parenting/kids hashtags
- Include location tags if relevant
- Use 8-12 hashtags total

**KEYWORDS TO INCLUDE:**
MIH, teeth whitening, children's dental health, dental expert, Dr. Linda Greenwall, pediatric dentistry, tooth decay, dental problems, kids teeth

**RETURN EXACTLY THIS JSON:**
```json
{
  "title": "Viral title under 70 characters with hook",
  "description": "Engaging description 150-200 chars with emojis and CTA",
  "hashtags": ["#MIH", "#DentalHealth", "#KidsTeeth", "#Dentist", "#ParentingTips", "#ToothCare", "#DentalExpert", "#ChildrensDentist"],
  "keywords": ["MIH", "children dental health", "Dr Linda Greenwall", "pediatric dentistry"],
  "hook_element": "What makes this scroll-stopping",
  "cta_focus": "Primary call to action",
  "target_audience": "Specific parent demographic"
}
```

**EXAMPLES OF GREAT TITLES:**
- "Why 1 in 6 Kids Have These White Spots" 
- "Dentist Reveals: MIH Treatment That Works"
- "Your Child's Teeth Are Telling You This"
- "The MIH Mistake Every Parent Makes"

**DESCRIPTION EXAMPLES:**
"🦷 Is your child one of the 1 in 6 kids affected by MIH? Dr. Linda Greenwall, Europe's leading MIH expert, reveals the treatment that actually works! 👨‍⚕️✨ Don't wait - early intervention is key! #MIH #DentalHealth"

Create content that makes parents NEED to watch and share!
"""
    
    def _parse_content_response(self, response_text: str) -> Dict:
        """Parse and validate content generation response"""
        try:
            clean_text = response_text.strip()
            if '```json' in clean_text:
                clean_text = clean_text.split('```json')[1].split('```')[0]
            elif '```' in clean_text:
                clean_text = clean_text.split('```')[1].split('```')[0]
            
            content = json.loads(clean_text)
            
            # Validate and enhance content
            return self._validate_and_enhance_content(content)
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse content response: {e}")
            return {}
    
    def _validate_and_enhance_content(self, content: Dict) -> Dict:
        """Validate and enhance generated content"""
        # Ensure required fields with defaults
        title = content.get('title', 'MIH Expert Advice')[:70]
        description = content.get('description', '🦷 Expert MIH advice from Dr. Linda Greenwall')[:200]
        hashtags = content.get('hashtags', ['#MIH', '#DentalCare', '#KidsTeeth'])
        keywords = content.get('keywords', ['MIH', 'dental health'])
        
        # Ensure essential hashtags
        essential_tags = ['#MIH', '#DentalHealth', '#DrGreenwall', '#KidsTeeth']
        for tag in essential_tags:
            if tag not in hashtags:
                hashtags.append(tag)
        
        # Add engagement-boosting elements
        if not any(emoji in description for emoji in ['🦷', '👨‍⚕️', '✨', '❤️']):
            description = '🦷 ' + description
        
        return {
            'title': title,
            'description': description,
            'hashtags': hashtags[:12],  # Limit to 12 hashtags
            'keywords': keywords[:8],   # Limit keywords
            'hook_element': content.get('hook_element', 'Educational content'),
            'cta_focus': content.get('cta_focus', 'Learn more'),
            'target_audience': content.get('target_audience', 'Parents')
        }
    
    def _fallback_clip_detection(self, transcript: str, video_data: Dict) -> List[Dict]:
        """Intelligent fallback clip detection"""
        words = transcript.split()
        if len(words) < 200:
            return []
        
        clips = []
        
        # Look for key phrases that indicate good clips
        hook_phrases = [
            'did you know', 'here\'s why', 'the truth is', 'what you need to know',
            'this is important', 'let me show you', 'the problem is', 'the solution'
        ]
        
        sentences = transcript.split('.')
        good_starts = []
        
        for i, sentence in enumerate(sentences):
            sentence_lower = sentence.lower().strip()
            if any(phrase in sentence_lower for phrase in hook_phrases):
                good_starts.append(i)
        
        # Create clips around good starting points
        for start_idx in good_starts[:2]:
            # Estimate timing (rough: 4 words per second)
            start_words = sum(len(s.split()) for s in sentences[:start_idx])
            start_time = start_words * 0.25
            
            # Create 30-40 second clips
            end_time = start_time + 35
            
            clips.append({
                'start_timestamp': start_time,
                'end_timestamp': end_time,
                'engagement_score': 7.0,
                'key_topic': 'MIH advice',
                'target_emotion': 'educational',
                'clip_type': 'educational'
            })
        
        # Fallback: create clips from beginning and middle
        if not clips:
            total_words = len(words)
            if total_words > 300:
                clips.extend([
                    {
                        'start_timestamp': 30,
                        'end_timestamp': 65,
                        'engagement_score': 6.0,
                        'key_topic': 'MIH introduction',
                        'target_emotion': 'educational',
                        'clip_type': 'educational'
                    },
                    {
                        'start_timestamp': total_words * 0.125,  # Middle section
                        'end_timestamp': total_words * 0.125 + 35,
                        'engagement_score': 6.0,
                        'key_topic': 'MIH treatment',
                        'target_emotion': 'educational',
                        'clip_type': 'educational'
                    }
                ])
        
        logger.info(f"[PROC] Fallback method found {len(clips)} clips")
        return clips
    
    def _fallback_content_generation(self, transcript: str, duration: float, clip_data: Dict) -> Dict:
        """Fallback content generation"""
        key_topic = clip_data.get('key_topic', 'MIH')
        
        # Extract key terms from transcript
        words = transcript.lower().split()
        dental_terms = [w for w in words if w in ['teeth', 'tooth', 'dental', 'mih', 'treatment', 'children', 'kids']]
        
        if dental_terms:
            title = f"MIH Expert: {dental_terms[0].title()} Advice"
        else:
            title = "Dr. Greenwall's MIH Expert Advice"
        
        return {
            'title': title[:70],
            'description': f'🦷 Expert MIH advice from Dr. Linda Greenwall about {key_topic} #MIH #DentalCare',
            'hashtags': ['#MIH', '#DentalHealth', '#KidsTeeth', '#DrGreenwall', '#PediatricDentistry', '#ToothCare'],
            'keywords': ['MIH', 'dental health', 'children teeth', 'Dr Linda Greenwall'],
            'hook_element': 'Educational content',
            'cta_focus': 'Learn more',
            'target_audience': 'Parents'
        }

class TranscriptProcessor(BaseProcessor):
    """Enhanced transcript processing with better timing"""
    
    def extract_transcript(self, video_id: str) -> List[Dict]:
        """Extract transcript with enhanced processing"""
        try:
            logger.info(f"📝 Extracting transcript for {video_id}...")
            srt_file = self.temp_dir / f"{video_id}.en.srt"
            
            if srt_file.exists():
                srt_file.unlink()
            
            cmd = [
                'yt-dlp',
                '--write-auto-subs',
                '--sub-langs', 'en',
                '--sub-format', 'srt',
                '--skip-download',
                '--socket-timeout', '30',
                '--retries', '3',
                '--fragment-retries', '3',
                '--no-warnings',
                '-o', str(self.temp_dir / f"{video_id}.%(ext)s"),
                f'https://www.youtube.com/watch?v={video_id}'
            ]
            
            result = safe_execute(cmd, timeout=120)
            
            if srt_file.exists():
                transcript = self._parse_srt_enhanced(srt_file)
                srt_file.unlink()
                
                if transcript:
                    logger.info(f"✅ Transcript extracted: {len(transcript)} segments")
                    return transcript
                    
        except Exception as e:
            logger.error(f"❌ Transcript extraction failed: {e}")
        
        return []
    
    def _parse_srt_enhanced(self, srt_file: Path) -> List[Dict]:
        """Enhanced SRT parsing with better timing"""
        transcript = []
        
        try:
            with open(srt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            blocks = content.strip().split('\n\n')
            
            for block in blocks:
                if not block.strip():
                    continue
                
                lines = block.strip().split('\n')
                if len(lines) >= 3 and ' --> ' in lines[1]:
                    try:
                        start_str, end_str = lines[1].split(' --> ')
                        start_sec = self._parse_timestamp(start_str)
                        end_sec = self._parse_timestamp(end_str)
                        text = ' '.join(lines[2:])
                        
                        # Enhanced text cleaning
                        text = self._clean_transcript_text(text)
                        
                        if text and end_sec > start_sec >= 0:
                            transcript.append({
                                'text': text,
                                'start': start_sec,
                                'duration': end_sec - start_sec,
                                'end': end_sec
                            })
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Skipping malformed subtitle: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"❌ SRT parsing failed: {e}")
        
        return transcript
    
    def _clean_transcript_text(self, text: str) -> str:
        """Enhanced text cleaning for transcripts"""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove formatting markers
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\(.*?\)', '', text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove filler words and sounds
        filler_words = ['um', 'uh', 'ah', 'er', 'like', 'you know']
        words = text.split()
        cleaned_words = [w for w in words if w.lower() not in filler_words]
        
        return ' '.join(cleaned_words).strip()
    
    def _parse_timestamp(self, timestamp: str) -> float:
        """Parse SRT timestamp to seconds"""
        try:
            time_part, ms_part = timestamp.split(',')
            h, m, s = map(int, time_part.split(':'))
            return h * 3600 + m * 60 + s + int(ms_part) / 1000.0
        except:
            return 0.0
    
    def create_enhanced_subtitles(self, transcript: List[Dict], start_time: float, end_time: float) -> List[Dict]:
        """Create enhanced subtitle segments for clips"""
        segments = []
        
        for item in transcript:
            item_start = item['start']
            item_end = item['end']
            
            # Check overlap with clip timeframe
            if item_end >= start_time and item_start <= end_time:
                # Adjust timing relative to clip start
                segment_start = max(0, item_start - start_time)
                segment_end = min(end_time - start_time, item_end - start_time)
                
                if segment_end > segment_start:
                    # Split long texts for better readability
                    text = item['text']
                    if len(text) > 50:
                        words = text.split()
                        mid = len(words) // 2
                        text = ' '.join(words[:mid]) + '\n' + ' '.join(words[mid:])
                    
                    segments.append({
                        'start': segment_start,
                        'end': segment_end,
                        'text': text,
                        'words': len(text.split())
                    })
        
        # Ensure readable durations
        for segment in segments:
            min_duration = max(1.5, segment['words'] * 0.3)  # 0.3 seconds per word
            if segment['end'] - segment['start'] < min_duration:
                segment['end'] = segment['start'] + min_duration
        
        return segments

class EnhancedVideoProcessor(BaseProcessor):
    """Enhanced video processing with audio and visual improvements"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.audio_processor = AudioProcessor(config)
        self.visual_processor = VisualProcessor(config)
        self.transcript_processor = TranscriptProcessor(config)
        self.output_dir = Path(config.get('output_dir', 'processed_videos'))
        self.output_dir.mkdir(exist_ok=True)
    
    def download_source_video(self, video_id: str) -> str:
        """Download source video with quality optimization"""
        try:
            logger.info(f"📥 Downloading video {video_id}...")
            output_pattern = self.output_dir / f"{video_id}.%(ext)s"
            
            cmd = [
                'yt-dlp',
                '-f', 'best[height<=1080]/best',  # Limit to 1080p
                '--socket-timeout', '30',
                '--retries', '3',
                '--fragment-retries', '3',
                '--no-warnings',
                '--no-playlist',
                '-o', str(output_pattern),
                f'https://www.youtube.com/watch?v={video_id}'
            ]
            
            result = safe_execute(cmd, timeout=600)  # 10 minutes
            
            if result.returncode == 0:
                for file in self.output_dir.glob(f"{video_id}.*"):
                    if file.suffix in ['.mp4', '.webm', '.mkv']:
                        file_size = file.stat().st_size // 1024 // 1024
                        logger.info(f"✅ Downloaded: {file.name} ({file_size} MB)")
                        return str(file)
            
            logger.error("❌ Video download failed")
            
        except Exception as e:
            logger.error(f"❌ Download error: {e}")
        
        return ""
    
    def create_enhanced_clip(self, input_file: str, clip_data: VideoClip) -> bool:
        """Create enhanced clip with audio and visual improvements"""
        try:
            start_time = clip_data.start_time
            end_time = clip_data.end_time
            duration = end_time - start_time
            
            if not (20 <= duration <= 65):
                logger.warning(f"⚠️ Invalid duration: {duration}s")
                return False
            
            logger.info(f"🎬 Creating enhanced clip: {duration:.1f}s")
            
            # Step 1: Create intro with TTS
            intro_file = ""
            if clip_data.title:
                intro_file = self._create_intro_with_audio(clip_data.title)
            
            # Step 2: Create outro with TTS
            outro_file = self._create_outro_with_audio()
            
            # Step 3: Extract and enhance main clip
            main_clip = self._extract_enhanced_clip(
                input_file, start_time, end_time, 
                clip_data.title, clip_data.subtitle_segments
            )
            
            if not main_clip:
                logger.error("❌ Main clip extraction failed")
                return False
            
            # Step 4: Add background music to main clip
            enhanced_main = self.temp_dir / f"enhanced_main_{uuid.uuid4().hex[:8]}.mp4"
            self.audio_processor.add_background_music(main_clip, str(enhanced_main), "upbeat")
            
            # Step 5: Combine all parts
            parts = []
            if intro_file:
                parts.append(intro_file)
            parts.append(str(enhanced_main))
            if outro_file:
                parts.append(outro_file)
            
            success = self._combine_parts_safely(parts, clip_data.file_path)
            
            # Cleanup temporary files
            temp_files = [intro_file, outro_file, main_clip, str(enhanced_main)]
            for temp_file in temp_files:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
            
            if success:
                logger.info(f"✅ Enhanced clip created: {os.path.basename(clip_data.file_path)}")
                return True
            
        except Exception as e:
            logger.error(f"❌ Enhanced clip creation failed: {e}")
        
        return False
    
    def _create_intro_with_audio(self, title: str) -> str:
        """Create intro with TTS audio"""
        try:
            # Create visual intro
            visual_intro = self.visual_processor.create_animated_intro(title, 3.0)
            if not visual_intro:
                return ""
            
            # Create TTS audio
            audio_file = self.temp_dir / f"intro_audio_{uuid.uuid4().hex[:8]}.aac"
            tts_audio = self.audio_processor.create_tts_audio(title, str(audio_file))
            
            if not tts_audio:
                return visual_intro
            
            # Combine visual and audio
            output_file = self.temp_dir / f"intro_with_audio_{uuid.uuid4().hex[:8]}.mp4"
            
            cmd = [
                'ffmpeg', '-y', '-i', visual_intro,
                '-i', tts_audio,
                '-c:v', 'copy', '-c:a', 'aac',
                '-shortest',
                str(output_file)
            ]
            
            result = safe_execute(cmd, timeout=60)
            
            # Cleanup
            if os.path.exists(visual_intro):
                os.remove(visual_intro)
            if os.path.exists(tts_audio):
                os.remove(tts_audio)
            
            if result.returncode == 0 and output_file.exists():
                return str(output_file)
            
        except Exception as e:
            logger.warning(f"⚠️ Intro with audio failed: {e}")
        
        return ""
    
    def _create_outro_with_audio(self) -> str:
        """Create outro with TTS audio"""
        try:
            # Create visual outro
            visual_outro = self.visual_processor.create_animated_outro(3.0)
            if not visual_outro:
                return ""
            
            # Create TTS audio
            audio_file = self.temp_dir / f"outro_audio_{uuid.uuid4().hex[:8]}.aac"
            tts_audio = self.audio_processor.create_tts_audio("Please like and subscribe", str(audio_file))
            
            if not tts_audio:
                return visual_outro
            
            # Combine visual and audio
            output_file = self.temp_dir / f"outro_with_audio_{uuid.uuid4().hex[:8]}.mp4"
            
            cmd = [
                'ffmpeg', '-y', '-i', visual_outro,
                '-i', tts_audio,
                '-c:v', 'copy', '-c:a', 'aac',
                '-shortest',
                str(output_file)
            ]
            
            result = safe_execute(cmd, timeout=60)
            
            # Cleanup
            if os.path.exists(visual_outro):
                os.remove(visual_outro)
            if os.path.exists(tts_audio):
                os.remove(tts_audio)
            
            if result.returncode == 0 and output_file.exists():
                return str(output_file)
                
        except Exception as e:
            logger.warning(f"⚠️ Outro with audio failed: {e}")
        
        return ""
    
    def _extract_enhanced_clip(self, input_file: str, start_time: float, end_time: float,
                             title: str, subtitle_segments: List[Dict]) -> str:
        """Extract and enhance main clip"""
        try:
            duration = end_time - start_time
            temp_output = self.temp_dir / f"enhanced_clip_{uuid.uuid4().hex[:8]}.mp4"
            
            # Extract base clip first
            base_clip = self.temp_dir / f"base_clip_{uuid.uuid4().hex[:8]}.mp4"
            
            cmd = [
                'ffmpeg', '-y', '-i', input_file,
                '-ss', str(start_time),
                '-t', str(duration),
                '-c', 'copy',
                str(base_clip)
            ]
            
            result = safe_execute(cmd, timeout=120)
            
            if result.returncode != 0 or not base_clip.exists():
                logger.error("❌ Base clip extraction failed")
                return ""
            
            # Apply visual enhancements
            success = self.visual_processor.enhance_clip_visuals(
                str(base_clip), str(temp_output), title, subtitle_segments
            )
            
            # Cleanup base clip
            if base_clip.exists():
                base_clip.unlink()
            
            if success and temp_output.exists():
                return str(temp_output)
            
        except Exception as e:
            logger.error(f"❌ Enhanced clip extraction failed: {e}")
        
        return ""
    
    def _combine_parts_safely(self, parts: List[str], output_file: str) -> bool:
        """Safely combine video parts"""
        try:
            # Filter out empty/missing parts
            valid_parts = [part for part in parts if part and os.path.exists(part)]
            
            if not valid_parts:
                logger.error("❌ No valid parts to combine")
                return False
            
            if len(valid_parts) == 1:
                # Just copy single file
                shutil.copy2(valid_parts[0], output_file)
                return True
            
            # Create concat file
            concat_file = self.temp_dir / f"concat_{uuid.uuid4().hex[:8]}.txt"
            
            with open(concat_file, 'w', encoding='utf-8') as f:
                for part in valid_parts:
                    abs_path = os.path.abspath(part).replace('\\', '/')
                    f.write(f"file '{abs_path}'\n")
            
            # Concatenate
            cmd = [
                'ffmpeg', '-y', '-f', 'concat',
                '-safe', '0', '-i', str(concat_file),
                '-c:v', 'libx264', '-c:a', 'aac',
                '-preset', 'fast', '-crf', '23',
                output_file
            ]
            
            result = safe_execute(cmd, timeout=180)
            
            # Cleanup
            if concat_file.exists():
                concat_file.unlink()
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"❌ Parts combination failed: {e}")
            return False

class EnhancedYouTubeManager(BaseProcessor):
    """Enhanced YouTube upload manager"""
    
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.api_key = config['youtube_api_key']
        self.channel_configs = config['upload_channels']
        self.youtube_services = {}
        self._authenticate_channels()
    
    def _authenticate_channels(self):
        """Authenticate YouTube channels"""
        for i, config in enumerate(self.channel_configs):
            channel_key = f"channel_{i+1}"
            creds_file = config.get('credentials_file')
            
            if not creds_file or not os.path.exists(creds_file):
                logger.error(f"❌ Missing credentials for {config.get('name', 'channel')}")
                continue
            
            try:
                logger.info(f"🔑 Authenticating {config.get('name', 'channel')}...")
                
                creds = None
                token_file = f'token_{channel_key}.json'
                
                if os.path.exists(token_file):
                    creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
                
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        flow = InstalledAppFlow.from_client_secrets_file(creds_file, self.SCOPES)
                        creds = flow.run_local_server(port=0, timeout_seconds=120)
                    
                    with open(token_file, 'w') as token:
                        token.write(creds.to_json())
                
                service = build('youtube', 'v3', credentials=creds)
                self.youtube_services[channel_key] = {
                    'service': service, 
                    'config': config
                }
                logger.info(f"✅ Authenticated: {config.get('name', 'channel')}")
                
            except Exception as e:
                logger.error(f"❌ Auth failed for {config.get('name', 'channel')}: {e}")
    
    def upload_enhanced_clip(self, clip: VideoClip) -> Dict:
        """Upload clip to all channels with enhanced metadata"""
        results = {}
        
        if not clip.file_path or not os.path.exists(clip.file_path):
            logger.error(f"❌ Clip file not found: {clip.file_path}")
            return results
        
        file_size = os.path.getsize(clip.file_path)
        logger.info(f"📤 Uploading: {os.path.basename(clip.file_path)} ({file_size // 1024 // 1024} MB)")
        
        for channel_key, data in self.youtube_services.items():
            try:
                service = data['service']
                config = data['config']
                channel_name = config.get('name', 'Channel')
                
                logger.info(f"📺 Uploading to {channel_name}...")
                
                # Enhanced metadata
                metadata = self._build_enhanced_metadata(clip, config)
                
                media = MediaFileUpload(clip.file_path, resumable=True)
                request = service.videos().insert(
                    part=','.join(metadata.keys()),
                    body=metadata,
                    media_body=media
                )
                
                # Upload with progress tracking
                response = self._execute_upload_with_progress(request, channel_name)
                
                if response and 'id' in response:
                    video_id = response['id']
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    results[channel_key] = {
                        'status': 'success',
                        'video_id': video_id,
                        'url': video_url,
                        'channel_name': channel_name
                    }
                    logger.info(f"✅ {channel_name}: {video_url}")
                else:
                    results[channel_key] = {
                        'status': 'failed',
                        'error': 'Upload failed',
                        'channel_name': channel_name
                    }
                    
            except Exception as e:
                results[channel_key] = {
                    'status': 'failed',
                    'error': str(e),
                    'channel_name': config.get('name', 'Channel')
                }
                logger.error(f"❌ Upload to {config.get('name', 'channel')} failed: {e}")
            
            # Rate limiting
            if len(self.youtube_services) > 1:
                time.sleep(45)
        
        return results
    
    def _build_enhanced_metadata(self, clip: VideoClip, channel_config: Dict) -> Dict:
        """Build enhanced metadata for upload"""
        # Enhanced description with more details
        enhanced_description = self._build_enhanced_description(clip)
        
        # Enhanced tags
        enhanced_tags = self._build_enhanced_tags(clip)
        
        return {
            'snippet': {
                'title': clip.title[:100],
                'description': enhanced_description[:5000],
                'tags': enhanced_tags[:15],
                'categoryId': '27',  # Education
                'defaultLanguage': 'en',
                'defaultAudioLanguage': 'en'
            },
            'status': {
                'privacyStatus': 'public',
                'selfDeclaredMadeForKids': False
            }
        }
    
    def _build_enhanced_description(self, clip: VideoClip) -> str:
        """Build enhanced description with SEO optimization"""
        description_parts = []
        
        # Main description
        description_parts.append(clip.description)
        description_parts.append("")
        
        # About Dr. Greenwall
        description_parts.extend([
            "👨‍⚕️ About Dr. Linda Greenwall:",
            "Europe's leading MIH (Molar Incisor Hypomineralization) expert",
            "Specialist in pediatric dentistry and children's oral health",
            "Author of numerous research papers on MIH treatment",
            ""
        ])
        
        # Key information
        if clip.keywords:
            description_parts.extend([
                "🔍 Key Topics:",
                " • " + "\n • ".join(clip.keywords[:5]),
                ""
            ])
        
        # Call to action
        description_parts.extend([
            "📞 Need MIH treatment advice?",
            "Contact Dr. Greenwall's clinic for consultation",
            "",
            "👍 Found this helpful? Please LIKE and SUBSCRIBE!",
            "🔔 Turn on notifications for more MIH expert advice",
            ""
        ])
        
        # Hashtags
        if clip.hashtags:
            description_parts.append(" ".join(clip.hashtags))
        
        # Disclaimer
        description_parts.extend([
            "",
            "⚠️ Disclaimer: This content is for educational purposes only.",
            "Always consult with a qualified dentist for personalized advice.",
            "",
            f"📹 Original video: {clip.source_url}",
            f"⏱️ Clip duration: {clip.duration:.0f} seconds",
            f"🆔 Clip ID: {clip.clip_id[:8]}"
        ])
        
        return "\n".join(description_parts)
    
    def _build_enhanced_tags(self, clip: VideoClip) -> List[str]:
        """Build enhanced tags for SEO"""
        tags = set()
        
        # Original hashtags (remove # symbol)
        for tag in clip.hashtags:
            clean_tag = tag.replace('#', '').strip()
            if clean_tag:
                tags.add(clean_tag)
        
        # Keywords
        for keyword in clip.keywords:
            tags.add(keyword)
        
        # Additional MIH-related tags
        mih_tags = [
            'MIH treatment', 'children dental health', 'pediatric dentistry',
            'tooth discoloration', 'dental expert advice', 'kids teeth problems',
            'molar incisor hypomineralization', 'dental education', 'oral health'
        ]
        
        for tag in mih_tags:
            tags.add(tag)
        
        # Location-based tags
        location_tags = ['UK dentist', 'London dental expert', 'European MIH specialist']
        for tag in location_tags:
            tags.add(tag)
        
        # Convert to list and limit
        return list(tags)[:15]
    
    def _execute_upload_with_progress(self, request, channel_name: str):
        """Execute upload with progress tracking"""
        response = None
        last_progress = 0
        upload_start = time.time()
        max_upload_time = 900  # 15 minutes
        
        while response is None:
            try:
                # Check timeout
                if time.time() - upload_start > max_upload_time:
                    logger.error(f"❌ Upload to {channel_name} timed out")
                    break
                
                status, response = request.next_chunk()
                
                if status:
                    progress = int(status.progress() * 100)
                    if progress >= last_progress + 25:  # Log every 25%
                        logger.info(f"📊 {channel_name}: {progress}% uploaded")
                        last_progress = progress
                        
            except Exception as e:
                logger.error(f"❌ Upload error for {channel_name}: {e}")
                break
        
        return response

class EnhancedMIHAutomation:
    """Main enhanced automation system"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.content_generator = EnhancedContentGenerator(config)
        self.video_processor = EnhancedVideoProcessor(config)
        self.youtube_manager = EnhancedYouTubeManager(config)
        self.processed_videos = self._load_processed_videos()
        
        # Performance tracking
        self.stats = {
            'videos_processed': 0,
            'clips_created': 0,
            'uploads_successful': 0,
            'processing_time': 0
        }
    
    def _load_processed_videos(self) -> set:
        """Load processed videos list"""
        try:
            if os.path.exists('processed_videos.json'):
                with open('processed_videos.json', 'r') as f:
                    return set(json.load(f))
        except Exception as e:
            logger.warning(f"⚠️ Could not load processed videos: {e}")
        return set()
    
    def _save_processed_videos(self):
        """Save processed videos list"""
        try:
            with open('processed_videos.json', 'w') as f:
                json.dump(list(self.processed_videos), f)
        except Exception as e:
            logger.warning(f"⚠️ Could not save processed videos: {e}")
    
    def process_video_enhanced(self, video_data: Dict) -> List[VideoClip]:
        """Enhanced video processing pipeline"""
        video_id = video_data['id']
        processing_start = time.time()
        max_processing_time = 2400  # 40 minutes
        
        logger.info(f"🎬 Enhanced processing: {video_data['title'][:50]}...")
        
        try:
            # Step 1: Extract transcript
            transcript = self.video_processor.transcript_processor.extract_transcript(video_id)
            if not transcript:
                logger.error("❌ No transcript available")
                return []
            
            # Step 2: Find viral clips with AI
            full_transcript = ' '.join([item['text'] for item in transcript])
            clip_data_list = self.content_generator.find_viral_clips(full_transcript, video_data)
            
            if not clip_data_list:
                logger.error("❌ No viral clips found")
                return []
            
            # Step 3: Download source video
            source_video = self.video_processor.download_source_video(video_id)
            if not source_video:
                logger.error("❌ Video download failed")
                return []
            
            # Step 4: Process each clip
            created_clips = []
            
            for i, clip_data in enumerate(clip_data_list):
                # Check timeout
                if time.time() - processing_start > max_processing_time:
                    logger.warning(f"⚠️ Timeout reached, stopping at clip {i+1}")
                    break
                
                logger.info(f"🎬 Processing viral clip {i+1}/{len(clip_data_list)}...")
                
                start_time = float(clip_data['start_timestamp'])
                end_time = float(clip_data['end_timestamp'])
                duration = end_time - start_time
                
                # Extract clip transcript
                clip_transcript = self._extract_clip_transcript(transcript, start_time, end_time)
                
                # Generate viral content
                content = self.content_generator.generate_viral_content(
                    clip_transcript, duration, clip_data
                )
                
                # Create subtitle segments
                subtitle_segments = self.video_processor.transcript_processor.create_enhanced_subtitles(
                    transcript, start_time, end_time
                )
                
                # Create output filename
                timestamp = int(time.time())
                safe_title = re.sub(r'[^\w\-_\.]', '_', content['title'][:30])
                output_file = f"viral_clip_{video_id}_{i+1}_{safe_title}_{timestamp}.mp4"
                output_path = self.video_processor.output_dir / output_file
                
                # Create enhanced video clip object
                clip = VideoClip(
                    clip_id=str(uuid.uuid4()),
                    start_time=start_time,
                    end_time=end_time,
                    transcript=clip_transcript,
                    source_video_id=video_id,
                    source_title=video_data['title'],
                    source_url=video_data['url'],
                    title=content['title'],
                    description=content['description'],
                    hashtags=content['hashtags'],
                    keywords=content['keywords'],
                    engagement_score=clip_data.get('engagement_score', 7.0),
                    file_path=str(output_path),
                    subtitle_segments=subtitle_segments,
                    visual_effects=['enhanced_colors', 'progress_bar', 'watermark'],
                    audio_features={'tts_intro': True, 'tts_outro': True, 'background_music': True}
                )
                
                # Create enhanced clip with audio and visuals
                success = self.video_processor.create_enhanced_clip(source_video, clip)
                
                if success and os.path.exists(str(output_path)):
                    created_clips.append(clip)
                    logger.info(f"✅ Viral clip {i+1} created: {duration:.1f}s")
                    self.stats['clips_created'] += 1
                else:
                    logger.error(f"❌ Failed to create clip {i+1}")
            
            # Cleanup source video
            if source_video and os.path.exists(source_video):
                try:
                    os.remove(source_video)
                except:
                    pass
            
            # Update stats
            self.processed_videos.add(video_id)
            self._save_processed_videos()
            self.stats['videos_processed'] += 1
            self.stats['processing_time'] += time.time() - processing_start
            
            logger.info(f"🎉 Enhanced processing complete: {len(created_clips)} viral clips created")
            return created_clips
            
        except Exception as e:
            logger.error(f"❌ Enhanced processing failed: {e}")
            return []
    
    def _extract_clip_transcript(self, transcript: List[Dict], start_time: float, end_time: float) -> str:
        """Extract transcript text for clip timeframe"""
        clip_texts = []
        
        for item in transcript:
            item_start = item['start']
            item_end = item['end']
            
            if item_end >= start_time and item_start <= end_time:
                clip_texts.append(item['text'])
        
        return ' '.join(clip_texts)
    
    def publish_viral_clips(self, clips: List[VideoClip]):
        """Publish clips with enhanced upload process"""
        if not clips:
            logger.info("❌ No clips to publish")
            return
        
        logger.info(f"📤 Publishing {len(clips)} viral clips...")
        
        for i, clip in enumerate(clips):
            logger.info(f"📤 Publishing viral clip {i+1}: {clip.title[:40]}...")
            
            try:
                results = self.youtube_manager.upload_enhanced_clip(clip)
                
                successful = sum(1 for r in results.values() if r.get('status') == 'success')
                total = len(results)
                
                logger.info(f"📊 Upload results for clip {i+1}: {successful}/{total} successful")
                
                # Log results
                for channel_key, result in results.items():
                    if result['status'] == 'success':
                        logger.info(f"✅ {result['channel_name']}: {result['url']}")
                        self.stats['uploads_successful'] += 1
                    else:
                        logger.error(f"❌ {result.get('channel_name', channel_key)}: {result['error']}")
                
                # Generate performance report
                self._log_clip_performance(clip, results)
                        
            except Exception as e:
                logger.error(f"❌ Error publishing clip {i+1}: {e}")
            
            finally:
                # Cleanup clip file
                if clip.file_path and os.path.exists(clip.file_path):
                    try:
                        os.remove(clip.file_path)
                    except:
                        pass
            
            # Rate limiting
            if i < len(clips) - 1:
                logger.info("⏱️ Waiting 60 seconds before next upload...")
                time.sleep(60)
        
        logger.info("🎉 All viral clips published!")
        self._generate_session_report()
    
    def _log_clip_performance(self, clip: VideoClip, results: Dict):
        """Log clip performance metrics"""
        performance_data = {
            'clip_id': clip.clip_id,
            'title': clip.title,
            'duration': clip.duration,
            'engagement_score': clip.engagement_score,
            'upload_results': results,
            'timestamp': datetime.now().isoformat(),
            'audio_features': clip.audio_features,
            'visual_effects': clip.visual_effects
        }
        
        # Save to performance log
        try:
            performance_file = 'clip_performance.jsonl'
            with open(performance_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(performance_data) + '\n')
        except Exception as e:
            logger.warning(f"⚠️ Could not log performance: {e}")
    
    def _generate_session_report(self):
        """Generate session performance report"""
        report = f"""
🎉 SESSION COMPLETE - ENHANCED MIH AUTOMATION REPORT
{'='*60}
📊 PERFORMANCE METRICS:
   Videos Processed: {self.stats['videos_processed']}
   Clips Created: {self.stats['clips_created']}
   Uploads Successful: {self.stats['uploads_successful']}
   Total Processing Time: {self.stats['processing_time']:.1f} seconds
   Average Time per Video: {self.stats['processing_time']/max(1, self.stats['videos_processed']):.1f} seconds

✨ ENHANCED FEATURES USED:
   🎤 TTS Audio (Intro/Outro)
   🎵 Background Music
   🎨 Visual Enhancements  
   📝 AI-Generated Content
   🔥 Viral Optimization
   📺 Multi-Channel Upload

🚀 SUCCESS RATE: {(self.stats['uploads_successful']/(max(1, self.stats['clips_created'])*len(self.youtube_manager.youtube_services)))*100:.1f}%
"""
        
        logger.info(report)
        
        # Save report to file
        try:
            with open(f'session_report_{int(time.time())}.txt', 'w') as f:
                f.write(report)
        except:
            pass
    
    def test_single_video_enhanced(self, video_id: str):
        """Enhanced single video test"""
        logger.info(f"🧪 Enhanced testing: {video_id}")
        test_start = time.time()
        max_test_time = 3000  # 50 minutes
        
        try:
            # Get video details
            youtube = build('youtube', 'v3', developerKey=self.config['youtube_api_key'])
            video_details = youtube.videos().list(part='snippet', id=video_id).execute()
            
            if not video_details['items']:
                logger.error("❌ Video not found")
                return
            
            video_item = video_details['items'][0]
            video_data = {
                'id': video_id,
                'title': video_item['snippet']['title'],
                'description': video_item['snippet']['description'],
                'url': f"https://www.youtube.com/watch?v={video_id}"
            }
            
            logger.info(f"🎬 Enhanced Video: {video_data['title'][:60]}...")
            
            # Process with enhanced pipeline
            clips = self.process_video_enhanced(video_data)
            
            if time.time() - test_start > max_test_time:
                logger.error("❌ Test timed out")
                self._cleanup_clips(clips)
                return
            
            if clips:
                logger.info(f"🎉 SUCCESS! Created {len(clips)} enhanced viral clips")
                
                # Display enhanced clip information
                for i, clip in enumerate(clips, 1):
                    logger.info(f"📋 ENHANCED CLIP {i}:")
                    logger.info(f"   🎬 Title: {clip.title}")
                    logger.info(f"   ⏱️ Duration: {clip.duration:.1f}s")
                    logger.info(f"   🔥 Engagement Score: {clip.engagement_score:.1f}/10")
                    logger.info(f"   🎤 Audio Features: {', '.join(f'{k}={v}' for k, v in clip.audio_features.items())}")
                    logger.info(f"   🎨 Visual Effects: {', '.join(clip.visual_effects)}")
                    logger.info(f"   📝 Subtitles: {len(clip.subtitle_segments)} segments")
                    logger.info(f"   🏷️ Keywords: {', '.join(clip.keywords[:5])}")
                
                # Enhanced publishing prompt
                try:
                    logger.info("\n📤 Publish enhanced clips to all channels? (y/n): ")
                    logger.info("⏰ You have 90 seconds to respond...")
                    
                    # Cross-platform input with timeout
                    publish = self._get_user_input_with_timeout(90)
                    
                    if publish == 'y':
                        self.publish_viral_clips(clips)
                        logger.info("🎉 Enhanced publishing complete!")
                    elif publish == "timeout":
                        logger.info("⏰ No response received, clips ready for manual upload")
                    else:
                        logger.info("📋 Enhanced clips ready for manual upload")
                        
                except Exception as e:
                    logger.info(f"📋 Enhanced clips created, input error: {e}")
            else:
                logger.error("❌ No enhanced clips could be created")
                
        except Exception as e:
            logger.error(f"❌ Enhanced test failed: {e}")
        finally:
            total_test_time = time.time() - test_start
            logger.info(f"🏁 Enhanced test completed in {total_test_time:.1f} seconds")
    
    def _get_user_input_with_timeout(self, timeout_seconds: int) -> str:
        """Get user input with cross-platform timeout"""
        if sys.platform != "win32":
            # Unix/Linux/Mac
            if select.select([sys.stdin], [], [], timeout_seconds) == ([sys.stdin], [], []):
                return input().lower().strip()
            else:
                return "timeout"
        else:
            # Windows
            q = queue.Queue()
            
            def get_input():
                try:
                    q.put(input().lower().strip())
                except:
                    q.put("error")
            
            t = threading.Thread(target=get_input)
            t.daemon = True
            t.start()
            
            try:
                return q.get(timeout=timeout_seconds)
            except queue.Empty:
                return "timeout"
    
    def _cleanup_clips(self, clips: List[VideoClip]):
        """Cleanup clip files"""
        for clip in clips:
            if clip.file_path and os.path.exists(clip.file_path):
                try:
                    os.remove(clip.file_path)
                except:
                    pass
    
    def cleanup(self):
        """Comprehensive system cleanup"""
        try:
            self.content_generator.cleanup()
            self.video_processor.cleanup()
            self.video_processor.audio_processor.cleanup()
            self.video_processor.visual_processor.cleanup()
            self.video_processor.transcript_processor.cleanup()
            self.youtube_manager.cleanup()
            
            logger.info("🧹 Enhanced system cleanup complete")
        except Exception as e:
            logger.warning(f"⚠️ Cleanup error: {e}")

def main():
    """Enhanced main function"""
    print("ENHANCED MIH CONTENT AUTOMATION SYSTEM v2.0")
    print("=" * 60)
    print("NEW FEATURES:")
    print("  [AUDIO] TTS Audio (Intro/Outro with voice)")
    print("  [MUSIC] Background Music")
    print("  [VISUAL] Enhanced Visual Effects")
    print("  [AI] AI Viral Content Generation")
    print("  [ANALYTICS] Performance Tracking")
    print("  [SEO] SEO-Optimized Uploads")
    print("=" * 60)
    
    try:
        # Load enhanced configuration
        try:
            import config
            automation_config = {
                'youtube_api_key': config.YOUTUBE_API_KEY,
                'upload_channels': config.UPLOAD_CHANNELS,
                'gemini_api_key': config.GEMINI_API_KEY,
                'output_dir': getattr(config, 'OUTPUT_DIR', 'processed_videos'),
                'audio_config': getattr(config, 'AUDIO_CONFIG', {}),
                'visual_config': getattr(config, 'VISUAL_CONFIG', {})
            }
            
            logger.info("[OK] Enhanced configuration loaded")
            
        except ImportError:
            logger.error("[ERROR] Config file not found. Create config.py with enhanced settings:")
            print("\n" + "="*60)
            print("# config.py - Enhanced Configuration")
            print("="*60)
            print()
            print("# API Keys")
            print("YOUTUBE_API_KEY = 'your_youtube_api_key'")
            print("GEMINI_API_KEY = 'your_gemini_api_key'")
            print()
            print("# Upload Channels")
            print("UPLOAD_CHANNELS = [")
            print("    {'name': 'MIH Expert Channel', 'credentials_file': 'channel1.json'},")
            print("    {'name': 'Kids Dental Care', 'credentials_file': 'channel2.json'}")
            print("]")
            print()
            print("# Enhanced Settings")
            print("OUTPUT_DIR = 'viral_clips'")
            print("AUDIO_CONFIG = {")
            print("    'tts_voice': 'en-US-Neural2-F',")
            print("    'background_music': True,")
            print("    'master_volume': 0.8")
            print("}")
            print("VISUAL_CONFIG = {")
            print("    'resolution': (1080, 1920),")
            print("    'enhanced_effects': True,")
            print("    'animations': True")
            print("}")
            print("="*60)
            return
        
        # Validate dependencies
        dependencies = [
            ('ffmpeg', 'FFmpeg'),
            ('yt-dlp', 'yt-dlp'),
            ('espeak', 'eSpeak TTS (optional)')
        ]
        
        missing_deps = []
        for cmd, name in dependencies:
            try:
                safe_execute([cmd, '--version'], timeout=5)
                logger.info(f"[OK] {name} detected")
            except:
                if cmd != 'espeak':  # eSpeak is optional
                    missing_deps.append(name)
                else:
                    logger.info(f"[INFO] {name} not found (TTS will be disabled)")
        
        if missing_deps:
            logger.error(f"[ERROR] Missing dependencies: {', '.join(missing_deps)}")
            return
        
        # Initialize enhanced system
        logger.info("[INIT] Initializing Enhanced MIH Automation System v2.0...")
        automation = EnhancedMIHAutomation(automation_config)
        
        # Parse command line arguments
        if len(sys.argv) > 1:
            if sys.argv[1] == '--test' and len(sys.argv) > 2:
                video_id = sys.argv[2]
                automation.test_single_video_enhanced(video_id)
            elif sys.argv[1] == '--help':
                print("\nEnhanced Usage Instructions:")
                print("=" * 40)
                print("Test enhanced processing:")
                print("  python automation_v2.py --test VIDEO_ID")
                print()
                print("Performance tracking:")
                print("  python automation_v2.py --stats")
                print()
                print("Enhanced Features:")
                print("  [TTS] TTS intro/outro with voice")
                print("  [MUSIC] Background music integration")
                print("  [VISUAL] Advanced visual effects")
                print("  [AI] AI-powered viral optimization")
                print("  [SEO] SEO-optimized descriptions")
                print("  [ANALYTICS] Performance analytics")
                print()
                print("Timeout: 50 minutes per test")
            else:
                logger.error("[ERROR] Unknown command. Use --help for instructions")
        else:
            logger.info("[INFO] Usage: python automation_v2.py --test VIDEO_ID")
            logger.info("[INFO] Example: python automation_v2.py --test uaHNk_fPzgA")
            logger.info("[INFO] Use --help for detailed instructions")
                
    except KeyboardInterrupt:
        logger.info("[INFO] Process interrupted by user")
    except Exception as e:
        logger.error(f"[ERROR] Enhanced system error: {e}")
    finally:
        try:
            if 'automation' in locals():
                automation.cleanup()
        except:
            pass

if __name__ == "__main__":
    main()

"""
🎉 ENHANCED MIH AUTOMATION SYSTEM v2.0 - COMPLETE REDESIGN
================================================================

🚀 NEW FEATURES:
✅ TTS Audio Integration (Intro/Outro with voice)
✅ Background Music for enhanced engagement
✅ Advanced Visual Effects & Animations
✅ AI-Powered Viral Content Generation  
✅ Enhanced Prompts for better AI results
✅ SEO-Optimized Descriptions & Tags
✅ Performance Analytics & Tracking
✅ Modular Architecture for easy maintenance
✅ Cross-platform compatibility
✅ Enhanced error handling & recovery

🎤 AUDIO ENHANCEMENTS:
- TTS intro with video title
- TTS outro "Please like and subscribe"
- Background music integration
- Audio normalization & quality control
- Multi-platform TTS support (eSpeak, macOS say)

🎨 VISUAL IMPROVEMENTS:
- Animated intro with gradient backgrounds
- Enhanced outro with call-to-action buttons
- Progress bars and visual indicators
- Dynamic subtitle styling
- Channel watermarks and branding
- GPU-accelerated rendering when available

🤖 AI OPTIMIZATION:
- Viral clip detection with engagement scoring
- Enhanced content generation prompts
- Hook factor analysis for better retention
- Target emotion identification
- SEO keyword optimization
- Trending format integration

📊 PERFORMANCE FEATURES:
- Upload success tracking
- Processing time monitoring
- Engagement score calculation
- Performance report generation
- Session analytics
- Clip performance logging

🔧 TECHNICAL IMPROVEMENTS:
- Modular class-based architecture
- Enhanced error handling & recovery
- Cross-platform timeout handling
- Memory optimization
- Resource cleanup automation
- Comprehensive logging

📖 USAGE:
python automation_v2.py --test VIDEO_ID

🎯 EXAMPLE:
python automation_v2.py --test uaHNk_fPzgA

⚠️ REQUIREMENTS:
- FFmpeg (video processing)
- yt-dlp (video downloading)
- eSpeak or macOS say (TTS, optional)
- Google Gemini API key
- YouTube Data API key
- YouTube OAuth credentials

🚀 INSTALLATION:
1. Install dependencies: pip install google-generativeai google-api-python-client
2. Install FFmpeg: https://ffmpeg.org/download.html
3. Install yt-dlp: pip install yt-dlp
4. Install eSpeak (optional): apt-get install espeak (Linux) or brew install espeak (macOS)
5. Create config.py with your API keys and credentials
6. Run: python automation_v2.py --test VIDEO_ID

🎊 RESULT:
- Creates viral-optimized short clips (20-60 seconds)
- Adds TTS intro/outro with voice
- Applies background music and visual effects
- Generates SEO-optimized titles and descriptions
- Uploads to multiple YouTube channels
- Provides detailed performance analytics

This enhanced version focuses on creating viral, engaging content with
professional audio/visual quality and AI-optimized metadata for maximum
reach and engagement on YouTube Shorts.
"""