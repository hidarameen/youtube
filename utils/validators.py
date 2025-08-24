"""
URL validation and platform detection utilities
Validates URLs and identifies supported video platforms
"""

import re
import logging
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, parse_qs
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PlatformInfo:
    """Platform information data class"""
    name: str
    display_name: str
    base_domains: List[str]
    url_patterns: List[str]
    supports_playlists: bool = False
    requires_cookies: bool = False

# Comprehensive platform definitions
SUPPORTED_PLATFORMS = {
    'youtube': PlatformInfo(
        name='youtube',
        display_name='YouTube',
        base_domains=['youtube.com', 'youtu.be', 'm.youtube.com', 'www.youtube.com'],
        url_patterns=[
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)',
            r'youtube\.com/channel/([a-zA-Z0-9_-]+)',
            r'youtube\.com/user/([a-zA-Z0-9_-]+)',
            r'youtube\.com/@([a-zA-Z0-9_.-]+)'
        ],
        supports_playlists=True
    ),
    'tiktok': PlatformInfo(
        name='tiktok',
        display_name='TikTok',
        base_domains=['tiktok.com', 'www.tiktok.com', 'm.tiktok.com', 'vm.tiktok.com'],
        url_patterns=[
            r'tiktok\.com/@([^/]+)/video/(\d+)',
            r'tiktok\.com/t/([a-zA-Z0-9]+)',
            r'vm\.tiktok\.com/([a-zA-Z0-9]+)',
            r'tiktok\.com/@([^/]+)'
        ]
    ),
    'instagram': PlatformInfo(
        name='instagram',
        display_name='Instagram',
        base_domains=['instagram.com', 'www.instagram.com', 'm.instagram.com'],
        url_patterns=[
            r'instagram\.com/p/([a-zA-Z0-9_-]+)(?:\?.*)?',
            r'instagram\.com/reel/([a-zA-Z0-9_-]+)(?:\?.*)?',
            r'instagram\.com/tv/([a-zA-Z0-9_-]+)(?:\?.*)?',
            r'instagram\.com/stories/([^/]+)/(\d+)(?:\?.*)?',
            r'instagram\.com/([^/]+)/?(?:\?.*)?'
        ]
    ),
    'facebook': PlatformInfo(
        name='facebook',
        display_name='Facebook',
        base_domains=['facebook.com', 'www.facebook.com', 'm.facebook.com', 'fb.watch'],
        url_patterns=[
            r'facebook\.com/watch/?\?v=(\d+)',
            r'facebook\.com/([^/]+)/videos/(\d+)',
            r'facebook\.com/video\.php\?v=(\d+)',
            r'fb\.watch/([a-zA-Z0-9_-]+)',
            r'facebook\.com/reel/(\d+)(?:\?.*)?',
            r'facebook\.com/share/r/([a-zA-Z0-9_-]+)/?(?:\?.*)?',
            r'facebook\.com/share/v/([a-zA-Z0-9_-]+)/?(?:\?.*)?'
        ]
    ),
    'twitter': PlatformInfo(
        name='twitter',
        display_name='Twitter/X',
        base_domains=['twitter.com', 'www.twitter.com', 'm.twitter.com', 'x.com', 'www.x.com'],
        url_patterns=[
            r'(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)',
            r'(?:twitter\.com|x\.com)/i/web/status/(\d+)',
            r'(?:twitter\.com|x\.com)/([^/]+)/moments/(\d+)'
        ]
    ),
    'dailymotion': PlatformInfo(
        name='dailymotion',
        display_name='Dailymotion',
        base_domains=['dailymotion.com', 'www.dailymotion.com', 'dai.ly'],
        url_patterns=[
            r'dailymotion\.com/video/([a-zA-Z0-9]+)',
            r'dai\.ly/([a-zA-Z0-9]+)',
            r'dailymotion\.com/playlist/([a-zA-Z0-9]+)'
        ],
        supports_playlists=True
    ),
    'vimeo': PlatformInfo(
        name='vimeo',
        display_name='Vimeo',
        base_domains=['vimeo.com', 'www.vimeo.com', 'player.vimeo.com'],
        url_patterns=[
            r'vimeo\.com/(\d+)',
            r'vimeo\.com/channels/([^/]+)/(\d+)',
            r'player\.vimeo\.com/video/(\d+)'
        ]
    ),
    'twitch': PlatformInfo(
        name='twitch',
        display_name='Twitch',
        base_domains=['twitch.tv', 'www.twitch.tv', 'm.twitch.tv', 'clips.twitch.tv'],
        url_patterns=[
            r'twitch\.tv/videos/(\d+)',
            r'twitch\.tv/([^/]+)/clip/([a-zA-Z0-9_-]+)',
            r'clips\.twitch\.tv/([a-zA-Z0-9_-]+)',
            r'twitch\.tv/([^/]+)'
        ]
    ),
    'reddit': PlatformInfo(
        name='reddit',
        display_name='Reddit',
        base_domains=['reddit.com', 'www.reddit.com', 'm.reddit.com', 'v.redd.it'],
        url_patterns=[
            r'reddit\.com/r/([^/]+)/comments/([a-zA-Z0-9]+)',
            r'v\.redd\.it/([a-zA-Z0-9]+)',
            r'reddit\.com/user/([^/]+)/comments/([a-zA-Z0-9]+)'
        ]
    ),
    'streamable': PlatformInfo(
        name='streamable',
        display_name='Streamable',
        base_domains=['streamable.com', 'www.streamable.com'],
        url_patterns=[
            r'streamable\.com/([a-zA-Z0-9]+)'
        ]
    )
}

