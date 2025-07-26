# Installation Requirements:
# pip install google-generativeai google-api-python-client google-auth-httplib2 google-auth-oauthlib gTTS pytrends yt-dlp

# Setup Instructions:
# 1. Install Python 3.8+
# 2. Install requirements above using pip.
# 3. Install FFmpeg (https://ffmpeg.org/download.html) and ensure it's in your system's PATH.
# 4. Get a YouTube Data API v3 key.
# 5. Get a Google Gemini API key.
# 6. Setup OAuth credentials (credentials.json) for YouTube uploading.
# 7. Create and configure a 'config.py' file with your settings (see create_example_config function for a template).
# 8. Run from your terminal. For usage, run: python mih_automation.py --help

import os
import re
import json
import time
import logging
import subprocess
import uuid
import tempfile
import shutil
import sys
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Any
from dataclasses import dataclass, field
from pathlib import Path

# --- Dependency Check ---
try:
    import google.generativeai as genai
    from googleapiclient.discovery import build, Resource
    from googleapiclient.http import MediaFileUpload
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from gtts import gTTS
    from pytrends.request import TrendReq
except ImportError as e:
    print(f"ERROR: A required library is missing. Please run the command below:")
    print(f"pip install google-generativeai google-api-python-client google-auth-httplib2 google-auth-oauthlib gTTS pytrends yt-dlp")
    print(f"(Missing library: {e.name})")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Data Classes for Structure ---

@dataclass
class MIHConfig:
    """Configuration for MIH content style and parameters."""
    expert_name: str = "Dr. Linda Greenwall"
    expert_handle: str = "@DrGreenwall"
    min_clip_duration: int = 15
    max_clip_duration: int = 90
    target_duration: int = 45
    clips_per_video: int = 3
    brand_colors: Dict[str, str] = field(default_factory=lambda: {
        'primary': '#2E8B57',
        'secondary': '#FF6B6B',
        'accent': '#4ECDC4',
        'text': '#FFFFFF',
        'bg_gradient_start': '#1a1a2e',
        'bg_gradient_end': '#16213e'
    })
    trending_mih_topics: List[str] = field(default_factory=lambda: [
        "MIH causes", "chalky teeth", "ICON treatment", "pediatric whitening",
        "enamel defects", "children tooth discoloration", "MIH prevention",
        "baby teeth problems", "white spots teeth", "dental anxiety kids"
    ])

@dataclass
class TrendingTopic:
    """Represents a single trending topic related to MIH."""
    keyword: str
    search_volume: int
    rising_trend: bool
    related_queries: List[str]
    urgency_score: float

@dataclass
class EnhancedVideoClip:
    """Represents a fully processed, ready-to-upload video clip."""
    clip_id: str
    start_time: float
    end_time: float
    transcript: str
    source_video_id: str
    source_title: str
    source_url: str
    catchy_title: str
    engaging_description: str
    viral_hooks: List[str]
    target_tags: List[str]
    trending_score: float
    parent_appeal_score: float
    file_path: Optional[str] = None
    duration: float = 0.0
    subtitle_segments: List[Dict] = field(default_factory=list)
    thumbnail_path: Optional[str] = None

    def __post_init__(self):
        self.duration = self.end_time - self.start_time

# --- Core Logic Classes ---

