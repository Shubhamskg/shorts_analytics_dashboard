"""
Enhanced MIH Content Automation System - Visual Effects Engine
Advanced graphics, animations, and visual enhancements
"""

import os
import tempfile
import subprocess
import logging
import json
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import colorsys
import math

from config import config
from utils import run_with_timeout, TimeoutError

logger = logging.getLogger(__name__)

class VisualEngine:
    """Advanced visual effects and graphics generation"""
    
    def __init__(self):
        self.temp_dir = Path(config.temp_dir) / "visual"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.assets_dir = Path(config.assets_dir)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        
        # Visual templates and styles
        self.templates = self._load_templates()
        self.brand_colors = self._get_brand_colors()
        
        # Resolution settings
        self.width, self.height = map(int, config.video.resolution.split('x'))
        self.fps = config.video.frame_rate
        
        # Setup visual assets
        self._setup_visual_assets()
    
    def _load_templates(self) -> Dict:
        """Load visual templates configuration"""
        return {
            'dental_modern': {
                'primary_color': '#4ECDC4',
                'secondary_color': '#45B7D1',
                'accent_color': '#96CEB4',
                'font': 'Arial',
                'style': 'modern_medical'
            },
            'kids_friendly': {
                'primary_color': '#FFD93D',
                'secondary_color': '#6BCF7F',
                'accent_color': '#FF6B6B',
                'font': 'Arial',
                'style': 'playful'
            },
            'professional': {
                'primary_color': '#2C3E50',
                'secondary_color': '#3498DB',
                'accent_color': '#E74C3C',
                'font': 'Arial',
                'style': 'corporate'
            }
        }
    
    def _get_brand_colors(self) -> Dict:
        """Get brand colors for different channels"""
        colors = {}
        for channel in config.upload_channels:
            colors[channel.name] = {
                'primary': channel.brand_color,
                'secondary': self._generate_complementary_color(channel.brand_color),
                'accent': self._generate_accent_color(channel.brand_color)
            }
        return colors
    
    def _generate_complementary_color(self, hex_color: str) -> str:
        """Generate complementary color"""
        try:
            # Remove '#' if present
            hex_color = hex_color.lstrip('#')
            
            # Convert to RGB
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            
            # Convert to HSV
            h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
            
            # Get complementary hue
            comp_h = (h + 0.5) % 1.0
            
            # Convert back to RGB
            comp_r, comp_g, comp_b = colorsys.hsv_to_rgb(comp_h, s, v)
            
            # Convert to hex
            return f"#{int(comp_r*255):02x}{int(comp_g*255):02x}{int(comp_b*255):02x}"
            
        except:
            return "#FFFFFF"  # Fallback to white
    
    def _generate_accent_color(self, hex_color: str) -> str:
        """Generate accent color (lighter version)"""
        try:
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            
            # Convert to HSV and increase lightness
            h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
            v = min(1.0, v + 0.3)  # Increase brightness
            s = max(0.3, s - 0.2)  # Decrease saturation
            
            # Convert back
            acc_r, acc_g, acc_b = colorsys.hsv_to_rgb(h, s, v)
            return f"#{int(acc_r*255):02x}{int(acc_g*255):02x}{int(acc_b*255):02x}"
            
        except:
            return "#F0F0F0"  # Light gray fallback
    
    def _setup_visual_assets(self):
        """Setup visual assets and templates"""
        try:
            # Create gradient backgrounds
            self._create_gradient_backgrounds()
            
            # Create logo overlays
            self._create_logo_overlays()
            
            # Create animated elements
            self._create_animated_elements()
            
        except Exception as e:
            logger.warning(f"⚠️ Visual assets setup error: {e}")
    
    def _create_gradient_backgrounds(self):
        """Create gradient background images"""
        try:
            for template_name, template in self.templates.items():
                output_file = self.assets_dir / f"gradient_{template_name}.png"
                
                if not output_file.exists():
                    primary = template['primary_color']
                    secondary = template['secondary_color']
                    
                    # Create diagonal gradient
                    cmd = [
                        'ffmpeg', '-y', '-f', 'lavfi',
                        '-i', f'color=c={primary}:size={self.width}x{self.height}:duration=1',
                        '-vf', f'geq=r=\'if(lt(X*Y,{self.width}*{self.height}/2),'
                              f'{int(primary[1:3], 16)},'
                              f'{int(secondary[1:3], 16)})\':'
                              f'g=\'if(lt(X*Y,{self.width}*{self.height}/2),'
                              f'{int(primary[3:5], 16)},'
                              f'{int(secondary[3:5], 16)})\':'
                              f'b=\'if(lt(X*Y,{self.width}*{self.height}/2),'
                              f'{int(primary[5:7], 16)},'
                              f'{int(secondary[5:7], 16)})\'',
                        '-frames:v', '1',
                        str(output_file)
                    ]
                    
                    run_with_timeout(cmd, timeout_seconds=15)
                    logger.info(f"✅ Created gradient for {template_name}")
                    
        except Exception as e:
            logger.warning(f"⚠️ Gradient creation error: {e}")
    
    def _create_logo_overlays(self):
        """Create logo and branding overlays"""
        try:
            # Dr. Greenwall branding
            logo_file = self.assets_dir / "dr_greenwall_logo.png"
            
            if not logo_file.exists():
                # Create text-based logo
                cmd = [
                    'ffmpeg', '-y', '-f', 'lavfi',
                    '-i', f'color=c=transparent:size=400x100:duration=1',
                    '-vf', "drawtext=text='Dr. Linda Greenwall':"
                          "fontfile=/System/Library/Fonts/Arial.ttf:"
                          "fontsize=32:fontcolor=#2C3E50:x=(w-text_w)/2:y=(h-text_h)/2",
                    '-frames:v', '1',
                    str(logo_file)
                ]
                
                run_with_timeout(cmd, timeout_seconds=15)
                logger.info("✅ Created Dr. Greenwall logo")
                
        except Exception as e:
            logger.warning(f"⚠️ Logo creation error: {e}")
    
    def _create_animated_elements(self):
        """Create animated visual elements"""
        try:
            # Pulsing circle animation
            pulse_file = self.assets_dir / "pulse_animation.mov"
            
            if not pulse_file.exists():
                cmd = [
                    'ffmpeg', '-y', '-f', 'lavfi',
                    '-i', f'color=c=transparent:size={self.width}x{self.height}:duration=2',
                    '-vf', f'geq=r=\'255*exp(-((X-{self.width//2})*(X-{self.width//2})+'
                          f'(Y-{self.height//2})*(Y-{self.height//2}))/'
                          f'(2*pow(50+30*sin(2*PI*T/2),2)))\':'
                          'g=r:b=r:a=r',
                    '-r', str(self.fps),
                    str(pulse_file)
                ]
                
                run_with_timeout(cmd, timeout_seconds=30)
                logger.info("✅ Created pulse animation")
                
        except Exception as e:
            logger.warning(f"⚠️ Animation creation error: {e}")
    
    def create_intro_video(self, title: str, template: str = "dental_modern") -> Optional[str]:
        """Create visually stunning intro video"""
        try:
            logger.info(f"🎨 Creating intro video: {title[:30]}...")
            
            output_file = self.temp_dir / f"intro_{uuid.uuid4().hex[:8]}.mp4"
            template_config = self.templates.get(template, self.templates['dental_modern'])
            
            # Clean title for display
            clean_title = self._clean_text_for_display(title)
            subtitle = "Expert MIH Treatment"
            
            # Get colors
            primary_color = template_config['primary_color']
            secondary_color = template_config['secondary_color']
            accent_color = template_config['accent_color']
            
            # Create complex intro with animations
            filter_complex = self._build_intro_filter(
                clean_title, subtitle, primary_color, secondary_color, accent_color
            )
            
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi', '-i', f'color=c={primary_color}:size={self.width}x{self.height}',
                '-f', 'lavfi', '-i', f'color=c={secondary_color}:size={self.width}x{self.height}',
                '-filter_complex', filter_complex,
                '-t', str(config.video.intro_duration),
                '-r', str(self.fps),
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-pix_fmt', 'yuv420p',
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=45)
            
            if output_file.exists() and output_file.stat().st_size > 1000:
                logger.info("✅ Stunning intro video created")
                return str(output_file)
            
        except Exception as e:
            logger.error(f"❌ Intro video creation failed: {e}")
            # Fallback to simple intro
            return self._create_simple_intro(title, template)
        
        return None
    
    def _build_intro_filter(self, title: str, subtitle: str, 
                           primary: str, secondary: str, accent: str) -> str:
        """Build complex filter for intro animation"""
        
        # Animated gradient background
        bg_filter = (
            f"[0][1]blend=all_mode=screen:"
            f"all_opacity=0.5+0.3*sin(2*PI*t/{config.video.intro_duration})"
        )
        
        # Title animation (zoom in with fade)
        title_filter = (
            f"drawtext=text='{title}':"
            f"fontsize=64*min(1\\,t/{config.video.intro_duration/2}):"
            f"fontcolor={accent}:"
            f"x=(w-text_w)/2:"
            f"y=(h-text_h)/2-50:"
            f"alpha=min(1\\,t/{config.video.intro_duration/3})"
        )
        
        # Subtitle animation (slide up)
        subtitle_filter = (
            f"drawtext=text='{subtitle}':"
            f"fontsize=32:"
            f"fontcolor=white:"
            f"x=(w-text_w)/2:"
            f"y=(h-text_h)/2+50+max(0\\,100-100*t/{config.video.intro_duration/2}):"
            f"alpha=max(0\\,min(1\\,(t-{config.video.intro_duration/3})/{config.video.intro_duration/3}))"
        )
        
        # Particle effect overlay
        particles_filter = (
            f"geq=r='255*random(0)*exp(-pow((X-{self.width//2})/200\\,2))':"
            f"g=r:b=r:a=r"
        )
        
        return f"{bg_filter}[bg];[bg]{title_filter}[titled];[titled]{subtitle_filter}[final];[final]{particles_filter}"
    
    def _create_simple_intro(self, title: str, template: str) -> Optional[str]:
        """Create simple fallback intro"""
        try:
            output_file = self.temp_dir / f"simple_intro_{uuid.uuid4().hex[:8]}.mp4"
            template_config = self.templates.get(template, self.templates['dental_modern'])
            
            clean_title = self._clean_text_for_display(title)
            color = template_config['primary_color']
            
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi', '-i', f'color=c={color}:size={self.width}x{self.height}:duration={config.video.intro_duration}',
                '-vf', f"drawtext=text='{clean_title}':"
                      f"fontsize=48:fontcolor=white:"
                      f"x=(w-text_w)/2:y=(h-text_h)/2",
                '-r', str(self.fps),
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=30)
            
            if output_file.exists():
                logger.info("✅ Simple intro created")
                return str(output_file)
                
        except Exception as e:
            logger.warning(f"⚠️ Simple intro creation failed: {e}")
        
        return None
    
    def create_outro_video(self, template: str = "dental_modern") -> Optional[str]:
        """Create engaging outro video with subscribe animation"""
        try:
            logger.info("🎨 Creating outro video...")
            
            output_file = self.temp_dir / f"outro_{uuid.uuid4().hex[:8]}.mp4"
            template_config = self.templates.get(template, self.templates['dental_modern'])
            
            primary_color = template_config['primary_color']
            secondary_color = template_config['secondary_color']
            accent_color = template_config['accent_color']
            
            # Create animated outro
            filter_complex = self._build_outro_filter(primary_color, secondary_color, accent_color)
            
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi', '-i', f'color=c={primary_color}:size={self.width}x{self.height}',
                '-f', 'lavfi', '-i', f'color=c={secondary_color}:size={self.width}x{self.height}',
                '-filter_complex', filter_complex,
                '-t', str(config.video.outro_duration),
                '-r', str(self.fps),
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-pix_fmt', 'yuv420p',
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=45)
            
            if output_file.exists() and output_file.stat().st_size > 1000:
                logger.info("✅ Engaging outro video created")
                return str(output_file)
            
        except Exception as e:
            logger.error(f"❌ Outro video creation failed: {e}")
            return self._create_simple_outro(template)
        
        return None
    
    def _build_outro_filter(self, primary: str, secondary: str, accent: str) -> str:
        """Build complex filter for outro animation"""
        
        # Animated background
        bg_filter = (
            f"[0][1]blend=all_mode=multiply:"
            f"all_opacity=0.7+0.3*cos(2*PI*t/{config.video.outro_duration})"
        )
        
        # Main text with pulsing effect
        main_text = (
            f"drawtext=text='LIKE & SUBSCRIBE':"
            f"fontsize=56+8*sin(4*PI*t/{config.video.outro_duration}):"
            f"fontcolor={accent}:"
            f"x=(w-text_w)/2:"
            f"y=(h-text_h)/2-30"
        )
        
        # Subtitle
        subtitle_text = (
            f"drawtext=text='For Expert Dental Advice':"
            f"fontsize=28:"
            f"fontcolor=white:"
            f"x=(w-text_w)/2:"
            f"y=(h-text_h)/2+50"
        )
        
        # Animated subscribe button
        button_filter = (
            f"drawbox=x={self.width//2-100}:y={self.height//2+100}:"
            f"w=200:h=60:"
            f"color={primary}@0.8:"
            f"t=3"
        )
        
        return f"{bg_filter}[bg];[bg]{main_text}[text1];[text1]{subtitle_text}[text2];[text2]{button_filter}"
    
    def _create_simple_outro(self, template: str) -> Optional[str]:
        """Create simple fallback outro"""
        try:
            output_file = self.temp_dir / f"simple_outro_{uuid.uuid4().hex[:8]}.mp4"
            template_config = self.templates.get(template, self.templates['dental_modern'])
            
            color = template_config['secondary_color']
            
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi', '-i', f'color=c={color}:size={self.width}x{self.height}:duration={config.video.outro_duration}',
                '-vf', "drawtext=text='LIKE & SUBSCRIBE':"
                      "fontsize=48:fontcolor=white:"
                      "x=(w-text_w)/2:y=(h-text_h)/2",
                '-r', str(self.fps),
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=30)
            
            if output_file.exists():
                logger.info("✅ Simple outro created")
                return str(output_file)
                
        except Exception as e:
            logger.warning(f"⚠️ Simple outro creation failed: {e}")
        
        return None
    
    def enhance_clip_visuals(self, input_video: str, title: str, 
                           template: str = "dental_modern") -> Optional[str]:
        """Enhance clip with visual effects and branding"""
        try:
            if not os.path.exists(input_video):
                logger.warning("⚠️ Input video not found")
                return input_video
            
            logger.info("🎨 Enhancing clip visuals...")
            
            output_file = self.temp_dir / f"enhanced_{uuid.uuid4().hex[:8]}.mp4"
            template_config = self.templates.get(template, self.templates['dental_modern'])
            
            # Build enhancement filter
            filter_complex = self._build_enhancement_filter(title, template_config)
            
            cmd = [
                'ffmpeg', '-y',
                '-i', input_video,
                '-filter_complex', filter_complex,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'copy',
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=120)
            
            if output_file.exists() and output_file.stat().st_size > 1000:
                logger.info("✅ Clip visuals enhanced")
                return str(output_file)
            
        except Exception as e:
            logger.warning(f"⚠️ Visual enhancement failed: {e}")
        
        return input_video
    
    def _build_enhancement_filter(self, title: str, template_config: Dict) -> str:
        """Build filter for clip enhancement"""
        
        # Base video adjustments
        base_filter = (
            "eq=brightness=0.05:contrast=1.1:saturation=1.1,"
            "unsharp=5:5:0.3:3:3:0.2"
        )
        
        # Branding overlay (top)
        brand_text = (
            f"drawtext=text='Dr. Linda Greenwall - MIH Expert':"
            f"fontsize=24:"
            f"fontcolor={template_config['accent_color']}@0.8:"
            f"x=50:y=80:"
            f"box=1:boxcolor=black@0.5:boxborderw=5"
        )
        
        # Title overlay (bottom)
        clean_title = self._clean_text_for_display(title[:50])
        title_text = (
            f"drawtext=text='{clean_title}':"
            f"fontsize=28:"
            f"fontcolor=white:"
            f"x=50:y=h-120:"
            f"box=1:boxcolor={template_config['primary_color']}@0.7:boxborderw=5"
        )
        
        # Subtle animated border
        border_effect = (
            f"drawbox=x=10:y=10:w=iw-20:h=ih-20:"
            f"color={template_config['secondary_color']}@0.3:t=3"
        )
        
        # Combine all filters
        return f"[0:v]{base_filter},{brand_text},{title_text},{border_effect}[v]"
    
    def add_visual_transitions(self, clips: List[str]) -> Optional[str]:
        """Add smooth transitions between clips"""
        try:
            if len(clips) < 2:
                return clips[0] if clips else None
            
            logger.info(f"🎨 Adding transitions between {len(clips)} clips...")
            
            output_file = self.temp_dir / f"transitions_{uuid.uuid4().hex[:8]}.mp4"
            
            # Build transition filter
            filter_parts = []
            input_parts = []
            
            for i, clip in enumerate(clips):
                input_parts.extend(['-i', clip])
            
            # Create crossfade transitions
            current_stream = '[0:v]'
            for i in range(1, len(clips)):
                fade_duration = 0.5  # 0.5 second crossfade
                
                filter_parts.append(
                    f'{current_stream}[{i}:v]xfade=transition=fade:'
                    f'duration={fade_duration}:offset=0[v{i}]'
                )
                current_stream = f'[v{i}]'
            
            # Audio mixing
            audio_filter = ''.join([f'[{i}:a]' for i in range(len(clips))])
            audio_filter += f'amix=inputs={len(clips)}:duration=longest[a]'
            
            filter_complex = ';'.join(filter_parts + [audio_filter])
            
            cmd = ['ffmpeg', '-y'] + input_parts + [
                '-filter_complex', filter_complex,
                '-map', current_stream,
                '-map', '[a]',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=180)
            
            if output_file.exists():
                logger.info("✅ Transitions added successfully")
                return str(output_file)
            
        except Exception as e:
            logger.warning(f"⚠️ Transition creation failed: {e}")
        
        return clips[0] if clips else None
    
    def create_thumbnail(self, video_file: str, title: str, 
                        template: str = "dental_modern") -> Optional[str]:
        """Create eye-catching thumbnail for the video"""
        try:
            if not os.path.exists(video_file):
                return None
            
            logger.info("🎨 Creating eye-catching thumbnail...")
            
            output_file = self.temp_dir / f"thumbnail_{uuid.uuid4().hex[:8]}.jpg"
            template_config = self.templates.get(template, self.templates['dental_modern'])
            
            # Extract frame from middle of video
            temp_frame = self.temp_dir / f"frame_{uuid.uuid4().hex[:8]}.jpg"
            
            cmd = [
                'ffmpeg', '-y',
                '-i', video_file,
                '-ss', '00:00:15',  # 15 seconds in
                '-vframes', '1',
                str(temp_frame)
            ]
            
            run_with_timeout(cmd, timeout_seconds=30)
            
            if not temp_frame.exists():
                return None
            
            # Enhance thumbnail with graphics
            clean_title = self._clean_text_for_display(title)
            
            # Create thumbnail with overlays
            cmd = [
                'ffmpeg', '-y',
                '-i', str(temp_frame),
                '-vf', 
                f"eq=brightness=0.1:contrast=1.2:saturation=1.3,"
                f"drawtext=text='{clean_title}':"
                f"fontsize=48:"
                f"fontcolor=white:"
                f"x=(w-text_w)/2:"
                f"y=h-150:"
                f"box=1:boxcolor={template_config['primary_color']}@0.8:boxborderw=10,"
                f"drawtext=text='Dr. Linda Greenwall':"
                f"fontsize=32:"
                f"fontcolor={template_config['accent_color']}:"
                f"x=50:y=80:"
                f"box=1:boxcolor=black@0.6:boxborderw=5",
                '-q:v', '2',  # High quality
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=30)
            
            # Cleanup temp frame
            try:
                temp_frame.unlink()
            except:
                pass
            
            if output_file.exists():
                logger.info("✅ Eye-catching thumbnail created")
                return str(output_file)
            
        except Exception as e:
            logger.warning(f"⚠️ Thumbnail creation failed: {e}")
        
        return None
    
    def create_animated_subtitles(self, subtitle_file: str, duration: float,
                                template: str = "dental_modern") -> Optional[str]:
        """Create animated subtitle overlay"""
        try:
            if not os.path.exists(subtitle_file):
                return None
            
            logger.info("🎨 Creating animated subtitles...")
            
            output_file = self.temp_dir / f"animated_subs_{uuid.uuid4().hex[:8]}.mov"
            template_config = self.templates.get(template, self.templates['dental_modern'])
            
            # Create animated subtitle style
            subtitle_style = (
                f"FontName=Arial,"
                f"FontSize=28,"
                f"PrimaryColour=&Hffffff,"
                f"OutlineColour=&H{template_config['primary_color'][1:]},"
                f"BorderStyle=3,"
                f"Outline=3,"
                f"Shadow=2,"
                f"Alignment=2,"
                f"MarginV=120,"
                f"BackColour=&H80000000"
            )
            
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi', '-i', f'color=c=transparent:size={self.width}x{self.height}:duration={duration}',
                '-vf', f"subtitles='{subtitle_file}':force_style='{subtitle_style}'",
                '-c:v', 'png',
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=60)
            
            if output_file.exists():
                logger.info("✅ Animated subtitles created")
                return str(output_file)
            
        except Exception as e:
            logger.warning(f"⚠️ Animated subtitles creation failed: {e}")
        
        return None
    
    def _clean_text_for_display(self, text: str) -> str:
        """Clean and prepare text for visual display"""
        # Remove problematic characters
        text = text.replace("'", "\\'").replace('"', '\\"')
        text = text.replace(':', '\\:').replace(',', '\\,')
        
        # Limit length for display
        if len(text) > 60:
            text = text[:57] + "..."
        
        return text.strip()
    
    def apply_motion_graphics(self, input_video: str, effects: List[Dict]) -> Optional[str]:
        """Apply motion graphics and animations to video"""
        try:
            if not effects or not os.path.exists(input_video):
                return input_video
            
            logger.info(f"🎨 Applying {len(effects)} motion graphics...")
            
            output_file = self.temp_dir / f"motion_{uuid.uuid4().hex[:8]}.mp4"
            
            # Build motion graphics filter
            filter_parts = ["[0:v]"]
            
            for effect in effects:
                effect_type = effect.get('type', 'fade')
                start_time = effect.get('start', 0)
                duration = effect.get('duration', 1)
                
                if effect_type == 'zoom':
                    zoom_filter = (
                        f"zoompan=z='min(max(zoom,pzoom)+0.0015,1.5)':"
                        f"d=25*{duration}:x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2):"
                        f"s={self.width}x{self.height}"
                    )
                    filter_parts.append(zoom_filter)
                
                elif effect_type == 'slide':
                    direction = effect.get('direction', 'left')
                    if direction == 'left':
                        slide_filter = f"crop=iw:ih:max(0\\,iw*({start_time}-t/{duration})):0"
                    else:  # right
                        slide_filter = f"crop=iw:ih:min(0\\,iw*(t/{duration}-{start_time})):0"
                    filter_parts.append(slide_filter)
                
                elif effect_type == 'fade':
                    fade_filter = f"fade=t=in:st={start_time}:d={duration}"
                    filter_parts.append(fade_filter)
            
            filter_complex = ','.join(filter_parts[1:]) if len(filter_parts) > 1 else ""
            
            if filter_complex:
                cmd = [
                    'ffmpeg', '-y',
                    '-i', input_video,
                    '-vf', filter_complex,
                    '-c:a', 'copy',
                    str(output_file)
                ]
                
                run_with_timeout(cmd, timeout_seconds=120)
                
                if output_file.exists():
                    logger.info("✅ Motion graphics applied")
                    return str(output_file)
            
        except Exception as e:
            logger.warning(f"⚠️ Motion graphics failed: {e}")
        
        return input_video
    
    def cleanup_temp_files(self):
        """Clean up temporary visual files"""
        try:
            for temp_file in self.temp_dir.glob("*"):
                try:
                    if temp_file.is_file():
                        temp_file.unlink()
                except:
                    pass
            logger.info("🧹 Visual temp files cleaned up")
        except Exception as e:
            logger.warning(f"⚠️ Visual cleanup error: {e}")