def is_valid_url(url: str) -> bool:
    """
    Validate if the provided string is a valid URL
    
    Args:
        url: URL string to validate
        
    Returns:
        bool: True if valid URL, False otherwise
    """
    try:
        if not url or not isinstance(url, str):
            return False
        
        # Basic URL structure validation
        if not url.startswith(('http://', 'https://')):
            # Try adding https prefix
            url = 'https://' + url.lstrip('/')
        
        # Parse URL
        parsed = urlparse(url)
        
        # Check required components
        if not parsed.netloc:
            return False
        
        # Check for valid domain structure
        domain_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-_.]*[a-zA-Z0-9]$'
        if not re.match(domain_pattern, parsed.netloc.replace('www.', '')):
            return False
        
        # Check for dangerous schemes
        dangerous_schemes = ['javascript', 'data', 'vbscript', 'file']
        if parsed.scheme.lower() in dangerous_schemes:
            return False
        
        return True
        
    except Exception as e:
        logger.debug(f"URL validation error for '{url}': {e}")
        return False

def get_platform_from_url(url: str) -> Optional[str]:
    """
    Identify the platform from a video URL
    
    Args:
        url: Video URL to analyze
        
    Returns:
        str or None: Platform name if recognized, None otherwise
    """
    try:
        if not is_valid_url(url):
            return None
        
        # Parse URL
        parsed = urlparse(url.lower())
        domain = parsed.netloc
        
        # Remove common prefixes properly
        if domain.startswith('www.'):
            domain = domain[4:]
        elif domain.startswith('m.'):
            domain = domain[2:]
        
        # Check each platform
        for platform_name, platform_info in SUPPORTED_PLATFORMS.items():
            # Check domain match
            for base_domain in platform_info.base_domains:
                if domain == base_domain or domain.endswith('.' + base_domain):
                    # Verify with URL patterns
                    for pattern in platform_info.url_patterns:
                        if re.search(pattern, url, re.IGNORECASE):
                            return platform_name
                    
                    # If domain matches but no specific pattern, still return platform
                    return platform_name
        
        return None
        
    except Exception as e:
        logger.error(f"Platform detection error for '{url}': {e}")
        return None

def get_platform_info(platform_name: str) -> Optional[PlatformInfo]:
    """
    Get detailed information about a platform
    
    Args:
        platform_name: Name of the platform
        
    Returns:
        PlatformInfo or None: Platform information if found
    """
    return SUPPORTED_PLATFORMS.get(platform_name.lower())

def extract_video_id(url: str, platform: str) -> Optional[str]:
    """
    Extract video ID from URL for a specific platform
    
    Args:
        url: Video URL
        platform: Platform name
        
    Returns:
        str or None: Video ID if found
    """
    try:
        platform_info = get_platform_info(platform)
        if not platform_info:
            return None
        
        for pattern in platform_info.url_patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                # Return the first captured group (video ID)
                return match.group(1) if match.groups() else None
        
        return None
        
    except Exception as e:
        logger.error(f"Video ID extraction error for '{url}': {e}")
        return None

def normalize_url(url: str) -> str:
    """
    Normalize URL for consistent processing
    
    Args:
        url: URL to normalize
        
    Returns:
        str: Normalized URL
    """
    try:
        if not url:
            return url
        
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url.lstrip('/')
        
        # Parse and reconstruct
        parsed = urlparse(url)
        
        # Normalize domain
        domain = parsed.netloc.lower()
        
        # Remove unnecessary www prefix for some platforms
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Reconstruct URL
        normalized = f"{parsed.scheme}://{domain}{parsed.path}"
        
        if parsed.query:
            normalized += f"?{parsed.query}"
        
        if parsed.fragment:
            normalized += f"#{parsed.fragment}"
        
        return normalized
        
    except Exception as e:
        logger.error(f"URL normalization error for '{url}': {e}")
        return url

