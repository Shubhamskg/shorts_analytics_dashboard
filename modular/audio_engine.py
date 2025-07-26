"""
Enhanced MIH Content Automation System - Audio Engine
Advanced text-to-speech, background music, and sound effects
"""

import os
import tempfile
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, List
import uuid
import time

# Audio libraries
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

try:
    import azure.cognitiveservices.speech as speechsdk
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

from config import config
# from utils import run_with_timeout, TimeoutError
def  run_with_timeout(cmd, timeout_seconds=30):
    pass


logger = logging.getLogger(__name__)

class AudioEngine:
    """Advanced audio processing for intros, outros, and clips"""
    
    def __init__(self):
        self.temp_dir = Path(config.temp_dir) / "audio"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.assets_dir = Path(config.assets_dir)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize TTS engines
        self.tts_engine = config.audio.tts_engine
        self._setup_azure_tts()
        
        # Download/prepare background music and sound effects
        self._setup_audio_assets()
    
    def _setup_azure_tts(self):
        """Setup Azure Text-to-Speech if available"""
        self.azure_speech_config = None
        if AZURE_AVAILABLE and config.azure_speech_key:
            try:
                self.azure_speech_config = speechsdk.SpeechConfig(
                    subscription=config.azure_speech_key,
                    region=config.azure_speech_region
                )
                # Use professional female voice for medical content
                self.azure_speech_config.speech_synthesis_voice_name = "en-AU-NatashaNeural"
                logger.info("✅ Azure TTS initialized with professional voice")
            except Exception as e:
                logger.warning(f"⚠️ Azure TTS setup failed: {e}")
    
    def _setup_audio_assets(self):
        """Setup background music and sound effects"""
        self.audio_assets = {
            'background_music': {
                'intro': self.assets_dir / 'intro_music.wav',
                'medical': self.assets_dir / 'medical_background.wav',
                'upbeat': self.assets_dir / 'upbeat_background.wav'
            },
            'sound_effects': {
                'swoosh': self.assets_dir / 'swoosh.wav',
                'pop': self.assets_dir / 'pop.wav',
                'ding': self.assets_dir / 'notification.wav',
                'heartbeat': self.assets_dir / 'heartbeat.wav'
            }
        }
        
        # Generate default audio files if they don't exist
        self._generate_default_audio_assets()
    
    def _generate_default_audio_assets(self):
        """Generate default audio assets using FFmpeg"""
        try:
            # Generate intro music (uplifting chord progression)
            if not self.audio_assets['background_music']['intro'].exists():
                self._generate_intro_music()
            
            # Generate medical background (calm, professional)
            if not self.audio_assets['background_music']['medical'].exists():
                self._generate_medical_background()
            
            # Generate upbeat background
            if not self.audio_assets['background_music']['upbeat'].exists():
                self._generate_upbeat_background()
            
            # Generate sound effects
            self._generate_sound_effects()
            
        except Exception as e:
            logger.warning(f"⚠️ Could not generate audio assets: {e}")
    
    def _generate_intro_music(self):
        """Generate uplifting intro music"""
        try:
            output_file = self.audio_assets['background_music']['intro']
            
            # Create a pleasant chord progression
            cmd = [
                'ffmpeg', '-y', '-f', 'lavfi',
                '-i', 'sine=frequency=261.63:duration=0.5',  # C
                '-i', 'sine=frequency=329.63:duration=0.5',  # E
                '-i', 'sine=frequency=392.00:duration=0.5',  # G
                '-i', 'sine=frequency=523.25:duration=0.5',  # C high
                '-filter_complex', 
                '[0][1][2][3]amix=inputs=4:duration=longest:weights=0.3 0.3 0.3 0.3,'
                'aenvelope=attack=0.1:decay=0.1:sustain=0.8:release=0.3,'
                'volume=0.4',
                '-t', '3',
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=30)
            logger.info("✅ Generated intro music")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not generate intro music: {e}")
    
    def _generate_medical_background(self):
        """Generate calm medical background music"""
        try:
            output_file = self.audio_assets['background_music']['medical']
            
            # Soft, calming tones
            cmd = [
                'ffmpeg', '-y', '-f', 'lavfi',
                '-i', 'sine=frequency=220:duration=10',  # A
                '-i', 'sine=frequency=261.63:duration=10',  # C
                '-filter_complex', 
                '[0][1]amix=inputs=2:duration=longest:weights=0.2 0.15,'
                'aenvelope=attack=1:decay=0.5:sustain=0.8:release=2,'
                'volume=0.2',
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=30)
            logger.info("✅ Generated medical background music")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not generate medical background: {e}")
    
    def _generate_upbeat_background(self):
        """Generate upbeat background music"""
        try:
            output_file = self.audio_assets['background_music']['upbeat']
            
            # More energetic progression
            cmd = [
                'ffmpeg', '-y', '-f', 'lavfi',
                '-i', 'sine=frequency=440:duration=10',  # A
                '-i', 'sine=frequency=554.37:duration=10',  # C#
                '-i', 'sine=frequency=659.25:duration=10',  # E
                '-filter_complex', 
                '[0][1][2]amix=inputs=3:duration=longest:weights=0.25 0.2 0.2,'
                'aenvelope=attack=0.1:decay=0.2:sustain=0.7:release=1,'
                'volume=0.3',
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=30)
            logger.info("✅ Generated upbeat background music")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not generate upbeat background: {e}")
    
    def _generate_sound_effects(self):
        """Generate basic sound effects"""
        effects = {
            'swoosh': {
                'generator': 'sine=frequency=800:duration=0.3',
                'filter': 'aenvelope=attack=0.01:decay=0.29:sustain=0:release=0,'
                         'highpass=f=400,lowpass=f=2000,volume=0.5'
            },
            'pop': {
                'generator': 'sine=frequency=1000:duration=0.1',
                'filter': 'aenvelope=attack=0.01:decay=0.09:sustain=0:release=0,'
                         'volume=0.6'
            },
            'ding': {
                'generator': 'sine=frequency=1319:duration=1',  # E6
                'filter': 'aenvelope=attack=0.01:decay=0.3:sustain=0.2:release=0.5,'
                         'volume=0.4'
            },
            'heartbeat': {
                'generator': 'sine=frequency=60:duration=1',
                'filter': 'aenvelope=attack=0.01:decay=0.1:sustain=0.1:release=0.1,'
                         'volume=0.3'
            }
        }
        
        for effect_name, params in effects.items():
            try:
                output_file = self.audio_assets['sound_effects'][effect_name]
                if not output_file.exists():
                    cmd = [
                        'ffmpeg', '-y', '-f', 'lavfi',
                        '-i', params['generator'],
                        '-af', params['filter'],
                        str(output_file)
                    ]
                    
                    run_with_timeout(cmd, timeout_seconds=15)
                    logger.info(f"✅ Generated {effect_name} sound effect")
                    
            except Exception as e:
                logger.warning(f"⚠️ Could not generate {effect_name}: {e}")
    
    def create_tts_audio(self, text: str, voice_type: str = "professional") -> Optional[str]:
        """Create text-to-speech audio with multiple fallbacks"""
        try:
            # Clean text for TTS
            clean_text = self._clean_text_for_tts(text)
            
            # Try Azure TTS first (highest quality)
            if self.azure_speech_config and voice_type == "professional":
                audio_file = self._create_azure_tts(clean_text)
                if audio_file:
                    return audio_file
            
            # Fallback to gTTS
            if GTTS_AVAILABLE:
                return self._create_gtts_audio(clean_text)
            
            # Last resort: Generate synthetic speech with FFmpeg
            return self._create_synthetic_speech(clean_text)
            
        except Exception as e:
            logger.error(f"❌ TTS creation failed: {e}")
            return None
    
    def _clean_text_for_tts(self, text: str) -> str:
        """Clean and prepare text for TTS"""
        # Remove unwanted characters
        text = text.replace('#', '').replace('@', '')
        text = text.replace('&', 'and')
        
        # Add pauses for better speech
        text = text.replace('.', '. ')
        text = text.replace(',', ', ')
        text = text.replace('!', '! ')
        text = text.replace('?', '? ')
        
        # Limit length
        if len(text) > 200:
            text = text[:197] + "..."
        
        return text.strip()
    
    def _create_azure_tts(self, text: str) -> Optional[str]:
        """Create high-quality TTS using Azure Cognitive Services"""
        try:
            output_file = self.temp_dir / f"azure_tts_{uuid.uuid4().hex[:8]}.wav"
            
            # Configure audio output
            audio_config = speechsdk.audio.AudioOutputConfig(filename=str(output_file))
            
            # Create synthesizer
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.azure_speech_config,
                audio_config=audio_config
            )
            
            # Use SSML for better control
            ssml_text = f"""
            <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-AU">
                <voice name="en-AU-NatashaNeural">
                    <prosody rate="medium" pitch="medium" volume="loud">
                        {text}
                    </prosody>
                </voice>
            </speak>
            """
            
            # Synthesize speech
            result = synthesizer.speak_ssml_async(ssml_text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info("✅ Azure TTS audio created")
                return str(output_file)
            else:
                logger.warning(f"⚠️ Azure TTS failed: {result.reason}")
                
        except Exception as e:
            logger.warning(f"⚠️ Azure TTS error: {e}")
        
        return None
    
    def _create_gtts_audio(self, text: str) -> Optional[str]:
        """Create TTS using Google Text-to-Speech"""
        try:
            output_file = self.temp_dir / f"gtts_{uuid.uuid4().hex[:8]}.mp3"
            
            # Create TTS object with Australian accent
            tts = gTTS(
                text=text,
                lang=config.audio.voice_language,
                tld=config.audio.voice_accent,
                slow=False
            )
            
            # Save to temporary file
            tts.save(str(output_file))
            
            # Convert to WAV for better compatibility
            wav_file = output_file.with_suffix('.wav')
            cmd = [
                'ffmpeg', '-y', '-i', str(output_file),
                '-acodec', 'pcm_s16le', '-ar', '44100',
                str(wav_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=30)
            
            # Cleanup MP3
            if output_file.exists():
                output_file.unlink()
            
            if wav_file.exists():
                logger.info("✅ gTTS audio created")
                return str(wav_file)
                
        except Exception as e:
            logger.warning(f"⚠️ gTTS error: {e}")
        
        return None
    
    def _create_synthetic_speech(self, text: str) -> Optional[str]:
        """Create basic synthetic speech using FFmpeg (fallback)"""
        try:
            output_file = self.temp_dir / f"synthetic_{uuid.uuid4().hex[:8]}.wav"
            
            # Estimate duration (average speaking rate: 150 words per minute)
            words = len(text.split())
            duration = max(2, min(10, words / 2.5))  # 2-10 seconds
            
            # Create basic tone pattern
            cmd = [
                'ffmpeg', '-y', '-f', 'lavfi',
                '-i', f'sine=frequency=200:duration={duration}',
                '-af', 'aenvelope=attack=0.1:decay=0.1:sustain=0.8:release=0.1,'
                      'volume=0.3',
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=20)
            
            if output_file.exists():
                logger.info("✅ Synthetic speech created (fallback)")
                return str(output_file)
            print(cmd)       
        except Exception as e:
            logger.warning(f"⚠️ Synthetic speech error: {e}")
        
        return None
    
    def create_intro_audio(self, title: str) -> Optional[str]:
        """Create engaging intro audio with title narration and music"""
        try:
            logger.info(f"🎵 Creating intro audio: {title[:30]}...")
            
            # Create TTS for title
            intro_text = f"Dr. Linda Greenwall presents: {title}"
            tts_file = self.create_tts_audio(intro_text, "professional")
            
            if not tts_file or not os.path.exists(tts_file):
                logger.warning("⚠️ Could not create intro TTS")
                return None
            
            # Get background music
            music_file = self.audio_assets['background_music']['intro']
            if not music_file.exists():
                logger.warning("⚠️ Intro music not available")
                return tts_file  # Return just TTS
            
            # Mix TTS with background music
            output_file = self.temp_dir / f"intro_final_{uuid.uuid4().hex[:8]}.wav"
            
            cmd = [
                'ffmpeg', '-y',
                '-i', tts_file,
                '-i', str(music_file),
                '-filter_complex', 
                f'[0]volume={config.audio.intro_volume}[voice];'
                f'[1]volume={config.audio.background_music_volume}[music];'
                '[voice][music]amix=inputs=2:duration=shortest:weights=1 0.5',
                '-t', str(config.video.intro_duration),
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=30)
            
            # Cleanup TTS file
            try:
                os.remove(tts_file)
            except:
                pass
            
            if output_file.exists():
                logger.info("✅ Intro audio created with music")
                return str(output_file)
            
        except Exception as e:
            logger.error(f"❌ Intro audio creation failed: {e}")
        
        return None
    
    def create_outro_audio(self) -> Optional[str]:
        """Create engaging outro audio with call-to-action"""
        try:
            logger.info("🎵 Creating outro audio...")
            
            # Create TTS for outro
            outro_text = "Please like and subscribe for more expert dental advice!"
            tts_file = self.create_tts_audio(outro_text, "professional")
            
            if not tts_file or not os.path.exists(tts_file):
                logger.warning("⚠️ Could not create outro TTS")
                return None
            
            # Get background music
            music_file = self.audio_assets['background_music']['upbeat']
            if not music_file.exists():
                logger.warning("⚠️ Outro music not available")
                return tts_file
            
            # Add notification sound effect
            ding_file = self.audio_assets['sound_effects']['ding']
            
            # Mix TTS with background music and sound effect
            output_file = self.temp_dir / f"outro_final_{uuid.uuid4().hex[:8]}.wav"
            
            if ding_file.exists():
                cmd = [
                    'ffmpeg', '-y',
                    '-i', tts_file,
                    '-i', str(music_file),
                    '-i', str(ding_file),
                    '-filter_complex', 
                    f'[0]volume={config.audio.outro_volume}[voice];'
                    f'[1]volume={config.audio.background_music_volume}[music];'
                    f'[2]volume={config.audio.sound_effects_volume},adelay=2000|2000[ding];'
                    '[voice][music][ding]amix=inputs=3:duration=longest:weights=1 0.4 0.6',
                    '-t', str(config.video.outro_duration),
                    str(output_file)
                ]
            else:
                cmd = [
                    'ffmpeg', '-y',
                    '-i', tts_file,
                    '-i', str(music_file),
                    '-filter_complex', 
                    f'[0]volume={config.audio.outro_volume}[voice];'
                    f'[1]volume={config.audio.background_music_volume}[music];'
                    '[voice][music]amix=inputs=2:duration=shortest:weights=1 0.5',
                    '-t', str(config.video.outro_duration),
                    str(output_file)
                ]
            
            run_with_timeout(cmd, timeout_seconds=30)
            
            # Cleanup TTS file
            try:
                os.remove(tts_file)
            except:
                pass
            
            if output_file.exists():
                logger.info("✅ Outro audio created with music and effects")
                return str(output_file)
            
        except Exception as e:
            logger.error(f"❌ Outro audio creation failed: {e}")
        
        return None
    
    def enhance_clip_audio(self, input_audio: str, clip_duration: float) -> Optional[str]:
        """Enhance clip audio with background music and effects"""
        try:
            if not os.path.exists(input_audio):
                logger.warning("⚠️ Input audio file not found")
                return input_audio
            
            logger.info("🎵 Enhancing clip audio...")
            
            # Choose background music based on content type
            bg_music = self.audio_assets['background_music']['medical']
            if not bg_music.exists():
                logger.warning("⚠️ Background music not available")
                return input_audio
            
            output_file = self.temp_dir / f"enhanced_audio_{uuid.uuid4().hex[:8]}.wav"
            
            # Mix original audio with background music
            cmd = [
                'ffmpeg', '-y',
                '-i', input_audio,
                '-i', str(bg_music),
                '-filter_complex', 
                f'[0]volume=1.0[original];'
                f'[1]volume={config.audio.background_music_volume}[bg];'
                '[original][bg]amix=inputs=2:duration=shortest:weights=1 0.3',
                '-t', str(clip_duration),
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=60)
            
            if output_file.exists():
                logger.info("✅ Clip audio enhanced")
                return str(output_file)
            
        except Exception as e:
            logger.warning(f"⚠️ Audio enhancement failed: {e}")
        
        return input_audio
    
    def add_sound_effects_to_clip(self, input_audio: str, effect_timings: List[Dict]) -> Optional[str]:
        """Add sound effects at specific timings in the clip"""
        try:
            if not effect_timings or not os.path.exists(input_audio):
                return input_audio
            
            logger.info(f"🎵 Adding {len(effect_timings)} sound effects to clip...")
            
            # Build complex filter for sound effects
            filter_parts = [f'[0]volume=1.0[main]']
            input_parts = ['-i', input_audio]
            
            for i, effect in enumerate(effect_timings):
                effect_type = effect.get('type', 'pop')
                timing = effect.get('time', 0)
                
                effect_file = self.audio_assets['sound_effects'].get(effect_type)
                if not effect_file or not effect_file.exists():
                    continue
                
                input_parts.extend(['-i', str(effect_file)])
                delay_ms = int(timing * 1000)
                filter_parts.append(
                    f'[{i+1}]volume={config.audio.sound_effects_volume},'
                    f'adelay={delay_ms}|{delay_ms}[fx{i}]'
                )
            
            if len(filter_parts) == 1:
                return input_audio  # No effects to add
            
            # Combine all effects
            mix_inputs = ['[main]'] + [f'[fx{i}]' for i in range(len(effect_timings))]
            filter_parts.append(
                f'{" ".join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=longest'
            )
            
            output_file = self.temp_dir / f"effects_audio_{uuid.uuid4().hex[:8]}.wav"
            
            cmd = ['ffmpeg', '-y'] + input_parts + [
                '-filter_complex', ';'.join(filter_parts),
                str(output_file)
            ]
            
            run_with_timeout(cmd, timeout_seconds=60)
            
            if output_file.exists():
                logger.info("✅ Sound effects added to clip")
                return str(output_file)
            
        except Exception as e:
            logger.warning(f"⚠️ Sound effects addition failed: {e}")
        
        return input_audio
    
    def cleanup_temp_files(self):
        """Clean up temporary audio files"""
        try:
            for temp_file in self.temp_dir.glob("*"):
                try:
                    if temp_file.is_file():
                        temp_file.unlink()
                except:
                    pass
            logger.info("🧹 Audio temp files cleaned up")
        except Exception as e:
            logger.warning(f"⚠️ Audio cleanup error: {e}")

class AudioEffectGenerator:
    """Generate dynamic audio effects based on content"""
    
    def __init__(self, audio_engine: AudioEngine):
        self.audio_engine = audio_engine
    
    def analyze_content_for_effects(self, transcript: str, duration: float) -> List[Dict]:
        """Analyze transcript content to suggest sound effects"""
        effects = []
        
        # Keywords that trigger specific sound effects
        effect_keywords = {
            'pop': ['pop', 'bubble', 'burst', 'quick', 'snap'],
            'swoosh': ['move', 'swipe', 'transition', 'change', 'shift'],
            'ding': ['important', 'remember', 'note', 'tip', 'key'],
            'heartbeat': ['health', 'vital', 'life', 'heart', 'pulse']
        }
        
        words = transcript.lower().split()
        
        # Analyze content for effect placement
        for i, word in enumerate(words):
            word_time = (i / len(words)) * duration
            
            # Skip if too close to start/end
            if word_time < 2 or word_time > duration - 2:
                continue
            
            for effect_type, keywords in effect_keywords.items():
                if any(keyword in word for keyword in keywords):
                    effects.append({
                        'type': effect_type,
                        'time': word_time,
                        'trigger_word': word
                    })
                    break
        
        # Limit effects to prevent overcrowding
        if len(effects) > 3:
            effects = effects[:3]
        
        # Add emphasis effects at natural pauses
        if duration > 30:
            effects.append({
                'type': 'ding',
                'time': duration * 0.7,
                'trigger_word': 'emphasis'
            })
        
        return effects

# Global audio engine instance
audio_engine = AudioEngine()
effect_generator = AudioEffectGenerator(audio_engine)

if __name__ == "__main__":
    # Test audio engine
    print("🎵 Testing Audio Engine...")
    
    # Test TTS
    test_audio = audio_engine.create_tts_audio("This is a test of the audio engine", "professional")
    if test_audio:
        print(f"✅ TTS test successful: {test_audio}")
    
    # # Test intro
    # intro_audio = audio_engine.create_intro_audio("MIH Treatment Options")
    # if intro_audio:
    #     print(f"✅ Intro test successful: {intro_audio}")
    
    # # Test outro
    # outro_audio = audio_engine.create_outro_audio()
    # if outro_audio:
    #     print(f"✅ Outro test successful: {outro_audio}")
    
    print("🎵 Audio Engine test complete!")