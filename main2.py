"""
Enhanced MIH Content Automation System - Fixed Version
Features: Intro, Outro, Subtitles, Graphics, AI Content Generation
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
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path

import google.generativeai as genai
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class VideoClip:
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
    file_path: Optional[str] = None
    duration: float = 0.0
    subtitle_segments: List[Dict] = None
    
    def __post_init__(self):
        if self.duration == 0.0:
            self.duration = self.end_time - self.start_time
        if self.subtitle_segments is None:
            self.subtitle_segments = []

class MediaGenerator:
    """Handles creation of intro, outro, and subtitles"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "mih_media"
        self.temp_dir.mkdir(exist_ok=True)
    
class MediaGenerator:
    """Handles creation of intro, outro, and subtitles with GPU acceleration"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "mih_media"
        self.temp_dir.mkdir(exist_ok=True)
        self.gpu_available = self._detect_gpu()
    
    def _detect_gpu(self) -> Dict[str, bool]:
        """Detect available GPU acceleration for media generation"""
        gpu_support = {
            'nvidia': False,
            'intel': False,
            'amd': False
        }
        
        try:
            result = subprocess.run([
                'ffmpeg', '-hide_banner', '-encoders'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                encoders = result.stdout.lower()
                if 'h264_nvenc' in encoders:
                    gpu_support['nvidia'] = True
                if 'h264_qsv' in encoders:
                    gpu_support['intel'] = True
                if 'h264_amf' in encoders:
                    gpu_support['amd'] = True
                    
        except Exception as e:
            logger.warning(f"GPU detection failed: {e}")
        
        return gpu_support
    
    def _get_encoder_settings(self) -> Tuple[str, List[str]]:
        """Get best available encoder and settings for intro/outro"""
        if self.gpu_available['nvidia']:
            return 'h264_nvenc', [
                '-preset', 'p4',  # Fast preset
                '-tune', 'hq',    # High quality
                '-rc', 'vbr',     # Variable bitrate
                '-cq', '20',      # High quality for intro/outro
                '-b:v', '1M',     # Lower bitrate for graphics
                '-maxrate', '2M'
            ]
        elif self.gpu_available['intel']:
            return 'h264_qsv', [
                '-preset', 'medium',
                '-global_quality', '20'
            ]
        elif self.gpu_available['amd']:
            return 'h264_amf', [
                '-quality', 'speed',
                '-rc', 'vbr_peak',
                '-qp_i', '20'
            ]
        else:
            return 'libx264', [
                '-preset', 'ultrafast',  # Very fast CPU preset for intro/outro
                '-crf', '20'             # High quality for graphics
            ]
    
    def create_intro(self, title: str, duration: float = 3.0) -> str:
        """Create professional intro with animations and audio using GPU acceleration"""
        try:
            output_file = self.temp_dir / f"intro_{uuid.uuid4().hex[:8]}.mp4"
            safe_title = self._clean_text(title)
            
            # Smart text sizing based on title length
            if len(safe_title) > 50:
                title_size = 36
                line_break_at = len(safe_title) // 2
                # Find nearest space for natural line break
                space_pos = safe_title.find(' ', line_break_at)
                if space_pos != -1 and space_pos < len(safe_title) - 10:
                    safe_title = safe_title[:space_pos] + '\\n' + safe_title[space_pos+1:]
                else:
                    safe_title = safe_title[:line_break_at] + '\\n' + safe_title[line_break_at:]
            elif len(safe_title) > 30:
                title_size = 42
            else:
                title_size = 48
            
            # Get GPU encoder settings
            encoder, encoder_settings = self._get_encoder_settings()
            
            # Create intro with video and silent audio track
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi', '-i', f'color=c=#1a1a2e:size=1080x1920:duration={duration}',
                '-f', 'lavfi', '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100:duration={duration}',
                '-vf', (
                    f"drawtext=text='{safe_title}':fontsize={title_size}:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2-150:"
                    f"alpha='if(lt(t,0.5),0,if(lt(t,1.5),2*(t-0.5),1))',"
                    f"drawtext=text='Dr. Linda Greenwall':fontsize=32:fontcolor=#00d4ff:x=(w-text_w)/2:y=(h-text_h)/2+50:"
                    f"alpha='if(lt(t,1),0,if(lt(t,2),t-1,1))',"
                    f"drawtext=text='MIH Expert':fontsize=28:fontcolor=#ff6b6b:x=(w-text_w)/2:y=(h-text_h)/2+120:"
                    f"alpha='if(lt(t,1.5),0,if(lt(t,2.5),t-1.5,1))'"
                ),
                '-c:v', encoder
            ]
            
            cmd.extend(encoder_settings)
            cmd.extend([
                '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
                '-r', '30', '-pix_fmt', 'yuv420p',
                '-shortest',
                str(output_file)
            ])
            
            result = subprocess.run(cmd, capture_output=True, timeout=45)
            if result.returncode == 0:
                logger.info(f"✅ Created animated intro with {encoder}")
                return str(output_file)
            else:
                error_msg = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "Unknown error"
                logger.warning(f"Intro creation failed: {error_msg[:200]}...")
        except Exception as e:
            logger.warning(f"Intro creation failed: {e}")
        return ""
    
    def create_outro(self, duration: float = 3.0) -> str:
        """Create professional outro with call-to-action and audio using GPU acceleration"""
        try:
            output_file = self.temp_dir / f"outro_{uuid.uuid4().hex[:8]}.mp4"
            
            # Get GPU encoder settings
            encoder, encoder_settings = self._get_encoder_settings()
            
            # Create outro with video and silent audio track
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi', '-i', f'color=c=#2c3e50:size=1080x1920:duration={duration}',
                '-f', 'lavfi', '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100:duration={duration}',
                '-vf', (
                    f"drawtext=text='👍 LIKE & SUBSCRIBE':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2-80:"
                    f"alpha='0.8+0.2*sin(4*PI*t)',"
                    f"drawtext=text='For More MIH Content':fontsize=32:fontcolor=#e74c3c:x=(w-text_w)/2:y=(h-text_h)/2+60:"
                    f"alpha='0.9',"
                    f"drawtext=text='Dr. Linda Greenwall':fontsize=28:fontcolor=#3498db:x=(w-text_w)/2:y=(h-text_h)/2+140:"
                    f"alpha='if(lt(t,1),t,1)'"
                ),
                '-c:v', encoder
            ]
            
            cmd.extend(encoder_settings)
            cmd.extend([
                '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
                '-r', '30', '-pix_fmt', 'yuv420p',
                '-shortest',
                str(output_file)
            ])
            
            result = subprocess.run(cmd, capture_output=True, timeout=45)
            if result.returncode == 0:
                logger.info(f"✅ Created animated outro with {encoder}")
                return str(output_file)
            else:
                error_msg = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "Unknown error"
                logger.warning(f"Outro creation failed: {error_msg[:200]}...")
        except Exception as e:
            logger.warning(f"Outro creation failed: {e}")
        return ""
    
    def create_subtitle_file(self, segments: List[Dict]) -> str:
        """Create SRT subtitle file"""
        try:
            srt_file = self.temp_dir / f"subtitles_{uuid.uuid4().hex[:8]}.srt"
            
            with open(srt_file, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(segments, 1):
                    start_time = self._seconds_to_srt(segment['start'])
                    end_time = self._seconds_to_srt(segment['end'])
                    text = self._clean_text(segment['text'])
                    
                    # Split long text
                    if len(text) > 40:
                        words = text.split()
                        mid = len(words) // 2
                        text = ' '.join(words[:mid]) + '\n' + ' '.join(words[mid:])
                    
                    f.write(f"{i}\n{start_time} --> {end_time}\n{text}\n\n")
            
            logger.info(f"✅ Created subtitles with {len(segments)} segments")
            return str(srt_file)
        except Exception as e:
            logger.error(f"Subtitle creation failed: {e}")
        return ""
    
    def _clean_text(self, text: str) -> str:
        """Clean text for FFmpeg and handle long titles"""
        # Remove special characters that could break FFmpeg
        text = re.sub(r'[^\w\s\-\.\!\?\&\(\)]', '', text)
        # Limit length to prevent overflow
        if len(text) > 80:
            text = text[:77] + '...'
        return text.strip()
    
    def _seconds_to_srt(self, seconds: float) -> str:
        """Convert seconds to SRT timestamp"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"
    
    def cleanup(self):
        """Clean up temporary files"""
        try:
            for file in self.temp_dir.glob("*"):
                file.unlink()
        except:
            pass

