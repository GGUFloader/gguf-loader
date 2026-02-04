"""
Update Checker Module
Checks for new versions of GGUF Loader from GitHub releases
"""
import json
import logging
from typing import Optional, Dict
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from packaging import version

logger = logging.getLogger(__name__)

# Get version without circular import
def get_current_version():
    """Get current version from __init__.py"""
    try:
        with open('__init__.py', 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('__version__'):
                    return line.split('=')[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "2.0.1"  # Fallback version

class UpdateChecker:
    """Checks for application updates from GitHub releases"""
    
    GITHUB_API_URL = "https://api.github.com/repos/GGUFloader/gguf-loader/releases/latest"
    GITHUB_RELEASES_URL = "https://github.com/GGUFloader/gguf-loader/releases"
    
    def __init__(self):
        self.current_version = get_current_version()
        self.latest_version = None
        self.download_url = None
        self.release_notes = None
        
    def check_for_updates(self, timeout: int = 5) -> Optional[Dict]:
        """
        Check if a new version is available
        
        Args:
            timeout: Request timeout in seconds
            
        Returns:
            Dict with update info if available, None otherwise
            {
                'available': bool,
                'current_version': str,
                'latest_version': str,
                'download_url': str,
                'release_notes': str,
                'release_url': str
            }
        """
        try:
            # Create request with user agent (GitHub API requires it)
            request = Request(
                self.GITHUB_API_URL,
                headers={'User-Agent': f'GGUF-Loader/{self.current_version}'}
            )
            
            # Fetch latest release info
            with urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            # Extract version info
            latest_tag = data.get('tag_name', '').lstrip('v')
            self.latest_version = latest_tag
            self.release_notes = data.get('body', 'No release notes available.')
            
            # Find Windows executable download URL
            assets = data.get('assets', [])
            for asset in assets:
                if asset['name'].endswith('.exe'):
                    self.download_url = asset['browser_download_url']
                    break
            
            # If no exe found, use the release page
            if not self.download_url:
                self.download_url = data.get('html_url', self.GITHUB_RELEASES_URL)
            
            # Compare versions
            update_available = self._is_newer_version(latest_tag, self.current_version)
            
            if update_available:
                logger.info(f"Update available: {self.current_version} -> {latest_tag}")
                return {
                    'available': True,
                    'current_version': self.current_version,
                    'latest_version': latest_tag,
                    'download_url': self.download_url,
                    'release_notes': self.release_notes,
                    'release_url': data.get('html_url', self.GITHUB_RELEASES_URL)
                }
            else:
                logger.info(f"No updates available. Current version: {self.current_version}")
                return {
                    'available': False,
                    'current_version': self.current_version,
                    'latest_version': latest_tag
                }
                
        except HTTPError as e:
            logger.error(f"HTTP error checking for updates: {e.code} {e.reason}")
            return None
        except URLError as e:
            logger.error(f"Network error checking for updates: {e.reason}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing update response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error checking for updates: {e}")
            return None
    
    def _is_newer_version(self, latest: str, current: str) -> bool:
        """
        Compare version strings
        
        Args:
            latest: Latest version string
            current: Current version string
            
        Returns:
            True if latest is newer than current
        """
        try:
            return version.parse(latest) > version.parse(current)
        except Exception as e:
            logger.error(f"Error comparing versions: {e}")
            return False
