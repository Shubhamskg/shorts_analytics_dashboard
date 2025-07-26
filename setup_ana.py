#!/usr/bin/env python3
"""
Setup script for YouTube Shorts Analytics Dashboard
Run this script to set up the analytics dashboard for Dr. Greenwall's MIH content
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def print_header():
    """Print setup header"""
    print("=" * 80)
    print("🦷 DR. LINDA GREENWALL MIH SHORTS ANALYTICS DASHBOARD SETUP")
    print("=" * 80)
    print("Setting up comprehensive analytics for MIH expert content...")
    print()

def check_python_version():
    """Check Python version compatibility"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required. Current version:", sys.version)
        return False
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True

def install_requirements():
    """Install required packages"""
    print("\n📦 Installing required packages...")
    
    requirements = [
        "streamlit>=1.28.0",
        "plotly>=5.15.0", 
        "pandas>=1.5.0",
        "google-api-python-client>=2.70.0",
        "google-auth-httplib2>=0.1.0",
        "google-auth-oauthlib>=0.5.0",
        "google-auth>=2.15.0"
    ]
    
    for package in requirements:
        try:
            print(f"Installing {package}...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", package
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"✅ {package} installed successfully")
        except subprocess.CalledProcessError:
            print(f"❌ Failed to install {package}")
            return False
    
    return True