class TranscriptProcessor:
    """Handles transcript extraction and subtitle creation"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "transcripts"
        self.temp_dir.mkdir(exist_ok=True)
    
    def get_transcript(self, video_id: str) -> List[Dict]:
        """Get transcript using yt-dlp"""
        try:
            srt_file = self.temp_dir / f"{video_id}.en.srt"
            
            cmd = [
                'yt-dlp', '--write-auto-subs', '--sub-langs', 'en',
                '--sub-format', 'srt', '--skip-download',
                '-o', str(self.temp_dir / f"{video_id}.%(ext)s"),
                f'https://www.youtube.com/watch?v={video_id}'
            ]
            
            subprocess.run(cmd, capture_output=True, timeout=120)
            
            if srt_file.exists():
                transcript = self._parse_srt(srt_file)
                srt_file.unlink()
                logger.info(f"✅ Got transcript: {len(transcript)} segments")
                return transcript
        except Exception as e:
            logger.error(f"Transcript extraction failed: {e}")
        return []
    
    def _parse_srt(self, srt_file: Path) -> List[Dict]:
        """Parse SRT file"""
        transcript = []
        try:
            with open(srt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            for block in content.strip().split('\n\n'):
                lines = block.strip().split('\n')
                if len(lines) >= 3 and ' --> ' in lines[1]:
                    start_str, end_str = lines[1].split(' --> ')
                    start_sec = self._parse_timestamp(start_str)
                    end_sec = self._parse_timestamp(end_str)
                    text = ' '.join(lines[2:])
                    text = re.sub(r'<[^>]+>', '', text).strip()
                    
                    if text:
                        transcript.append({
                            'text': text,
                            'start': start_sec,
                            'duration': end_sec - start_sec
                        })
        except Exception as e:
            logger.error(f"SRT parsing failed: {e}")
        return transcript
    
    def _parse_timestamp(self, timestamp: str) -> float:
        """Parse SRT timestamp to seconds"""
        time_part, ms_part = timestamp.split(',')
        h, m, s = map(int, time_part.split(':'))
        return h * 3600 + m * 60 + s + int(ms_part) / 1000.0
    
    def create_clip_subtitles(self, transcript: List[Dict], start_time: float, end_time: float) -> List[Dict]:
        """Create subtitle segments for clip"""
        segments = []
        for item in transcript:
            item_start = item['start']
            item_end = item_start + item['duration']
            
            if item_end >= start_time and item_start <= end_time:
                segment_start = max(0, item_start - start_time)
                segment_end = min(end_time - start_time, item_end - start_time)
                
                if segment_end > segment_start:
                    segments.append({
                        'start': segment_start,
                        'end': segment_end,
                        'text': item['text']
                    })
        
        # Optimize timing
        for segment in segments:
            duration = segment['end'] - segment['start']
            min_duration = max(1.5, len(segment['text']) * 0.04)
            if duration < min_duration:
                segment['end'] = segment['start'] + min_duration
        
        return segments

class ContentGenerator:
    """AI-powered content generation"""
    
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-001')
    
    def find_best_clips(self, transcript: str, video_data: Dict) -> List[Dict]:
        """Find best clips using AI"""
        prompt = f"""
        Find 3 best clips (15-60 seconds) from this MIH video transcript:
        Title: {video_data.get('title', '')}
        Transcript: {transcript[:3000]}
        
        Return JSON only:
        [{{"start_timestamp": 45, "end_timestamp": 90}}]
        """
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith('```json'):
                text = text[7:-3]
            elif text.startswith('```'):
                text = text[3:-3]
            clips = json.loads(text)
            logger.info(f"✅ AI found {len(clips)} clips")
            return clips
        except Exception as e:
            logger.error(f"AI clip detection failed: {e}")
        return []
    
    def generate_content(self, transcript: str, duration: float) -> Dict:
        """Generate catchy content"""
        prompt = f"""
        Create viral content for {duration}s MIH video:
        Content: {transcript[:600]}
        
        Return JSON only:
        {{"title": "Catchy title with power words", "description": "Engaging description with emojis", "hashtags": ["#MIH", "#TeethWhitening", "#KidsTeeth"]}}
        """
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith('```json'):
                text = text[7:-3]
            elif text.startswith('```'):
                text = text[3:-3]
            
            content = json.loads(text)
            
            # Fix: Ensure content is a dict, not a list
            if isinstance(content, list) and len(content) > 0:
                content = content[0]
            elif not isinstance(content, dict):
                raise ValueError("Invalid content format")
            
            # Ensure hashtags
            hashtags = content.get('hashtags', [])
            if not isinstance(hashtags, list):
                hashtags = ['#MIH', '#TeethWhitening', '#KidsTeeth', '#DrGreenwall']
            
            required = ['#MIH', '#TeethWhitening', '#KidsTeeth', '#DrGreenwall']
            for tag in required:
                if tag not in hashtags:
                    hashtags.append(tag)
            content['hashtags'] = hashtags[:10]
            
            logger.info(f"✅ Generated content: {content.get('title', 'No title')}")
            return content
            
        except Exception as e:
            logger.error(f"Content generation failed: {e}")
            return {
                'title': 'Dr. Greenwall MIH Expert Advice',
                'description': '🦷 Expert MIH advice from Dr. Linda Greenwall',
                'hashtags': ['#MIH', '#TeethWhitening', '#KidsTeeth', '#DrGreenwall']
            }

class VideoProcessor:
    """Enhanced video processing with GPU acceleration"""
    
    def __init__(self, output_dir: str = "processed_videos"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.media_generator = MediaGenerator()
        self.transcript_processor = TranscriptProcessor()
        self.gpu_available = self._detect_gpu()
    
    def _detect_gpu(self) -> Dict[str, bool]:
        """Detect available GPU acceleration"""
        gpu_support = {
            'nvidia': False,
            'intel': False,
            'amd': False
        }
        
        try:
            # Test NVIDIA NVENC
            result = subprocess.run([
                'ffmpeg', '-hide_banner', '-encoders'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                encoders = result.stdout.lower()
                if 'h264_nvenc' in encoders:
                    gpu_support['nvidia'] = True
                    logger.info("🚀 NVIDIA GPU acceleration detected")
                if 'h264_qsv' in encoders:
                    gpu_support['intel'] = True
                    logger.info("🚀 Intel QuickSync acceleration detected")
                if 'h264_amf' in encoders:
                    gpu_support['amd'] = True
                    logger.info("🚀 AMD GPU acceleration detected")
            
            if not any(gpu_support.values()):
                logger.info("💻 Using CPU encoding (no GPU acceleration available)")
                
        except Exception as e:
            logger.warning(f"GPU detection failed: {e}")
        
        return gpu_support
    
    def _get_encoder_settings(self) -> Tuple[str, List[str]]:
        """Get best available encoder and settings"""
        if self.gpu_available['nvidia']:
            return 'h264_nvenc', [
                '-preset', 'p4',  # Fast preset for NVENC
                '-tune', 'hq',    # High quality
                '-rc', 'vbr',     # Variable bitrate
                '-cq', '23',      # Quality level
                '-b:v', '2M',     # Target bitrate
                '-maxrate', '4M', # Max bitrate
                '-bufsize', '8M'  # Buffer size
            ]
        elif self.gpu_available['intel']:
            return 'h264_qsv', [
                '-preset', 'medium',
                '-global_quality', '23',
                '-look_ahead', '1'
            ]
        elif self.gpu_available['amd']:
            return 'h264_amf', [
                '-quality', 'speed',
                '-rc', 'vbr_peak',
                '-qp_i', '23',
                '-qp_p', '25'
            ]
        else:
            return 'libx264', [
                '-preset', 'veryfast',  # Faster CPU preset
                '-crf', '25'            # Slightly lower quality for speed
            ]
    
    def download_video(self, video_id: str) -> str:
        """Download video"""
        try:
            output_path = self.output_dir / f"{video_id}.%(ext)s"
            cmd = [
                'yt-dlp', '-f', 'best[height<=720]/best',
                '-o', str(output_path),
                f'https://www.youtube.com/watch?v={video_id}'
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            
            if result.returncode == 0:
                for file in self.output_dir.glob(f"{video_id}.*"):
                    if file.suffix in ['.mp4', '.webm', '.mkv']:
                        logger.info(f"✅ Downloaded: {file.name}")
                        return str(file)
        except Exception as e:
            logger.error(f"Download failed: {e}")
        return ""
    
    def create_enhanced_clip(self, input_file: str, start_time: float, end_time: float,
                           output_file: str, title: str, subtitle_segments: List[Dict]) -> bool:
        """Create clip with intro, outro, subtitles, and effects"""
        try:
            duration = end_time - start_time
            if duration < 10 or duration > 65:
                logger.warning(f"Invalid duration: {duration}s")
                return False
            
            logger.info(f"🎬 Creating enhanced clip: {duration:.1f}s")
            
            # Ensure output file doesn't exist before starting
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                    logger.info(f"🗑️ Removed existing output file: {output_file}")
                except Exception as e:
                    logger.warning(f"Could not remove existing file: {e}")
            
            # Create components with proper durations
            intro_duration = 3.5  # Slightly longer intro
            outro_duration = 3.0  # Standard outro
            
            intro_file = self.media_generator.create_intro(title, duration=intro_duration)
            outro_file = self.media_generator.create_outro(duration=outro_duration)
            subtitle_file = ""
            if subtitle_segments:
                subtitle_file = self.media_generator.create_subtitle_file(subtitle_segments)
            
            # Extract main clip with enhancements
            main_clip = self._extract_enhanced_main(input_file, start_time, end_time, subtitle_file)
            if not main_clip:
                logger.error("Main clip extraction failed")
                return False
            
            # Always try to create enhanced video with intro/outro
            parts = []
            if intro_file and os.path.exists(intro_file):
                parts.append(intro_file)
                logger.info("✅ Intro will be added")
            else:
                logger.warning("⚠️ No intro created")
                
            parts.append(main_clip)
            
            if outro_file and os.path.exists(outro_file):
                parts.append(outro_file)
                logger.info("✅ Outro will be added")
            else:
                logger.warning("⚠️ No outro created")
            
            # Create final video - always try concatenation if we have multiple parts
            success = False
            if len(parts) > 1:
                logger.info(f"🔗 Concatenating {len(parts)} parts (intro + main + outro)")
                success = self._concatenate_parts(parts, output_file)
                if success:
                    logger.info("✅ Successfully concatenated all parts")
                else:
                    logger.warning("⚠️ Concatenation failed, using main clip only")
                    try:
                        shutil.move(main_clip, output_file)
                        success = True
                    except Exception as e:
                        logger.error(f"Failed to move main clip: {e}")
            else:
                # Only main clip
                try:
                    shutil.move(main_clip, output_file)
                    success = True
                    logger.info(f"✅ Moved main clip to final location: {output_file}")
                except Exception as e:
                    logger.error(f"Failed to move main clip: {e}")
                    success = False
            
            # Cleanup temporary files
            temp_files = [intro_file, outro_file, subtitle_file]
            for file in temp_files:
                if file and os.path.exists(file):
                    try:
                        os.remove(file)
                    except Exception as e:
                        logger.warning(f"Could not clean up temp file {file}: {e}")
            
            # Only clean up main_clip if it's different from output_file
            if main_clip and os.path.exists(main_clip) and main_clip != output_file:
                try:
                    os.remove(main_clip)
                except Exception as e:
                    logger.warning(f"Could not clean up main clip: {e}")
            
            if success:
                # Verify final video duration
                try:
                    import subprocess
                    result = subprocess.run([
                        'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', output_file
                    ], capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        final_duration = float(result.stdout.strip())
                        expected_duration = duration + intro_duration + outro_duration
                        logger.info(f"📊 Final video: {final_duration:.1f}s (expected: {expected_duration:.1f}s)")
                except Exception as e:
                    logger.warning(f"Could not verify video duration: {e}")
                
                logger.info(f"✅ Enhanced clip created: {output_file}")
            return success
            
        except Exception as e:
            logger.error(f"Enhanced clip creation failed: {e}")
            return False
    
    def _extract_enhanced_main(self, input_file: str, start_time: float, end_time: float, subtitle_file: str) -> str:
        """Extract main clip with all enhancements using GPU acceleration"""
        try:
            duration = end_time - start_time
            temp_output = self.output_dir / f"temp_main_{uuid.uuid4().hex[:8]}.mp4"
            
            # Get GPU encoder settings
            encoder, encoder_settings = self._get_encoder_settings()
            
            # Build video filter chain
            video_filters = []
            
            # Resize and pad to vertical format
            video_filters.extend([
                'scale=1080:1920:force_original_aspect_ratio=decrease',
                'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black'
            ])
            
            # Enhance video quality
            video_filters.extend([
                'eq=brightness=0.08:contrast=1.2:saturation=1.2',
                'unsharp=5:5:1.0:3:3:0.5'
            ])
            
            # Add branding overlay (larger and more visible)
            branding_text = "Dr. Linda Greenwall - MIH Expert"
            video_filters.append(f"drawtext=text='{branding_text}':fontsize=32:fontcolor=white:x=40:y=40:alpha=0.9:box=1:boxcolor=black@0.7:boxborderw=5")
            
            # Try adding subtitles if available
            if subtitle_file and os.path.exists(subtitle_file):
                try:
                    # Fix Windows path issues for FFmpeg
                    # Convert to absolute path and normalize
                    abs_subtitle_path = os.path.abspath(subtitle_file)
                    # For Windows, use forward slashes and escape special characters
                    subtitle_path = abs_subtitle_path.replace('\\', '/').replace(':', '\\:')
                    
                    # Use ASS style for better subtitle control
                    subtitle_style = "FontName=Arial Bold,FontSize=28,PrimaryColour=&Hffffff,OutlineColour=&H000000,BackColour=&H80000000,BorderStyle=3,Outline=3,Shadow=2,Alignment=2,MarginV=200"
                    subtitle_filter = f"subtitles='{subtitle_path}':force_style='{subtitle_style}'"
                    video_filters.append(subtitle_filter)
                    logger.info("✅ Added enhanced subtitles")
                except Exception as e:
                    logger.warning(f"Subtitle path processing failed: {e}")
            
            vf_string = ','.join(video_filters)
            
            # Build FFmpeg command with GPU acceleration
            cmd = [
                'ffmpeg', '-y'
            ]
            
            # Add hardware decoding if available
            if self.gpu_available['nvidia']:
                cmd.extend(['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda'])
            elif self.gpu_available['intel']:
                cmd.extend(['-hwaccel', 'qsv'])
            
            cmd.extend([
                '-i', input_file,
                '-ss', str(start_time),
                '-t', str(duration),
                '-vf', vf_string,
                '-c:v', encoder
            ])
            
            # Add encoder-specific settings
            cmd.extend(encoder_settings)
            
            # Add audio settings
            cmd.extend([
                '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
                '-movflags', '+faststart',
                str(temp_output)
            ])
            
            logger.info(f"🎥 Processing main clip with {encoder} acceleration...")
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            
            if result.returncode == 0:
                logger.info("✅ Enhanced main clip created successfully")
                return str(temp_output)
            else:
                error_output = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "No error details"
                logger.warning(f"GPU processing failed: {error_output[:500]}...")
                # Try without subtitles
                return self._extract_enhanced_without_subtitles(input_file, start_time, end_time)
                
        except Exception as e:
            logger.error(f"Enhanced main clip extraction failed: {e}")
            return self._extract_basic_clip(input_file, start_time, end_time)
    
    def _extract_enhanced_without_subtitles(self, input_file: str, start_time: float, end_time: float) -> str:
        """Extract enhanced clip without subtitles"""
        try:
            duration = end_time - start_time
            temp_output = self.output_dir / f"temp_enhanced_nosub_{uuid.uuid4().hex[:8]}.mp4"
            
            # Enhanced processing without subtitles
            filters = [
                'scale=1080:1920:force_original_aspect_ratio=decrease',
                'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
                'eq=brightness=0.05:contrast=1.1:saturation=1.15',
                'unsharp=5:5:0.8:3:3:0.4',
                "drawtext=text='Dr. Linda Greenwall - MIH Expert':fontsize=16:fontcolor=white:x=20:y=20:alpha=0.8:box=1:boxcolor=black@0.5"
            ]
            
            vf_string = ','.join(filters)
            
            cmd = [
                'ffmpeg', '-y',
                '-i', input_file,
                '-ss', str(start_time),
                '-t', str(duration),
                '-vf', vf_string,
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '25',
                '-c:a', 'aac', '-b:a', '128k',
                str(temp_output)
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            
            if result.returncode == 0:
                logger.info("✅ Enhanced clip without subtitles created")
                return str(temp_output)
            else:
                logger.warning("Enhanced processing failed, using basic")
                error_output = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "No error details"
                logger.warning(f"FFmpeg error: {error_output}")
                return self._extract_basic_clip(input_file, start_time, end_time)
                
        except Exception as e:
            logger.error(f"Enhanced without subtitles failed: {e}")
            return self._extract_basic_clip(input_file, start_time, end_time)
    
    def _extract_basic_clip(self, input_file: str, start_time: float, end_time: float) -> str:
        """Fallback basic clip extraction"""
        try:
            duration = end_time - start_time
            temp_output = self.output_dir / f"temp_basic_{uuid.uuid4().hex[:8]}.mp4"
            
            cmd = [
                'ffmpeg', '-y',
                '-i', input_file,
                '-ss', str(start_time),
                '-t', str(duration),
                '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '25',
                '-c:a', 'aac',
                str(temp_output)
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=180)
            if result.returncode == 0:
                logger.info("✅ Basic clip created")
                return str(temp_output)
            else:
                error_output = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "No error details"
                logger.error(f"Basic clip extraction failed: {error_output}")
        except Exception as e:
            logger.error(f"Basic clip extraction failed: {e}")
        return ""
    
    def _concatenate_parts(self, parts: List[str], output_file: str) -> bool:
        """Concatenate video parts with GPU acceleration"""
        try:
            # Verify all parts exist
            missing_parts = [part for part in parts if not os.path.exists(part)]
            if missing_parts:
                logger.error(f"Missing video parts: {missing_parts}")
                return False
            
            logger.info(f"🔗 Concatenating {len(parts)} video parts...")
            
            # Log part details for debugging
            for i, part in enumerate(parts):
                try:
                    result = subprocess.run([
                        'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                        '-of', 'csv=p=0', part
                    ], capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        duration = float(result.stdout.strip())
                        logger.info(f"  Part {i+1}: {duration:.1f}s - {os.path.basename(part)}")
                except Exception as e:
                    logger.warning(f"Could not get duration for part {i+1}: {e}")
            
            # Get GPU encoder settings
            encoder, encoder_settings = self._get_encoder_settings()
            
            # Method 1: Filter complex with GPU acceleration
            logger.info(f"🎬 Running concatenation with {encoder} acceleration...")
            inputs = []
            for part in parts:
                inputs.extend(['-i', part])
            
            # Build filter complex ensuring all inputs have both video and audio
            filter_parts = []
            for i in range(len(parts)):
                # Ensure all parts have both video and audio streams
                filter_parts.append(f'[{i}:v]scale=1080:1920,setsar=1,fps=30[v{i}]')
                filter_parts.append(f'[{i}:a]aresample=44100,apad[a{i}]')
            
            concat_inputs = ''.join([f'[v{i}][a{i}]' for i in range(len(parts))])
            filter_complex = '; '.join(filter_parts) + f'; {concat_inputs}concat=n={len(parts)}:v=1:a=1[outv][outa]'
            
            cmd = ['ffmpeg', '-y']
            
            # Add hardware acceleration for concatenation
            if self.gpu_available['nvidia']:
                cmd.extend(['-hwaccel', 'cuda'])
            elif self.gpu_available['intel']:
                cmd.extend(['-hwaccel', 'qsv'])
            
            cmd.extend([
                *inputs,
                '-filter_complex', filter_complex,
                '-map', '[outv]', '-map', '[outa]',
                '-c:v', encoder
            ])
            
            cmd.extend(encoder_settings)
            cmd.extend([
                '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
                '-movflags', '+faststart',
                output_file
            ])
            
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            
            if result.returncode == 0:
                logger.info(f"✅ Successfully concatenated with {encoder}")
                return True
            else:
                error_output = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "No error details"
                logger.warning(f"GPU concatenation failed: {error_output[:300]}...")
            
            # Method 2: Simple concat demuxer as fallback
            logger.info("🔄 Trying concat demuxer method...")
            concat_file = self.output_dir / f"concat_{uuid.uuid4().hex[:8]}.txt"
            try:
                with open(concat_file, 'w', encoding='utf-8') as f:
                    for part in parts:
                        # Use absolute paths and forward slashes for FFmpeg compatibility
                        abs_path = os.path.abspath(part).replace('\\', '/')
                        f.write(f"file '{abs_path}'\n")
                
                # Try with GPU acceleration first
                cmd = ['ffmpeg', '-y']
                
                if self.gpu_available['nvidia']:
                    cmd.extend(['-hwaccel', 'cuda'])
                elif self.gpu_available['intel']:
                    cmd.extend(['-hwaccel', 'qsv'])
                
                cmd.extend([
                    '-f', 'concat', '-safe', '0',
                    '-i', str(concat_file),
                    '-c:v', encoder
                ])
                
                cmd.extend(encoder_settings)
                cmd.extend([
                    '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
                    '-movflags', '+faststart',
                    output_file
                ])
                
                result = subprocess.run(cmd, capture_output=True, timeout=180)
                
                if result.returncode == 0:
                    logger.info(f"✅ Successfully concatenated with demuxer ({encoder})")
                    return True
                else:
                    # Try copy codec as final fallback
                    logger.info("🔄 Trying copy codec...")
                    cmd = [
                        'ffmpeg', '-y',
                        '-f', 'concat', '-safe', '0',
                        '-i', str(concat_file),
                        '-c', 'copy',
                        output_file
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, timeout=180)
                    
                    if result.returncode == 0:
                        logger.info("✅ Successfully concatenated with copy codec")
                        return True
                    else:
                        error_output = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "No error details"
                        logger.error(f"All concatenation methods failed: {error_output[:300]}...")
                    
            finally:
                # Clean up concat file
                if concat_file.exists():
                    concat_file.unlink()
            
        except Exception as e:
            logger.error(f"Concatenation failed: {e}")
        return False
                   

class YouTubeManager:
    """Simplified YouTube operations"""
    
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    def __init__(self, api_key: str, channel_configs: List[Dict]):
        self.api_key = api_key
        self.channel_configs = channel_configs
        self.youtube_services = {}
        self._authenticate_channels()
    
    def _authenticate_channels(self):
        """Authenticate channels"""
        for i, config in enumerate(self.channel_configs):
            channel_key = f"channel_{i+1}"
            creds_file = config.get('credentials_file')
            
            if not creds_file or not os.path.exists(creds_file):
                logger.error(f"Missing credentials for {config.get('name', 'channel')}")
                continue
            
            try:
                creds = None
                token_file = f'token_{channel_key}.json'
                
                if os.path.exists(token_file):
                    creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
                
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        flow = InstalledAppFlow.from_client_secrets_file(creds_file, self.SCOPES)
                        creds = flow.run_local_server(port=0)
                    
                    with open(token_file, 'w') as token:
                        token.write(creds.to_json())
                
                service = build('youtube', 'v3', credentials=creds)
                self.youtube_services[channel_key] = {'service': service, 'config': config}
                logger.info(f"✅ Authenticated: {config.get('name', 'channel')}")
                
            except Exception as e:
                logger.error(f"Auth failed for {config.get('name', 'channel')}: {e}")
    
    def upload_to_all_channels(self, file_path: str, title: str, description: str, tags: List[str]) -> Dict:
        """Upload to all channels"""
        results = {}
        
        for channel_key, data in self.youtube_services.items():
            try:
                service = data['service']
                config = data['config']
                
                body = {
                    'snippet': {
                        'title': title[:100],
                        'description': description[:5000],
                        'tags': tags[:15],
                        'categoryId': '27'
                    },
                    'status': {'privacyStatus': 'public'}
                }
                
                media = MediaFileUpload(file_path, resumable=True)
                request = service.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
                
                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        progress = int(status.progress() * 100)
                        if progress % 25 == 0:
                            logger.info(f"Upload progress: {progress}%")
                
                if response and 'id' in response:
                    results[channel_key] = {
                        'status': 'success',
                        'video_id': response['id'],
                        'url': f"https://www.youtube.com/watch?v={response['id']}",
                        'channel_name': config.get('name', 'Channel')
                    }
                    logger.info(f"✅ Uploaded to {config.get('name', 'channel')}")
                else:
                    results[channel_key] = {
                        'status': 'failed', 
                        'error': 'No video ID returned',
                        'channel_name': config.get('name', 'Channel')
                    }
                    
            except Exception as e:
                results[channel_key] = {
                    'status': 'failed', 
                    'error': str(e),
                    'channel_name': config.get('name', 'Channel')
                }
                logger.error(f"Upload failed for {config.get('name', 'channel')}: {e}")
            
            time.sleep(30)  # Delay between uploads
        
        return results

class MIHAutomation:
    """Main automation system"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.youtube_manager = YouTubeManager(config['youtube_api_key'], config['upload_channels'])
        self.video_processor = VideoProcessor(config.get('output_dir', 'processed_videos'))
        self.content_generator = ContentGenerator(config['gemini_api_key'])
        self.processed_videos = set()
        self._load_processed_videos()
    
    def _load_processed_videos(self):
        """Load processed videos"""
        if os.path.exists('processed_videos.json'):
            with open('processed_videos.json', 'r') as f:
                self.processed_videos = set(json.load(f))
    
    def _save_processed_videos(self):
        """Save processed videos"""
        with open('processed_videos.json', 'w') as f:
            json.dump(list(self.processed_videos), f)
    
    def process_video(self, video_data: Dict) -> List[VideoClip]:
        """Process single video"""
        video_id = video_data['id']
        logger.info(f"🎬 Processing: {video_data['title']}")
        
        try:
            # Get transcript
            transcript = self.video_processor.transcript_processor.get_transcript(video_id)
            if not transcript:
                logger.error("❌ No transcript available")
                return []
            
            full_transcript = ' '.join([item['text'] for item in transcript])
            
            # Find best clips
            clip_suggestions = self.content_generator.find_best_clips(full_transcript, video_data)
            if not clip_suggestions:
                logger.error("❌ No clips found")
                return []
            
            # Download video
            video_file = self.video_processor.download_video(video_id)
            if not video_file:
                logger.error("❌ Download failed")
                return []
            
            clips = []
            for i, clip_data in enumerate(clip_suggestions):
                try:
                    start_time = float(clip_data['start_timestamp'])
                    end_time = float(clip_data['end_timestamp'])
                    duration = end_time - start_time
                    
                    if duration < 10 or duration > 65:
                        logger.warning(f"Skipping clip {i+1}: duration {duration:.1f}s")
                        continue
                    
                    logger.info(f"📝 Creating clip {i+1}: {duration:.1f}s")
                    
                    # Extract clip transcript
                    clip_transcript = self._get_clip_transcript(transcript, start_time, end_time)
                    
                    # Generate content
                    content = self.content_generator.generate_content(clip_transcript, duration)
                    
                    # Create subtitle segments
                    subtitle_segments = self.video_processor.transcript_processor.create_clip_subtitles(
                        transcript, start_time, end_time
                    )
                    
                    # Create enhanced clip with unique filename
                    timestamp = int(time.time())
                    output_file = f"enhanced_clip_{video_id}_{i+1}_{timestamp}.mp4"
                    output_path = self.video_processor.output_dir / output_file
                    
                    success = self.video_processor.create_enhanced_clip(
                        video_file, start_time, end_time, str(output_path),
                        content['title'], subtitle_segments
                    )
                    
                    if success and os.path.exists(str(output_path)):
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
                            file_path=str(output_path),
                            subtitle_segments=subtitle_segments
                        )
                        clips.append(clip)
                        logger.info(f"✅ Enhanced clip {i+1} created: {duration:.1f}s")
                    else:
                        logger.error(f"❌ Failed to create clip {i+1}")
                    
                except Exception as e:
                    logger.error(f"❌ Error creating clip {i+1}: {e}")
                    continue
            
            # Cleanup source video
            if os.path.exists(video_file):
                try:
                    os.remove(video_file)
                    logger.info("🧹 Cleaned up source video")
                except Exception as e:
                    logger.warning(f"Could not clean up source video: {e}")
            
            logger.info(f"🎉 Created {len(clips)} enhanced clips")
            return clips
            
        except Exception as e:
            logger.error(f"❌ Error processing video: {e}")
            return []
    
    def _get_clip_transcript(self, transcript: List[Dict], start_time: float, end_time: float) -> str:
        """Extract transcript for clip"""
        clip_text = []
        for item in transcript:
            item_start = item['start']
            item_end = item_start + item['duration']
            if item_end >= start_time and item_start <= end_time:
                clip_text.append(item['text'])
        return ' '.join(clip_text)
    
    def publish_clips(self, clips: List[VideoClip]):
        """Publish clips to all channels"""
        if not clips:
            logger.info("❌ No clips to publish")
            return
        
        logger.info(f"📤 Publishing {len(clips)} clips to all channels")
        
        for i, clip in enumerate(clips):
            if not clip.file_path or not os.path.exists(clip.file_path):
                logger.warning(f"❌ Clip file not found: {clip.file_path}")
                continue
            
            logger.info(f"📤 Publishing clip {i+1}: {clip.title}")
            
            try:
                results = self.youtube_manager.upload_to_all_channels(
                    clip.file_path, clip.title, clip.description, clip.hashtags
                )
                
                successful = sum(1 for r in results.values() if r.get('status') == 'success')
                total = len(results)
                logger.info(f"📊 Upload results: {successful}/{total} successful")
                
                for channel_key, result in results.items():
                    if result['status'] == 'success':
                        logger.info(f"✅ {result['channel_name']}: {result['url']}")
                    else:
                        logger.error(f"❌ {result.get('channel_name', channel_key)}: {result['error']}")
                        
            except Exception as e:
                logger.error(f"❌ Error publishing clip {i+1}: {e}")
            
            finally:
                # Cleanup clip file
                try:
                    if os.path.exists(clip.file_path):
                        os.remove(clip.file_path)
                        logger.info(f"🧹 Cleaned up: {os.path.basename(clip.file_path)}")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ Could not clean up file: {cleanup_error}")
            
            # Wait between clips
            if i < len(clips) - 1:
                logger.info("⏱️ Waiting 45 seconds before next clip...")
                time.sleep(45)
        
        logger.info("🎉 All clips published!")
    
    def run_single_video_test(self, video_id: str):
        """Test single video processing"""
        logger.info(f"🧪 Testing video: {video_id}")
        
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
            
            logger.info(f"🎬 Processing: {video_data['title']}")
            
            # Process video
            clips = self.process_video(video_data)
            
            if clips:
                logger.info(f"🎉 SUCCESS! Created {len(clips)} enhanced clips")
                
                # Show clip details
                for i, clip in enumerate(clips, 1):
                    logger.info(f"📋 CLIP {i}:")
                    logger.info(f"   🎬 Title: {clip.title}")
                    logger.info(f"   ⏱️ Duration: {clip.duration:.1f}s")
                    logger.info(f"   📝 Subtitles: {len(clip.subtitle_segments)} segments")
                    logger.info(f"   📁 File: {clip.file_path}")
                    logger.info(f"   🏷️ Hashtags: {', '.join(clip.hashtags[:5])}")
                
                # Ask to publish
                try:
                    publish = input("\n📤 Publish clips to all channels? (y/n): ").lower().strip()
                    if publish == 'y':
                        self.publish_clips(clips)
                        logger.info("🎉 Publishing complete!")
                    else:
                        logger.info("📋 Clips ready for manual upload")
                except KeyboardInterrupt:
                    logger.info("\n📋 Clips created but not published")
                except Exception as input_error:
                    logger.info(f"📋 Clips created, input error: {input_error}")
            else:
                logger.error("❌ No clips could be created from this video")
                
        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
    
    def cleanup(self):
        """Cleanup temporary files"""
        try:
            self.video_processor.media_generator.cleanup()
            logger.info("🧹 Cleanup complete")
        except Exception as e:
            logger.warning(f"⚠️ Cleanup error: {e}")

