"""Credential testing utilities"""
import aiohttp
import asyncio
from typing import Dict, Tuple, Optional
import logging

class CredentialTester:
    """Utility class for testing Reddit API credentials"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    async def _test_client_credentials(self, client_id: str, client_secret: str) -> Tuple[bool, Optional[str]]:
        """Test client credentials by attempting to get an access token"""
        auth_url = "https://www.reddit.com/api/v1/access_token"
        
        try:
            auth = aiohttp.BasicAuth(client_id, client_secret)
            async with aiohttp.ClientSession(auth=auth) as session:
                data = {
                    'grant_type': 'client_credentials',
                    'duration': 'temporary'
                }
                headers = {'User-Agent': 'CredentialTester/1.0'}
                
                async with session.post(auth_url, data=data, headers=headers) as response:
                    if response.status == 401:
                        return False, "Invalid client_id or client_secret"
                    elif response.status != 200:
                        return False, f"HTTP {response.status}: {await response.text()}"
                        
                    response_data = await response.json()
                    if 'error' in response_data:
                        return False, f"API Error: {response_data['error']}"
                        
                    return True, None
                    
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    async def _test_user_auth(self, username: str, password: str, 
                            client_id: str, client_secret: str) -> Tuple[bool, Optional[str]]:
        """Test user authentication credentials"""
        auth_url = "https://www.reddit.com/api/v1/access_token"
        
        try:
            auth = aiohttp.BasicAuth(client_id, client_secret)
            async with aiohttp.ClientSession(auth=auth) as session:
                data = {
                    'grant_type': 'password',
                    'username': username,
                    'password': password
                }
                headers = {'User-Agent': 'CredentialTester/1.0'}
                
                async with session.post(auth_url, data=data, headers=headers) as response:
                    if response.status == 401:
                        return False, "Invalid username or password"
                    elif response.status != 200:
                        return False, f"HTTP {response.status}: {await response.text()}"
                        
                    response_data = await response.json()
                    if 'error' in response_data:
                        error = response_data['error']
                        if error == 'unauthorized_client':
                            return False, ("Your Reddit App is not configured correctly.\n"
                                         "Please ensure you:\n"
                                         "1. Have selected 'script' as the app type when creating your app\n"
                                         "2. Are using the correct client_id from your app\n"
                                         "3. Have created the app under the same account you're using\n"
                                         "\nVisit https://www.reddit.com/prefs/apps to check your app settings")
                        elif error == 'invalid_grant':
                            return False, "Invalid username or password"
                        else:
                            return False, f"API Error: {error}"
                        
                    return True, None
                    
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    async def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """
        Validate Reddit API credentials with detailed feedback
        
        Args:
            credentials: Dictionary containing Reddit API credentials
            
        Returns:
            bool: True if credentials are valid, False otherwise
        """
        required_fields = ['client_id', 'client_secret', 'username', 'password', 'user_agent']
        
        # Check all required fields exist
        for field in required_fields:
            if not credentials.get(field):
                self.logger.error(f"[ERROR] Missing or empty {field}")
                return False
        
        # Test client credentials first
        self.logger.info("Testing client credentials...")
        client_success, client_error = await self._test_client_credentials(
            credentials['client_id'], 
            credentials['client_secret']
        )
        
        if not client_success:
            self.logger.error(f"[ERROR] Client credential test failed: {client_error}")
            self.logger.error("[HELP] Please verify your client_id and client_secret at:")
            self.logger.error("https://www.reddit.com/prefs/apps")
            return False
            
        self.logger.info("[SUCCESS] Client credentials verified")
        
        # Test user authentication
        self.logger.info("Testing user authentication...")
        user_success, user_error = await self._test_user_auth(
            credentials['username'],
            credentials['password'],
            credentials['client_id'],
            credentials['client_secret']
        )
        
        if not user_success:
            self.logger.error(f"[ERROR] User authentication failed: {user_error}")
            self.logger.error("[HELP] Please verify your username and password")
            return False
            
        self.logger.info("[SUCCESS] User credentials verified")
        
        # Test User-Agent by making a simple API call
        self.logger.info("Testing API access...")
        try:
            async with aiohttp.ClientSession() as session:
                headers = {'User-Agent': credentials['user_agent']}
                async with session.get('https://www.reddit.com/api/v1/me', headers=headers) as response:
                    if response.status == 429:
                        self.logger.warning("[WARNING] Rate limited. User-Agent might need adjustment")
                    elif response.status != 200:
                        self.logger.warning(f"[WARNING] Unexpected response testing User-Agent: {response.status}")
        except Exception as e:
            self.logger.warning(f"[WARNING] Error testing User-Agent: {e}")
        
        return True