def setup_config_file():
    """Set up configuration file"""
    print("\n⚙️ Setting up configuration...")
    
    config_path = Path("config.py")
    template_path = Path("analytics_config.py")
    
    if config_path.exists():
        response = input("Config file already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("✅ Using existing config file")
            return True
    
    if template_path.exists():
        # Copy template to config
        import shutil
        shutil.copy(template_path, config_path)
        print("✅ Configuration template created as config.py")
        print("⚠️  Please edit config.py and add your API keys and credentials")
        return True
    else:
        # Create basic config
        config_content = '''# config.py - YouTube Analytics Configuration

# YouTube Data API v3 Key
YOUTUBE_API_KEY = "YOUR_YOUTUBE_API_KEY_HERE"

# Upload Channels Configuration
UPLOAD_CHANNELS = [
    {
        "name": "Dr Greenwall MIH Channel",
        "credentials_file": "channel1_credentials.json",
        "privacy_status": "private"
    }
]

# Analytics Settings
ANALYTICS_SETTINGS = {
    "default_time_period_days": 30,
    "max_videos_per_analysis": 50
}
'''
        
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        print("✅ Basic configuration file created")
        print("⚠️  Please edit config.py and add your actual API keys")
        return True

def setup_credentials_directory():
    """Set up credentials directory"""
    print("\n🔐 Setting up credentials directory...")
    
    creds_dir = Path("credentials")
    creds_dir.mkdir(exist_ok=True)
    
    print("✅ Credentials directory created")
    print("📝 Place your Google OAuth2 JSON files in the 'credentials' directory")
    print("   Example: credentials/channel1_credentials.json")
    
    return True

def setup_output_directories():
    """Set up output directories"""
    print("\n📁 Setting up output directories...")
    
    directories = [
        "analytics_exports",
        "dashboard_cache", 
        "reports"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created directory: {directory}")
    
    return True

def create_launch_script():
    """Create dashboard launch script"""
    print("\n🚀 Creating launch script...")
    
    launch_script = '''#!/usr/bin/env python3
"""
Launch script for YouTube Shorts Analytics Dashboard
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    print("🦷 Launching Dr. Greenwall MIH Analytics Dashboard...")
    
    # Check if config exists
    if not Path("config.py").exists():
        print("❌ config.py not found! Please run setup.py first.")
        return
    
    # Launch Streamlit dashboard
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "youtube_analytics_dashboard.py",
            "--browser.gatherUsageStats", "false",
            "--server.headless", "false"
        ])
    except KeyboardInterrupt:
        print("\\n👋 Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Error launching dashboard: {e}")

if __name__ == "__main__":
    main()
'''
    
    with open("launch_dashboard.py", 'w') as f:
        f.write(launch_script)
    
    # Make executable on Unix systems
    if os.name != 'nt':
        os.chmod("launch_dashboard.py", 0o755)
    
    print("✅ Launch script created: launch_dashboard.py")
    return True

def create_readme():
    """Create README file"""
    print("\n📖 Creating documentation...")
    
    readme_content = '''# Dr. Linda Greenwall MIH Shorts Analytics Dashboard

## Overview
Comprehensive analytics dashboard for YouTube Shorts performance tracking across multiple channels focused on Molar Incisor Hypomineralisation (MIH) expert content.

## Features
- 📊 Multi-channel performance comparison
- 🎯 Top-performing videos identification  
- 💬 Engagement metrics analysis
- 📈 Growth trend visualization
- 🦷 MIH-specific content insights
- 📥 Data export capabilities
- 🎨 Interactive charts and graphs

## Setup Instructions

### 1. Install Dependencies
```bash
python setup.py
```

### 2. Configure API Access
1. Edit `config.py` with your YouTube Data API key
2. Place OAuth2 credential files in `credentials/` directory
3. Update channel configurations in `config.py`

### 3. Launch Dashboard
```bash
python launch_dashboard.py
```

## Configuration

### API Keys Required
- YouTube Data API v3 key
- OAuth2 credentials for each channel

### Channels Setup
Configure each channel in `config.py`:
```python
UPLOAD_CHANNELS = [
    {
        "name": "Channel Name",
        "credentials_file": "credentials/channel_creds.json",
        "privacy_status": "private"
    }
]
```

## Dashboard Sections

### 📊 Performance Overview
- Total shorts, views, subscribers
- Cross-channel metrics comparison
- Key performance indicators

### 🏆 Channel Performance
- Individual channel breakdowns
- Views and engagement analysis
- Top performing videos

### 📈 Comparative Analysis  
- Multi-channel performance comparison
- Best performing content identification
- Growth trend analysis

### 💡 Insights & Recommendations
- MIH content performance analysis
- Optimization recommendations
- Content strategy insights

### 📥 Data Export
- CSV export for further analysis
- Comprehensive performance reports
- Historical data backup

## Key Metrics Tracked

### Video Metrics
- Views, likes, comments, shares
- Watch time and retention
- Subscriber growth attribution
- Engagement rates

### Channel Metrics  
- Total subscribers and growth
- Average views per video
- Overall engagement rates
- Content performance trends

### MIH-Specific Analysis
- MIH keyword performance
- Educational content effectiveness
- Parent engagement patterns
- Expert authority metrics

## Troubleshooting

### Common Issues
1. **Authentication Errors**: Ensure OAuth2 files are correctly placed
2. **API Quota Exceeded**: Check YouTube API quota limits
3. **No Data Displayed**: Verify channel permissions and video privacy

### Support
For technical support or feature requests, refer to the main automation system documentation.

## Data Privacy
All analytics data is processed locally. No sensitive information is stored externally beyond Google's YouTube Analytics API requirements.
'''
    
    with open("README.md", 'w') as f:
        f.write(readme_content)
    
    print("✅ Documentation created: README.md")
    return True

def run_verification():
    """Run setup verification"""
    print("\n🔍 Verifying setup...")
    
    required_files = [
        "config.py",
        "youtube_analytics_dashboard.py", 
        "launch_dashboard.py",
        "README.md"
    ]
    
    required_dirs = [
        "analytics_exports",
        "credentials"
    ]
    
    all_good = True
    
    for file in required_files:
        if Path(file).exists():
            print(f"✅ {file}")
        else:
            print(f"❌ {file} missing")
            all_good = False
    
    for directory in required_dirs:
        if Path(directory).exists():
            print(f"✅ {directory}/")
        else:
            print(f"❌ {directory}/ missing")
            all_good = False
    
    return all_good

def print_next_steps():
    """Print next steps for user"""
    print("\n" + "=" * 80)
    print("🎉 SETUP COMPLETE!")
    print("=" * 80)
    print()
    print("📋 NEXT STEPS:")
    print()
    print("1. 🔑 Edit config.py and add your YouTube Data API key")
    print("2. 📁 Place OAuth2 credential JSON files in credentials/ directory")
    print("3. ⚙️  Update channel configurations in config.py")
    print("4. 🚀 Launch dashboard: python launch_dashboard.py")
    print()
    print("📖 For detailed instructions, see README.md")
    print()
    print("🦷 Ready to analyze your MIH content performance!")
    print("=" * 80)

def main():
    """Main setup function"""
    print_header()
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Install requirements
    if not install_requirements():
        print("❌ Package installation failed")
        return False
    
    # Setup configuration
    if not setup_config_file():
        print("❌ Configuration setup failed")
        return False
    
    # Setup directories
    if not setup_credentials_directory():
        return False
    
    if not setup_output_directories():
        return False
    
    # Create scripts and documentation
    if not create_launch_script():
        return False
    
    if not create_readme():
        return False
    
    # Verify setup
    if not run_verification():
        print("❌ Setup verification failed")
        return False
    
    # Show next steps
    print_next_steps()
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed with error: {e}")
        sys.exit(1)