def main():
    """Main function"""
    print("🚀 Enhanced MIH Content Automation System")
    print("✨ Features: Intro, Outro, Subtitles, AI Content, Multi-Channel Upload")
    print("=" * 60)
    
    try:
        import config
        automation_config = {
            'youtube_api_key': config.YOUTUBE_API_KEY,
            'upload_channels': config.UPLOAD_CHANNELS,
            'gemini_api_key': config.GEMINI_API_KEY,
            'output_dir': getattr(config, 'OUTPUT_DIR', 'processed_videos')
        }
        
        logger.info("✅ Configuration loaded successfully")
        logger.info(f"📺 Channels configured: {len(automation_config['upload_channels'])}")
        
    except ImportError:
        logger.error("❌ Config file not found. Create config.py with:")
        print("\n# Example config.py")
        print("YOUTUBE_API_KEY = 'your_youtube_api_key'")
        print("GEMINI_API_KEY = 'your_gemini_api_key'")
        print("UPLOAD_CHANNELS = [")
        print("    {")
        print("        'name': 'Your Channel Name',")
        print("        'credentials_file': 'channel_credentials.json'")
        print("    }")
        print("]")
        print("OUTPUT_DIR = 'processed_videos'")
        return
    
    # Validate configuration
    if not automation_config['youtube_api_key'] or 'YOUR_' in automation_config['youtube_api_key']:
        logger.error("❌ YouTube API key not configured")
        return
    
    if not automation_config['gemini_api_key'] or 'YOUR_' in automation_config['gemini_api_key']:
        logger.error("❌ Gemini API key not configured")
        return
    
    if not automation_config['upload_channels']:
        logger.error("❌ No upload channels configured")
        return
    
    # Check credential files
    missing_creds = []
    for i, channel in enumerate(automation_config['upload_channels']):
        cred_file = channel.get('credentials_file')
        if not cred_file or not os.path.exists(cred_file):
            missing_creds.append(f"Channel {i+1}: {channel.get('name', 'Unknown')}")
    
    if missing_creds:
        logger.error("❌ Missing credential files:")
        for missing in missing_creds:
            logger.error(f"   {missing}")
        logger.info("💡 Download OAuth credentials from YouTube API Console")
        return
    
    try:
        logger.info("🚀 Initializing Enhanced MIH Automation System...")
        automation = MIHAutomation(automation_config)
        
        # Parse command line arguments
        import sys
        if len(sys.argv) > 1 and sys.argv[1] == '--test' and len(sys.argv) > 2:
            automation.run_single_video_test(sys.argv[2])
        else:
            logger.info("📋 Usage: python automation.py --test VIDEO_ID")
            logger.info("🎯 Example: python automation.py --test uaHNk_fPzgA")
            
    except Exception as e:
        logger.error(f"❌ System initialization failed: {e}")
    finally:
        try:
            if 'automation' in locals():
                automation.cleanup()
        except Exception as cleanup_error:
            logger.warning(f"⚠️ Final cleanup error: {cleanup_error}")

