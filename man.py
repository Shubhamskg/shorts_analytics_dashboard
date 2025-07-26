import re
import unicodedata
import json
import time
import logging
import subprocess
import asyncio
import uuid
import tempfile
import shutil
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path
import edge_tts


try:
    import google.generativeai as genai
    from googleapiclient.discovery import build
    # from googleapri_client.http import MediaFileUpload
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from gtts import gTTS # Kept for potential fallback, though edge_tts is preferred
    import pytrends
    from pytrends.request import TrendReq
except ImportError as e:
    print(f"ERROR: Missing required libraries. Please install: pip install {e.name}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class MIHConfig:
    expert_name: str = "Dr. Linda Greenwall"
    expert_handle: str = "@DrGreenwall"
    min_clip_duration: int = 15
    max_clip_duration: int = 90
    target_duration: int = 60
    clips_per_video: int = 50
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
    keyword: str
    search_volume: int
    rising_trend: bool
    related_queries: List[str]
    urgency_score: float

@dataclass
class EnhancedVideoClip:
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

class TrendingTopicsManager:
    def __init__(self, config: MIHConfig):
        self.config = config
        self.trending_cache_file = 'trending_mih_topics.json'
        self.cache_duration = timedelta(days=7)
        
    def get_trending_topics(self) -> List[TrendingTopic]:
        cached_data = self._load_cached_trends()
        if cached_data and self._is_cache_fresh(cached_data):
            logger.info("Using cached trending topics")
            return [TrendingTopic(**topic) for topic in cached_data['topics']]
        
        logger.info("Fetching trending topics from Google Trends")
        trending_topics = []
        try:
            pytrends = TrendReq(hl='en-US', tz=360)
            for keyword in self.config.trending_mih_topics:
                try:
                    pytrends.build_payload([keyword], timeframe='now 7-d')
                    interest_data = pytrends.interest_over_time()
                    related_queries = pytrends.related_queries()
                    
                    if not interest_data.empty:
                        avg_interest = interest_data[keyword].mean()
                        is_rising = self._is_trend_rising(interest_data[keyword])
                        
                        related = []
                        if keyword in related_queries and related_queries[keyword]['top'] is not None:
                            related = related_queries[keyword]['top']['query'].head(5).tolist()
                        
                        urgency_score = self._calculate_urgency_score(avg_interest, is_rising, keyword)
                        
                        trending_topics.append(TrendingTopic(
                            keyword=keyword,
                            search_volume=int(avg_interest),
                            rising_trend=is_rising,
                            related_queries=related,
                            urgency_score=urgency_score
                        ))
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"Failed to get trends for '{keyword}': {e}")
                    continue
        except Exception as e:
            logger.error(f"Trending topics fetch failed: {e}")
            return self._get_fallback_topics()
        
        trending_topics.sort(key=lambda x: x.urgency_score, reverse=True)
        self._cache_trends(trending_topics)
        logger.info(f"Retrieved {len(trending_topics)} trending topics")
        return trending_topics
    
    def _is_trend_rising(self, series) -> bool:
        if len(series) < 3:
            return False
        recent_avg = series.tail(3).mean()
        earlier_avg = series.head(len(series)//2).mean()
        return recent_avg > earlier_avg * 1.2
    
    def _calculate_urgency_score(self, avg_interest: float, is_rising: bool, keyword: str) -> float:
        base_score = min(avg_interest / 100.0, 1.0)
        if is_rising:
            base_score *= 1.5
        high_value_keywords = ['MIH', 'chalky teeth', 'ICON treatment', 'pediatric whitening']
        if any(hvk.lower() in keyword.lower() for hvk in high_value_keywords):
            base_score *= 1.3
        return min(base_score, 1.0)
    
    def _load_cached_trends(self) -> Optional[Dict]:
        try:
            if Path(self.trending_cache_file).exists():
                with open(self.trending_cache_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return None
    
    def _is_cache_fresh(self, cached_data: Dict) -> bool:
        try:
            cache_time = datetime.fromisoformat(cached_data['timestamp'])
            return datetime.now() - cache_time < self.cache_duration
        except:
            return False
    
    def _cache_trends(self, topics: List[TrendingTopic]):
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'topics': [
                    {
                        'keyword': t.keyword,
                        'search_volume': t.search_volume,
                        'rising_trend': t.rising_trend,
                        'related_queries': t.related_queries,
                        'urgency_score': t.urgency_score
                    }
                    for t in topics
                ]
            }
            with open(self.trending_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except Exception:
            pass
    
    def _get_fallback_topics(self) -> List[TrendingTopic]:
        fallback_keywords = [
            "MIH treatment", "chalky teeth children", "pediatric whitening",
            "enamel defects kids", "children dental problems"
        ]
        return [
            TrendingTopic(
                keyword=keyword,
                search_volume=50,
                rising_trend=False,
                related_queries=[],
                urgency_score=0.5
            )
            for keyword in fallback_keywords
        ]

class EnhancedContentGenerator:
    def __init__(self, api_key: str, config: MIHConfig, trending_manager: TrendingTopicsManager):
        self.config = config
        self.trending_manager = trending_manager
        self.model = None
        
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash-lite-preview-06-17')
            logger.info("AI content generator initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI: {e}")
    
    def find_viral_clips(self, transcript: str, video_data: Dict, trending_topics: List[TrendingTopic]) -> List[Dict]:
        if not self.model:
            logger.warning("AI model not available, using fallback clip detection")
            return self._fallback_clip_detection(transcript)
                
        trending_context = self._build_trending_context(trending_topics)
                
        prompt = f"""
    ROLE: You are an expert viral content strategist specializing in healthcare and parenting content.

    CONTEXT:
    Video Title: "{video_data.get('title', '')}"
    Speaker: Dr. Linda Greenwall (Global MIH & Pediatric Whitening Expert)
    Target Audience: Worried parents seeking dental health solutions

    TRANSCRIPT:
    "{transcript}"

    TRENDING TOPICS (prioritize clips matching these):
    {trending_context}

    VIRAL CLIP CRITERIA:
    1. HOOK POWER: Opens with shock, surprise, or urgent concern
    2. PARENT TRIGGER: Addresses specific fears/problems parents face
    3. AUTHORITY SIGNAL: Showcases Dr. Greenwall's expertise clearly
    4. ACTIONABLE VALUE: Provides immediate, practical advice
    5. EMOTIONAL RESONANCE: Creates strong emotional response
    6. TRENDING ALIGNMENT: Matches current search behaviors

    ANALYSIS INSTRUCTIONS:
    1. Scan transcript for moments with highest emotional intensity
    2. Identify knowledge gaps that create "aha!" moments
    3. Look for counterintuitive/surprising medical insights
    4. Find specific timestamps where Dr. Greenwall provides definitive answers
    5. Prioritize clips that solve immediate parent concerns

    OUTPUT FORMAT:
    Return EXACTLY 10-15 clips as a JSON array. Each clip must be 15-90 seconds long.

    REQUIRED JSON STRUCTURE:
    [
        {{
            "start_timestamp": 45,
            "end_timestamp": 75,
            "viral_hook": "What every parent gets WRONG about white spots on teeth",
            "parent_trigger": "fear/concern being addressed",
            "authority_moment": "specific expertise Dr. Greenwall demonstrates",
            "action_item": "immediate step parents can take",
            "trending_match": "matching search term",
            "emotional_score": 9,
            "urgency_level": "high",
            "shareability_factor": "parents will tag other parents"
        }}
    ]

    VIRAL HOOK EXAMPLES:
    - "The mistake 90% of parents make with chalky teeth"
    - "Why dentists DON'T tell you this about MIH"
    - "The 30-second test that reveals if your child needs urgent dental care"
    - "What white spots on teeth REALLY mean (it's not what you think)"

    FOCUS ON:
    - Moments of revelation or surprise
    - Times when Dr. Greenwall contradicts common beliefs
    - Specific symptoms parents can check for
    - Immediate actions parents should take
    - Prevention strategies that work

    AVOID:
    - Generic advice without specific context
    - Technical explanations without parent relevance
    - Clips without clear emotional hooks
    - Content that doesn't feature Dr. Greenwall's expertise

    Return ONLY the JSON array, no additional text.
    """
        
        try:
            logger.info("AI analyzing transcript for viral clips with enhanced prompt")
            response = self.model.generate_content(prompt)
            
            # Enhanced JSON extraction with better error handling
            json_match = re.search(r'\[.*?\]', response.text, re.DOTALL)
            if json_match:
                clips_data = json.loads(json_match.group(0))
                valid_clips = []
                
                for clip in clips_data:
                    if self._validate_enhanced_clip_data(clip):
                        # Enhanced scoring system
                        clip['trending_score'] = self._calculate_enhanced_trending_score(clip, trending_topics)
                        clip['viral_potential'] = self._calculate_viral_potential(clip)
                        valid_clips.append(clip)
                            
                if valid_clips:
                    # Sort by combined viral potential and trending score
                    valid_clips.sort(
                        key=lambda x: (x.get('viral_potential', 0) * 0.6 + x.get('trending_score', 0) * 0.4), 
                        reverse=True
                    )
                    logger.info(f"AI found {len(valid_clips)} viral clips")
                    return valid_clips[:self.config.clips_per_video]
                    
        except Exception as e:
            logger.error(f"AI clip detection failed: {e}")
                
        return self._fallback_clip_detection(transcript)

    def _validate_enhanced_clip_data(self, clip: Dict) -> bool:
        """Enhanced validation for clip data"""
        required_fields = [
            'start_timestamp', 'end_timestamp', 'viral_hook', 
            'parent_trigger', 'authority_moment', 'action_item',
            'emotional_score', 'urgency_level'
        ]
        
        # Check all required fields exist
        if not all(field in clip for field in required_fields):
            return False
        
        # Validate timestamp logic
        if clip['end_timestamp'] <= clip['start_timestamp']:
            return False
        
        # Check clip duration (15-90 seconds)
        duration = clip['end_timestamp'] - clip['start_timestamp']
        if duration < 15 or duration > 90:
            return False
        
        # Validate emotional score
        if not isinstance(clip.get('emotional_score'), (int, float)) or clip['emotional_score'] < 1 or clip['emotional_score'] > 10:
            return False
        
        return True

    def _calculate_viral_potential(self, clip: Dict) -> float:
        """Calculate viral potential score based on multiple factors"""
        score = 0
        
        # Emotional score weight (30%)
        score += clip.get('emotional_score', 0) * 0.3
        
        # Urgency level weight (25%)
        urgency_weights = {'high': 1.0, 'medium': 0.7, 'low': 0.4}
        score += urgency_weights.get(clip.get('urgency_level', 'low'), 0.4) * 2.5
        
        # Hook quality weight (25%)
        hook = clip.get('viral_hook', '').lower()
        hook_keywords = ['shocking', 'mistake', 'wrong', 'secret', 'never', 'always', 'truth', 'revealed']
        hook_score = sum(1 for keyword in hook_keywords if keyword in hook)
        score += min(hook_score * 0.5, 2.5)
        
        # Action item clarity weight (20%)
        action = clip.get('action_item', '')
        if action and len(action) > 20:  # Substantial action item
            score += 2.0
        
        return min(score, 10.0)  # Cap at 10

    def _calculate_enhanced_trending_score(self, clip: Dict, trending_topics: List[TrendingTopic]) -> float:
        """Enhanced trending score calculation"""
        if not trending_topics:
            return 0
        
        clip_text = f"{clip.get('viral_hook', '')} {clip.get('parent_trigger', '')} {clip.get('trending_match', '')}"
        max_score = 0
        
        for topic in trending_topics:
            # Check for keyword matches
            # Assuming TrendingTopic has 'keywords' attribute, if not, use 'keyword'
            topic_keywords = [topic.keyword] + topic.related_queries 
            keyword_matches = sum(1 for kw in topic_keywords if kw.lower() in clip_text.lower())
            
            # Weight by urgency score
            topic_score = (keyword_matches * topic.urgency_score * 5) # Scale to max 10
            max_score = max(max_score, topic_score)
        
        return min(max_score, 10.0)  # Cap at 10

    def generate_viral_content(self, transcript: str, duration: float, trending_topics: List[TrendingTopic], clip_data: Dict = None) -> Dict:
        if not self.model:
            logger.warning("AI model not available, using fallback content generation")
            return self._fallback_content_generation(transcript, clip_data)
                
        trending_context = self._build_trending_context(trending_topics)
        viral_hook = clip_data.get('viral_hook', '') if clip_data else ''
        key_takeaway = clip_data.get('key_takeaway', '') if clip_data else ''
        parent_trigger = clip_data.get('parent_trigger', '') if clip_data else ''
        authority_moment = clip_data.get('authority_moment', '') if clip_data else ''
        urgency_level = clip_data.get('urgency_level', 'medium') if clip_data else 'medium'
                
        prompt = f"""
    ROLE: You are a viral content strategist specializing in healthcare content that drives massive parent engagement.

    MISSION: Create scroll-stopping social media content that makes worried parents INSTANTLY click, watch, and share.

    CLIP DETAILS:
    Duration: {duration:.0f} seconds
    Transcript: "{transcript}"
    Viral Hook: "{viral_hook}"
    Key Takeaway: "{key_takeaway}"
    Parent Trigger: "{parent_trigger}"
    Authority Signal: "{authority_moment}"
    Urgency Level: {urgency_level}

    TRENDING TOPICS (incorporate when relevant):
    {trending_context}

    TARGET AUDIENCE PSYCHOLOGY:
    - Worried parents seeking immediate answers
    - High anxiety about child's dental health
    - Trust medical experts but want accessible info
    - Share content that helps other parents
    - Respond to urgency and fear-based triggers

    VIRAL CONTENT FORMULAS:

    TITLE PATTERNS (choose most fitting):
    1. SHOCK REVEAL: "The [Problem] 90% of Parents Miss"
    2. MISTAKE PATTERN: "Stop [Common Action] - It's Making [Problem] Worse"
    3. EXPERT WARNING: "Dentist: '[Shocking Truth]' About [Condition]"
    4. PARENT ALERT: "[Time Frame] to Fix [Problem] Before It's Too Late"
    5. COUNTER-INTUITIVE: "Why [Common Belief] is Wrong About [Condition]"
    6. INSIDER SECRET: "What Dentists Don't Tell Parents About [Issue]"

    DESCRIPTION FORMULA:
    - Line 1: Attention grabber (shock/fear/curiosity)
    - Line 2: Expert credibility (Dr. Greenwall's authority)
    - Line 3: Specific actionable insight
    - Line 4: Urgency/consequence of inaction
    - Line 5: Call to action + emotion

    HASHTAG STRATEGY:
    - 3-5 HIGH-TRAFFIC parent hashtags
    - 2-3 MEDICAL/DENTAL authority hashtags
    - 1-2 TRENDING topic hashtags
    - 1-2 EMOTIONAL trigger hashtags
    - 1 BRAND/EXPERT hashtag

    EMOTIONAL TRIGGERS TO MAXIMIZE:
    - Fear of missing critical signs
    - Guilt about not knowing sooner
    - Hope for solutions
    - Urgency to act now
    - Relief from expert guidance

    VIRAL LANGUAGE PATTERNS:
    - "STOP doing this..."
    - "The truth about..."
    - "What they don't tell you..."
    - "Before it's too late..."
    - "Every parent needs to know..."
    - "The shocking reason..."
    - "Finally revealed..."

    Return ONLY this JSON format:
    {{
        "title": "Scroll-stopping title that creates curiosity gap",
        "description": "Multi-line description with emojis, urgency, and call-to-action",
        "hashtags": ["#array", "#of", "#strategic", "#hashtags"],
        "hook_type": "type of viral hook used",
        "emotional_trigger": "primary emotion targeted",
        "urgency_score": 8,
        "shareability_factor": "why parents will share this"
    }}
    """
        
        try:
            logger.info("AI generating enhanced viral content")
            response = self.model.generate_content(prompt)
            
            # Enhanced JSON extraction
            json_match = re.search(r'\{.*?\}', response.text, re.DOTALL)
            if json_match:
                content = json.loads(json_match.group(0))
                validated_content = self._validate_and_enhance_content(content, clip_data)
                return validated_content
                
        except Exception as e:
            logger.error(f"AI content generation failed: {e}")
                
        return self._fallback_content_generation(transcript, clip_data)

    def _validate_and_enhance_content(self, content: Dict, clip_data: Dict = None) -> Dict:
        """Enhanced content validation and optimization"""
        
        # Validate required fields
        required_fields = ['title', 'description', 'hashtags']
        for field in required_fields:
            if field not in content:
                logger.warning(f"Missing required field: {field}")
                return self._fallback_content_generation("", clip_data)
        
        # Enhance title if needed
        title = content['title']
        if not self._is_title_viral(title):
            title = self._enhance_title_virality(title, clip_data)
        
        # Enhance description
        description = content['description']
        if not self._has_viral_elements(description):
            description = self._add_viral_elements(description, clip_data)
        
        # Optimize hashtags
        hashtags = content['hashtags']
        if len(hashtags) < 5:
            hashtags = self._expand_hashtags(hashtags, clip_data)
        
        # Add engagement metrics
        enhanced_content = {
            'title': title,
            'description': description,
            'hashtags': hashtags,
            'hook_type': content.get('hook_type', 'curiosity'),
            'emotional_trigger': content.get('emotional_trigger', 'concern'),
            'urgency_score': content.get('urgency_score', 5),
            'shareability_factor': content.get('shareability_factor', 'parent helping other parents'),
            'estimated_engagement': self._calculate_engagement_potential(content, clip_data)
        }
        
        return enhanced_content

    def _is_title_viral(self, title: str) -> bool:
        """Check if title has viral characteristics"""
        viral_patterns = [
            r'stop\s+\w+',
            r'why\s+\w+',
            r'what\s+\w+\s+don\'t',
            r'the\s+\w+\s+secret',
            r'mistake\s+\w+\s+make',
            r'shocking\s+\w+',
            r'before\s+it\'s\s+too\s+late',
            r'every\s+parent',
            r'finally\s+revealed'
        ]
        
        title_lower = title.lower()
        return any(re.search(pattern, title_lower) for pattern in viral_patterns)

    def _enhance_title_virality(self, title: str, clip_data: Dict = None) -> str:
        """Enhance title with viral elements"""
        if not clip_data:
            return title
        
        urgency_level = clip_data.get('urgency_level', 'medium')
        parent_trigger = clip_data.get('parent_trigger', '')
        
        # Add urgency prefixes based on level
        if urgency_level == 'high':
            prefixes = ['🚨 URGENT:', 'STOP:', 'WARNING:', 'ALERT:']
        elif urgency_level == 'medium':
            prefixes = ['Important:', 'Attention Parents:', 'Must Know:']
        else:
            prefixes = ['FYI:', 'Heads Up:', 'PSA:']
        
        # Select appropriate prefix
        import random
        prefix = random.choice(prefixes)
        
        return f"{prefix} {title}"

    def _has_viral_elements(self, description: str) -> bool:
        """Check if description has viral elements"""
        viral_elements = [
            '🚨', '💡', '👆', '👇', '⚠️',  # Emojis
            'tag a parent', 'save this', 'share this', 'don\'t wait',  # CTAs
            'shocked', 'finally', 'revealed', 'truth'  # Emotional words
        ]
        
        description_lower = description.lower()
        return any(element.lower() in description_lower for element in viral_elements)

    def _add_viral_elements(self, description: str, clip_data: Dict = None) -> str:
        """Add viral elements to description"""
        viral_ctas = [
            "👆 Save this for later",
            "Tag a parent who needs to see this 👇",
            "Share to help other parents! 🙏",
            "Don't scroll past this! ⚠️"
        ]
        
        emotional_boosters = [
            "This changes everything! 💡",
            "I wish I knew this sooner 😳",
            "Finally, answers! 🙌",
            "Every parent needs to know this! 🚨"
        ]
        
        # Add emotional booster at the start
        import random
        booster = random.choice(emotional_boosters)
        cta = random.choice(viral_ctas)
        
        return f"{booster} {description} {cta}"

    def _expand_hashtags(self, hashtags: List[str], clip_data: Dict = None) -> List[str]:
        """Expand hashtag list for maximum reach"""
        base_hashtags = set(hashtags)
        
        # Parent-focused hashtags
        parent_hashtags = [
            '#ParentingTips', '#MomLife', '#DadLife', '#ParentAlert',
            '#ChildHealth', '#WorriedParent', '#ParentingHacks'
        ]
        
        # Dental/Medical hashtags
        medical_hashtags = [
            '#PediatricDentistry', '#ChildDental', '#MIH', '#DentalHealth',
            '#ToothCare', '#OralHealth', '#DentalExpert'
        ]
        
        # Emotional hashtags
        emotional_hashtags = [
            '#ParentGuilt', '#MomGuilt', '#ChildCare', '#ParentWorries',
            '#EarlyIntervention', '#PreventiveCare'
        ]
        
        # Authority hashtags
        authority_hashtags = [
            '#DrGreenwall', '#DentalExpert', '#MIHExpert', '#TrustedAdvice'
        ]
        
        # Add hashtags strategically
        all_additional = parent_hashtags + medical_hashtags + emotional_hashtags + authority_hashtags
        
        # Add non-duplicate hashtags
        for tag in all_additional:
            if tag not in base_hashtags and len(base_hashtags) < 12:
                base_hashtags.add(tag)
        
        return list(base_hashtags)

    def _calculate_engagement_potential(self, content: Dict, clip_data: Dict = None) -> float:
        """Calculate estimated engagement potential"""
        score = 0
        
        # Title viral score
        if self._is_title_viral(content.get('title', '')):
            score += 3
        
        # Description viral elements
        if self._has_viral_elements(content.get('description', '')):
            score += 2
        
        # Hashtag count bonus
        hashtag_count = len(content.get('hashtags', []))
        score += min(hashtag_count * 0.2, 2)
        
        # Urgency score bonus
        urgency = content.get('urgency_score', 5)
        score += urgency * 0.3
        
        # Clip data bonus
        if clip_data:
            emotional_score = clip_data.get('emotional_score', 5)
            score += emotional_score * 0.2
        
        return min(score, 10.0)  # Cap at 10

    def _build_trending_context(self, trending_topics: List[TrendingTopic]) -> str:
        context_lines = []
        for topic in trending_topics:
            status = "RISING" if topic.rising_trend else "STEADY"
            context_lines.append(f"- {topic.keyword} ({status}, {topic.search_volume} searches)")
        return '\n'.join(context_lines)
    
    def _calculate_clip_trending_score(self, clip: Dict, trending_topics: List[TrendingTopic]) -> float:
        clip_text = f"{clip.get('viral_hook', '')} {clip.get('key_takeaway', '')}".lower()
        
        score = 0.0
        for topic in trending_topics:
            if topic.keyword.lower() in clip_text:
                base_score = topic.urgency_score
                if topic.rising_trend:
                    base_score *= 1.5
                score += base_score
            
            for query in topic.related_queries:
                if query.lower() in clip_text:
                    score += topic.urgency_score * 0.5
        
        return min(score, 1.0)
    
    def _validate_clip_data(self, clip: Dict) -> bool:
        required_fields = ['start_timestamp', 'end_timestamp']
        if not all(field in clip for field in required_fields):
            return False
        
        duration = clip['end_timestamp'] - clip['start_timestamp']
        return self.config.min_clip_duration <= duration <= self.config.max_clip_duration
    
    def _validate_and_clean_content(self, content: Dict) -> Dict:
        title = content.get('title', 'MIH Expert Advice')[:60]
        if not title:
            title = "Dr. Greenwall's MIH Insight"
        
        description = content.get('description', 'Expert MIH guidance from Dr. Greenwall')
        
        hashtags = content.get('hashtags', [])
        if not isinstance(hashtags, list):
            hashtags = ['#MIH', '#DrGreenwall', '#PediatricDentistry']
        else:
            cleaned_hashtags = []
            for tag in hashtags:
                if isinstance(tag, str):
                    clean_tag = tag.strip()
                    if not clean_tag.startswith('#'):
                        clean_tag = f"#{clean_tag}"
                    clean_tag = re.sub(r'[^#\w]', '', clean_tag)
                    if len(clean_tag) > 1:
                        cleaned_hashtags.append(clean_tag)
            
            if len(cleaned_hashtags) < 3:
                default_tags = ['#MIH', '#DrGreenwall', '#PediatricDentistry', '#ChildrensDental', '#EnamelDefects']
                for tag in default_tags:
                    if tag not in cleaned_hashtags:
                        cleaned_hashtags.append(tag)
                        if len(cleaned_hashtags) >= 3:
                            break
            
            hashtags = cleaned_hashtags[:3]
        
        return {
            'title': title,
            'description': description,
            'hashtags': hashtags
        }
    
    def _fallback_clip_detection(self, transcript: str) -> List[Dict]:
        logger.info("Using fallback clip detection")
        words = transcript.split()
        if len(words) < 100:
            return []
        
        mih_keywords = ['MIH', 'molar', 'incisor', 'hypomineralisation', 'enamel', 'whitening', 'ICON']
        clips = []
        
        for keyword in mih_keywords:
            keyword_positions = [i for i, word in enumerate(words) if keyword.lower() in word.lower()]
            for pos in keyword_positions[:1]:
                start_pos = max(0, pos - 30)
                end_pos = min(len(words), pos + 60)
                
                start_time = start_pos * 2.5
                end_time = end_pos * 2.5
                
                if end_time - start_time >= self.config.min_clip_duration:
                    clips.append({
                        'start_timestamp': start_time,
                        'end_timestamp': min(start_time + self.config.target_duration, end_time),
                        'viral_hook': f"Important {keyword} information",
                        'parent_appeal': "Medium - contains relevant keyword",
                        'trending_match': keyword.lower(),
                        'key_takeaway': f"Learn about {keyword} from Dr. Greenwall",
                        'trending_score': 0.5
                    })
        
        return clips[:self.config.clips_per_video]
    
    def _fallback_content_generation(self, transcript: str, clip_data: Dict = None) -> Dict:
        logger.info("Using fallback content generation")
        
        key_terms = []
        mih_terms = ['MIH', 'molar', 'incisor', 'enamel', 'whitening', 'children', 'teeth']
        for term in mih_terms:
            if term.lower() in transcript.lower():
                key_terms.append(term)
        
        primary_term = key_terms[0] if key_terms else 'MIH'
        
        return {
            'title': f"Dr. Greenwall's {primary_term} Expert Advice",
            'description': f"Essential {primary_term} guidance from leading expert Dr. Linda Greenwall. Parents need to see this!",
            'hashtags': [f"#{primary_term}", "#DrGreenwall", "#PediatricDentistry"]
        }

class EnhancedVisualCreator:
    def __init__(self, config: MIHConfig, sfx_path: Optional[str] = None):
        self.config = config
        self.temp_dir = Path(tempfile.gettempdir()) / f"mih_visuals_{uuid.uuid4().hex[:6]}"
        self.temp_dir.mkdir(exist_ok=True, parents=True)
        self.sfx_path = sfx_path if sfx_path and Path(sfx_path).exists() else None
        self.font_path = self._get_system_font()
        logger.info(f"Visual creator initialized with temp dir: {self.temp_dir}")
        if self.sfx_path:
            logger.info(f"Sound effects enabled: {self.sfx_path}")
    
    def _escape_text_for_ffmpeg(self, text: str) -> str:
        """Properly escape text for FFmpeg drawtext filter"""
        if not text:
            return ""

        # Normalize unicode characters to closest ASCII equivalent where possible
        # This helps avoid 'Non-UTF-8 characters' errors with fonts or FFmpeg setup
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')

        # FFmpeg drawtext requires specific escaping:
        # Backslashes must be escaped: \ -> \\
        # Single quotes must be escaped: ' -> \'
        # Colons need to be escaped: : -> \:
        # Commas need to be escaped: , -> \,
        # Square brackets need to be escaped: [ -> \[ and ] -> \]
        # Semicolons need to be escaped: ; -> \;

        text = text.replace('\\', '\\\\')
        text = text.replace("'", "\\'") # Escape single quotes
        text = text.replace(':', '\\:') # Escape colons
        text = text.replace(',', '\\,') # Escape commas
        text = text.replace('[', '\\[') # Escape opening square brackets
        text = text.replace(']', '\\]') # Escape closing square brackets
        text = text.replace(';', '\\;') # Escape semicolons

        # Clean up multiple spaces (after escaping to avoid issues)
        text = ' '.join(text.split())

        return text

    def _escape_path_for_ffmpeg(self, path: str) -> str:
        """Escape a file path for use in FFmpeg filters, especially fontfile."""
        path = str(Path(path).resolve())
        # Convert backslashes to forward slashes for cross-platform compatibility with FFmpeg filters
        path = path.replace('\\', '/')
        # Escape colons for drive letters on Windows (e.g., C:/ -> C\:/)
        # Escape single quotes if present in path (unlikely but safe)
        path = path.replace("'", "\\'")
        path = path.replace(":", "\\:")
        return path

    def _get_drawtext_font_arg(self) -> str:
        """Constructs the font argument for FFmpeg drawtext filter."""
        if self.font_path:
            # Use fontfile if a specific font path is found
            return f"fontfile='{self._escape_path_for_ffmpeg(self.font_path)}'"
        else:
            # Fallback to a generic font name. This might still cause 'Fontconfig error'
            # if FFmpeg's font resolution system is broken.
            logger.warning("No specific font file found, falling back to 'Arial'. Text rendering might fail.")
            return "font='Arial'"

    def create_branded_intro(self, title: str, trending_hook: str = "", duration: float = 5.0) -> Optional[str]:
        output_path = self.temp_dir / f"intro_{uuid.uuid4().hex[:8]}.mp4"
        
        # Clean and escape the title properly
        clean_title = self._escape_text_for_ffmpeg(title) if title else "Amazing Content"
        clean_expert_name = self._escape_text_for_ffmpeg(self.config.expert_name) if (self.config and hasattr(self.config, 'expert_name') and self.config.expert_name) else "Expert"
        
        logger.info(f"Creating branded intro: {clean_title}...")
        
        intro_text = clean_title
        tts_file = asyncio.run(self._create_tts_audio(intro_text))
        
        if not tts_file:
            logger.error("Failed to create TTS audio for intro")
            return None
        
        # Path to the dental image (adjust path as needed)
        dental_image_path = "intro.jpg"  # Update with actual path
        if not Path(dental_image_path).exists():
            logger.error(f"Intro image not found at: {dental_image_path}. Cannot create intro.")
            return None

        cmd = [
            'ffmpeg', '-y', '-v', 'error',
            '-loop', '1', '-i', dental_image_path,  # Use dental image as background
            '-i', tts_file
        ]
        
        if self.sfx_path:
            cmd.extend(['-i', self.sfx_path])
        
        # Function to split title into lines based on character count
        def split_title(text, max_chars=30):
            words = text.split()
            lines = []
            current_line = ""
            
            for word in words:
                if not word: continue # Skip empty words
                if len(current_line + " " + word) <= max_chars:
                    current_line += (" " + word) if current_line else word
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            
            if current_line:
                lines.append(current_line)
            
            return lines[:3] # Limit to max 3 lines for intro
        
        # Split title into lines
        title_lines = split_title(clean_title)
        
        font_arg = self._get_drawtext_font_arg()

        # Build video filters
        video_filters = [
            'format=rgb24',
            'scale=1080:1920:force_original_aspect_ratio=decrease',  # Scale image to fit 9:16
            'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black',  # Pad to exact size
            'gblur=sigma=1.5',  # Slight blur for background effect
            'eq=brightness=0.3:contrast=1.2'  # Darken and increase contrast for text readability
        ]
        
        # Add semi-transparent overlay for better text readability
        video_filters.append('drawbox=x=0:y=750:w=1080:h=450:color=black@0.7:t=fill') # Adjusted Y and H for better fit
        
        # Add title text (handle 1, 2 or 3 lines)
        if len(title_lines) == 1:
            # Single line - center vertically
            video_filters.append(f"drawtext=text='{title_lines[0]}':fontsize=44:fontcolor=white:x=(w-text_w)/2:y=880:{font_arg}")
        elif len(title_lines) == 2:
            # Two lines - position them appropriately
            video_filters.append(f"drawtext=text='{title_lines[0]}':fontsize=44:fontcolor=white:x=(w-text_w)/2:y=840:{font_arg}")
            video_filters.append(f"drawtext=text='{title_lines[1]}':fontsize=44:fontcolor=white:x=(w-text_w)/2:y=900:{font_arg}")
        else: # 3 lines
            video_filters.append(f"drawtext=text='{title_lines[0]}':fontsize=40:fontcolor=white:x=(w-text_w)/2:y=820:{font_arg}")
            video_filters.append(f"drawtext=text='{title_lines[1]}':fontsize=40:fontcolor=white:x=(w-text_w)/2:y=870:{font_arg}")
            video_filters.append(f"drawtext=text='{title_lines[2]}':fontsize=40:fontcolor=white:x=(w-text_w)/2:y=920:{font_arg}")
        
        # Expert Insights badge
        video_filters.append(f"drawtext=text='EXPERT INSIGHTS':fontsize=20:fontcolor=white:x=(w-text_w)/2:y=1000:{font_arg}")
        
        # Expert name
        video_filters.append(f"drawtext=text='{clean_expert_name}':fontsize=38:fontcolor=yellow:x=(w-text_w)/2:y=1030:{font_arg}")
        
        # MIH Expert badge
        video_filters.append(f"drawtext=text='MIH EXPERT':fontsize=24:fontcolor=white:x=(w-text_w)/2:y=1080:{font_arg}")
        
        # Add subtle fade in effect
        video_filters.append(f'fade=t=in:st=0:d=0.5')
        
        # Add final settings
        video_filters.append('setsar=1')
        
        video_filter_chain = ','.join(video_filters)
        
        if self.sfx_path:
            audio_filter = '[1:a][2:a]amix=inputs=2:duration=first,volume=1.5[a_out]'
        else:
            audio_filter = '[1:a]volume=1.2[a_out]'
        
        filter_complex = f"[0:v]{video_filter_chain}[v_out];{audio_filter}"
        
        cmd.extend([
            '-filter_complex', filter_complex,
            '-map', '[v_out]', '-map', '[a_out]',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
            '-c:a', 'aac', '-b:a', '192k',
            '-pix_fmt', 'yuv420p', '-t', str(duration),
            str(output_path)
        ])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=60
            )
            
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000:
                logger.info(f"Intro created successfully: {output_path.name}")
                return str(output_path)
            else:
                logger.error(f"FFmpeg failed with return code {result.returncode}")
                logger.error(f"FFmpeg stderr: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg command timed out")
        except Exception as e:
            logger.error(f"Intro creation failed: {e}")
        finally:
            if tts_file and Path(tts_file).exists():
                Path(tts_file).unlink(missing_ok=True)
        
        return None

    def create_branded_outro(self, duration: float = 3.5) -> Optional[str]:
        output_path = self.temp_dir / f"outro_{uuid.uuid4().hex[:8]}.mp4"
        logger.info("Creating branded outro...")
        
        cta_text = "Follow for more M I H expert tips!"
        tts_file = asyncio.run(self._create_tts_audio(cta_text))

        if not tts_file:
            logger.error("Failed to create TTS audio for outro")
            return None
        
        # Path to the dental image (adjust path as needed)
        dental_image_path = "intro.jpg"  # Assuming intro.jpg can be used for outro too
        if not Path(dental_image_path).exists():
            logger.error(f"Outro image not found at: {dental_image_path}. Cannot create outro.")
            return None

        cmd = [
            'ffmpeg', '-y', '-v', 'error',
            '-loop', '1', '-i', dental_image_path,  # Use dental image as background
            '-i', tts_file
        ]
        
        if self.sfx_path:
            cmd.extend(['-i', self.sfx_path])
        
        # Clean and safe expert name
        clean_expert_name = self._escape_text_for_ffmpeg(self.config.expert_name) if (self.config and hasattr(self.config, 'expert_name') and self.config.expert_name) else "Expert"
        
        font_arg = self._get_drawtext_font_arg()
        
        # Enhanced video filters for catchy outro design
        video_filters = [
            'format=rgb24',
            'scale=1080:1920:force_original_aspect_ratio=decrease',  # Scale image to fit 9:16
            'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black',  # Pad to exact size
            'gblur=sigma=2',  # More blur for outro effect
            'eq=brightness=0.2:contrast=1.3',  # Darker with higher contrast
            
            # Add subtle color overlay (static instead of animated to avoid syntax issues)
            'colorbalance=rs=0.1:gs=0.2:bs=0.1',
            
            # Semi-transparent overlay for better text readability
            'drawbox=x=0:y=750:w=1080:h=450:color=black@0.7:t=fill', # Adjusted Y and H
            
            # Main CTA background with layered effect
            'drawbox=x=90:y=780:w=900:h=80:color=red@0.95:t=fill',
            'drawbox=x=95:y=785:w=890:h=70:color=white@0.1:t=fill',  # Inner highlight
            
            # Main CTA text with bold styling
            f"drawtext=text='FOLLOW FOR MORE':fontsize=42:fontcolor=white:x=(w-text_w)/2:y=805:{font_arg}",
            
            # Expert name background with gradient effect
            'drawbox=x=140:y=880:w=800:h=60:color=yellow@0.9:t=fill',
            'drawbox=x=145:y=885:w=790:h=50:color=orange@0.3:t=fill',  # Gradient effect
            
            # Expert name with dynamic styling
            f"drawtext=text='{clean_expert_name}':fontsize=36:fontcolor=black:x=(w-text_w)/2:y=900:{font_arg}",
            
            # MIH Expert Tips with modern styling
            'drawbox=x=200:y=960:w=680:h=50:color=blue@0.85:t=fill',
            'drawbox=x=205:y=965:w=670:h=40:color=cyan@0.2:t=fill',  # Inner glow
            f"drawtext=text='MIH EXPERT TIPS':fontsize=28:fontcolor=white:x=(w-text_w)/2:y=975:{font_arg}",
            
            # Like and Subscribe with call-to-action styling
            'drawbox=x=250:y=1030:w=580:h=40:color=green@0.9:t=fill',
            f"drawtext=text='LIKE and SUBSCRIBE':fontsize=26:fontcolor=white:x=(w-text_w)/2:y=1045:{font_arg}",
            
            # Add decorative elements (using simple shapes instead of emojis)
            'drawbox=x=150:y=820:w=15:h=15:color=yellow@0.8:t=fill',  # Star effect
            'drawbox=x=880:y=820:w=15:h=15:color=yellow@0.8:t=fill',  # Star effect
            'drawbox=x=200:y=1080:w=12:h=12:color=white@0.9:t=fill',  # Accent
            'drawbox=x=800:y=1080:w=12:h=12:color=white@0.9:t=fill',  # Accent
            
            # Professional tagline
            f"drawtext=text='Transform Your Smile Today!':fontsize=24:fontcolor=white:x=(w-text_w)/2:y=1120:{font_arg}",
            
            # Contact info or website
            f"drawtext=text='lindagreenwall.co.uk':fontsize=22:fontcolor=cyan:x=(w-text_w)/2:y=1160:{font_arg}",
            
            # Add fade in effect
            'fade=t=in:st=0:d=0.8',
            'setsar=1'
        ]
        
        video_filter_chain = ','.join(video_filters)
        
        if self.sfx_path:
            audio_filter = '[1:a][2:a]amix=inputs=2:duration=first,volume=1.3[a_out]'
        else:
            audio_filter = '[1:a]volume=1.1[a_out]'
        
        filter_complex = f"[0:v]{video_filter_chain}[v_out];{audio_filter}"
        
        cmd.extend([
            '-filter_complex', filter_complex,
            '-map', '[v_out]', '-map', '[a_out]',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
            '-c:a', 'aac', '-b:a', '192k',
            '-pix_fmt', 'yuv420p', '-t', str(duration),
            str(output_path)
        ])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=45
            )
            
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000:
                logger.info(f"Outro created successfully: {output_path.name}")
                return str(output_path)
            else:
                logger.error(f"FFmpeg failed with return code {result.returncode}")
                logger.error(f"FFmpeg stderr: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg command timed out")
        except Exception as e:
            logger.error(f"Outro creation failed: {e}")
        finally:
            if tts_file and Path(tts_file).exists():
                Path(tts_file).unlink(missing_ok=True)
        
        return None

    def create_enhanced_subtitles(self, segments: List[Dict], style_preset: str = "viral") -> Optional[str]:
        if not segments:
            logger.warning("No subtitle segments provided")
            return None
        
        srt_file = self.temp_dir / f"enhanced_subs_{uuid.uuid4().hex[:8]}.srt"
        logger.info(f"Creating enhanced subtitles with {len(segments)} segments")
        
        try:
            with open(srt_file, 'w', encoding='utf-8') as f:
                for i, seg in enumerate(segments, 1):
                    text = self._clean_text_for_subtitles(seg['text'])
                    
                    if style_preset == "viral":
                        text = self._apply_viral_subtitle_styling(text)
                    
                    text = self._split_subtitle_text(text)
                    
                    start_time = self._seconds_to_srt_time(seg['start'])
                    end_time = self._seconds_to_srt_time(seg['end'])
                    
                    f.write(f"{i}\n{start_time} --> {end_time}\n{text}\n\n")
            
            logger.info(f"Subtitles created successfully: {srt_file.name}")
            return str(srt_file)
        except Exception as e:
            logger.error(f"Subtitle creation failed: {e}")
            return None
    
    async def _create_tts_audio(self, text: str, lang: str = 'en') -> Optional[str]:
        try:
            tts_file = self.temp_dir / f"tts_{uuid.uuid4().hex[:8]}.mp3"
            clean_text = re.sub(r'[^\w\s\.\!\?\,]', '', text)

            if len(clean_text) > 200:
                clean_text = clean_text + "..."

            logger.info(f"tts_file: {tts_file}")
            
            communicate = edge_tts.Communicate(
                text=clean_text,
                voice="en-US-JennyNeural",  # American accent
                rate="+0%",
                pitch="+0Hz"
            )
            await communicate.save(str(tts_file))

            if tts_file.exists() and tts_file.stat().st_size > 100:
                logger.debug(f"TTS audio created: {clean_text}...")
                return str(tts_file)
        except Exception as e:
            logger.error(f"TTS audio creation failed: {e}")
        return None

    def _apply_viral_subtitle_styling(self, text: str) -> str:
        emphasis_words = ['MIH', 'WARNING', 'IMPORTANT', 'NEVER', 'ALWAYS', 'STOP', 'START', 'MUST', 'SHOULD']
        
        words = text.split()
        styled_words = []
        
        for word in words:
            word_clean = re.sub(r'[^\w]', '', word.upper())
            if word_clean in emphasis_words:
                styled_words.append(word.upper())
            else:
                styled_words.append(word)
        
        return ' '.join(styled_words)
    
    def _split_subtitle_text(self, text: str, max_chars_per_line: int = 35) -> str:
        words = text.split()
        if len(' '.join(words)) <= max_chars_per_line:
            return text
        
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 <= max_chars_per_line:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        if len(lines) > 2:
            lines = lines[:2]
            if not lines[1].endswith('...'):
                lines[1] += '...'
        
        return '\\N'.join(lines)
    
    def _clean_text_for_subtitles(self, text: str) -> str:
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\(.*?\)', '', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        sentences = text.split('.')
        capitalized_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                sentence = sentence[0].upper() + sentence[1:] if len(sentence) > 1 else sentence.upper()
                capitalized_sentences.append(sentence)
        
        return '. '.join(capitalized_sentences)
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
    
    def _get_system_font(self) -> Optional[str]:
        font_paths = {
            "win32": ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"],
            "darwin": ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Arial.ttf"],
            "linux": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf"]
        }
        
        system_fonts = font_paths.get(sys.platform, font_paths["linux"])
        for font_path in system_fonts:
            if Path(font_path).exists():
                logger.debug(f"Using system font: {font_path}")
                return font_path
        
        logger.warning("No system font found, FFmpeg's drawtext might fail.")
        return None
    
    def _run_ffmpeg_command(self, cmd: List[str], timeout: int = 120) -> bool:
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg command failed with code {result.returncode}: {result.stderr[:500]}")
                return False
            
            return True
        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg command timed out after {timeout} seconds")
            return False
        except Exception as e:
            logger.error(f"FFmpeg command failed with exception: {e}")
            return False
    
    def cleanup(self):
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.info("Visual creator temporary files cleaned up")
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")

