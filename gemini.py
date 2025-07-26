# ==============================================================================
# ✨ MIH Content Automation System - Redesigned & Enhanced Version (FINAL PATCH 4) ✨
#
# PATCH NOTES:
#   - FIXED: Added a `setsar=1` filter to all video generation and extraction
#     commands. This normalizes the Sample Aspect Ratio across all video parts,
#     resolving the "Input link parameters do not match" error during concatenation.
#   - All previous patches for audio, ordering, fonts, and filters are retained.
# ==============================================================================

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
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

# Third-party libraries
try:
    import google.generativeai as genai
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from gtts import gTTS
except ImportError as e:
    print(f"ERROR: Missing required libraries. Please install them: pip install {e.name}")
    sys.exit(1)


# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Core Stability Utilities ---
class TimeoutError(Exception):
    """Custom timeout exception"""
    pass

def timeout_handler(signum, frame):
    """Handle timeout signals on Unix-like systems"""
    raise TimeoutError("Operation timed out via signal")

def run_with_timeout(cmd: List[str], timeout_seconds: int = 120, **kwargs) -> subprocess.CompletedProcess:
    """Run a subprocess with robust timeout handling for both Unix and Windows."""
    process_start_time = time.time()
    try:
        if sys.platform != "win32":
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)

        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', **kwargs) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout_seconds)
                returncode = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                elapsed = time.time() - process_start_time
                logger.error(f"Command timed out after {elapsed:.1f}s: {' '.join(cmd[:3])}...")
                raise TimeoutError(f"Command timed out after {timeout_seconds} seconds")

        if sys.platform != "win32":
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

        if returncode != 0:
            if "Error parsing" not in stderr and "Option not found" not in stderr and "do not match" not in stderr:
                logger.warning(f"Command failed with code {returncode}. Stderr: {stderr[:500]}")

        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    except TimeoutError:
        raise
    except Exception as e:
        if sys.platform != "win32" and 'old_handler' in locals():
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        logger.error(f"Subprocess failed with unexpected error: {e}")
        raise

# --- Helper Functions ---
def get_system_font_path() -> Optional[str]:
    """Find a common system font file path for cross-platform compatibility."""
    if sys.platform == "win32":
        path = "C:/Windows/Fonts/arialbd.ttf"
        if Path(path).exists(): return path
        path = "C:/Windows/Fonts/arial.ttf"
        if Path(path).exists(): return path
    elif sys.platform == "darwin":
        path = "/System/Library/Fonts/Supplemental/Arial.ttf"
        if Path(path).exists(): return path
    else:
        paths = ["/usr/share/fonts/truetype/msttcorefonts/Arial.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf"]
        for path in paths:
            if Path(path).exists(): return path
    logger.warning("Could not find a common system font (Arial). FFmpeg will use its default.")
    return None

# --- Data Structures ---
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
        self.duration = self.end_time - self.start_time
        if self.subtitle_segments is None:
            self.subtitle_segments = []