def is_playlist_url(url: str, platform: str) -> bool:
    """
    Check if URL is a playlist URL
    
    Args:
        url: URL to check
        platform: Platform name
        
    Returns:
        bool: True if playlist URL
    """
    try:
        platform_info = get_platform_info(platform)
        if not platform_info or not platform_info.supports_playlists:
            return False
        
        # Platform-specific playlist detection
        if platform == 'youtube':
            return 'list=' in url or '/playlist' in url
        elif platform == 'dailymotion':
            return '/playlist/' in url
        
        return False
        
    except Exception as e:
        logger.error(f"Playlist detection error for '{url}': {e}")
        return False

def validate_platform_support(platform: str) -> bool:
    """
    Check if platform is supported
    
    Args:
        platform: Platform name to check
        
    Returns:
        bool: True if supported
    """
    return platform.lower() in SUPPORTED_PLATFORMS

def get_supported_platforms() -> List[Dict[str, Any]]:
    """
    Get list of all supported platforms with their information
    
    Returns:
        List of platform dictionaries
    """
    return [
        {
            'name': info.name,
            'display_name': info.display_name,
            'base_domains': info.base_domains,
            'supports_playlists': info.supports_playlists,
            'requires_cookies': info.requires_cookies
        }
        for info in SUPPORTED_PLATFORMS.values()
    ]

def extract_url_from_text(text: str) -> Optional[str]:
    """
    Extract URL from text message
    
    Args:
        text: Text that may contain URL
        
    Returns:
        str or None: Extracted URL if found
    """
    try:
        # URL regex pattern
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        
        matches = re.findall(url_pattern, text)
        if matches:
            return matches[0]  # Return first URL found
        
        # Try to detect URLs without protocol
        domain_pattern = r'(?:www\.)?[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]*\.(?:com|org|net|edu|gov|mil|int|co|io|ly|be|me|tv)'
        
        matches = re.findall(domain_pattern, text)
        if matches:
            url = matches[0]
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            return url
        
        return None
        
    except Exception as e:
        logger.error(f"URL extraction error from text: {e}")
        return None

def validate_file_size_limit(file_size: int, max_size: int = 2 * 1024 * 1024 * 1024) -> bool:
    """
    Validate if file size is within limits
    
    Args:
        file_size: File size in bytes
        max_size: Maximum allowed size in bytes (default 2GB)
        
    Returns:
        bool: True if within limits
    """
    return 0 < file_size <= max_size

def is_live_stream_url(url: str, platform: str) -> bool:
    """
    Check if URL is for a live stream
    
    Args:
        url: URL to check
        platform: Platform name
        
    Returns:
        bool: True if live stream URL
    """
    try:
        # Platform-specific live stream detection
        if platform == 'youtube':
            return '/watch' in url and 'live' in url.lower()
        elif platform == 'twitch':
            # Twitch channel URLs (not clips/videos) are typically live
            return re.search(r'twitch\.tv/([^/]+)/?$', url) is not None
        elif platform == 'facebook':
            return 'live' in url.lower()
        
        return False
        
    except Exception as e:
        logger.error(f"Live stream detection error for '{url}': {e}")
        return False

def sanitize_url(url: str) -> str:
    """
    Sanitize URL for safe processing
    
    Args:
        url: URL to sanitize
        
    Returns:
        str: Sanitized URL
    """
    try:
        if not url:
            return ""
        
        # Remove dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '`', '\n', '\r', '\t']
        for char in dangerous_chars:
            url = url.replace(char, '')
        
        # Limit length
        if len(url) > 2048:  # Standard URL length limit
            url = url[:2048]
        
        return url.strip()
        
    except Exception as e:
        logger.error(f"URL sanitization error: {e}")
        return ""

def get_platform_limitations(platform: str) -> Dict[str, Any]:
    """
    Get platform-specific limitations and capabilities
    
    Args:
        platform: Platform name
        
    Returns:
        dict: Platform limitations and capabilities
    """
    limitations = {
        'youtube': {
            'max_quality': '4K',
            'audio_extraction': True,
            'playlist_support': True,
            'live_stream_support': False,
            'age_restricted_content': False,
            'private_content': False
        },
        'tiktok': {
            'max_quality': '1080p',
            'audio_extraction': True,
            'playlist_support': False,
            'live_stream_support': False,
            'age_restricted_content': True,
            'private_content': False
        },
        'instagram': {
            'max_quality': '1080p',
            'audio_extraction': True,
            'playlist_support': False,
            'live_stream_support': False,
            'age_restricted_content': False,
            'private_content': True
        },
        'facebook': {
            'max_quality': '1080p',
            'audio_extraction': True,
            'playlist_support': False,
            'live_stream_support': False,
            'age_restricted_content': False,
            'private_content': True
        },
        'twitter': {
            'max_quality': '1080p',
            'audio_extraction': True,
            'playlist_support': False,
            'live_stream_support': False,
            'age_restricted_content': False,
            'private_content': True
        }
    }
    
    return limitations.get(platform, {
        'max_quality': '1080p',
        'audio_extraction': True,
        'playlist_support': False,
        'live_stream_support': False,
        'age_restricted_content': False,
        'private_content': False
    })