class EnhancedVideoProcessor:
    def __init__(self, config: MIHConfig, output_dir: str, sfx_path: Optional[str] = None):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.visual_creator = EnhancedVisualCreator(config, sfx_path)
        self.transcript_processor = TranscriptProcessor()
        logger.info(f"Video processor initialized with output dir: {self.output_dir}")

    # Removed the duplicate _escape_text_for_ffmpeg method here.
    # It should only exist in EnhancedVisualCreator and be called via self.visual_creator.

    def download_source_video(self, video_id: str) -> Optional[str]:
        logger.info(f"Downloading source video: {video_id}")
        try:
            output_pattern = self.visual_creator.temp_dir / f"source_{video_id}.%(ext)s"
            
            cmd = [
                'yt-dlp',
                '-f', 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best',
                '--merge-output-format', 'mp4',
                '--socket-timeout', '60',
                '--retries', '5',
                '--no-playlist',
                '--no-warnings',
                '-o', str(output_pattern),
                f'https://www.youtube.com/watch?v={video_id}'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                video_files = list(self.visual_creator.temp_dir.glob(f"source_{video_id}.*"))
                video_files = [f for f in video_files if f.suffix in ['.mp4', '.mkv', '.webm']]
                
                if video_files:
                    logger.info(f"Video downloaded successfully: {video_files[0].name}")
                    return str(video_files[0])
                else:
                    logger.error("No video files found after download")
            else:
                logger.error(f"Download failed with return code {result.returncode}: {result.stderr}")
            
            return None
        except Exception as e:
            logger.error(f"Download error for {video_id}: {e}")
            return None
    
    def create_viral_clip(self, source_file: str, clip_data: Dict, content_data: Dict, subtitle_segments: List[Dict]) -> Optional[str]:
        clip_id = uuid.uuid4().hex[:8]
        final_output = self.output_dir / f"viral_clip_{clip_id}.mp4"
        
        logger.info(f"Creating viral clip: {content_data.get('title', '')[:50]}...")
        
        intro_path = None
        outro_path = None
        main_clip_path = None
        
        try:
            # Create intro
            logger.info("Creating intro...")
            intro_path = self.visual_creator.create_branded_intro(
                content_data['title'],
                clip_data.get('viral_hook', ''),
                duration=5.0
            )
            
            # Create outro
            logger.info("Creating outro...")
            outro_path = self.visual_creator.create_branded_outro(duration=3.5)
            
            # Create main clip
            logger.info("Creating main clip...")
            main_clip_path = self._create_enhanced_main_clip(
                source_file,
                clip_data['start_timestamp'],
                clip_data['end_timestamp'],
                subtitle_segments,
                content_data
            )
            
            if not main_clip_path:
                logger.error("Failed to create main clip")
                return None
            
            # Combine all parts
            components = []
            if intro_path and Path(intro_path).exists():
                components.append(intro_path)
                logger.info("Intro will be included in final clip")
            else:
                logger.warning("Intro not available for final clip")
            
            components.append(main_clip_path)
            logger.info("Main clip added to final clip")
            
            if outro_path and Path(outro_path).exists():
                components.append(outro_path)
                logger.info("Outro will be included in final clip")
            else:
                logger.warning("Outro not available for final clip")
            
            if len(components) > 1:
                logger.info(f"Combining {len(components)} video components...")
                success = self._concatenate_video_components(components, str(final_output))
            else:
                logger.info("Only main clip available, copying to final output")
                shutil.copy(main_clip_path, final_output) # Use copy, not move, if main_clip_path should be cleaned up later.
                success = True
            
            if success and final_output.exists():
                file_size = final_output.stat().st_size / (1024 * 1024)  # MB
                logger.info(f"Viral clip created successfully: {final_output.name} ({file_size:.1f} MB)")
                return str(final_output)
            else:
                logger.error("Final clip assembly failed")
                return None
                
        except Exception as e:
            logger.error(f"Viral clip creation failed: {e}")
            return None
        finally:
            # Cleanup temporary components
            temp_files = [intro_path, outro_path, main_clip_path]
            for temp_file in temp_files:
                if temp_file and Path(temp_file).exists() and Path(temp_file) != final_output:
                    try:
                        Path(temp_file).unlink(missing_ok=True)
                    except Exception as e:
                        logger.debug(f"Could not delete temporary file {temp_file}: {e}")
    
    def _create_enhanced_main_clip(self, source_file: str, start: float, end: float, subtitles: List[Dict], content_data: Dict) -> Optional[str]:
        duration = end - start
        output_path = self.visual_creator.temp_dir / f"main_clip_{uuid.uuid4().hex[:8]}.mp4"
        
        logger.info(f"Creating main clip segment: {duration:.1f} seconds")
        
        subtitle_file = self.visual_creator.create_enhanced_subtitles(subtitles, style_preset="viral")
        
        # Clean expert name for display
        clean_expert_name = self.visual_creator._escape_text_for_ffmpeg(self.config.expert_name) if (self.config and hasattr(self.config, 'expert_name') and self.config.expert_name) else "Expert"
        
        font_arg = self.visual_creator._get_drawtext_font_arg()
        
        video_filters = [
            'scale=1080:1920:force_original_aspect_ratio=decrease',
            'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
            'setsar=1', 
            'eq=contrast=1.15:saturation=1.2:brightness=0.05',
            'unsharp=5:5:1.0:5:5:0.0',
            'zoompan=z=\'min(zoom+0.0008,1.05)\':d=1:x=\'iw/2-(iw/zoom/2)\':y=\'ih/2-(ih/zoom/2)\':s=1080x1920',
            # Apply font_arg to drawtext filters
            f"drawtext=text='{clean_expert_name}':fontcolor=white@0.7:fontsize=40:x=w-tw-25:y=25:{font_arg}",
            f"drawtext=text='MIH EXPERT':fontcolor={self.config.brand_colors['accent']}:fontsize=32:x=25:y=25:{font_arg}"
        ]
        
        # Add subtitles if available
        if subtitle_file:
            try:
                subtitle_path = self.visual_creator._escape_path_for_ffmpeg(subtitle_file)
                
                # Fixed subtitle style - no Bold parameter
                subtitle_style = (
                    "FontName=Arial,FontSize=8,PrimaryColour=&H00FFFFFF,SecondaryColour=&H00000000,"
                    "BackColour=&H80000000,BorderStyle=1,Outline=1,Shadow=1,Alignment=2,MarginV=200"
                )
                video_filters.append(f"subtitles='{subtitle_path}':force_style='{subtitle_style}'")
                logger.info("Subtitles will be embedded")
            except Exception as e:
                logger.warning(f"Failed to add subtitles: {e}")
        
        cmd = [
            'ffmpeg', '-y', '-v', 'error',
            '-ss', str(start),
            '-t', str(duration),
            '-i', source_file,
            '-vf', ','.join(video_filters),
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '20',
            '-c:a', 'aac',
            '-b:a', '256k',
            '-movflags', '+faststart',
            str(output_path)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300
            )
            
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000:
                logger.info(f"Main clip created successfully: {output_path.name}")
                return str(output_path)
            else:
                logger.error(f"Main clip creation failed with return code {result.returncode}")
                logger.error(f"FFmpeg stderr: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Main clip creation timed out")
            return None
        except Exception as e:
            logger.error(f"Main clip creation failed: {e}")
            return None
        finally:
            if subtitle_file and Path(subtitle_file).exists():
                try:
                    Path(subtitle_file).unlink(missing_ok=True)
                except Exception as e:
                    logger.debug(f"Could not delete temporary subtitle file {subtitle_file}: {e}")


    def _concatenate_video_components(self, components: List[str], output_path: str) -> bool:
        logger.info(f"Concatenating {len(components)} video components into final clip")
        
        cmd = ['ffmpeg', '-y', '-v', 'error']
        
        # Create a concat list file
        concat_file_path = self.visual_creator.temp_dir / f"concat_list_{uuid.uuid4().hex[:8]}.txt"
        with open(concat_file_path, 'w') as f:
            for component in components:
                f.write(f"file '{self.visual_creator._escape_path_for_ffmpeg(component)}'\n") # Ensure paths are correctly escaped for concat

        cmd.extend([
            '-f', 'concat',
            '-safe', '0', # Allow absolute paths
            '-i', str(concat_file_path),
            '-c', 'copy', # Faster, lossless concatenation if formats are compatible
            '-movflags', '+faststart',
            output_path
        ])
        
        try:
            result = self.visual_creator._run_ffmpeg_command(cmd, timeout=180)
            if result and Path(output_path).exists():
                logger.info("Video concatenation completed successfully")
                return True
            else:
                logger.error("Video concatenation failed")
                return False
        except Exception as e:
            logger.error(f"Video concatenation error: {e}")
            return False
        finally:
            if concat_file_path.exists():
                try:
                    concat_file_path.unlink(missing_ok=True)
                except Exception as e:
                    logger.debug(f"Could not delete concat list file {concat_file_path}: {e}")

    
    def cleanup(self):
        logger.info("Cleaning up video processor resources")
        self.visual_creator.cleanup()
        self.transcript_processor.cleanup()

class EnhancedYouTubeManager:
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    def __init__(self, api_key: str, channel_configs: List[Dict]):
        self.api_key = api_key
        self.channel_configs = channel_configs
        self.youtube_services = {}
        self.upload_stats = {'successful': 0, 'failed': 0}
        
        self._authenticate_channels()
    
    def _authenticate_channels(self):
        logger.info(f"Authenticating {len(self.channel_configs)} YouTube channels")
        for i, config in enumerate(self.channel_configs):
            channel_key = f"channel_{i+1}"
            creds_file = config.get('credentials_file')
            channel_name = config.get('name', channel_key)
            
            if not creds_file or not Path(creds_file).exists():
                logger.error(f"Missing credentials file for {channel_name}: {creds_file}")
                continue
            
            try:
                logger.info(f"Authenticating channel: {channel_name}")
                
                token_file = f'token_{channel_key}.json'
                creds = None
                
                if Path(token_file).exists():
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
                self.youtube_services[channel_key] = {
                    'service': service,
                    'config': config
                }
                
                logger.info(f"Successfully authenticated: {channel_name}")
            except Exception as e:
                logger.error(f"Authentication failed for {channel_name}: {e}")
                continue
        
        logger.info(f"Authentication complete: {len(self.youtube_services)} channels ready")
    
    def upload_viral_clip(self, clip: EnhancedVideoClip) -> bool:
        if not clip.file_path or not Path(clip.file_path).exists():
            logger.error(f"Clip file not found: {clip.file_path}")
            return False
        
        logger.info(f"Starting upload for clip: {clip.catchy_title}")
        all_successful = True
        
        for channel_key, data in self.youtube_services.items():
            service = data['service']
            channel_config = data['config']
            channel_name = channel_config.get('name', 'Channel')
            
            success = self._upload_to_channel(clip, service, channel_name, channel_config)
            if success:
                self.upload_stats['successful'] += 1
                logger.info(f"Upload successful to {channel_name}")
            else:
                self.upload_stats['failed'] += 1
                all_successful = False
                logger.error(f"Upload failed to {channel_name}")
        
        return all_successful
    
    def _upload_to_channel(self, clip: EnhancedVideoClip, service, channel_name: str, channel_config: Dict) -> bool:
        try:
            logger.info(f"Uploading to {channel_name}: {clip.catchy_title}")
            
            snippet = {
                'title': clip.catchy_title,
                'description': self._format_description(clip, channel_config),
                'tags': clip.target_tags + ['MIH', 'DrGreenwall'],
                'categoryId': '27',
                'defaultLanguage': 'en',
                'defaultAudioLanguage': 'en'
            }
            
            privacy_status = channel_config.get('privacy_status', 'private')
            status = {'privacyStatus': privacy_status}
            
            body = {
                'snippet': snippet,
                'status': status
            }
            
            media = MediaFileUpload(
                clip.file_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/mp4'
            )
            
            request = service.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = None
            while response is None:
                try:
                    status_obj, response = request.next_chunk()
                    if status_obj:
                        progress = int(status_obj.progress() * 100)
                        logger.info(f"Upload progress to {channel_name}: {progress}%")
                except Exception as e:
                    logger.error(f"Upload interrupted for {channel_name}: {e}")
                    return False
            
            video_id = response.get('id')
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            logger.info(f"Upload completed to {channel_name}: {video_url}")
            
            return True
        except Exception as e:
            logger.error(f"Upload failed to {channel_name}: {e}")
            return False
    
    def _format_description(self, clip: EnhancedVideoClip, channel_config: Dict) -> str:
        description_parts = [
            clip.engaging_description,
            "",
            "About Dr. Linda Greenwall:",
            "Globally recognized expert in Molar Incisor Hypomineralisation (MIH)",
            "Leading specialist in pediatric-safe whitening treatments",
            "Helping parents navigate children's dental health for over a decade",
            "",
            "Learn More:",
            "- MIH causes and identification",
            "- ICON treatment options", 
            "- Child-friendly whitening solutions",
            "- Gentle enamel care techniques",
            "",
            "Follow for expert MIH guidance and parent tips!",
            "",
            f"#MIH #PediatricDentistry #DrGreenwall #ChildrensDental #EnamelDefects"
        ]
        
        if 'website' in channel_config:
            description_parts.insert(-2, f"Website: {channel_config['website']}")
        
        if 'social_links' in channel_config:
            description_parts.insert(-2, "Connect:")
            for platform, link in channel_config['social_links'].items():
                description_parts.insert(-2, f"- {platform.title()}: {link}")
        
        return '\n'.join(description_parts)
    
    def get_upload_stats(self) -> Dict[str, int]:
        return self.upload_stats.copy()

class MIHAutomationSystem:
    def __init__(self, config_dict: Dict):
        self.config = MIHConfig()
        self.system_config = config_dict
        
        logger.info("Initializing MIH Automation System components...")
        
        self.trending_manager = TrendingTopicsManager(self.config)
        self.content_generator = EnhancedContentGenerator(
            config_dict['gemini_api_key'],
            self.config,
            self.trending_manager
        )
        self.video_processor = EnhancedVideoProcessor(
            self.config,
            config_dict['output_dir'],
            config_dict.get('sfx_path')
        )
        self.youtube_manager = EnhancedYouTubeManager(
            config_dict['youtube_api_key'],
            config_dict['upload_channels']
        )
        
        self.processed_videos_file = 'processed_mih_videos.json'
        self.processed_videos = self._load_processed_videos()
        self.session_stats = {
            'videos_processed': 0,
            'clips_created': 0,
            'clips_uploaded': 0,
            'errors': 0
        }
        
        logger.info("MIH Automation System fully initialized")
        logger.info(f"Previously processed videos: {len(self.processed_videos)}")
    
    def process_dr_greenwall_video(self, video_data: Dict) -> List[EnhancedVideoClip]:
        video_id = video_data['id']
        
        logger.info(f"Processing Dr. Greenwall video: {video_data['title']}")
        logger.info(f"Video ID: {video_id}")
        
        if video_id in self.processed_videos:
            logger.info("Video already processed, skipping...")
            return []
        
        created_clips = []
        source_video_path = None
        
        try:
            self.session_stats['videos_processed'] += 1
            
            # Get trending topics
            logger.info("Analyzing trending topics...")
            trending_topics = self.trending_manager.get_trending_topics()
            
            # Extract transcript
            logger.info("Extracting video transcript...")
            transcript_segments = self.video_processor.transcript_processor.get_enhanced_transcript(video_id)
            if not transcript_segments:
                raise ValueError("Failed to extract transcript")
            
            # Build full transcript for AI analysis
            full_transcript = ' '.join(seg['text'] for seg in transcript_segments)
            logger.info(f"Transcript extracted: {len(full_transcript)} characters")
            
            # Find viral clips using AI
            logger.info("AI analyzing transcript for viral opportunities...")
            viral_clips = self.content_generator.find_viral_clips(
                full_transcript,
                video_data,
                trending_topics
            )
            
            if not viral_clips:
                raise ValueError("No viral clips found by AI analysis")
            
            logger.info(f"AI identified {len(viral_clips)} viral clip opportunities")
            
            # Download source video
            source_video_path = self.video_processor.download_source_video(video_id)
            if not source_video_path:
                raise ValueError("Failed to download source video")
            
            # Process each viral clip
            for i, clip_data in enumerate(viral_clips, 1):
                try:
                    logger.info(f"Processing viral clip {i}/{len(viral_clips)}")
                    
                    start_time = clip_data['start_timestamp']
                    end_time = clip_data['end_timestamp']
                    
                    # Get relevant transcript segments for this clip
                    clip_transcript_segments = [
                        seg for seg in transcript_segments
                        if seg['end'] >= start_time and seg['start'] <= end_time
                    ]
                    
                    # Adjust segment timings relative to clip start
                    adjusted_segments = []
                    for seg in clip_transcript_segments:
                        adjusted_seg = seg.copy()
                        adjusted_seg['start'] = max(0, seg['start'] - start_time)
                        adjusted_seg['end'] = min(end_time - start_time, seg['end'] - start_time)
                        adjusted_segments.append(adjusted_seg)
                    
                    # Generate viral content using AI
                    clip_transcript_text = ' '.join(seg['text'] for seg in clip_transcript_segments)
                    logger.info("Generating viral content for clip...")
                    content_data = self.content_generator.generate_viral_content(
                        clip_transcript_text,
                        end_time - start_time,
                        trending_topics,
                        clip_data
                    )
                    
                    # Create the viral clip with intro, main content, and outro
                    logger.info("Creating complete viral clip with intro, main content, and outro...")
                    clip_file_path = self.video_processor.create_viral_clip(
                        source_video_path,
                        clip_data,
                        content_data,
                        adjusted_segments
                    )
                    
                    if clip_file_path:
                        enhanced_clip = EnhancedVideoClip(
                            clip_id=uuid.uuid4().hex,
                            start_time=start_time,
                            end_time=end_time,
                            transcript=clip_transcript_text,
                            source_video_id=video_id,
                            source_title=video_data['title'],
                            source_url=video_data['url'],
                            catchy_title=content_data['title'],
                            engaging_description=content_data['description'],
                            viral_hooks=clip_data.get('viral_hook', '').split('.'),
                            target_tags=content_data['hashtags'],
                            trending_score=clip_data.get('trending_score', 0.5),
                            parent_appeal_score=clip_data.get('parent_appeal', 0.5),
                            file_path=clip_file_path,
                            subtitle_segments=adjusted_segments
                        )
                        
                        created_clips.append(enhanced_clip)
                        self.session_stats['clips_created'] += 1
                        
                        logger.info(f"Clip {i} created successfully: {content_data['title']}")
                        logger.info(f"Tags: {', '.join(content_data['hashtags'])}")
                    else:
                        logger.error(f"Failed to create clip {i}")
                        
                except Exception as e:
                    logger.error(f"Error creating clip {i}: {e}")
                    self.session_stats['errors'] += 1
                    continue
            
            # Mark video as processed if we created any clips
            if created_clips:
                self.processed_videos.add(video_id)
                self._save_processed_videos()
                logger.info(f"Successfully created {len(created_clips)} viral clips")
            
            return created_clips
            
        except Exception as e:
            logger.error(f"Video processing failed for {video_id}: {e}")
            self.session_stats['errors'] += 1
            return []
        finally:
            # Clean up source video
            if source_video_path and Path(source_video_path).exists():
                try:
                    Path(source_video_path).unlink(missing_ok=True)
                    logger.info("Source video cleaned up")
                except Exception as e:
                    logger.debug(f"Could not delete source video {source_video_path}: {e}")
    
    def upload_clips_to_channels(self, clips: List[EnhancedVideoClip]) -> bool:
        if not clips:
            logger.warning("No clips to upload")
            return False
        
        logger.info(f"Starting upload process for {len(clips)} viral clips")
        
        all_successful = True
        for i, clip in enumerate(clips, 1):
            try:
                logger.info(f"Uploading clip {i}/{len(clips)}: {clip.catchy_title}")
                
                success = self.youtube_manager.upload_viral_clip(clip)
                if success:
                    self.session_stats['clips_uploaded'] += 1
                else:
                    all_successful = False
                
                # Brief pause between uploads to avoid rate limits
                if i < len(clips):
                    logger.info("Waiting 2 seconds before next upload...")
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"Upload error for clip {i}: {e}")
                all_successful = False
                self.session_stats['errors'] += 1
        
        # Print upload statistics
        upload_stats = self.youtube_manager.get_upload_stats()
        logger.info(f"Upload Summary: {upload_stats['successful']} successful, {upload_stats['failed']} failed")
        
        return all_successful
    
    def run_single_video_automation(self, video_id: str):
        logger.info(f"Starting complete automation for video ID: {video_id}")
        
        try:
            # Get video metadata
            video_data = self._get_video_metadata(video_id)
            if not video_data:
                logger.error(f"Could not retrieve video metadata for {video_id}")
                return
            
            # Verify this is Dr. Greenwall content
            if not self._is_dr_greenwall_content(video_data):
                logger.warning(f"Video does not appear to be Dr. Greenwall content")
                logger.warning(f"Title: {video_data['title']}")
                logger.info("Proceeding anyway as requested...")
            
            # Process video to create viral clips
            viral_clips = self.process_dr_greenwall_video(video_data)
            
            if not viral_clips:
                logger.error("No viral clips were created")
                return
            
            # Upload clips to all channels
            upload_success = self.upload_clips_to_channels(viral_clips)
            
            # Print final summary
            self._print_session_summary()
            
            if upload_success:
                logger.info("AUTOMATION COMPLETED SUCCESSFULLY!")
            else:
                logger.warning("Automation completed with some upload failures")
                
        except Exception as e:
            logger.error(f"Automation failed with critical error: {e}")
            self.session_stats['errors'] += 1
        finally:
            self.cleanup()
    
    def run_batch_automation(self, video_ids: List[str]):
        logger.info(f"Starting batch automation for {len(video_ids)} videos")
        
        for i, video_id in enumerate(video_ids, 1):
            logger.info(f"Processing video {i}/{len(video_ids)}: {video_id}")
            
            try:
                video_data = self._get_video_metadata(video_id)
                if video_data:
                    viral_clips = self.process_dr_greenwall_video(video_data)
                    if viral_clips:
                        self.upload_clips_to_channels(viral_clips)
                
                # Brief pause between videos
                if i < len(video_ids):
                    logger.info("Waiting 5 seconds before next video...")
                    time.sleep(5)
                    
            except Exception as e:
                logger.error(f"Error processing video {video_id}: {e}")
                self.session_stats['errors'] += 1
                continue
        
        self._print_session_summary()
        self.cleanup()
    
    def _get_video_metadata(self, video_id: str) -> Optional[Dict]:
        logger.info(f"Retrieving metadata for video: {video_id}")
        try:
            youtube = build('youtube', 'v3', developerKey=self.system_config['youtube_api_key'])
            request = youtube.videos().list(part="snippet,statistics", id=video_id)
            response = request.execute()
            
            if not response.get("items"):
                logger.error(f"Video not found: {video_id}")
                return None
            
            item = response["items"][0]
            snippet = item['snippet']
            
            metadata = {
                'id': video_id,
                'title': snippet['title'],
                'description': snippet.get('description', ''),
                'channel_title': snippet.get('channelTitle', ''),
                'published_at': snippet.get('publishedAt', ''),
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'view_count': item.get('statistics', {}).get('viewCount', 0)
            }
            
            logger.info(f"Video metadata retrieved: {metadata['title'][:50]}...")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to get video metadata for {video_id}: {e}")
            return None
    
    def _is_dr_greenwall_content(self, video_data: Dict) -> bool:
        content_indicators = [
            'greenwall', 'linda greenwall', 'dr greenwall',
            'mih', 'molar incisor hypomineralisation',
            'pediatric whitening', 'enamel defects'
        ]
        
        searchable_text = f"{video_data['title']} {video_data['description']} {video_data['channel_title']}".lower()
        
        return any(indicator in searchable_text for indicator in content_indicators)
    
    def _load_processed_videos(self) -> Set[str]:
        try:
            if Path(self.processed_videos_file).exists():
                with open(self.processed_videos_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('processed_videos', []))
        except Exception as e:
            logger.warning(f"Could not load processed videos: {e}")
        return set()
    
    def _save_processed_videos(self):
        try:
            data = {
                'processed_videos': list(self.processed_videos),
                'last_updated': datetime.now().isoformat()
            }
            with open(self.processed_videos_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save processed videos: {e}")
    
    def _print_session_summary(self):
        logger.info("=" * 60)
        logger.info("SESSION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Videos Processed: {self.session_stats['videos_processed']}")
        logger.info(f"Viral Clips Created: {self.session_stats['clips_created']}")
        logger.info(f"Clips Uploaded: {self.session_stats['clips_uploaded']}")
        logger.info(f"Errors Encountered: {self.session_stats['errors']}")
        
        if self.session_stats['clips_created'] > 0:
            success_rate = (self.session_stats['clips_uploaded'] / self.session_stats['clips_created']) * 100
            logger.info(f"Upload Success Rate: {success_rate:.1f}%")
        
        logger.info("=" * 60)
    
    def cleanup(self):
        logger.info("Performing system cleanup...")
        self.video_processor.cleanup()
        logger.info("System cleanup completed")

def create_example_config():
    example_config = '''# Dr. Linda Greenwall MIH Content Automation - Configuration

# YouTube Data API v3 Key
YOUTUBE_API_KEY = "YOUR_YOUTUBE_API_KEY_HERE"

# Google Gemini API Key for AI content generation
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"

# Output directory for processed videos
OUTPUT_DIR = "viral_mih_clips"

# Optional: Path to sound effect file for intros/outros
SFX_POP_PATH = "sfx_pop.mp3"  # Optional

# Upload Channels Configuration
UPLOAD_CHANNELS = [
    {
        "name": "Dr Greenwall MIH Channel",
        "credentials_file": "channel1_credentials.json",
        "privacy_status": "private",  # private, unlisted, or public
        "website": "https://drgreenwall.com",
        "social_links": {
            "instagram": "https://instagram.com/drgreenwall",
            "twitter": "https://twitter.com/drgreenwall"
        }
    }
]

# Advanced Settings
MAX_CLIPS_PER_VIDEO = 3
TRENDING_UPDATE_FREQUENCY_DAYS = 7
'''
    
    with open('config_example.py', 'w') as f:
        f.write(example_config)
    
    logger.info("Created example configuration file: config_example.py")

def main():
    print("=" * 70)
    print("Dr. Linda Greenwall MIH Content Automation System")
    print("Creating Viral Clips from Expert MIH Content")
    print("=" * 70)
    print()
    
    # Load configuration
    try:
        import config
        logger.info("Configuration loaded successfully")
    except ImportError:
        logger.error("FATAL: config.py not found!")
        logger.info("Creating example configuration file...")
        create_example_config()
        logger.info("Please edit config_example.py and rename it to config.py")
        return
    
    # Validate configuration
    required_settings = ['YOUTUBE_API_KEY', 'GEMINI_API_KEY', 'UPLOAD_CHANNELS']
    for setting in required_settings:
        if not hasattr(config, setting) or 'YOUR_' in str(getattr(config, setting)):
            logger.error(f"FATAL: Please configure {setting} in config.py")
            return
    
    # Build system configuration
    system_config = {
        'youtube_api_key': config.YOUTUBE_API_KEY,
        'gemini_api_key': config.GEMINI_API_KEY,
        'upload_channels': config.UPLOAD_CHANNELS,
        'output_dir': getattr(config, 'OUTPUT_DIR', 'viral_mih_clips'),
        'sfx_path': getattr(config, 'SFX_POP_PATH', None),
        'max_clips_per_video': getattr(config, 'MAX_CLIPS_PER_VIDEO', 3)
    }
    
    logger.info("System configuration validated successfully")
    
    # Initialize automation system
    automation = None
    try:
        logger.info("Initializing MIH automation system...")
        automation = MIHAutomationSystem(system_config)
        
        # Parse command line arguments
        if len(sys.argv) < 2:
            print("USAGE EXAMPLES:")
            print()
            print("Single Video Processing:")
            print(f"  python {sys.argv[0]} --video VIDEO_ID")
            print(f"  python {sys.argv[0]} --video dQw4w9WgXcQ")
            print()
            print("Batch Processing:")
            print(f"  python {sys.argv[0]} --batch VIDEO_ID1 VIDEO_ID2 VIDEO_ID3")
            print()
            print("Test Mode (no uploads):")
            print(f"  python {sys.argv[0]} --test VIDEO_ID")
            print()
            return
        
        command = sys.argv[1]
        
        if command == '--video' and len(sys.argv) > 2:
            video_id = sys.argv[2]
            logger.info(f"Running single video automation for: {video_id}")
            automation.run_single_video_automation(video_id)
            
        elif command == '--batch' and len(sys.argv) > 2:
            video_ids = sys.argv[2:]
            logger.info(f"Running batch automation for {len(video_ids)} videos")
            automation.run_batch_automation(video_ids)
            
        elif command == '--test' and len(sys.argv) > 2:
            video_id = sys.argv[2]
            logger.info("TEST MODE: Creating clips but not uploading")
            
            video_data = automation._get_video_metadata(video_id)
            if video_data:
                viral_clips = automation.process_dr_greenwall_video(video_data)
                if viral_clips:
                    logger.info(f"TEST SUCCESSFUL: Created {len(viral_clips)} viral clips")
                    for i, clip in enumerate(viral_clips, 1):
                        logger.info(f"   Clip {i}: {clip.catchy_title}")
                        logger.info(f"       File: {clip.file_path}")
                        logger.info(f"       Tags: {', '.join(clip.target_tags)}")
                else:
                    logger.error("TEST FAILED: No clips created")
            else:
                logger.error("TEST FAILED: Could not retrieve video metadata")
                
        else:
            logger.error("Invalid command. Use one of: --video, --batch, --test")
            
    except KeyboardInterrupt:
        logger.info("Automation stopped by user")
    except Exception as e:
        logger.error(f"FATAL ERROR: {e}")
    finally:
        if automation:
            automation.cleanup()
        print()
        print("=" * 70)
        print("Dr. Greenwall MIH Automation System Shutdown")
        print("Thank you for helping spread MIH awareness!")
        print("=" * 70)

if __name__ == "__main__":
    main()