if __name__ == "__main__":
    main()

"""
EXAMPLE CONFIG.PY FILE:

# API Keys
YOUTUBE_API_KEY = "your_youtube_api_key_here"
GEMINI_API_KEY = "your_gemini_api_key_here"

# Output directory
OUTPUT_DIR = "processed_videos"

# Upload channels configuration
UPLOAD_CHANNELS = [
    {
        "name": "MIH Treatment Channel",
        "credentials_file": "channel1_credentials.json",
        "content_focus": "treatment_focused"
    },
    {
        "name": "Kids Dental Care",
        "credentials_file": "channel2_credentials.json", 
        "content_focus": "pediatric_care"
    },
    {
        "name": "Dental Education",
        "credentials_file": "channel3_credentials.json",
        "content_focus": "primary_education"
    }
]

# Optional settings
SEARCH_QUERIES = [
    "Dr Linda Greenwall MIH",
    "Molar Incisor Hypomineralisation treatment",
    "Linda Greenwall ICON treatment",
    "MIH white spots children teeth"
]

MIH_KEYWORDS = [
    "mih", "molar incisor hypomineralisation", "chalky teeth",
    "white spots", "enamel defects", "icon treatment",
    "dental fluorosis", "hypomineralization", "pediatric dentistry"
]

MAX_CLIPS_PER_VIDEO = 3
DELAY_BETWEEN_CLIPS = 45
"""