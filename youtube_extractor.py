import yt_dlp
import subprocess
import os
import sys
from datetime import datetime

def download_youtube_segment(url, start_time, end_time, output_filename=None, aspect_ratio="vertical"):
    """
    Download a specific time segment from a YouTube video with optional aspect ratio conversion.
    
    Args:
        url (str): YouTube video URL
        start_time (str): Start time in format "HH:MM:SS" or "MM:SS"
        end_time (str): End time in format "HH:MM:SS" or "MM:SS"
        output_filename (str, optional): Custom output filename (without extension)
        aspect_ratio (str): "original", "square" (1:1), or "vertical" (9:16) - default: "vertical"
    
    Returns:
        str: Path to the downloaded video file
    """
    
    try:
        # Create output directory if it doesn't exist
        output_dir = "downloaded_videos"
        os.makedirs(output_dir, exist_ok=True)
        
        # Get video info first
        print("Getting video information...")
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'video')
            video_id = info.get('id', 'unknown')
        
        # Clean title for filename
        safe_title = "".join(c for c in video_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        
        # Set output filename
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            aspect_suffix = f"_{aspect_ratio}" if aspect_ratio != "original" else ""
            output_filename = f"{safe_title}_{start_time.replace(':', '')}-{end_time.replace(':', '')}{aspect_suffix}_{timestamp}"
        
        temp_video_path = os.path.join(output_dir, f"temp_{video_id}.%(ext)s")
        final_video_path = os.path.join(output_dir, f"{output_filename}.mp4")
        
        # Download the full video first
        print("Downloading video...")
        ydl_opts = {
            'format': 'best[height<=720]/best',  # Download best quality up to 720p
            'outtmpl': temp_video_path,
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Find the actual downloaded file
        temp_files = [f for f in os.listdir(output_dir) if f.startswith(f"temp_{video_id}")]
        if not temp_files:
            raise Exception("Failed to download video")
        
        actual_temp_path = os.path.join(output_dir, temp_files[0])
        
        # Extract the segment using ffmpeg
        print(f"Extracting segment from {start_time} to {end_time}...")
        
        # Build FFmpeg command based on aspect ratio
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', actual_temp_path,
            '-ss', start_time,
            '-to', end_time,
        ]
        
        # Add video filters based on aspect ratio
        if aspect_ratio == "square":
            # Create 1:1 aspect ratio (square) with padding instead of cropping
            ffmpeg_cmd.extend([
                '-vf', 'scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:black',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'fast'
            ])
        elif aspect_ratio == "vertical":
            # Create 9:16 aspect ratio (vertical/portrait) with padding instead of cropping
            ffmpeg_cmd.extend([
                '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'fast'
            ])
        else:
            # Keep original aspect ratio
            ffmpeg_cmd.extend([
                '-c', 'copy',  # Copy streams without re-encoding for speed
            ])
        
        ffmpeg_cmd.extend([
            '-avoid_negative_ts', 'make_zero',
            final_video_path,
            '-y'  # Overwrite output file if exists
        ])
        
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        
        # Clean up temporary file
        os.remove(actual_temp_path)
        
        print(f"Successfully extracted segment with {aspect_ratio} aspect ratio: {final_video_path}")
        return final_video_path
        
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {e}")
        print("Make sure FFmpeg is installed and available in PATH")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def convert_time_format(time_str):
    """
    Convert time string to ensure it's in HH:MM:SS format.
    Accepts formats like "1:30", "01:30", "1:30:45", "01:30:45"
    """
    parts = time_str.split(':')
    if len(parts) == 2:
        # MM:SS format
        return f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    elif len(parts) == 3:
        # HH:MM:SS format
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
    else:
        raise ValueError("Invalid time format. Use MM:SS or HH:MM:SS")

def main():
    """
    Main function to run the script with user input or command line arguments.
    """
    
    # Check if ffmpeg is available
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: FFmpeg is not installed or not available in PATH.")
        print("Please install FFmpeg from https://ffmpeg.org/download.html")
        return
    
    # Get input from command line arguments or user input
    if len(sys.argv) >= 4:
        url = sys.argv[1]
        start_time = sys.argv[2]
        end_time = sys.argv[3]
        aspect_ratio = sys.argv[4] if len(sys.argv) > 4 else "vertical"
    else:
        print("YouTube Video Segment Extractor")
        print("=" * 40)
        url = input("Enter YouTube URL: ").strip()
        start_time = input("Enter start time (MM:SS or HH:MM:SS): ").strip()
        end_time = input("Enter end time (MM:SS or HH:MM:SS): ").strip()
        
    aspect_ratio = "vertical"
    
    # Validate and convert time formats
    try:
        start_time = convert_time_format(start_time)
        end_time = convert_time_format(end_time)
    except ValueError as e:
        print(f"Time format error: {e}")
        return
    
    # Optional: custom filename
    custom_filename = input("Enter custom filename (optional, press Enter to skip): ").strip()
    if not custom_filename:
        custom_filename = None
    
    print(f"\nStarting download and extraction with {aspect_ratio} aspect ratio...")
    result = download_youtube_segment(url, start_time, end_time, custom_filename, aspect_ratio)
    
    if result:
        print(f"\n✅ Success! Video segment saved as: {result}")
    else:
        print("\n❌ Failed to extract video segment")

if __name__ == "__main__":
    main()

# Example usage:
# python youtube_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID" "1:30" "3:45"           # Default: vertical
# python youtube_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID" "1:30" "3:45" "square"   # Square with padding
# python youtube_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID" "1:30" "3:45" "vertical" # Vertical with padding
# python youtube_extractor.py "https://www.youtube.com/watch?v=VIDEO_ID" "1:30" "3:45" "original" # Keep original
# 
# Or run the script and enter values interactively:
# python youtube_extractor.py

# Programmatic usage examples:
# download_youtube_segment(url, "1:30", "3:45", "my_clip")               # Default: vertical 9:16 with padding
# download_youtube_segment(url, "1:30", "3:45", "my_clip", "square")     # Square 1:1 with padding
# download_youtube_segment(url, "1:30", "3:45", "my_clip", "vertical")   # Vertical 9:16 with padding
# download_youtube_segment(url, "1:30", "3:45", "my_clip", "original")   # Keep original