class MotionGraphicsGenerator:
    """Generate dynamic motion graphics based on content"""
    
    def __init__(self, visual_engine: VisualEngine):
        self.visual_engine = visual_engine
    
    def analyze_content_for_motion(self, transcript: str, duration: float) -> List[Dict]:
        """Analyze content to suggest motion graphics"""
        effects = []
        
        # Keywords that trigger specific motion effects
        motion_keywords = {
            'zoom': ['focus', 'important', 'key', 'main', 'critical'],
            'slide': ['next', 'then', 'after', 'before', 'transition'],
            'fade': ['gentle', 'soft', 'calm', 'peaceful', 'gradual'],
            'pulse': ['emphasis', 'stress', 'urgent', 'attention']
        }
        
        words = transcript.lower().split()
        
        # Add motion effects based on content analysis
        for i, word in enumerate(words):
            word_time = (i / len(words)) * duration
            
            # Skip if too close to start/end
            if word_time < 1 or word_time > duration - 1:
                continue
            
            for effect_type, keywords in motion_keywords.items():
                if any(keyword in word for keyword in keywords):
                    effects.append({
                        'type': effect_type,
                        'start': word_time,
                        'duration': 2.0,
                        'trigger_word': word,
                        'direction': 'left' if i % 2 == 0 else 'right'
                    })
                    break
        
        # Limit effects to prevent overcrowding
        if len(effects) > 4:
            effects = effects[:4]
        
        # Add automatic fade transitions
        if duration > 20:
            effects.append({
                'type': 'fade',
                'start': 0,
                'duration': 1.0
            })
            effects.append({
                'type': 'fade',
                'start': duration - 1,
                'duration': 1.0
            })
        
        return effects

# Global visual engine instance
visual_engine = VisualEngine()
motion_generator = MotionGraphicsGenerator(visual_engine)

if __name__ == "__main__":
    # Test visual engine
    print("🎨 Testing Visual Engine...")
    
    # Test intro
    intro_video = visual_engine.create_intro_video("MIH Treatment Options", "dental_modern")
    if intro_video:
        print(f"✅ Intro test successful: {intro_video}")
    
    # Test outro
    outro_video = visual_engine.create_outro_video("dental_modern")
    if outro_video:
        print(f"✅ Outro test successful: {outro_video}")
    
    print("🎨 Visual Engine test complete!")