class TrendingTopicsManager:
    """Manages fetching and caching trending topics using pytrends."""
    def __init__(self, config: MIHConfig):
        self.config = config
        self.trending_cache_file = Path('trending_mih_topics.json')
        self.cache_duration = timedelta(days=7)

    def get_trending_topics(self) -> List[TrendingTopic]:
        """Gets trending topics, from cache if available and fresh, otherwise fetches new data."""
        cached_data = self._load_cached_trends()
        if cached_data and self._is_cache_fresh(cached_data):
            logger.info("Loading trending topics from fresh cache.")
            return [TrendingTopic(**topic) for topic in cached_data['topics']]

        logger.info("Fetching new trending topics from Google Trends.")
        trending_topics = []
        try:
            pytrends = TrendReq(hl='en-US', tz=360)
            for keyword in self.config.trending_mih_topics:
                try:
                    pytrends.build_payload([keyword], timeframe='now 7-d')
                    interest_data = pytrends.interest_over_time()
                    related_queries_data = pytrends.related_queries()

                    if not interest_data.empty:
                        avg_interest = interest_data[keyword].mean()
                        is_rising = self._is_trend_rising(interest_data[keyword])
                        related = []
                        if keyword in related_queries_data and related_queries_data[keyword]['top'] is not None:
                            related = related_queries_data[keyword]['top']['query'].head(5).tolist()

                        urgency_score = self._calculate_urgency_score(avg_interest, is_rising, keyword)
                        trending_topics.append(TrendingTopic(
                            keyword=keyword, search_volume=int(avg_interest),
                            rising_trend=is_rising, related_queries=related,
                            urgency_score=urgency_score
                        ))
                    time.sleep(2)  # Be respectful to the API
                except Exception as e:
                    logger.warning(f"Could not fetch trends for '{keyword}': {e}")
                    continue
        except Exception as e:
            logger.error(f"Failed to connect to Google Trends. Using fallback topics. Error: {e}")
            return self._get_fallback_topics()

        trending_topics.sort(key=lambda x: x.urgency_score, reverse=True)
        self._cache_trends(trending_topics)
        return trending_topics

    def _is_trend_rising(self, series) -> bool:
        if len(series) < 3: return False
        recent_avg = series.tail(3).mean()
        earlier_avg = series.head(len(series) // 2).mean()
        return recent_avg > earlier_avg * 1.1

    def _calculate_urgency_score(self, avg_interest: float, is_rising: bool, keyword: str) -> float:
        base_score = min(avg_interest / 100.0, 1.0)
        if is_rising: base_score *= 1.5
        high_value_keywords = ['MIH', 'chalky teeth', 'ICON treatment', 'pediatric whitening']
        if any(hvk.lower() in keyword.lower() for hvk in high_value_keywords):
            base_score *= 1.3
        return min(base_score, 1.0)

    def _load_cached_trends(self) -> Optional[Dict]:
        if self.trending_cache_file.exists():
            try:
                with open(self.trending_cache_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading trend cache: {e}")
        return None

    def _is_cache_fresh(self, cached_data: Dict) -> bool:
        try:
            cache_time = datetime.fromisoformat(cached_data['timestamp'])
            return datetime.now() - cache_time < self.cache_duration
        except (KeyError, ValueError):
            return False

    def _cache_trends(self, topics: List[TrendingTopic]):
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'topics': [t.__dict__ for t in topics]
            }
            with open(self.trending_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except IOError as e:
            logger.error(f"Could not write to trend cache file: {e}")

    def _get_fallback_topics(self) -> List[TrendingTopic]:
        return [TrendingTopic(k, 50, False, [], 0.5) for k in self.config.trending_mih_topics]

class EnhancedContentGenerator:
    """Uses Google Gemini to generate titles, descriptions, and find viral clips."""
    def __init__(self, api_key: str, config: MIHConfig, trending_manager: TrendingTopicsManager):
        self.config = config
        self.trending_manager = trending_manager
        self.model = None
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash-latest')
        except Exception as e:
            logger.error(f"Failed to initialize Gemini AI. Content generation will use fallbacks. Error: {e}")

    def find_viral_clips(self, transcript: str, video_title: str, trending_topics: List[TrendingTopic]) -> List[Dict]:
        """Identifies the most promising clips from a transcript using AI."""
        if not self.model:
            return self._fallback_clip_detection(transcript)

        trending_context = "\n".join([f"- {t.keyword} ({'RISING' if t.rising_trend else 'STEADY'})" for t in trending_topics[:5]])
        prompt = f"""
        Analyze the transcript of a video titled "{video_title}" featuring Dr. Linda Greenwall, a world-renowned expert in Molar Incisor Hypomineralisation (MIH).

        Your task is to identify the {self.config.clips_per_video} most viral-worthy clips. Each clip should be between {self.config.min_clip_duration} and {self.config.max_clip_duration} seconds.
        Prioritize clips that are highly relevant to these currently trending topics:
        {trending_context}

        For each clip, focus on content that:
        1. Is aimed at concerned parents.
        2. Offers clear, actionable advice or a surprising insight.
        3. Starts with a strong hook to grab attention.

        Provide your response ONLY as a valid JSON array. Do not include any other text or formatting.
        The JSON should have this exact structure:
        [
          {{
            "start_timestamp": <start time in seconds>,
            "end_timestamp": <end time in seconds>,
            "viral_hook": "A 3-second hook for the clip, e.g., 'The shocking reason your child's teeth have white spots'.",
            "key_takeaway": "A brief summary of the clip's main point."
          }}
        ]

        Transcript to analyze:
        ---
        {transcript[:15000]}
        ---
        """
        try:
            response = self.model.generate_content(prompt)
            json_text = self._extract_json_from_text(response.text)
            if not json_text:
                raise ValueError("AI response did not contain valid JSON.")
            
            clips_data = json.loads(json_text)
            valid_clips = [clip for clip in clips_data if self._validate_clip_data(clip)]
            
            if valid_clips:
                for clip in valid_clips:
                    clip['trending_score'] = self._calculate_clip_trending_score(clip, trending_topics)
                valid_clips.sort(key=lambda x: x.get('trending_score', 0), reverse=True)
                return valid_clips[:self.config.clips_per_video]
            
        except (json.JSONDecodeError, ValueError, Exception) as e:
            logger.error(f"AI failed to find clips. Using fallback. Reason: {e}\nAI Response: {response.text if 'response' in locals() else 'N/A'}")
        
        return self._fallback_clip_detection(transcript)

    def generate_viral_content(self, transcript_clip: str, duration: float, trending_topics: List[TrendingTopic], clip_data: Dict) -> Dict:
        """Generates a catchy title, description, and hashtags for a video clip."""
        if not self.model:
            return self._fallback_content_generation(transcript_clip)

        trending_context = "\n".join([f"- {t.keyword}" for t in trending_topics[:3]])
        prompt = f"""
        You are a social media expert creating content for a YouTube Short. The clip is {duration:.0f} seconds long and features Dr. Linda Greenwall, an MIH expert.
        The target audience is worried parents.

        Clip Information:
        - Viral Hook: "{clip_data.get('viral_hook', 'Important MIH advice')}"
        - Key Takeaway: "{clip_data.get('key_takeaway', 'Expert tips for children dental health')}"
        - Transcript Snippet: "{transcript_clip}"
        - Trending Topics: {trending_context}
        
        Generate a title (max 60 chars), description (max 200 chars), and 3 relevant hashtags.
        
        Return ONLY a valid JSON object with this structure:
        {{
            "title": "A short, viral-style title.",
            "description": "An engaging, short description with a call to action.",
            "hashtags": ["#HashtagOne", "#HashtagTwo", "#HashtagThree"]
        }}
        """
        try:
            response = self.model.generate_content(prompt)
            json_text = self._extract_json_from_text(response.text)
            if not json_text:
                raise ValueError("AI response did not contain valid JSON.")
            
            content = json.loads(json_text)
            return self._validate_and_clean_content(content)
        except (json.JSONDecodeError, ValueError, Exception) as e:
            logger.error(f"AI failed to generate content. Using fallback. Reason: {e}\nAI Response: {response.text if 'response' in locals() else 'N/A'}")

        return self._fallback_content_generation(transcript_clip)

    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """Finds and extracts a JSON object or array from a string."""
        # Find the first '{' or '['
        first_bracket = -1
        for i, char in enumerate(text):
            if char in '[{':
                first_bracket = i
                break
        
        if first_bracket == -1: return None
        
        # Find the last '}' or ']'
        last_bracket = -1
        for i, char in enumerate(reversed(text)):
            if char in ']}':
                last_bracket = len(text) - 1 - i
                break
                
        if last_bracket == -1 or last_bracket < first_bracket: return None

        return text[first_bracket:last_bracket+1]

    def _calculate_clip_trending_score(self, clip: Dict, trending_topics: List[TrendingTopic]) -> float:
        clip_text = f"{clip.get('viral_hook', '')} {clip.get('key_takeaway', '')}".lower()
        score = 0.0
        for topic in trending_topics:
            if topic.keyword.lower() in clip_text:
                score += topic.urgency_score * (1.5 if topic.rising_trend else 1.0)
            for query in topic.related_queries:
                if query.lower() in clip_text:
                    score += topic.urgency_score * 0.5
        return min(score, 1.0)

    def _validate_clip_data(self, clip: Dict) -> bool:
        return ('start_timestamp' in clip and 'end_timestamp' in clip and
                isinstance(clip['start_timestamp'], (int, float)) and
                isinstance(clip['end_timestamp'], (int, float)) and
                self.config.min_clip_duration <= (clip['end_timestamp'] - clip['start_timestamp']) <= self.config.max_clip_duration)

    def _validate_and_clean_content(self, content: Dict) -> Dict:
        title = content.get('title', 'MIH Expert Advice')[:60]
        description = content.get('description', 'Expert MIH guidance from Dr. Greenwall.')[:200]
        hashtags = content.get('hashtags', [])
        
        if not isinstance(hashtags, list): hashtags = []
        cleaned_tags = [f"#{re.sub(r'[^#a-zA-Z0-9]', '', tag).lstrip('#')}" for tag in hashtags if isinstance(tag, str)]
        cleaned_tags = [tag for tag in cleaned_tags if len(tag) > 1][:5] # Limit to 5 tags
        
        if len(cleaned_tags) < 3:
            default_tags = ['#MIH', '#DrGreenwall', '#PediatricDentistry']
            cleaned_tags.extend(tag for tag in default_tags if tag not in cleaned_tags)

        return {'title': title, 'description': description, 'hashtags': cleaned_tags[:3]}

    def _fallback_clip_detection(self, transcript: str) -> List[Dict]:
        logger.info("Using fallback clip detection method.")
        # Simple keyword-based fallback
        mih_keywords = ['MIH', 'molar', 'incisor', 'hypomineralisation', 'enamel', 'whitening', 'ICON']
        # For simplicity, just return one clip
        return [{
            'start_timestamp': 30.0,
            'end_timestamp': 30.0 + self.config.target_duration,
            'viral_hook': f"Important information about {mih_keywords[0]}",
            'key_takeaway': f"Learn about {mih_keywords[0]} from Dr. Greenwall",
            'trending_score': 0.5
        }]

    def _fallback_content_generation(self, transcript_clip: str) -> Dict:
        logger.info("Using fallback content generation method.")
        return {
            'title': "Dr. Greenwall's Expert MIH Advice",
            'description': "Essential guidance on Molar Incisor Hypomineralisation from a leading expert. Parents need to see this!",
            'hashtags': ["#MIH", "#DrGreenwall", "#PediatricDentistry"]
        }

class TranscriptProcessor:
    """Downloads and parses video transcripts using yt-dlp."""
    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir

    def get_transcript(self, video_id: str) -> Optional[List[Dict[str, Any]]]:
        """Downloads and parses the best available English subtitle file for a video."""
        try:
            output_template = self.temp_dir / f"{video_id}.%(ext)s"
            cmd = [
                'yt-dlp', '--write-auto-subs', '--write-subs', '--sub-langs', 'en.*',
                '--sub-format', 'srt', '--skip-download', '--socket-timeout', '45',
                '--retries', '3', '-o', str(output_template), f'https://www.youtube.com/watch?v={video_id}'
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True)

            srt_files = list(self.temp_dir.glob(f"{video_id}*.srt"))
            if not srt_files:
                logger.warning(f"No subtitles found for video {video_id}.")
                return None
            
            # Prefer manually created subs over auto-generated ones
            manual_subs = [f for f in srt_files if 'auto' not in f.name.lower()]
            best_sub_file = manual_subs[0] if manual_subs else srt_files[0]
            
            logger.info(f"Parsing transcript from: {best_sub_file.name}")
            return self._parse_srt(best_sub_file)

        except subprocess.CalledProcessError as e:
            logger.error(f"yt-dlp failed for video {video_id}. Stderr: {e.stderr}")
        except Exception as e:
            logger.error(f"Error getting transcript for {video_id}: {e}")
        return None

    def _parse_srt(self, srt_file: Path) -> Optional[List[Dict]]:
        content = srt_file.read_text(encoding='utf-8', errors='ignore')
        blocks = re.findall(r'(\d+)\n([\d:,]+ --> [\d:,]+)\n(.*?)\n\n', content, re.DOTALL)
        if not blocks: return None

        transcript = []
        for _, timestamp_line, text_lines in blocks:
            try:
                start_str, end_str = timestamp_line.split(' --> ')
                text = ' '.join(text_lines.strip().split('\n'))
                text = re.sub(r'<[^>]+>', '', text) # Remove HTML-like tags
                
                if text:
                    transcript.append({
                        'text': text,
                        'start': self._parse_srt_timestamp(start_str),
                        'end': self._parse_srt_timestamp(end_str)
                    })
            except ValueError:
                continue
        return transcript

    def _parse_srt_timestamp(self, ts: str) -> float:
        ts = ts.replace(',', '.')
        h, m, s = map(float, ts.split(':'))
        return h * 3600 + m * 60 + s

class EnhancedVideoProcessor:
    """Handles all video processing tasks using FFmpeg."""
    def __init__(self, config: MIHConfig, output_dir: Path, temp_dir: Path, sfx_path: Optional[str] = None):
        self.config = config
        self.output_dir = output_dir
        self.temp_dir = temp_dir
        self.sfx_path = sfx_path
        self.font_path = self._get_system_font()
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def download_source_video(self, video_id: str) -> Optional[Path]:
        """Downloads the best quality MP4 source video."""
        logger.info(f"Downloading source video: {video_id}")
        try:
            output_pattern = self.temp_dir / f"source_{video_id}.%(ext)s"
            cmd = [
                'yt-dlp', '-f', 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                '--merge-output-format', 'mp4', '--socket-timeout', '60',
                '--retries', '5', '--no-playlist', '--no-warnings',
                '-o', str(output_pattern), f'https://www.youtube.com/watch?v={video_id}'
            ]
            self._run_command(cmd, "yt-dlp download", timeout=600)
            
            video_files = list(self.temp_dir.glob(f"source_{video_id}.mp4"))
            if video_files and video_files[0].exists():
                logger.info(f"Source video downloaded to {video_files[0]}")
                return video_files[0]
            
        except Exception as e:
            logger.error(f"Failed to download source video {video_id}: {e}")
        return None

    def create_viral_clip(self, source_file: Path, clip_data: Dict, content_data: Dict, subtitle_segments: List[Dict]) -> Optional[Path]:
        """Orchestrates the creation of a complete viral clip with intro, main content, and outro."""
        clip_id = uuid.uuid4().hex[:8]
        final_output = self.output_dir / f"viral_clip_{clip_id}_{source_file.stem}.mp4"
        temp_files = []
        
        try:
            logger.info(f"Creating intro for clip '{content_data['title']}'")
            intro_path = self._create_branded_intro_outro(
                title=content_data['title'],
                hook=clip_data.get('viral_hook', ''),
                is_intro=True
            )
            if intro_path: temp_files.append(intro_path)

            logger.info("Creating main clip content.")
            main_clip_path = self._create_enhanced_main_clip(
                source_file,
                clip_data['start_timestamp'],
                clip_data['end_timestamp'],
                subtitle_segments
            )
            if not main_clip_path:
                raise ValueError("Failed to create the main video clip.")
            temp_files.append(main_clip_path)

            logger.info("Creating outro.")
            outro_path = self._create_branded_intro_outro(is_intro=False)
            if outro_path: temp_files.append(outro_path)

            components_to_concat = [f for f in [intro_path, main_clip_path, outro_path] if f]
            if len(components_to_concat) > 1:
                logger.info(f"Concatenating {len(components_to_concat)} video parts.")
                self._concatenate_video_components(components_to_concat, final_output)
            else:
                shutil.move(main_clip_path, final_output)

            if final_output.exists() and final_output.stat().st_size > 1000:
                logger.info(f"Successfully created final clip: {final_output}")
                return final_output
            
        except Exception as e:
            logger.error(f"Failed during viral clip creation: {e}", exc_info=True)
        finally:
            for temp_file in temp_files:
                temp_file.unlink(missing_ok=True)
        return None
        
    def _create_branded_intro_outro(self, title: str = "", hook: str = "", is_intro: bool = True) -> Optional[Path]:
        duration = 4.0 if is_intro else 3.5
        output_path = self.temp_dir / f"{'intro' if is_intro else 'outro'}_{uuid.uuid4().hex[:6]}.mp4"
        
        if is_intro:
            text = hook if hook else f"Dr. Greenwall on: {title}"
            bg_color = self.config.brand_colors['bg_gradient_start']
            main_text_filter = self._create_text_filter(title[:40], 60, '(h-text_h)/2-100', 'white')
            sub_text_filter1 = self._create_text_filter(self.config.expert_name, 40, '(h-text_h)/2+50', self.config.brand_colors['accent'])
            sub_text_filter2 = self._create_text_filter('MIH Expert', 28, '(h-text_h)/2+120', 'white@0.8')
        else:
            text = "Follow for more MIH expert tips!"
            bg_color = self.config.brand_colors['bg_gradient_end']
            main_text_filter = self._create_text_filter('FOLLOW FOR MORE', 55, '(h-text_h)/2-80', 'white')
            sub_text_filter1 = self._create_text_filter(self.config.expert_handle, 45, '(h-text_h)/2-20', self.config.brand_colors['accent'])
            sub_text_filter2 = self._create_text_filter('LIKE • SUBSCRIBE', 32, '(h-text_h)/2+100', self.config.brand_colors['secondary'])

        tts_file = self._create_tts_audio(text)
        if not tts_file: return None

        cmd = [
            'ffmpeg', '-y', '-f', 'lavfi', '-i', f'color=c={bg_color}:s=1080x1920:d={duration}',
            '-i', str(tts_file)
        ]
        
        video_filters = [
            'format=yuv420p',
            'zoompan=z=\'min(zoom+0.0015,1.2)\':d=125:x=\'iw/2-(iw/zoom/2)\':y=\'ih/2-(ih/zoom/2)\':s=1080x1920',
            main_text_filter, sub_text_filter1, sub_text_filter2, 'setsar=1'
        ]
        
        filter_complex_parts = [f"[0:v]{','.join(video_filters)}[v_out]"]
        
        if self.sfx_path and Path(self.sfx_path).exists():
            cmd.extend(['-i', self.sfx_path])
            filter_complex_parts.append('[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=2,volume=1.5[a_out]')
        else:
            filter_complex_parts.append('[1:a]volume=1.2[a_out]')

        cmd.extend([
            '-filter_complex', ';'.join(filter_complex_parts),
            '-map', '[v_out]', '-map', '[a_out]',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'aac', '-b:a', '192k',
            '-t', str(duration), str(output_path)
        ])
        
        try:
            self._run_command(cmd, "intro/outro generation", timeout=60)
            if output_path.exists() and output_path.stat().st_size > 1000:
                return output_path
        finally:
            tts_file.unlink(missing_ok=True)
        return None

    def _create_enhanced_main_clip(self, source_file: Path, start: float, end: float, subtitles: List[Dict]) -> Optional[Path]:
        output_path = self.temp_dir / f"main_clip_{uuid.uuid4().hex[:6]}.mp4"
        srt_file = None
        try:
            srt_file = self._create_srt_file(subtitles)
            if not srt_file:
                logger.warning("Could not create subtitle file, proceeding without subtitles.")

            # Filter to crop and pad the video to a 9:16 aspect ratio
            video_filters = [
                'scale=1080:-1,crop=iw:min(iw*16/9\\,ih),scale=1080:1920,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
                'eq=contrast=1.1:saturation=1.2:brightness=0.03',
                'unsharp=5:5:0.8:5:5:0.0',
                f"drawtext=text='{self._escape_text(self.config.expert_handle)}':fontcolor=white@0.8:fontsize=32:x=w-tw-30:y=30:box=1:boxcolor=black@0.5:boxborderw=8{self._get_font_filter()}",
            ]
            
            if srt_file:
                subtitle_path_escaped = self._escape_path_for_filter(srt_file)
                subtitle_style = "FontName=Arial Black,FontSize=36,PrimaryColour=&HFFFFFF,BackColour=&H99000000,BorderStyle=1,Outline=1,Shadow=1,Alignment=2,MarginV=150,Bold=-1"
                video_filters.append(f"subtitles=filename='{subtitle_path_escaped}':force_style='{subtitle_style}'")

            video_filters.append('setsar=1')
            
            cmd = [
                'ffmpeg', '-y', '-ss', str(start), '-to', str(end), '-i', str(source_file),
                '-vf', ','.join(video_filters),
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '21',
                '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(output_path)
            ]
            
            self._run_command(cmd, "main clip creation", timeout=300)
            if output_path.exists() and output_path.stat().st_size > 1000:
                return output_path

        finally:
            if srt_file: srt_file.unlink(missing_ok=True)
        return None
        
    def _concatenate_video_components(self, components: List[Path], output_path: Path):
        list_file = self.temp_dir / 'concat_list.txt'
        with open(list_file, 'w') as f:
            for comp in components:
                f.write(f"file '{comp.resolve()}'\n")

        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(list_file),
            '-c', 'copy', str(output_path)
        ]
        self._run_command(cmd, "video concatenation")
        list_file.unlink(missing_ok=True)
        
    def _create_text_filter(self, text: str, fontsize: int, y: str, color: str) -> str:
        return f"drawtext=text='{self._escape_text(text)}':fontsize={fontsize}:fontcolor={color}:x=(w-text_w)/2:y={y}:box=1:boxcolor=black@0.4:boxborderw=10{self._get_font_filter()}"

    def _get_font_filter(self) -> str:
        if self.font_path:
            return f":fontfile='{self._escape_path_for_filter(self.font_path)}'"
        return ""

    def _create_tts_audio(self, text: str) -> Optional[Path]:
        try:
            tts_file = self.temp_dir / f"tts_{uuid.uuid4().hex[:6]}.mp3"
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(str(tts_file))
            if tts_file.exists() and tts_file.stat().st_size > 100:
                return tts_file
        except Exception as e:
            logger.error(f"gTTS failed to create audio for '{text}': {e}")
        return None

    def _create_srt_file(self, segments: List[Dict]) -> Optional[Path]:
        if not segments: return None
        srt_file = self.temp_dir / f"subs_{uuid.uuid4().hex[:6]}.srt"
        with open(srt_file, 'w', encoding='utf-8') as f:
            for i, seg in enumerate(segments, 1):
                f.write(f"{i}\n")
                f.write(f"{self._seconds_to_srt_time(seg['start'])} --> {self._seconds_to_srt_time(seg['end'])}\n")
                f.write(f"{self._format_subtitle_text(seg['text'])}\n\n")
        return srt_file
    
    def _format_subtitle_text(self, text: str, max_chars_per_line: int = 35) -> str:
        # Simple word wrap
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 > max_chars_per_line:
                lines.append(current_line)
                current_line = word
            else:
                current_line += f" {word}"
        lines.append(current_line.strip())
        return '\n'.join(line.strip() for line in lines[:3]) # Max 3 lines

    def _seconds_to_srt_time(self, seconds: float) -> str:
        return str(timedelta(seconds=seconds)).replace('.', ',')[:12]
        
    def _escape_text(self, text: str) -> str:
        return text.replace("'", r"'\''").replace(":", r"\:").replace("%", r"\%").replace(",", r"\,")

    def _escape_path_for_filter(self, path: Path) -> str:
        # FFmpeg filters on Windows require escaping backslashes and the drive colon
        path_str = str(path.resolve())
        if sys.platform == "win32":
            return path_str.replace('\\', '/').replace(':', '\\:')
        return path_str

    def _get_system_font(self) -> Optional[str]:
        font_map = {
            "win32": ["C:/Windows/Fonts/Arialbd.ttf", "C:/Windows/Fonts/arial.ttf"],
            "darwin": ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"],
            "linux": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
        }
        for font in font_map.get(sys.platform, []):
            if Path(font).exists(): return font
        logger.warning("Could not find a default system font. Subtitles may have a basic appearance.")
        return None
        
    def _run_command(self, cmd: List[str], task_name: str, timeout: int = 120):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, check=True, encoding='utf-8'
            )
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Error during {task_name}. FFmpeg/yt-dlp command failed.")
            logger.error(f"Command: {' '.join(cmd)}")
            logger.error(f"Stderr: {e.stderr}")
            raise e # Re-raise to stop the process
        except FileNotFoundError:
            logger.error(f"Command '{cmd[0]}' not found. Is it installed and in your PATH?")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred running command for {task_name}: {e}")
            raise