# --- Enhanced Media Creation ---
class EnhancedMediaGenerator:
    """Handles creation of intros, outros, and subtitles with sound and animation."""
    def __init__(self, sfx_path: Optional[str] = None):
        self.temp_dir = Path(tempfile.gettempdir()) / f"mih_media_{uuid.uuid4().hex[:6]}"
        self.temp_dir.mkdir(exist_ok=True, parents=True)
        self.sfx_path = sfx_path if sfx_path and Path(sfx_path).exists() else None
        if not self.sfx_path:
            logger.warning("⚠️ Sound effect file not found. Intros/outros will be created without SFX.")
        self.font_path = get_system_font_path()

    def _create_tts_audio(self, text: str, lang: str = 'en') -> str:
        """Creates a temporary MP3 file from text using gTTS."""
        try:
            tts_file = self.temp_dir / f"tts_{uuid.uuid4().hex[:8]}.mp3"
            clean_text = re.sub(r'[^\w\s\.\!\?]', '', text)
            tts = gTTS(text=clean_text, lang=lang, slow=False)
            tts.save(str(tts_file))
            if tts_file.exists() and tts_file.stat().st_size > 100:
                logger.info(f"🎤 Generated TTS audio for: '{clean_text[:30]}...'")
                return str(tts_file)
        except Exception as e:
            logger.warning(f"⚠️ TTS audio generation failed: {e}")
        return ""

    def _generate_animated_video(self, text: str, duration: float, tts_audio_path: str) -> Optional[str]:
        output_path = self.temp_dir / f"animated_{uuid.uuid4().hex[:8]}.mp4"
        safe_text = self._clean_text_for_ffmpeg(text)
        
        cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=#1a1a2e:s=1080x1920:d={duration}', '-i', tts_audio_path]
        
        font_option = ""
        if self.font_path:
            path_for_ffmpeg = self.font_path.replace('\\', '/')
            if sys.platform == "win32":
                path_for_ffmpeg = path_for_ffmpeg.split(':', 1)[-1]
            font_option = f"fontfile='{path_for_ffmpeg}':"

        video_filter_chain = (
            "[0:v]format=rgb24,"
            "geq=r='X/W*100':g='(1-X/W)*100':b='(H-Y)/H*200',"
            "zoompan=z='min(zoom+0.001,1.1)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920,"
            f"drawtext=text='{safe_text}':{font_option}fontsize=70:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2"
            f":box=1:boxcolor=black@0.5:boxborderw=15,"
            "setsar=1[v_out]" # FIX: Normalize Sample Aspect Ratio
        )
        
        audio_filter_chain = ""
        if self.sfx_path:
            cmd.extend(['-i', self.sfx_path])
            audio_filter_chain = "[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=2,volume=1.2[a_out]"
        else:
            audio_filter_chain = "[1:a]acopy[a_out]"

        filter_complex_str = f"{video_filter_chain};{audio_filter_chain}"

        cmd.extend([
            '-filter_complex', filter_complex_str,
            '-map', '[v_out]', '-map', '[a_out]',
            '-c:v', 'libx264', '-preset', 'faster', '-crf', '24',
            '-c:a', 'aac', '-b:a', '128k',
            '-pix_fmt', 'yuv420p', '-t', str(duration),
            str(output_path)
        ])

        try:
            logger.info(f"🎨 Creating animated media: '{text[:20]}...'")
            result = run_with_timeout(cmd, timeout_seconds=45)
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000:
                logger.info(f"✅ Created animated media: {output_path.name}")
                return str(output_path)
            else:
                 logger.warning(f"⚠️ Animated media creation failed. FFmpeg stderr: {result.stderr[:400]}")
        except (TimeoutError, Exception) as e:
            logger.warning(f"⚠️ Animated media creation failed with exception: {e}. Will proceed without it.")
        return None

    def create_intro(self, title: str, duration: float = 3.0) -> str:
        tts_audio = self._create_tts_audio(title)
        if not tts_audio: return ""
        video_path = self._generate_animated_video(title, duration, tts_audio)
        if Path(tts_audio).exists(): Path(tts_audio).unlink()
        return video_path or ""

    def create_outro(self, duration: float = 3.0) -> str:
        text = "Like & Subscribe!"
        tts_audio = self._create_tts_audio(text)
        if not tts_audio: return ""
        video_path = self._generate_animated_video(text, duration, tts_audio)
        if Path(tts_audio).exists(): Path(tts_audio).unlink()
        return video_path or ""

    def create_subtitle_file(self, segments: List[Dict]) -> Optional[str]:
        if not segments: return None
        srt_file = self.temp_dir / f"subs_{uuid.uuid4().hex[:8]}.srt"
        try:
            with open(srt_file, 'w', encoding='utf-8') as f:
                for i, seg in enumerate(segments, 1):
                    text = self._clean_text_for_ffmpeg(seg['text']).upper()
                    words = text.split()
                    if len(words) > 6:
                        mid = len(words) // 2
                        text = ' '.join(words[:mid]) + r'\N' + ' '.join(words[mid:])
                    f.write(f"{i}\n{self._seconds_to_srt(seg['start'])} --> {self._seconds_to_srt(seg['end'])}\n{text}\n\n")
            return str(srt_file)
        except Exception as e:
            logger.error(f"❌ Subtitle file creation failed: {e}")
        return None

    def _clean_text_for_ffmpeg(self, text: str) -> str:
        text = text.replace("'", "’").replace(":", "-").replace("%", " percent")
        return re.sub(r'[\\"]', '', text)

    def _seconds_to_srt(self, seconds: float) -> str:
        h, m, s, ms = int(seconds // 3600), int(seconds % 3600 // 60), int(seconds % 60), int(seconds % 1 * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def cleanup(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            logger.info("🧹 Cleaned up temporary media files.")


# --- Transcript Processing ---
class TranscriptProcessor:
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / f"mih_transcripts_{uuid.uuid4().hex[:6]}"
        self.temp_dir.mkdir(exist_ok=True, parents=True)

    def get_transcript(self, video_id: str) -> List[Dict]:
        try:
            logger.info(f"📝 Extracting transcript for {video_id}...")
            output_template = self.temp_dir / f"{video_id}.%(ext)s"
            cmd = [
                'yt-dlp', '--write-auto-subs', '--sub-langs', 'en.*', '--sub-format', 'srt',
                '--skip-download', '--socket-timeout', '30', '--retries', '3', '-o', str(output_template),
                f'https://www.youtube.com/watch?v={video_id}'
            ]
            run_with_timeout(cmd, timeout_seconds=90)
            
            srt_files = list(self.temp_dir.glob(f"{video_id}.*.srt"))
            if not srt_files:
                logger.error(f"❌ No subtitle file was downloaded for {video_id}.")
                return []

            transcript = self._parse_srt(srt_files[0])
            if transcript:
                logger.info(f"✅ Got transcript with {len(transcript)} segments.")
            return transcript
        except (TimeoutError, Exception) as e:
            logger.error(f"❌ Transcript extraction failed for {video_id}: {e}")
        return []

    def _parse_srt(self, srt_file: Path) -> List[Dict]:
        transcript = []
        try:
            content = srt_file.read_text(encoding='utf-8')
            blocks = content.strip().split('\n\n')
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 3 and '-->' in lines[1]:
                    start_str, end_str = lines[1].split(' --> ')
                    text = ' '.join(lines[2:]).replace('\n', ' ').strip()
                    text = re.sub(r'<[^>]+>', '', text)
                    transcript.append({
                        'text': text,
                        'start': self._parse_timestamp(start_str),
                        'end': self._parse_timestamp(end_str)
                    })
        except Exception as e:
            logger.error(f"❌ SRT parsing failed for {srt_file.name}: {e}")
        return transcript

    def _parse_timestamp(self, ts: str) -> float:
        parts = ts.split(',')
        time_part = parts[0]
        ms = int(parts[1])
        h, m, s = map(int, time_part.split(':'))
        return h * 3600 + m * 60 + s + ms / 1000.0

    def cleanup(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            logger.info("🧹 Cleaned up temporary transcript files.")


# --- AI Content Generation ---
class ContentGenerator:
    def __init__(self, api_key: str):
        self.model = None
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash-latest')
            logger.info("✅ Gemini AI model initialized.")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize Gemini AI: {e}. Using fallback content.")

    def find_best_clips(self, transcript: str, video_data: Dict) -> List[Dict]:
        if not self.model or not transcript: return self._fallback_clip_detection(transcript)
        transcript_excerpt = transcript[:15000]
        prompt = f"""
        Analyze the transcript of a dental health video titled "{video_data.get('title', '')[:100]}".
        Identify the 2 most compelling, viral-worthy clips, each between 25 and 55 seconds.
        Look for: a strong hook, surprising facts, debunked myths, or clear, actionable tips.
        Transcript: "{transcript_excerpt}"
        Return ONLY a valid JSON array like: [{{"start_timestamp": 45, "end_timestamp": 85}}]
        """
        try:
            logger.info("🤖 Using AI to find best clips...")
            response = self.model.generate_content(prompt)
            cleaned_text = re.search(r'\[.*\]', response.text, re.DOTALL).group(0)
            clips = json.loads(cleaned_text)
            valid_clips = [c for c in clips if 'start_timestamp' in c and 'end_timestamp' in c and (c['end_timestamp'] - c['start_timestamp']) > 15]
            if valid_clips:
                logger.info(f"✅ AI found {len(valid_clips)} potential clips.")
                return valid_clips[:config.MAX_CLIPS_PER_VIDEO]
        except Exception as e:
            logger.warning(f"⚠️ AI clip detection failed: {e}. Using fallback.")
        return self._fallback_clip_detection(transcript)

    def _fallback_clip_detection(self, transcript: str) -> List[Dict]:
        logger.info("📋 Using fallback method to find clips.")
        words = transcript.split()
        if len(words) < 200: return []
        mid_point_word = len(words) // 2
        start_word = max(0, mid_point_word - 75)
        end_word = min(len(words), mid_point_word + 75)
        start_time = start_word / 2.5
        end_time = end_word / 2.5
        return [{'start_timestamp': start_time, 'end_timestamp': end_time}]

    def generate_content(self, transcript: str, duration: float) -> Dict:
        if not self.model: return self._fallback_content(transcript)
        transcript_excerpt = transcript[:800]
        prompt = f"""
        You are a social media expert creating a viral YouTube Short about MIH (Molar Incisor Hypomineralisation).
        The clip is {duration:.0f}s long. Content: "{transcript_excerpt}"
        **Instructions:**
        1. **Title:** Short, curiosity-driven title (< 70 chars). Make people NEED to know the answer.
        2. **Description:** Energetic description (< 250 chars) with 3-5 emojis and a hook.
        3. **Hashtags:** 5-7 relevant hashtags.
        **Return ONLY valid JSON.** Example:
        {{"title": "Your Kid's Teeth Have SPOTS?!", "description": "🤯 Seeing chalky spots on your child's teeth? It could be MIH! Dr. Greenwall reveals the #1 thing you MUST do. 🦷✨ #DentalTips", "hashtags": ["#MIH", "#KidsDentalCare", "#ParentingHacks", "#Teeth", "#DrGreenwall", "#DentalMyths"]}}
        """
        try:
            logger.info("🤖 Using AI to generate catchy content...")
            response = self.model.generate_content(prompt)
            cleaned_text = re.search(r'\{.*\}', response.text, re.DOTALL).group(0)
            content = json.loads(cleaned_text)
            content['title'] = content.get('title', 'Expert Dental Tip')[:70]
            content['description'] = content.get('description', 'Key dental tip!')[:4900]
            content['hashtags'] = content.get('hashtags', ['#MIH', '#DentalCare'])[:15]
            logger.info(f"✅ AI generated content: '{content['title']}'")
            return content
        except Exception as e:
            logger.warning(f"⚠️ AI content generation failed: {e}. Using fallback.")
        return self._fallback_content(transcript)

    def _fallback_content(self, transcript: str) -> Dict:
        logger.info("📋 Using fallback method for content generation.")
        return {'title': 'Important MIH Dental Tip', 'description': 'Dr. Greenwall shares expert advice on MIH. 🦷 #MIH #DentalCare', 'hashtags': ['#MIH', '#DentalHealth', '#DrGreenwall']}

# --- Video Processing Orchestration ---
class VideoProcessor:
    def __init__(self, output_dir: str, sfx_path: Optional[str]):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.media_generator = EnhancedMediaGenerator(sfx_path=sfx_path)
        self.transcript_processor = TranscriptProcessor()

    def download_video(self, video_id: str) -> Optional[str]:
        try:
            logger.info(f"📥 Downloading video {video_id} (up to 720p)...")
            output_pattern = self.media_generator.temp_dir / f"{video_id}.%(ext)s"
            cmd = [
                'yt-dlp', '-f', 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
                '--socket-timeout', '30', '--retries', '3', '--no-playlist', '-o', str(output_pattern),
                f'https://www.youtube.com/watch?v={video_id}'
            ]
            run_with_timeout(cmd, timeout_seconds=300)
            
            downloaded_files = list(self.media_generator.temp_dir.glob(f"{video_id}.*"))
            video_files = [f for f in downloaded_files if f.suffix in ['.mp4', '.mkv', '.webm']]
            if video_files:
                logger.info(f"✅ Downloaded: {video_files[0].name}")
                return str(video_files[0])
        except (TimeoutError, Exception) as e:
            logger.error(f"❌ Download failed for {video_id}: {e}")
        return None

    def create_enhanced_clip(self, input_file: str, start: float, end: float, title: str, subtitles: List[Dict]) -> Optional[str]:
        final_output_path = self.output_dir / f"clip_{Path(input_file).stem}_{int(start)}_{uuid.uuid4().hex[:6]}.mp4"
        intro_path, outro_path, main_clip_path = None, None, None
        try:
            logger.info(f"🎬 Creating full enhanced clip: {title}")
            intro_path = self.media_generator.create_intro(title)
            outro_path = self.media_generator.create_outro()
            main_clip_path = self._extract_and_enhance_main_clip(input_file, start, end, subtitles)

            if not main_clip_path:
                raise Exception("Main clip extraction failed.")

            # Correctly order the parts for concatenation
            parts_to_join = [p for p in [intro_path, main_clip_path, outro_path] if p and Path(p).exists()]
            
            if len(parts_to_join) > 1:
                success = self._concatenate_videos_with_filter(parts_to_join, str(final_output_path))
            elif main_clip_path and Path(main_clip_path).exists():
                shutil.move(main_clip_path, final_output_path)
                success = True
            else:
                logger.warning("No valid parts to assemble. Only main clip was created, but intro/outro failed.")
                success = False

            if success and final_output_path.exists():
                logger.info(f"🎉 Successfully created final clip with sound and effects: {final_output_path.name}")
                return str(final_output_path)
            else:
                if main_clip_path and Path(main_clip_path).exists():
                    logger.warning("Concatenation failed. Falling back to main clip without intro/outro.")
                    shutil.move(main_clip_path, final_output_path)
                    return str(final_output_path)
                raise Exception("Final clip assembly failed, and no fallback was possible.")

        except Exception as e:
            logger.error(f"❌ Enhanced clip creation failed: {e}")
            return None
        finally:
            for p in [intro_path, outro_path, main_clip_path]:
                if p and Path(p).exists() and Path(p) != final_output_path:
                    Path(p).unlink(missing_ok=True)

    def _extract_and_enhance_main_clip(self, input_file: str, start: float, end: float, subtitles: List[Dict]) -> Optional[str]:
        duration = end - start
        temp_output = self.media_generator.temp_dir / f"main_clip_{uuid.uuid4().hex[:8]}.mp4"
        subtitle_file = self.media_generator.create_subtitle_file(subtitles)

        # FIX: Added `setsar=1` to normalize aspect ratio for concatenation
        video_filters = [
            'scale=1080:1920:force_original_aspect_ratio=decrease',
            'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
            'eq=contrast=1.1:saturation=1.1',
            "drawtext=text='@DrGreenwall':fontcolor=white@0.7:fontsize=32:x=w-tw-30:y=30",
            'setsar=1'
        ]

        if subtitle_file:
            subtitle_path_escaped = str(Path(subtitle_file).resolve()).replace('\\', '/').replace(':', '\\:')
            style = "FontName=Arial Black,FontSize=28,PrimaryColour=&HFFFFFF,BackColour=&H80000000,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV=150"
            video_filters.append(f"subtitles='{subtitle_path_escaped}':force_style='{style}'")
        
        cmd = [
            'ffmpeg', '-y', '-v', 'error', '-ss', str(start), '-t', str(duration),
            '-i', input_file, '-vf', ','.join(video_filters), '-c:v', 'libx264',
            '-preset', 'medium', '-crf', '23', '-c:a', 'aac', '-b:a', '192k', str(temp_output)
        ]
        
        try:
            logger.info("🎥 Enhancing main clip with subtitles and effects...")
            run_with_timeout(cmd, timeout_seconds=180)
            if temp_output.exists() and temp_output.stat().st_size > 1000:
                return str(temp_output)
        except Exception as e:
            logger.error(f"❌ Main clip enhancement failed: {e}")
        finally:
            if subtitle_file and Path(subtitle_file).exists(): Path(subtitle_file).unlink(missing_ok=True)
        return None

    def _concatenate_videos_with_filter(self, file_list: List[str], output_file: str) -> bool:
        """
        Concatenates videos using the robust `concat` filter, which preserves all audio streams.
        """
        cmd = ['ffmpeg', '-y', '-v', 'error']
        filter_complex_parts = []
        
        for i, file_path in enumerate(file_list):
            cmd.extend(['-i', file_path])
            filter_complex_parts.append(f"[{i}:v:0][{i}:a:0]")
        
        filter_complex_str = f"{''.join(filter_complex_parts)}concat=n={len(file_list)}:v=1:a=1[v][a]"
        
        cmd.extend([
            '-filter_complex', filter_complex_str,
            '-map', '[v]', '-map', '[a]',
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
            '-c:a', 'aac', '-b:a', '192k',
            '-pix_fmt', 'yuv420p', output_file
        ])

        try:
            logger.info(f"🔗 Concatenating {len(file_list)} video parts with audio...")
            result = run_with_timeout(cmd, timeout_seconds=120)
            if result.returncode == 0 and Path(output_file).exists():
                return True
            else:
                logger.error(f"Concatenation command failed. Stderr: {result.stderr[:500]}")
                return False
        except Exception as e:
            logger.error(f"❌ Video concatenation failed with exception: {e}")
            return False

    def cleanup(self):
        self.media_generator.cleanup()
        self.transcript_processor.cleanup()


# --- YouTube Management ---
class YouTubeManager:
    """Handles YouTube authentication and uploads with robust error handling."""
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

    def __init__(self, api_key: str, channel_configs: List[Dict]):
        self.api_key = api_key
        self.channel_configs = channel_configs
        self.youtube_services = {}
        self._authenticate_channels()

    def _authenticate_channels(self):
        for i, config in enumerate(self.channel_configs):
            channel_key = f"channel_{i+1}"
            creds_file = config.get('credentials_file')
            channel_name = config.get('name', channel_key)

            if not creds_file or not os.path.exists(creds_file):
                logger.error(f"❌ Missing credentials file '{creds_file}' for channel '{channel_name}'")
                continue
            
            try:
                logger.info(f"🔑 Authenticating {channel_name}...")
                token_file = f'token_{channel_key}.json'
                creds = None
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
                logger.info(f"✅ Authenticated: {channel_name}")
            except Exception as e:
                logger.error(f"❌ Auth failed for {channel_name}: {e}")

    def upload_to_all_channels(self, file_path: str, title: str, description: str, tags: List[str]):
        if not os.path.exists(file_path):
            logger.error(f"❌ Cannot upload, file not found: {file_path}")
            return

        for channel_key, data in self.youtube_services.items():
            service = data['service']
            channel_name = data['config'].get('name', 'Channel')
            logger.info(f"📤 Uploading '{title}' to {channel_name}...")

            body = {
                'snippet': {'title': title, 'description': description, 'tags': tags, 'categoryId': '27'}, # 27 = Education
                'status': {'privacyStatus': 'private'} # Upload as private first
            }
            try:
                media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
                request = service.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
                
                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        logger.info(f"   -> Uploaded {int(status.progress() * 100)}% to {channel_name}")
                
                logger.info(f"✅ SUCCESS: Uploaded to {channel_name}. Video ID: {response['id']}")
            except Exception as e:
                logger.error(f"❌ FAILED to upload to {channel_name}: {e}")


# --- Main Automation System ---
class MIHAutomation:
    def __init__(self, config_dict: Dict):
        self.config = config_dict
        self.youtube_manager = YouTubeManager(self.config['youtube_api_key'], self.config['upload_channels'])
        self.video_processor = VideoProcessor(self.config['output_dir'], self.config['sfx_pop_path'])
        self.content_generator = ContentGenerator(self.config['gemini_api_key'])
        self.processed_videos_file = 'processed_videos.json'
        self.processed_videos = self._load_processed_videos()
        logger.info(f"🤖 MIH Automation System Initialized. Outputting to '{self.config['output_dir']}'.")

    def _load_processed_videos(self) -> set:
        try:
            if Path(self.processed_videos_file).exists() and Path(self.processed_videos_file).stat().st_size > 0:
                with open(self.processed_videos_file, 'r') as f:
                    return set(json.load(f))
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"⚠️ Could not load processed videos list: {e}")
        return set()

    def _save_processed_videos(self):
        try:
            with open(self.processed_videos_file, 'w') as f:
                json.dump(list(self.processed_videos), f, indent=2)
        except IOError as e:
            logger.warning(f"⚠️ Could not save processed videos list: {e}")

    def process_video(self, video_data: Dict) -> List[VideoClip]:
        video_id = video_data['id']
        logger.info(f"🎬 Starting processing for video: {video_data['title']} ({video_id})")
        
        if video_id in self.processed_videos:
            logger.info("⏭️ Video already processed. Skipping.")
            return []

        clips_to_upload = []
        source_video_path = None

        try:
            transcript_segments = self.video_processor.transcript_processor.get_transcript(video_id)
            if not transcript_segments: raise ValueError("Failed to get transcript.")
            
            full_transcript_text = ' '.join(seg['text'] for seg in transcript_segments)
            clip_suggestions = self.content_generator.find_best_clips(full_transcript_text, video_data)
            if not clip_suggestions: raise ValueError("AI could not find suitable clips.")

            source_video_path = self.video_processor.download_video(video_id)
            if not source_video_path: raise ValueError("Failed to download source video.")

            for i, clip_data in enumerate(clip_suggestions):
                start, end = clip_data['start_timestamp'], clip_data['end_timestamp']
                clip_transcript_segs = [s for s in transcript_segments if s['end'] >= start and s['start'] <= end]
                clip_transcript_text = ' '.join(s['text'] for s in clip_transcript_segs)
                
                content = self.content_generator.generate_content(clip_transcript_text, end - start)
                
                final_clip_path = self.video_processor.create_enhanced_clip(source_video_path, start, end, content['title'], clip_transcript_segs)
                
                if final_clip_path:
                    clip = VideoClip(
                        clip_id=uuid.uuid4().hex, start_time=start, end_time=end, transcript=clip_transcript_text,
                        source_video_id=video_id, source_title=video_data['title'], source_url=video_data['url'],
                        title=content['title'], description=content['description'], hashtags=content['hashtags'],
                        file_path=final_clip_path )
                    clips_to_upload.append(clip)

            if clips_to_upload:
                self.processed_videos.add(video_id)
                self._save_processed_videos()
            return clips_to_upload

        except Exception as e:
            logger.error(f"❌ Failed to process video {video_id}: {e}")
            return []
        finally:
            if source_video_path and Path(source_video_path).exists():
                Path(source_video_path).unlink(missing_ok=True)

    def run_single_video_test(self, video_id: str):
        logger.info(f"🧪 Starting single video test for ID: {video_id}")
        try:
            youtube = build('youtube', 'v3', developerKey=self.config['youtube_api_key'])
            request = youtube.videos().list(part="snippet", id=video_id)
            response = request.execute()

            if not response.get("items"):
                logger.error(f"❌ Video not found or API key invalid for ID: {video_id}")
                return

            item = response["items"][0]
            video_data = { 'id': video_id, 'title': item['snippet']['title'], 'url': f"https://www.youtube.com/watch?v={video_id}" }
            
            created_clips = self.process_video(video_data)
            
            if created_clips:
                logger.info(f"✅ SUCCESS! Created {len(created_clips)} clips.")
                for clip in created_clips:
                    logger.info(f"  -> Ready for upload: {clip.file_path}")
                
                for clip in created_clips:
                    self.youtube_manager.upload_to_all_channels(
                        clip.file_path, clip.title, clip.description, clip.hashtags
                    )
            else:
                logger.error("❌ Test finished, but no clips were created.")

        except Exception as e:
            logger.error(f"❌ Test failed with a critical error: {e}", exc_info=True)
        finally:
            self.cleanup()

    def cleanup(self):
        logger.info("🧹 Performing final system cleanup...")
        self.video_processor.cleanup()

# --- Main Execution ---
def main():
    print("🚀 Enhanced MIH Content Automation System 🚀")
    print("=" * 50)
    
    try:
        global config
        import config
    except ImportError:
        logger.error("❌ FATAL: config.py not found. Please create it based on the example in the script.")
        return

    if 'YOUR_' in config.GEMINI_API_KEY or 'YOUR_' in config.YOUTUBE_API_KEY:
        logger.error("❌ FATAL: Please replace placeholder API keys in config.py.")
        return

    automation_config = {
        'youtube_api_key': config.YOUTUBE_API_KEY,
        'gemini_api_key': config.GEMINI_API_KEY,
        'upload_channels': config.UPLOAD_CHANNELS,
        'output_dir': getattr(config, 'OUTPUT_DIR', 'processed_videos'),
        'sfx_pop_path': getattr(config, 'SFX_POP_PATH', 'sfx_pop.mp3'),
        'max_clips_per_video': getattr(config, 'MAX_CLIPS_PER_VIDEO', 2)
    }
    
    automation = None
    try:
        automation = MIHAutomation(automation_config)
        if len(sys.argv) > 1 and sys.argv[1] == '--test' and len(sys.argv) > 2:
            video_id = sys.argv[2]
            automation.run_single_video_test(video_id)
        else:
            print("📖 Usage: python your_script_name.py --test <YOUTUBE_VIDEO_ID>")
            print("   Example: python your_script_name.py --test dQw4w9WgXcQ")
    except Exception as e:
        logger.error(f"❌ An unhandled error occurred during execution: {e}", exc_info=True)
    finally:
        if automation:
            automation.cleanup()
        print("🏁 System shutdown.")

if __name__ == "__main__":
    main()