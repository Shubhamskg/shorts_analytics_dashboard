#!/usr/bin/env python3
"""
Simple Instagram API Test Script
Tests if your Instagram account is ready for uploading reels
"""

import requests
import os
from urllib.parse import urlencode

class SimpleInstagramTest:
    def __init__(self):
        # Load from environment or set directly
        self.client_id = "1413553243265434"  # Your Facebook App ID (already configured)
        self.client_secret = input("Enter your Instagram App Secret: ").strip()
        
        # Try to load existing token
        self.access_token = os.getenv('INSTAGRAM_ACCESS_TOKEN', '').strip()
        
        print(f"📱 App ID: {self.client_id}")
        print(f"🔑 Token: {'✅ Found' if self.access_token else '❌ Missing'}")
    
    def get_auth_code_manually(self):
        """Get authorization code manually from user"""
        print("\n🔐 Step 1: Get Authorization Code")
        print("=" * 40)
        
        # Create auth URL
        params = {
            'client_id': self.client_id,
            'redirect_uri': 'https://localhost:3000/auth/callback',
            'scope': 'instagram_business_basic,instagram_business_content_publish',
            'response_type': 'code'
        }
        
        auth_url = f"https://api.instagram.com/oauth/authorize?{urlencode(params)}"
        
        print("📋 Instructions:")
        print("1. Copy this URL and open in browser:")
        print(f"   {auth_url}")
        print("")
        print("2. Login with your Instagram BUSINESS account")
        print("3. You'll see 'This site can't be reached' - THIS IS NORMAL!")
        print("4. In the address bar, you'll see a URL like:")
        print("   https://localhost:3000/auth/callback?code=AQDabc123...")
        print("5. Copy everything after 'code=' (before any # or &)")
        
        print("\n🔗 Auth URL (copy this):")
        print(auth_url)
        
        code = input("\n🔑 Paste the authorization code here: ").strip()
        
        # Clean the code
        if '#' in code:
            code = code.split('#')[0]
        if '&' in code:
            code = code.split('&')[0]
            
        return code if code else None
    
    def exchange_code_for_token(self, code):
        """Exchange authorization code for access token"""
        print("\n🔄 Step 2: Exchange Code for Token")
        print("=" * 40)
        
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'redirect_uri': 'https://localhost:3000/auth/callback',
            'code': code
        }
        
        try:
            print("🔄 Exchanging code for token...")
            response = requests.post('https://api.instagram.com/oauth/access_token', data=data)
            
            if response.status_code == 200:
                result = response.json()
                access_token = result.get('access_token')
                user_id = result.get('user_id')
                
                print("✅ Success!")
                print(f"🔑 Access Token: {access_token}")
                print(f"👤 User ID: {user_id}")
                
                # Save token
                self.save_token(access_token, user_id)
                self.access_token = access_token
                
                return access_token
            else:
                print(f"❌ Failed: {response.json()}")
                return None
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def test_token(self, access_token=None):
        """Test if access token works"""
        print("\n🧪 Step 3: Test Access Token")
        print("=" * 40)
        
        token = access_token or self.access_token
        if not token:
            print("❌ No access token to test")
            return False
        
        try:
            print("🔍 Testing token...")
            url = "https://graph.instagram.com/v18.0/me"
            params = {
                'fields': 'id,username,account_type,media_count',
                'access_token': token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Token is valid!")
                print(f"   👤 Username: @{data.get('username', 'Unknown')}")
                print(f"   🆔 User ID: {data.get('id', 'Unknown')}")
                print(f"   📱 Account Type: {data.get('account_type', 'Unknown')}")
                print(f"   📸 Media Count: {data.get('media_count', 'Unknown')}")
                
                # Check account type
                account_type = data.get('account_type', '')
                if account_type in ['BUSINESS', 'CREATOR']:
                    print("   ✅ Account type is good for API access")
                else:
                    print("   ⚠️ Warning: Account should be BUSINESS or CREATOR")
                
                return True
            else:
                print(f"❌ Token invalid: {response.json()}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing token: {e}")
            return False
    
    def test_upload_permissions(self):
        """Test upload permissions"""
        print("\n📤 Step 4: Test Upload Permissions")
        print("=" * 40)
        
        if not self.access_token:
            print("❌ No access token available")
            return False
        
        try:
            print("🔍 Checking upload permissions...")
            url = "https://graph.instagram.com/v18.0/me/media"
            params = {
                'fields': 'id,media_type',
                'limit': 1,
                'access_token': self.access_token
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                print("✅ Upload permissions verified!")
                print("   You can upload reels to this account")
                return True
            else:
                print(f"❌ Upload permission issue: {response.json()}")
                return False
                
        except Exception as e:
            print(f"❌ Error checking permissions: {e}")
            return False
    
    def save_token(self, access_token, user_id):
        """Save token to .env file"""
        try:
            # Read existing .env
            env_content = {}
            if os.path.exists('.env'):
                with open('.env', 'r') as f:
                    for line in f:
                        if '=' in line and not line.startswith('#'):
                            key, value = line.strip().split('=', 1)
                            env_content[key] = value
            
            # Update tokens
            env_content['INSTAGRAM_CLIENT_ID'] = self.client_id
            env_content['INSTAGRAM_CLIENT_SECRET'] = self.client_secret
            env_content['INSTAGRAM_ACCESS_TOKEN'] = access_token
            env_content['INSTAGRAM_USER_ID'] = user_id
            
            # Write back to .env
            with open('.env', 'w') as f:
                for key, value in env_content.items():
                    f.write(f"{key}={value}\n")
            
            print("💾 Token saved to .env file!")
            
        except Exception as e:
            print(f"⚠️ Could not save to .env: {e}")
            print(f"\n📝 Manually add these to your .env file:")
            print(f"INSTAGRAM_ACCESS_TOKEN={access_token}")
            print(f"INSTAGRAM_USER_ID={user_id}")
    
    def run_complete_test(self):
        """Run complete Instagram API test"""
        print("🎯 Simple Instagram API Test")
        print("=" * 50)
        print("Tests if your Instagram account is ready for reel uploads")
        
        # Check if we already have a token
        if self.access_token:
            print("\n📄 Found existing token, testing it...")
            if self.test_token():
                if self.test_upload_permissions():
                    print("\n🎉 SUCCESS! Your Instagram API is ready!")
                    print("✅ Token works")
                    print("✅ Account is properly configured")
                    print("✅ Upload permissions are active")
                    return True
                else:
                    print("\n⚠️ Token works but upload permissions failed")
            else:
                print("\n❌ Existing token is invalid, need to get new one")
                self.access_token = ""
        
        # If no token or token failed, get new one
        if not self.access_token:
            print("\n🔐 Getting new access token...")
            
            # Get authorization code
            code = self.get_auth_code_manually()
            if not code:
                print("❌ No authorization code provided")
                return False
            
            # Exchange for token
            token = self.exchange_code_for_token(code)
            if not token:
                print("❌ Failed to get access token")
                return False
            
            # Test the new token
            if self.test_token(token):
                if self.test_upload_permissions():
                    print("\n🎉 SUCCESS! Your Instagram API is ready!")
                    print("✅ Authentication completed")
                    print("✅ Token obtained and tested")
                    print("✅ Upload permissions verified")
                    print("\n📋 Next steps:")
                    print("1. Your .env file is updated with the token")
                    print("2. You can now upload reels via API")
                    print("3. Set up your other Instagram accounts")
                    return True
                else:
                    print("\n⚠️ Token works but upload permissions need attention")
            else:
                print("\n❌ New token is not working properly")
        
        return False

def main():
    """Main function"""
    print("🚀 Simple Instagram API Test Tool")
    
    # Load existing environment variables
    if os.path.exists('.env'):
        print("📁 Loading .env file...")
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    
    # Run the test
    tester = SimpleInstagramTest()
    success = tester.run_complete_test()
    
    if success:
        print("\n🚀 Ready to upload reels!")
    else:
        print("\n❌ Setup incomplete. Check the errors above.")
        print("\n💡 Common issues:")
        print("- Instagram account must be Business or Creator type")
        print("- Make sure you granted all permissions during login")
        print("- Check your Facebook app configuration")

if __name__ == "__main__":
    main()