class EnhancedYouTubeManager:
    """Manages authentication and video uploads to one or more YouTube channels."""
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    def __init__(self, channel_configs: List[Dict]):
        self.channel_configs = channel_configs
        self.youtube_services: Dict[str, Dict] = {}
        self.upload_stats = {'successful': 0, 'failed': 0}

    def authenticate_channels(self):
        """Authenticates with all configured channels, creating token files."""
        for i, config in enumerate(self.channel_configs):
            channel_key = f"channel_{i+1}"
            creds_file = Path(config.get('credentials_file', ''))
            
            if not creds_file.exists():
                logger.error(f"Credentials file '{creds_file}' for channel '{config.get('name', channel_key)}' not found. Skipping.")
                continue

            token_file = Path(f'token_{creds_file.stem}.json')
            creds = None
            try:
                if token_file.exists():
                    creds = Credentials.from_authorized_user_file(str(token_file), self.SCOPES)
                
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        logger.info(f"Refreshing token for {config.get('name', channel_key)}...")
                        creds.refresh(Request())
                    else:
                        logger.info(f"Performing new OAuth flow for {config.get('name', channel_key)}...")
                        flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), self.SCOPES)
                        creds = flow.run_local_server(port=0)
                    
                    with open(token_file, 'w') as token:
                        token.write(creds.to_json())
                
                self.youtube_services[channel_key] = {
                    'service': build('youtube', 'v3', credentials=creds),
                    'config': config,
                    'name': config.get('name', channel_key)
                }
                logger.info(f"Successfully authenticated channel: {config.get('name', channel_key)}")
            except Exception as e:
                logger.error(f"Failed to authenticate channel '{config.get('name', channel_key)}': {e}")

    def upload_viral_clip(self, clip: EnhancedVideoClip) -> bool:
        """Uploads a single clip to all authenticated and configured channels."""
        if not self.youtube_services:
            logger.warning("No YouTube channels are authenticated. Cannot upload.")
            return False
        if not clip.file_path or not Path(clip.file_path).exists():
            logger.error(f"Cannot upload clip {clip.clip_id}: File path is missing or invalid.")
            return False

        any_successful = False
        for channel_data in self.youtube_services.values():
            success = self._upload_to_channel(clip, channel_data['service'], channel_data['name'], channel_data['config'])
            if success:
                self.upload_stats['successful'] += 1
                any_successful = True
            else:
                self.upload_stats['failed'] += 1
        return any_successful

    def _upload_to_channel(self, clip: EnhancedVideoClip, service: Resource, channel_name: str, channel_config: Dict) -> bool:
        try:
            logger.info(f"Starting upload of '{clip.catchy_title}' to channel '{channel_name}'.")
            body = {
                'snippet': {
                    'title': clip.catchy_title,
                    'description': self._format_description(clip, channel_config),
                    'tags': list(set(clip.target_tags + ['MIH', 'DrGreenwall', 'ChalkyTeeth'])),
                    'categoryId': '27' # Education
                },
                'status': { 'privacyStatus': channel_config.get('privacy_status', 'private') }
            }
            media = MediaFileUpload(clip.file_path, chunksize=-1, resumable=True)
            request = service.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info(f"Upload to '{channel_name}' is {int(status.progress() * 100)}% complete.")
            
            video_id = response.get('id')
            logger.info(f"SUCCESS: Uploaded to '{channel_name}'. Video ID: {video_id} (https://youtu.be/{video_id})")
            return True
        except Exception as e:
            logger.error(f"FAILED to upload to '{channel_name}': {e}")
            return False

    def _format_description(self, clip: EnhancedVideoClip, channel_config: Dict) -> str:
        parts = [
            clip.engaging_description,
            "\n---\n",
            "Dr. Linda Greenwall is a globally recognized expert in Molar Incisor Hypomineralisation (MIH) and pediatric whitening.",
            "Follow for more expert tips to protect your child's smile!",
            "\n#MIH #PediatricDentistry #DrGreenwall #ChildrensDental #EnamelDefects #ChalkyTeeth",
        ]
        if 'website' in channel_config:
            parts.append(f"\nVisit our website: {channel_config['website']}")
        return '\n'.join(parts)

class MIHAutomationSystem:
    """Main orchestrator for the entire video processing and uploading pipeline."""
    def __init__(self, system_config: Dict):
        self.config = MIHConfig()
        # Allow overriding MIHConfig from system_config
        self.config.clips_per_video = system_config.get('max_clips_per_video', self.config.clips_per_video)

        self.system_config = system_config
        self.temp_dir = Path(tempfile.gettempdir()) / f"mih_automation_{uuid.uuid4().hex[:6]}"
        self.temp_dir.mkdir(exist_ok=True, parents=True)
        logger.info(f"Using temporary directory: {self.temp_dir}")
        
        self.trending_manager = TrendingTopicsManager(self.config)
        self.content_generator = EnhancedContentGenerator(
            system_config['gemini_api_key'], self.config, self.trending_manager
        )
        self.video_processor = EnhancedVideoProcessor(
            self.config, Path(system_config['output_dir']), self.temp_dir, system_config.get('sfx_path')
        )
        self.transcript_processor = TranscriptProcessor(self.temp_dir)
        self.youtube_manager = EnhancedYouTubeManager(system_config['upload_channels'])
        
        self.processed_videos_file = Path('processed_mih_videos.json')
        self.processed_videos = self._load_processed_videos()
        self.session_stats = {'videos_processed': 0, 'clips_created': 0, 'uploads_attempted': 0, 'errors': 0}

    def process_video(self, video_id: str, test_mode: bool = False) -> None:
        """Processes a single video: finds clips, creates them, and (optionally) uploads."""
        if video_id in self.processed_videos and not test_mode:
            logger.info(f"Video {video_id} has already been processed. Skipping.")
            return

        source_video_path = None
        try:
            logger.info(f"--- Starting processing for video ID: {video_id} ---")
            self.session_stats['videos_processed'] += 1
            
            video_data = self._get_video_metadata(video_id)
            if not video_data:
                raise ValueError(f"Could not retrieve metadata for video {video_id}")

            transcript_segments = self.transcript_processor.get_transcript(video_id)
            if not transcript_segments:
                raise ValueError("Failed to extract transcript.")
            full_transcript = ' '.join(seg['text'] for seg in transcript_segments)

            trending_topics = self.trending_manager.get_trending_topics()
            
            viral_clip_definitions = self.content_generator.find_viral_clips(
                full_transcript, video_data['title'], trending_topics
            )
            if not viral_clip_definitions:
                raise ValueError("AI analysis did not identify any suitable clips.")
            logger.info(f"AI identified {len(viral_clip_definitions)} potential clips.")
            
            source_video_path = self.video_processor.download_source_video(video_id)
            if not source_video_path:
                raise ValueError("Failed to download source video.")

            created_clips: List[EnhancedVideoClip] = []
            for i, clip_def in enumerate(viral_clip_definitions, 1):
                logger.info(f"--- Generating clip {i}/{len(viral_clip_definitions)} from {video_id} ---")
                try:
                    start_time, end_time = clip_def['start_timestamp'], clip_def['end_timestamp']
                    clip_segments = [s for s in transcript_segments if s['end'] > start_time and s['start'] < end_time]
                    
                    # Adjust subtitle timestamps to be relative to the clip's start time
                    for seg in clip_segments:
                        seg['start'] = max(0, seg['start'] - start_time)
                        seg['end'] = min(end_time - start_time, seg['end'] - start_time)

                    clip_transcript_text = ' '.join(seg['text'] for seg in clip_segments)
                    content_data = self.content_generator.generate_viral_content(
                        clip_transcript_text, end_time - start_time, trending_topics, clip_def
                    )
                    
                    clip_file_path = self.video_processor.create_viral_clip(
                        source_video_path, clip_def, content_data, clip_segments
                    )
                    
                    if clip_file_path:
                        self.session_stats['clips_created'] += 1
                        created_clips.append(EnhancedVideoClip(
                            clip_id=uuid.uuid4().hex, start_time=start_time, end_time=end_time,
                            transcript=clip_transcript_text, source_video_id=video_id,
                            source_title=video_data['title'], source_url=video_data['url'],
                            catchy_title=content_data['title'], engaging_description=content_data['description'],
                            viral_hooks=[clip_def.get('viral_hook', '')], target_tags=content_data['hashtags'],
                            trending_score=clip_def.get('trending_score', 0.5), parent_appeal_score=0.5,
                            file_path=str(clip_file_path), subtitle_segments=clip_segments
                        ))
                except Exception as e:
                    logger.error(f"Failed to process a clip definition: {e}", exc_info=True)
                    self.session_stats['errors'] += 1
            
            if test_mode:
                logger.info(f"TEST MODE: {len(created_clips)} clips created but not uploaded.")
                for clip in created_clips:
                    logger.info(f"  -> Created Clip: {clip.file_path}")
            elif created_clips:
                self.youtube_manager.authenticate_channels()
                for clip in created_clips:
                    self.session_stats['uploads_attempted'] += 1
                    self.youtube_manager.upload_viral_clip(clip)
            
            self.processed_videos.add(video_id)
            self._save_processed_videos()
            
        except Exception as e:
            logger.error(f"FATAL ERROR while processing video {video_id}: {e}", exc_info=True)
            self.session_stats['errors'] += 1
        finally:
            if source_video_path: source_video_path.unlink(missing_ok=True)
            logger.info(f"--- Finished processing for video ID: {video_id} ---")

    def _get_video_metadata(self, video_id: str) -> Optional[Dict]:
        try:
            youtube = build('youtube', 'v3', developerKey=self.system_config['youtube_api_key'])
            response = youtube.videos().list(part="snippet,statistics", id=video_id).execute()
            
            if not response.get("items"): return None
            
            item = response["items"][0]
            return {
                'id': video_id,
                'title': item['snippet']['title'],
                'url': f"https://www.youtube.com/watch?v={video_id}"
            }
        except Exception as e:
            logger.error(f"Could not fetch YouTube video metadata: {e}")
            return None

    def _load_processed_videos(self) -> Set[str]:
        if self.processed_videos_file.exists():
            try:
                with open(self.processed_videos_file, 'r') as f:
                    return set(json.load(f).get('processed_videos', []))
            except (json.JSONDecodeError, IOError):
                pass
        return set()

    def _save_processed_videos(self):
        try:
            with open(self.processed_videos_file, 'w') as f:
                json.dump({
                    'processed_videos': list(self.processed_videos),
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
        except IOError:
            logger.error("Could not save list of processed videos.")

    def _print_session_summary(self):
        logger.info("\n" + "="*50)
        logger.info("SESSION SUMMARY")
        logger.info("="*50)
        logger.info(f"Videos Processed:      {self.session_stats['videos_processed']}")
        logger.info(f"Viral Clips Created:   {self.session_stats['clips_created']}")
        logger.info(f"Uploads Successful:    {self.youtube_manager.upload_stats['successful']}")
        logger.info(f"Uploads Failed:        {self.youtube_manager.upload_stats['failed']}")
        logger.info(f"Errors Encountered:    {self.session_stats['errors']}")
        logger.info("="*50 + "\n")

    def cleanup(self):
        logger.info(f"Cleaning up temporary directory: {self.temp_dir}")
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.error(f"Failed to clean up temporary directory {self.temp_dir}: {e}")

def create_example_config():
    """Creates a template config.py file for the user to fill out."""
    config_content = '''"""
Dr. Linda Greenwall MIH Content Automation - Configuration File
Please fill in your API keys and file paths below.
"""

# --- REQUIRED SETTINGS ---

# Google Gemini API Key for AI content generation and analysis
# Get one from Google AI Studio: https://aistudio.google.com/
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"

# YouTube Data API v3 Key (for fetching video metadata)
# Get one from Google Cloud Console: https://console.cloud.google.com/apis/
YOUTUBE_API_KEY = "YOUR_YOUTUBE_API_KEY_HERE"

# --- UPLOAD SETTINGS ---

# Configuration for the YouTube channel(s) to upload to.
# You can add more dictionaries to the list to upload to multiple channels.
UPLOAD_CHANNELS = [
    {
        "name": "Dr. Greenwall's MIH Shorts",
        # Path to the credentials.json file from your OAuth 2.0 Client ID setup.
        # This is required for uploading.
        "credentials_file": "credentials.json",
        # "private", "unlisted", or "public"
        "privacy_status": "private",
        # Optional: Add links to be included in the video description.
        "website": "https://www.drgreenwall.com",
    }
]

# --- DIRECTORY AND FILE PATHS ---

# Output directory for the final processed video clips
OUTPUT_DIR = "viral_mih_clips"

# Optional: Path to a short sound effect file (e.g., .mp3, .wav) for intros/outros
SFX_POP_PATH = None  # Example: "sfx/pop.mp3"

# --- ADVANCED SETTINGS ---

# Maximum number of clips to generate from a single long-form video
MAX_CLIPS_PER_VIDEO = 3
'''
    try:
        with open('config_example.py', 'w') as f:
            f.write(config_content)
        logger.info("Created example configuration file: config_example.py")
        logger.info("Please edit it with your details and rename it to 'config.py'.")
    except IOError as e:
        logger.error(f"Could not create config_example.py: {e}")

def main():
    print("--- Dr. Linda Greenwall MIH Content Automation System ---")
    
    if shutil.which("ffmpeg") is None:
        logger.error("FATAL: ffmpeg is not installed or not in your system's PATH.")
        logger.error("Please install it from https://ffmpeg.org/download.html")
        return

    try:
        import config
    except ImportError:
        logger.error("FATAL: config.py not found!")
        create_example_config()
        return

    required_settings = ['YOUTUBE_API_KEY', 'GEMINI_API_KEY', 'UPLOAD_CHANNELS']
    for setting in required_settings:
        if not hasattr(config, setting) or 'YOUR_' in str(getattr(config, setting, '')):
            logger.error(f"FATAL: Please configure '{setting}' in your config.py file.")
            return

    system_config = {
        'youtube_api_key': config.YOUTUBE_API_KEY,
        'gemini_api_key': config.GEMINI_API_KEY,
        'upload_channels': config.UPLOAD_CHANNELS,
        'output_dir': getattr(config, 'OUTPUT_DIR', 'viral_mih_clips'),
        'sfx_path': getattr(config, 'SFX_POP_PATH', None),
        'max_clips_per_video': getattr(config, 'MAX_CLIPS_PER_VIDEO', 3)
    }

    parser = argparse.ArgumentParser(
        description="Automates creating and uploading viral short clips from Dr. Greenwall's long-form MIH content.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--video', type=str, help='Process a single YouTube video ID.')
    parser.add_argument('--batch', type=str, nargs='+', help='Process a batch of YouTube video IDs separated by spaces.')
    parser.add_argument('--test', type=str, metavar='VIDEO_ID', help='Run in test mode for a single video. Creates clips but does not upload.')
    args = parser.parse_args()

    automation = None
    try:
        automation = MIHAutomationSystem(system_config)
        
        if args.video:
            automation.process_video(args.video)
        elif args.batch:
            for video_id in args.batch:
                automation.process_video(video_id)
                time.sleep(10) # Pause between videos
        elif args.test:
            automation.process_video(args.test, test_mode=True)
        else:
            parser.print_help()
            print("\nExample: python mih_automation.py --video dQw4w9WgXcQ")

    except KeyboardInterrupt:
        logger.info("Automation stopped by user.")
    except Exception as e:
        logger.error(f"A fatal, unhandled error occurred: {e}", exc_info=True)
    finally:
        if automation:
            automation._print_session_summary()
            automation.cleanup()
        print("--- Automation System Shutdown ---")

if __name__ == "__main__":
    main()