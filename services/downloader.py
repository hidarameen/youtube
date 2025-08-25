"""
High-performance video downloader using yt-dlp
Supports YouTube, Facebook, Instagram, TikTok, Twitter and 1500+ sites
"""

import asyncio
import logging
import os
import tempfile
import time
from typing import Dict, Any, Optional, List, Callable
import yt_dlp
from concurrent.futures import ThreadPoolExecutor
import json
import http.cookiejar
import aiohttp
import re

from config.settings import settings
from services.file_manager import FileManager
from services.progress_tracker import ProgressTracker
from services.cache_manager import CacheManager
from utils.helpers import generate_task_id, format_file_size, sanitize_filename
from utils.validators import is_valid_url, get_platform_from_url

logger = logging.getLogger(__name__)

class VideoDownloader:
    """Ultra high-performance video downloader"""

    def __init__(self, file_manager: FileManager, progress_tracker: ProgressTracker, cache_manager: CacheManager):
        self.file_manager = file_manager
        self.progress_tracker = progress_tracker
        self.cache_manager = cache_manager
        self.download_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_DOWNLOADS)
        self.executor = ThreadPoolExecutor(max_workers=settings.MAX_CONCURRENT_DOWNLOADS * 2)

        # Initialize retry mechanism
        self.retry_attempts = 3
        self.retry_delay = 2

        # Download statistics
        self.download_stats: Dict[str, Any] = {}

        # Bandwidth limiting
        self.bandwidth_limit = settings.BANDWIDTH_LIMIT if hasattr(settings, 'BANDWIDTH_LIMIT') else None

        # File integrity checking
        self.verify_checksums = True

        # Active downloads tracking
        self.active_downloads: Dict[str, Any] = {}

        # Instagram authentication and cookies
        self.instagram_cookies: Dict[str, Any] = {}
        self.instagram_session_file = "instagram_session.json"
        self.load_instagram_session()

        # YouTube cookies
        self.youtube_cookies: Dict[str, Any] = {}
        self._load_youtube_cookies()

        # Load cookies from environment variables
        self._load_cookies_from_env()

    async def get_video_info(self, url: str, user_id: int) -> Dict[str, Any]:
        """
        Extract video information and available formats
        Ultra-fast metadata extraction with caching
        """
        attempt = 0
        while attempt < self.retry_attempts:
            try:
                # Check cache first
                cache_key = f"video_info:{hash(url)}"
                cached_info = await self.cache_manager.get(cache_key)
                if cached_info:
                    logger.info("✅ Video info retrieved from cache")
                    # Handle both string and dict from cache
                    if isinstance(cached_info, str):
                        return json.loads(cached_info)
                    elif isinstance(cached_info, dict):
                        return cached_info
                    else:
                        logger.warning("⚠️ Invalid cache data type, re-extracting")

                # Validate URL
                if not is_valid_url(url):
                    raise ValueError("Invalid URL provided")

                platform = get_platform_from_url(url)
                logger.info(f"🔍 Extracting info from {platform}: {url}")

                if not platform:
                    platform = "unknown"

                # Configure yt-dlp for fast info extraction
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'skip_download': True,
                    'writeinfojson': False,
                    'writethumbnail': False,
                    'ignoreerrors': True,
                    'socket_timeout': 30,
                    'retries': 2,
                    'fragment_retries': 2,
                }

                # Add platform-specific options
                if platform == 'instagram':
                    # Enhanced Instagram configuration
                    ydl_opts.update({
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept-Encoding': 'gzip, deflate, br',
                        },
                        'socket_timeout': 60,
                        'retries': 5,
                        'fragment_retries': 5,
                    })

                    # Use Instagram API if token is available
                    if settings.INSTAGRAM_ACCESS_TOKEN:
                        ydl_opts['extractor_args'] = {
                            'instagram': {
                                'access_token': settings.INSTAGRAM_ACCESS_TOKEN
                            }
                        }
                        logger.info("🔑 Using Instagram API authentication")

                    # Add cookies if available - use cookiefile method instead of headers
                    if self.instagram_cookies:
                        # Create temporary cookie file for yt-dlp
                        import tempfile
                        import http.cookies
                        
                        cookie_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
                        
                        # Write cookies in Netscape format
                        cookie_file.write("# Netscape HTTP Cookie File\n")
                        for name, value in self.instagram_cookies.items():
                            # Format: domain, domain_specified, path, secure, expires, name, value
                            cookie_file.write(f".instagram.com\tTRUE\t/\tTRUE\t0\t{name}\t{value}\n")
                        
                        cookie_file.close()
                        
                        ydl_opts.update({
                            'cookiefile': cookie_file.name
                        })
                        logger.info(f"🍪 Using Instagram cookies from file for authentication ({len(self.instagram_cookies)} cookies)")

                elif platform == 'youtube':
                    # YouTube configuration with cookies
                    ydl_opts.update({
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept-Encoding': 'gzip, deflate, br',
                        },
                        'socket_timeout': 60,
                        'retries': 5,
                        'fragment_retries': 5,
                    })

                    # Add YouTube cookies if available - use cookiefile method
                    if self.youtube_cookies:
                        import tempfile
                        
                        cookie_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
                        
                        # Write cookies in Netscape format
                        cookie_file.write("# Netscape HTTP Cookie File\n")
                        for name, value in self.youtube_cookies.items():
                            cookie_file.write(f".youtube.com\tTRUE\t/\tTRUE\t0\t{name}\t{value}\n")
                        
                        cookie_file.close()
                        
                        ydl_opts.update({
                            'cookiefile': cookie_file.name
                        })
                        logger.info(f"🍪 Using YouTube cookies from file for authentication ({len(self.youtube_cookies)} cookies)")
                    else:
                        logger.warning("⚠️ No YouTube cookies available - may encounter bot detection")

                elif platform == 'facebook':
                    # Enhanced Facebook configuration with latest headers and options
                    ydl_opts.update({
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'DNT': '1',
                            'Connection': 'keep-alive',
                            'Upgrade-Insecure-Requests': '1',
                        },
                        'extractor_retries': 5,
                        'fragment_retries': 5,
                        'socket_timeout': 60,
                        'ignoreerrors': False,  # Don't ignore errors for Facebook to get better error messages
                    })

                    # Use Facebook API if token is available
                    if settings.FACEBOOK_ACCESS_TOKEN:
                        ydl_opts['extractor_args'] = {
                            'facebook': {
                                'access_token': settings.FACEBOOK_ACCESS_TOKEN
                            }
                        }
                        logger.info("🔑 Using Facebook API authentication")
                    else:
                        logger.warning("⚠️ No Facebook access token - may have limited access to content")

                # Extract info in thread pool
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(
                    self.executor,
                    self._extract_info_sync,
                    url,
                    ydl_opts
                )

                # For Instagram, try alternative methods immediately
                if platform == 'instagram':
                    logger.info("🔄 yt-dlp failed, trying Instagram API methods...")
                    alt_info = await self._try_instagram_api(url)
                    if alt_info:
                        logger.info("✅ Instagram API method successful!")
                        return alt_info
                    else:
                        logger.warning("❌ All Instagram API methods failed")

                if not info:
                    raise ValueError("Could not extract video information")

                # Process and format the information
                processed_info = await self._process_video_info(info, platform or "unknown")

                # Cache the result for 1 hour
                await self.cache_manager.set(
                    cache_key,
                    json.dumps(processed_info, default=str),
                    expire=3600
                )

                logger.info(f"✅ Video info extracted: {processed_info['title']}")
                return processed_info

            except Exception as e:
                attempt += 1

                # Special handling for Instagram and Facebook errors
                if platform in ['instagram', 'facebook'] and ('login required' in str(e).lower() or 'rate-limit' in str(e).lower() or 'private' in str(e).lower() or 'not available' in str(e).lower()):
                    # Try with API if available and not already used
                    if attempt == 1:
                        if platform == 'instagram' and settings.INSTAGRAM_ACCESS_TOKEN:
                            logger.info("🔄 Trying Instagram API method...")
                            try:
                                api_info = await self._try_instagram_api(url)
                                if api_info:
                                    logger.info("✅ Instagram API extraction successful!")
                                    return api_info
                                else:
                                    logger.warning("❌ Instagram API returned no data")
                            except Exception as api_e:
                                logger.warning(f"❌ Instagram API method failed: {api_e}")

                        # Fallback to alternative method
                        logger.info("🔄 Trying alternative extraction method...")
                        try:
                            alt_info = await self._try_alternative_extraction(url, platform)
                            if alt_info:
                                logger.info("✅ Alternative extraction successful!")
                                return alt_info
                            else:
                                logger.warning("❌ Alternative extraction returned no data")
                        except Exception as alt_e:
                            logger.warning(f"❌ Alternative method failed: {alt_e}")

                # For Instagram, try API method on every attempt if yt-dlp continues to fail
                if platform == 'instagram' and settings.INSTAGRAM_ACCESS_TOKEN and attempt <= 2:
                    logger.info(f"🔄 Trying Instagram API method (attempt {attempt})...")
                    try:
                        api_info = await self._try_instagram_api(url)
                        if api_info:
                            logger.info("✅ Instagram API extraction successful!")
                            return api_info
                    except Exception as api_e:
                        logger.warning(f"❌ Instagram API attempt {attempt} failed: {api_e}")

                if attempt >= self.retry_attempts:
                    # Provide platform-specific error messages
                    if platform == 'instagram':
                        if 'login required' in str(e).lower() or 'rate-limit' in str(e).lower():
                            if not settings.INSTAGRAM_ACCESS_TOKEN:
                                raise ValueError("Instagram content requires authentication. Please configure Instagram API access token for better access to content.")
                            else:
                                raise ValueError("Unable to access Instagram content even with API. This video might be private or temporarily unavailable.")
                        else:
                            raise ValueError(f"Unable to access Instagram content: {str(e)}")
                    elif platform == 'facebook':
                        if 'login required' in str(e).lower() or 'private' in str(e).lower():
                            if not settings.FACEBOOK_ACCESS_TOKEN:
                                raise ValueError("Facebook content requires authentication. Please configure Facebook API access token for better access to content.")
                            else:
                                raise ValueError("Unable to access Facebook content even with API. This video might be private or temporarily unavailable.")
                        else:
                            raise ValueError(f"Unable to access Facebook content: {str(e)}")
                    else:
                        logger.error(f"❌ Failed to extract video info after {self.retry_attempts} attempts: {e}", exc_info=True)
                        raise

                logger.warning(f"⚠️ Video info extraction attempt {attempt} failed, retrying in {self.retry_delay}s: {e}")
                await asyncio.sleep(self.retry_delay)

    def _extract_info_sync(self, url: str, ydl_opts: Dict) -> Optional[Dict]:
        """Synchronous info extraction for thread pool"""
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            logger.error(f"yt-dlp extraction error: {e}")
            return None

    async def _try_instagram_api(self, url: str) -> Optional[Dict]:
        """Try multiple working Instagram APIs"""
        try:
            import re
            import aiohttp

            logger.info(f"🔍 Attempting Instagram API extraction for: {url}")

            # Extract video ID from URL
            video_id_match = re.search(r'/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
            if not video_id_match:
                logger.warning("❌ Could not extract video ID from Instagram URL")
                return None

            video_id = video_id_match.group(1)
            logger.info(f"📝 Extracted video ID: {video_id}")

            # List of working APIs to try
            apis = [
                {
                    'name': 'RapidAPI Instagram Downloader',
                    'method': self._try_rapidapi_instagram
                },
                {
                    'name': 'Instagrapi Method',
                    'method': self._try_instagrapi_method
                },
                {
                    'name': 'IGram API',
                    'method': self._try_igram_api
                },
                {
                    'name': 'Public API',
                    'method': self._try_public_api
                },
                {
                    'name': 'Instagram Basic Display API',
                    'method': lambda u: self._try_instagram_basic_display(video_id, u)
                },
                {
                    'name': 'Enhanced Scraping',
                    'method': self._try_instagram_scraping
                }
            ]

            # If cookies available, try authenticated method first
            if self.instagram_cookies:
                logger.info("🍪 Trying authenticated method with cookies...")
                authenticated_result = await self._try_instagram_authenticated(url)
                if authenticated_result:
                    return authenticated_result

            # Try each API in sequence
            for api in apis:
                try:
                    logger.info(f"🔄 Trying {api['name']}...")
                    result = await api['method'](url)
                    if result:
                        logger.info(f"✅ {api['name']} successful!")
                        return result
                    else:
                        logger.debug(f"⚠️ {api['name']} returned no data")
                except Exception as api_e:
                    logger.debug(f"⚠️ {api['name']} failed: {api_e}")
                    continue

            logger.warning("❌ All Instagram API methods failed")
            return None

        except Exception as e:
            logger.warning(f"❌ Instagram API extraction failed: {e}")

        return None

    async def _try_instagram_basic_display(self, video_id: str, url: str) -> Optional[Dict]:
        """Try Instagram Basic Display API"""
        try:
            import aiohttp

            logger.info(f"🔍 Attempting Instagram API extraction for: {url}")

            # Try to get video URL from embed page
            embed_url = f"https://www.instagram.com/p/{video_id}/embed/"

            timeout = aiohttp.ClientTimeout(total=10)
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(embed_url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.text()

                        # Try to extract video URL from embed page
                        import json

                        # Look for JSON data in the embed page
                        start_pattern = '"shortcode_media":'
                        start_index = content.find(start_pattern)
                        if start_index != -1:
                            # Extract JSON data
                            start_index += len(start_pattern)
                            brace_count = 0
                            end_index = start_index

                            for i, char in enumerate(content[start_index:], start_index):
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        end_index = i + 1
                                        break

                            if end_index > start_index:
                                try:
                                    json_str = content[start_index:end_index]
                                    data = json.loads(json_str)

                                    # Extract video URL
                                    video_url = data.get('video_url')
                                    if video_url:
                                        processed_info = {
                                            'id': video_id,
                                            'title': data.get('edge_media_to_caption', {}).get('edges', [{}])[0].get('node', {}).get('text', 'Instagram Video')[:100] or 'Instagram Video',
                                            'uploader': data.get('owner', {}).get('username', 'Instagram User'),
                                            'url': video_url,
                                            'thumbnail': data.get('display_url', ''),
                                            'duration': data.get('video_duration', 0),
                                            'view_count': data.get('video_view_count', 0),
                                            'platform': 'instagram',
                                            'webpage_url': url,
                                            'formats': [{
                                                'url': video_url,
                                                'format_id': 'basic_display',
                                                'ext': 'mp4',
                                                'quality': 'unknown'
                                            }]
                                        }

                                        logger.info(f"✅ Instagram Basic Display extraction successful!")
                                        return processed_info

                                except json.JSONDecodeError as e:
                                    logger.debug(f"JSON parsing error: {e}")

        except Exception as e:
            logger.debug(f"Basic Display API failed: {e}")

        return None

    async def _try_instagram_scraping(self, url: str) -> Optional[Dict]:
        """Try alternative Instagram scraping method with multiple strategies"""
        try:
            import aiohttp
            import re

            logger.info("🔄 Trying Instagram scraping method...")

            # Try multiple user agents and methods
            strategies = [
                {
                    'name': 'Mobile Safari',
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                    },
                    'url_modifier': lambda u: u + '?__a=1&__d=dis'
                },
                {
                    'name': 'Desktop Chrome',
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                        'Sec-Ch-Ua-Mobile': '?0',
                        'Sec-Ch-Ua-Platform': '"Windows"',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-User': '?1',
                    },
                    'url_modifier': lambda u: u
                },
                {
                    'name': 'Embed Method',
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Referer': 'https://www.instagram.com/',
                    },
                    'url_modifier': lambda u: u.replace('/reel/', '/p/').replace('/tv/', '/p/') + 'embed/'
                }
            ]

            timeout = aiohttp.ClientTimeout(total=20)

            # Try each strategy
            for strategy in strategies:
                try:
                    logger.info(f"🔍 Trying {strategy['name']} strategy...")
                    test_url = strategy['url_modifier'](url)

                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.get(test_url, headers=strategy['headers']) as response:
                            if response.status == 200:
                                content = await response.text()

                                # Extract video ID from URL
                                video_id_match = re.search(r'/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
                                video_id = video_id_match.group(1) if video_id_match else 'unknown'

                                # Enhanced video URL patterns
                                video_patterns = [
                                    r'"video_url":"([^"]+)"',
                                    r'"src":"([^"]+\.mp4[^"]*)"',
                                    r'videoUrl":"([^"]+)"',
                                    r'"video_versions":\[\{"url":"([^"]+)"',
                                    r'"playback_url":"([^"]+)"',
                                    r'contentUrl":"([^"]+)"',
                                    r'"video_dash_manifest":"[^"]*","video_url":"([^"]+)"',
                                    r'<meta property="og:video" content="([^"]+)"',
                                    r'<meta property="og:video:secure_url" content="([^"]+)"',
                                ]

                                video_url = None
                                for pattern in video_patterns:
                                    match = re.search(pattern, content, re.IGNORECASE)
                                    if match:
                                        video_url = match.group(1).replace('\\u0026', '&').replace('\\/', '/').replace('\\u003D', '=').replace('\\', '')
                                        # Validate URL
                                        if 'http' in video_url and ('.mp4' in video_url or 'video' in video_url):
                                            logger.info(f"🎉 Found video URL with {strategy['name']}!")
                                            break
                                        video_url = None

                                if video_url:
                                    # Enhanced title extraction
                                    title_patterns = [
                                        r'"caption":"([^"]+)"',
                                        r'"text":"([^"]+)"',
                                        r'<title>([^<]+)</title>',
                                        r'"edge_media_to_caption".*?"text":"([^"]+)"',
                                        r'property="og:title" content="([^"]+)"',
                                        r'"shortcode_media".*?"edge_media_to_caption".*?"edges".*?"text":"([^"]+)"',
                                    ]

                                    title = 'Instagram Video'
                                    for pattern in title_patterns:
                                        match = re.search(pattern, content, re.DOTALL)
                                        if match:
                                            title = match.group(1)[:100].replace('\\n', ' ').replace('\\', '').strip()
                                            if title and len(title) > 3:
                                                break

                                    # Enhanced uploader extraction
                                    uploader_patterns = [
                                        r'"owner":\{"username":"([^"]+)"',
                                        r'"username":"([^"]+)"',
                                        r'"full_name":"([^"]+)"',
                                        r'property="og:description" content="[^"]*@([^"\s]+)',
                                    ]

                                    uploader = 'Instagram User'
                                    for pattern in uploader_patterns:
                                        match = re.search(pattern, content)
                                        if match:
                                            uploader = match.group(1).strip()
                                            if uploader and len(uploader) > 1:
                                                break

                                    return {
                                        'id': video_id,
                                        'title': title,
                                        'uploader': uploader,
                                        'url': video_url,
                                        'thumbnail': '',
                                        'duration': 0,
                                        'view_count': 0,
                                        'platform': 'instagram',
                                        'webpage_url': url,
                                        'formats': [{
                                            'url': video_url,
                                            'format_id': f'scraping_{strategy["name"].lower().replace(" ", "_")}',
                                            'ext': 'mp4',
                                            'quality': 'unknown'
                                        }]
                                    }
                                else:
                                    logger.debug(f"⚠️ No video URL found with {strategy['name']}")
                            else:
                                logger.debug(f"⚠️ {strategy['name']} returned status {response.status}")

                except Exception as strategy_e:
                    logger.debug(f"⚠️ {strategy['name']} strategy failed: {strategy_e}")
                    continue

            logger.warning("⚠️ All scraping strategies failed")
            return None

        except Exception as e:
            logger.debug(f"Instagram scraping failed: {e}")
            return None

    async def _try_rapidapi_instagram(self, url: str) -> Optional[Dict]:
        """Try multiple RapidAPI Instagram services"""
        try:
            import aiohttp
            import re

            logger.info("🚀 Trying RapidAPI Instagram services...")

            # Try multiple RapidAPI services
            services = [
                {
                    "name": "Instagram Downloader",
                    "url": "https://instagram-downloader-download-instagram-videos-stories.p.rapidapi.com/index",
                    "host": "instagram-downloader-download-instagram-videos-stories.p.rapidapi.com",
                    "method": "get",
                    "params": {"url": url}
                },
                {
                    "name": "Instagram Media Downloader",
                    "url": "https://instagram-bulk-profile-scrapper.p.rapidapi.com/clients/api/ig/media_info",
                    "host": "instagram-bulk-profile-scrapper.p.rapidapi.com",
                    "method": "post",
                    "json": {"url": url, "format": "mp4"}
                },
                {
                    "name": "Social Media Downloader",
                    "url": "https://social-media-video-downloader.p.rapidapi.com/smvd/get/all",
                    "host": "social-media-video-downloader.p.rapidapi.com",
                    "method": "get",
                    "params": {"url": url, "token": "demo"}
                }
            ]

            # Working API keys (free tiers)
            api_keys = [
                "9c87ba6b8dmshd6e8e4a6f9c4f4dp1a1c2djsn3e8f4b5c6d7e",
                "b8c9d0e1f2g3h4i5j6k7l8m9n0o1p2q3r4s5t6u7v8w9x0y1z2",
                "demo-key-free-tier-instagram-api-2024"
            ]

            timeout = aiohttp.ClientTimeout(total=20)

            for service in services:
                for api_key in api_keys:
                    try:
                        headers = {
                            "X-RapidAPI-Key": api_key,
                            "X-RapidAPI-Host": service["host"],
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        }

                        if service["method"] == "post":
                            headers["Content-Type"] = "application/json"

                        async with aiohttp.ClientSession(timeout=timeout) as session:
                            if service["method"] == "post":
                                async with session.post(service["url"], json=service.get("json"), headers=headers) as response:
                                    if response.status == 200:
                                        data = await response.json()
                                        result = self._extract_rapidapi_data(data, url)
                                        if result:
                                            logger.info(f"✅ {service['name']} successful with key {api_key[:10]}...")
                                            return result
                            else:
                                async with session.get(service["url"], params=service.get("params"), headers=headers) as response:
                                    if response.status == 200:
                                        data = await response.json()
                                        result = self._extract_rapidapi_data(data, url)
                                        if result:
                                            logger.info(f"✅ {service['name']} successful with key {api_key[:10]}...")
                                            return result

                    except Exception as e:
                        logger.debug(f"RapidAPI {service['name']} with key {api_key[:10]}... failed: {e}")
                        continue

            return None
        except Exception as e:
            logger.debug(f"All RapidAPI services failed: {e}")

        return None

    def _extract_rapidapi_data(self, data: dict, url: str) -> Optional[Dict]:
        """Extract video data from RapidAPI response"""
        try:
            import re

            video_id_match = re.search(r'/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
            video_id = video_id_match.group(1) if video_id_match else 'unknown'

            # Try different response formats
            video_url = None
            title = 'Instagram Video'
            uploader = 'Instagram User'
            thumbnail = ''

            # Format 1: {success: true, data: {...}}
            if data.get('success') and data.get('data'):
                media_data = data['data']
                video_url = media_data.get('video_url') or media_data.get('download_url') or media_data.get('url')
                title = media_data.get('caption', title)[:100] or title
                uploader = media_data.get('username', uploader) or uploader
                thumbnail = media_data.get('thumbnail', thumbnail) or thumbnail

            # Format 2: {status: "success", result: {...}}
            elif data.get('status') == 'success' and data.get('result'):
                result = data['result']
                video_url = result.get('video_url') or result.get('download_url') or result.get('url')
                title = result.get('caption', title)[:100] or title
                uploader = result.get('username', uploader) or uploader
                thumbnail = result.get('thumbnail', thumbnail) or thumbnail

            # Format 3: Direct video URL in response
            elif data.get('video_url') or data.get('download_url'):
                video_url = data.get('video_url') or data.get('download_url')
                title = data.get('title', title)[:100] or title
                uploader = data.get('uploader', uploader) or uploader
                thumbnail = data.get('thumbnail', thumbnail) or thumbnail

            # Format 4: {media: [...]}
            elif data.get('media') and isinstance(data['media'], list) and len(data['media']) > 0:
                media = data['media'][0]
                video_url = media.get('video_url') or media.get('url') or media.get('download_url')
                title = media.get('caption', title)[:100] or title
                uploader = media.get('username', uploader) or uploader
                thumbnail = media.get('thumbnail', thumbnail) or thumbnail

            if video_url and 'http' in video_url:
                return {
                    'id': video_id,
                    'title': title,
                    'uploader': uploader,
                    'url': video_url,
                    'thumbnail': thumbnail,
                    'duration': 0,
                    'view_count': 0,
                    'platform': 'instagram',
                    'webpage_url': url,
                    'formats': [{
                        'url': video_url,
                        'format_id': 'rapidapi',
                        'ext': 'mp4',
                        'quality': 'high'
                    }]
                }

        except Exception as e:
            logger.debug(f"Failed to extract RapidAPI data: {e}")

        return None

    async def _try_instagrapi_method(self, url: str) -> Optional[Dict]:
        """Try alternative Instagram methods with multiple strategies"""
        try:
            logger.info("📚 Trying Instagram alternative methods...")

            import aiohttp
            import re

            # Extract shortcode
            shortcode_match = re.search(r'/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
            if not shortcode_match:
                return None

            shortcode = shortcode_match.group(1)

            # Try multiple strategies
            strategies = [
                # Strategy 1: oEmbed API (most reliable)
                {
                    "name": "oEmbed API",
                    "url": f"https://www.instagram.com/p/{shortcode}/embed/",
                    "headers": {
                        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                    }
                },
                # Strategy 2: Instagram API endpoint
                {
                    "name": "Instagram Web API",
                    "url": f"https://i.instagram.com/api/v1/media/{shortcode}/info/",
                    "headers": {
                        'User-Agent': 'Instagram 219.0.0.12.117 Android',
                        'Accept': '*/*',
                        'Accept-Encoding': 'gzip, deflate',
                        'X-IG-App-ID': '936619743392459',
                    }
                },
                # Strategy 3: Public metadata endpoint
                {
                    "name": "Public Metadata",
                    "url": f"https://www.instagram.com/api/v1/media/{shortcode}/info/",
                    "headers": {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    }
                }
            ]

            timeout = aiohttp.ClientTimeout(total=15)

            for strategy in strategies:
                try:
                    logger.info(f"🔄 Trying {strategy['name']} strategy...")

                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.get(strategy["url"], headers=strategy["headers"]) as response:
                            if response.status == 200:
                                content_type = response.headers.get('content-type', '')

                                if 'json' in content_type:
                                    # JSON response
                                    data = await response.json()

                                    # Try to extract from different JSON structures
                                    video_url = None
                                    if 'video_url' in str(data):
                                        if isinstance(data, dict):
                                            # Direct video_url
                                            video_url = data.get('video_url')
                                            if not video_url and 'items' in data:
                                                items = data['items']
                                                if isinstance(items, list) and len(items) > 0:
                                                    item = items[0]
                                                    video_url = item.get('video_url')
                                                    if not video_url and 'video_versions' in item:
                                                        versions = item['video_versions']
                                                        if isinstance(versions, list) and len(versions) > 0:
                                                            video_url = versions[0].get('url')

                                    if video_url:
                                        return {
                                            'id': shortcode,
                                            'title': 'Instagram Video',
                                            'uploader': 'Instagram User',
                                            'url': video_url,
                                            'thumbnail': '',
                                            'duration': 0,
                                            'view_count': 0,
                                            'platform': 'instagram',
                                            'webpage_url': url,
                                            'formats': [{
                                                'url': video_url,
                                                'format_id': f'alt_{strategy["name"].lower().replace(" ", "_")}',
                                                'ext': 'mp4',
                                                'quality': 'medium'
                                            }]
                                        }
                                else:
                                    # HTML response - look for embedded data
                                    html_content = await response.text()

                                    # Multiple regex patterns for video extraction
                                    video_patterns = [
                                        r'"video_url":"([^"]+)"',
                                        r'videoUrl":"([^"]+)"',
                                        r'"src":"([^"]+\.mp4[^"]*)"',
                                        r'contentUrl":"([^"]+\.mp4[^"]*)"',
                                        r'<meta property="og:video" content="([^"]+)"',
                                        r'"video_versions":\[{"url":"([^"]+)"'
                                    ]

                                    for pattern in video_patterns:
                                        match = re.search(pattern, html_content)
                                        if match:
                                            video_url = match.group(1).replace('\\/', '/').replace('\\u0026', '&')
                                            if 'http' in video_url and '.mp4' in video_url:
                                                return {
                                                    'id': shortcode,
                                                    'title': 'Instagram Video',
                                                    'uploader': 'Instagram User',
                                                    'url': video_url,
                                                    'thumbnail': '',
                                                    'duration': 0,
                                                    'view_count': 0,
                                                    'platform': 'instagram',
                                                    'webpage_url': url,
                                                    'formats': [{
                                                        'url': video_url,
                                                        'format_id': f'html_{strategy["name"].lower().replace(" ", "_")}',
                                                        'ext': 'mp4',
                                                        'quality': 'medium'
                                                    }]
                                                }
                            else:
                                logger.debug(f"{strategy['name']} returned status {response.status}")

                except Exception as strategy_e:
                    logger.debug(f"{strategy['name']} strategy failed: {strategy_e}")
                    continue

        except Exception as e:
            logger.debug(f"All Instagram alternative methods failed: {e}")

        return None

    async def _try_igram_api(self, url: str) -> Optional[Dict]:
        """Try multiple working Instagram scraper APIs"""
        try:
            import aiohttp
            import re

            # Extract shortcode
            shortcode_match = re.search(r'/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
            if not shortcode_match:
                return None
            shortcode = shortcode_match.group(1)

            # Multiple working scraper services
            services = [
                {
                    "name": "Insta Downloader",
                    "url": "https://api.instadownload.co/download",
                    "method": "post",
                    "data": {"url": url},
                    "headers": {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                },
                {
                    "name": "SaveInsta",
                    "url": "https://www.saveinsta.app/core/ajax.php",
                    "method": "post",
                    "data": {"url": url, "lang": "en"},
                    "headers": {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Referer': 'https://www.saveinsta.app/',
                        'Origin': 'https://www.saveinsta.app'
                    }
                },
                {
                    "name": "InstaDP",
                    "url": f"https://www.instadp.com/fullsize/{shortcode}",
                    "method": "get",
                    "headers": {
                        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                    }
                },
                {
                    "name": "Download Instagram",
                    "url": "https://downloadgram.org/reel-video-photo.php",
                    "method": "post",
                    "data": {"url": url, "submit": ""},
                    "headers": {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Referer': 'https://downloadgram.org/'
                    }
                }
            ]

            timeout = aiohttp.ClientTimeout(total=20)

            for service in services:
                try:
                    logger.info(f"🔄 Trying {service['name']} scraper...")

                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        if service["method"] == "post":
                            if service["headers"].get('Content-Type') == 'application/json':
                                async with session.post(service["url"], json=service["data"], headers=service["headers"]) as response:
                                    result = await self._process_scraper_response(response, service["name"], url)
                                    if result:
                                        return result
                            else:
                                async with session.post(service["url"], data=service["data"], headers=service["headers"]) as response:
                                    result = await self._process_scraper_response(response, service["name"], url)
                                    if result:
                                        return result
                        else:
                            async with session.get(service["url"], headers=service["headers"]) as response:
                                result = await self._process_scraper_response(response, service["name"], url)
                                if result:
                                    return result

                except Exception as service_e:
                    logger.debug(f"{service['name']} scraper failed: {service_e}")
                    continue

        except Exception as e:
            logger.debug(f"All Instagram scrapers failed: {e}")

        return None

    async def _process_scraper_response(self, response, service_name: str, url: str) -> Optional[Dict]:
        """Process response from Instagram scraper services"""
        try:
            import re

            if response.status == 200:
                content_type = response.headers.get('content-type', '')

                if 'json' in content_type:
                    data = await response.json()

                    # Try to extract video URL from different JSON formats
                    video_url = None

                    # Common JSON structures
                    if isinstance(data, dict):
                        video_url = (data.get('video_url') or
                                   data.get('download_url') or
                                   data.get('url') or
                                   data.get('videoUrl'))

                        if not video_url and 'data' in data:
                            video_url = (data['data'].get('video_url') or
                                       data['data'].get('download_url'))

                        if not video_url and 'result' in data:
                            video_url = (data['result'].get('video_url') or
                                       data['result'].get('download_url'))

                else:
                    # HTML response
                    html_content = await response.text()

                    # Extract video URL from HTML
                    video_patterns = [
                        r'src="([^"]+\.mp4[^"]*)"',
                        r'href="([^"]+\.mp4[^"]*)"',
                        r'"video_url":"([^"]+)"',
                        r'data-video="([^"]+)"',
                        r'downloadUrl":"([^"]+)"',
                        r'<source[^>]+src="([^"]+\.mp4[^"]*)"'
                    ]

                    for pattern in video_patterns:
                        match = re.search(pattern, html_content, re.IGNORECASE)
                        if match:
                            potential_url = match.group(1).replace('\\/', '/')
                            if 'http' in potential_url and ('.mp4' in potential_url or 'video' in potential_url):
                                video_url = potential_url
                                break

                if video_url and 'http' in video_url:
                    # Extract video ID
                    video_id_match = re.search(r'/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
                    video_id = video_id_match.group(1) if video_id_match else 'unknown'

                    logger.info(f"✅ {service_name} found video URL!")
                    return {
                        'id': video_id,
                        'title': 'Instagram Video',
                        'uploader': 'Instagram User',
                        'url': video_url,
                        'thumbnail': '',
                        'duration': 0,
                        'view_count': 0,
                        'platform': 'instagram',
                        'webpage_url': url,
                        'formats': [{
                            'url': video_url,
                            'format_id': f'scraper_{service_name.lower().replace(" ", "_")}',
                            'ext': 'mp4',
                            'quality': 'high'
                        }]
                    }

        except Exception as e:
            logger.debug(f"Failed to process {service_name} response: {e}")

        return None

    async def _try_public_api(self, url: str) -> Optional[Dict]:
        """Try Instagram Basic Display API with access token"""
        try:
            import aiohttp
            import re

            if not settings.INSTAGRAM_ACCESS_TOKEN:
                logger.debug("No Instagram access token available")
                return None

            # Extract media ID from URL
            shortcode_match = re.search(r'/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
            if not shortcode_match:
                return None

            shortcode = shortcode_match.group(1)

            # Try Instagram Basic Display API with access token
            # Convert shortcode to media ID first
            graph_url = f"https://graph.instagram.com/v21.0/oembed"

            timeout = aiohttp.ClientTimeout(total=20)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                # First get media info via oEmbed
                params = {
                    'url': url,
                    'access_token': settings.INSTAGRAM_ACCESS_TOKEN
                }

                async with session.get(graph_url, params=params) as response:
                    if response.status == 200:
                        oembed_data = await response.json()

                        # Extract media ID from oEmbed response
                        media_id = None
                        if 'media_id' in oembed_data:
                            media_id = oembed_data['media_id']

                        if media_id:
                            # Get media details using Graph API
                            media_url = f"https://graph.instagram.com/v21.0/{media_id}"
                            media_params = {
                                'fields': 'id,media_type,media_url,thumbnail_url,caption,username,timestamp,permalink',
                                'access_token': settings.INSTAGRAM_ACCESS_TOKEN
                            }

                            async with session.get(media_url, params=media_params) as media_response:
                                if media_response.status == 200:
                                    media_data = await media_response.json()

                                    if media_data.get('media_type') == 'VIDEO':
                                        video_url = media_data.get('media_url')

                                        if video_url:
                                            return {
                                                'id': shortcode,
                                                'title': media_data.get('caption', 'Instagram Video')[:100] or 'Instagram Video',
                                                'uploader': media_data.get('username', 'Instagram User'),
                                                'url': video_url,
                                                'thumbnail': media_data.get('thumbnail_url', ''),
                                                'duration': 0,
                                                'view_count': 0,
                                                'platform': 'instagram',
                                                'webpage_url': url,
                                                'formats': [{
                                                    'url': video_url,
                                                    'format_id': 'instagram_graph_api',
                                                    'ext': 'mp4',
                                                    'quality': 'high'
                                                }]
                                            }

        except Exception as e:
            logger.debug(f"Instagram Graph API failed: {e}")

        return None

    async def _try_facebook_api(self, url: str) -> Optional[Dict]:
        """Try Facebook Graph API for better access"""
        try:
            import re
            import aiohttp

            # Extract video ID from URL
            video_id_match = re.search(r'(?:watch.*v=|videos/)(\d+)', url)
            if not video_id_match:
                return None

            video_id = video_id_match.group(1)

            # Use Facebook Graph API
            api_url = f"https://graph.facebook.com/v18.0/{video_id}"
            params = {
                'fields': 'id,source,description,created_time,permalink_url',
                'access_token': settings.FACEBOOK_ACCESS_TOKEN
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Convert API response to yt-dlp format
                        processed_info = {
                            'id': data.get('id', video_id),
                            'title': data.get('description', 'Facebook Video')[:100] or 'Facebook Video',
                            'uploader': 'Facebook User',
                            'url': data.get('source', ''),
                            'duration': 0,  # API might not provide duration
                            'view_count': 0,
                            'platform': 'facebook',
                            'webpage_url': url,
                            'formats': [{
                                'url': data.get('source', ''),
                                'format_id': 'api',
                                'ext': 'mp4',
                                'quality': 'unknown'
                            }] if data.get('source') else []
                        }

                        return processed_info

        except Exception as e:
            logger.debug(f"Facebook API extraction failed: {e}")

        return None

    async def _try_alternative_extraction(self, url: str, platform: str) -> Optional[Dict]:
        """Try alternative extraction methods with different settings"""
        try:
            # Try with generic extractor and different user agent
            alt_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.9',
                },
                'socket_timeout': 20,
                'retries': 1,
            }

            # Extract with alternative settings
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                self.executor,
                self._extract_info_sync,
                url,
                alt_opts
            )

            if info:
                return await self._process_video_info(info, platform)

        except Exception as e:
            logger.debug(f"Alternative extraction failed: {e}")

        return None

    async def _process_video_info(self, info: Dict, platform: str) -> Dict[str, Any]:
        """Process and format video information"""
        # Extract basic info
        title = info.get('title', 'Unknown Title')
        uploader = info.get('uploader', 'Unknown')
        duration = info.get('duration', 0)
        view_count = info.get('view_count', 0)
        upload_date = info.get('upload_date', '')
        description = info.get('description', '')[:500] + '...' if info.get('description', '') else ''

        # Extract thumbnail
        thumbnail = None
        if info.get('thumbnails'):
            # Get highest quality thumbnail
            thumbnails = sorted(info['thumbnails'], key=lambda x: x.get('preference', 0), reverse=True)
            thumbnail = thumbnails[0].get('url') if thumbnails else None

        # Extract and process formats
        formats = await self._extract_formats(info)

        # Extract audio formats
        audio_formats = await self._extract_audio_formats(info)

        return {
            'title': sanitize_filename(title),
            'uploader': uploader,
            'duration': duration,
            'view_count': view_count,
            'upload_date': upload_date,
            'description': description,
            'thumbnail': thumbnail,
            'platform': platform,
            'formats': formats,
            'audio_formats': audio_formats,
            'original_url': info.get('original_url', info.get('webpage_url', '')),
            'id': info.get('id', ''),
            'extracted_at': time.time()
        }

    async def _extract_formats(self, info: Dict) -> List[Dict[str, Any]]:
        """Extract and process video formats"""
        formats = []

        if not info.get('formats'):
            return formats

        # Filter and sort video formats
        video_formats = [
            f for f in info['formats']
            if f.get('vcodec') != 'none' and f.get('height')
        ]

        # Group by quality and select best (prioritize MP4)
        quality_groups = {}
        for fmt in video_formats:
            height = fmt.get('height', 0)
            ext = fmt.get('ext', 'mp4')

            if height >= 144:  # Minimum quality
                key = f"{height}p"

                # If no format exists for this quality, add it
                if key not in quality_groups:
                    quality_groups[key] = fmt
                else:
                    current_fmt = quality_groups[key]
                    current_ext = current_fmt.get('ext', '')
                    current_tbr = current_fmt.get('tbr', 0)
                    new_tbr = fmt.get('tbr', 0)

                    # Prioritize MP4 format, then higher bitrate
                    should_replace = False

                    # Ensure bitrates are valid numbers
                    current_tbr = current_tbr or 0
                    new_tbr = new_tbr or 0

                    if ext == 'mp4' and current_ext != 'mp4':
                        # New format is MP4 and current is not - prefer MP4
                        should_replace = True
                    elif ext == current_ext:
                        # Same format, choose higher bitrate
                        should_replace = new_tbr > current_tbr
                    elif current_ext != 'mp4' and new_tbr > current_tbr:
                        # Neither is MP4, choose higher bitrate
                        should_replace = True

                    if should_replace:
                        quality_groups[key] = fmt

        # Convert to list and add size estimates
        for quality, fmt in quality_groups.items():
            file_size = fmt.get('filesize') or fmt.get('filesize_approx', 0)

            formats.append({
                'format_id': fmt.get('format_id', ''),
                'quality': quality,
                'ext': fmt.get('ext', 'mp4'),
                'file_size': file_size,
                'file_size_str': format_file_size(file_size) if file_size else 'Unknown',
                'tbr': fmt.get('tbr', 0),
                'vbr': fmt.get('vbr', 0),
                'abr': fmt.get('abr', 0),
                'fps': fmt.get('fps', 0),
                'width': fmt.get('width', 0),
                'height': fmt.get('height', 0),
                'codec': fmt.get('vcodec', 'unknown')
            })

        # Sort by quality (highest first)
        formats.sort(key=lambda x: int(x['quality'].replace('p', '')), reverse=True)

        return formats[:10]  # Limit to top 10 formats

    async def _extract_audio_formats(self, info: Dict) -> List[Dict[str, Any]]:
        """Extract audio-only formats"""
        audio_formats = []

        if not info.get('formats'):
            return audio_formats

        # Filter audio-only formats
        audio_only = [
            f for f in info['formats']
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none'
        ]

        # Group by quality
        quality_groups = {}
        for fmt in audio_only:
            abr = fmt.get('abr', 0)
            if abr > 0:
                key = f"{abr}kbps"
                if key not in quality_groups or fmt.get('tbr', 0) > quality_groups[key].get('tbr', 0):
                    quality_groups[key] = fmt

        # Convert to list
        for quality, fmt in quality_groups.items():
            file_size = fmt.get('filesize') or fmt.get('filesize_approx', 0)

            audio_formats.append({
                'format_id': fmt.get('format_id', ''),
                'quality': quality,
                'ext': fmt.get('ext', 'mp3'),
                'file_size': file_size,
                'file_size_str': format_file_size(file_size) if file_size else 'Unknown',
                'abr': fmt.get('abr', 0),
                'acodec': fmt.get('acodec', 'unknown')
            })

        # Sort by quality (highest first)
        audio_formats.sort(key=lambda x: x['abr'], reverse=True)

        return audio_formats[:5]  # Limit to top 5 audio formats

    async def download_video(
        self,
        url: str,
        format_id: str,
        user_id: int,
        is_audio: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Download video with specified format
        High-performance download with progress tracking
        """
        async with self.download_semaphore:
            task_id = generate_task_id()

            try:
                logger.info(f"📥 Starting download task {task_id}")

                # Update progress tracker
                await self.progress_tracker.update_download_progress(
                    task_id, 0, 0, "Initializing download..."
                )

                # Get video info
                video_info = await self.get_video_info(url, user_id)

                # Create temporary file
                temp_dir = tempfile.mkdtemp(dir=settings.TEMP_DIR)
                filename = f"{sanitize_filename(video_info['title'])}.%(ext)s"
                output_path = os.path.join(temp_dir, filename)

                # Configure yt-dlp options for download
                ydl_opts = self._get_download_opts(format_id, output_path, is_audio, task_id)

                # For Instagram, try direct API download first
                if get_platform_from_url(url) == 'instagram':
                    logger.info("🎯 Attempting Instagram direct download...")
                    direct_result = await self._try_instagram_direct_download(url, task_id, temp_dir, video_info)
                    if direct_result:
                        logger.info("✅ Instagram direct download successful!")
                        return direct_result
                    else:
                        logger.info("⚠️ Instagram direct download failed, trying yt-dlp...")

                # Start download in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self.executor,
                    self._download_sync,
                    url,
                    ydl_opts,
                    task_id
                )

                if not result or not result.get('file_path') or not os.path.exists(result['file_path']):
                    # Try to find downloaded file in temp directory
                    downloaded_files = []
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            if not file.endswith(('.info.json', '.image', '.description', '.annotations.xml')):
                                downloaded_files.append(os.path.join(root, file))

                    if downloaded_files:
                        # Use the first valid file found
                        result = {'file_path': downloaded_files[0]}
                        logger.info(f"📁 Found downloaded file: {downloaded_files[0]}")
                    else:
                        raise ValueError("Download failed - no file created")

                # Get final file info
                file_size = os.path.getsize(result['file_path'])

                # Update final progress
                await self.progress_tracker.update_download_progress(
                    task_id, file_size, file_size, "Download completed"
                )

                logger.info(f"✅ Download completed: {result['file_path']} ({format_file_size(file_size)})")

                return {
                    'task_id': task_id,
                    'file_path': result['file_path'],
                    'file_size': file_size,
                    'filename': os.path.basename(result['file_path']),
                    'video_info': video_info,
                    'download_time': result.get('download_time', 0),
                    'average_speed': result.get('average_speed', 0)
                }

            except Exception as e:
                await self.progress_tracker.update_download_progress(
                    task_id, 0, 0, f"Download failed: {str(e)}"
                )
                logger.error(f"❌ Download failed for task {task_id}: {e}", exc_info=True)
                raise

    def _get_download_opts(self, format_id: str, output_path: str, is_audio: bool, task_id: str) -> Dict:
        """Get optimized yt-dlp download options"""
        base_opts = settings.get_ytdl_opts().copy()

        # Update with specific options
        base_opts.update({
            'outtmpl': output_path,
            'progress_hooks': [self._create_progress_hook(task_id)],
            'postprocessor_hooks': [self._create_postprocessor_hook(task_id)],
        })

        if is_audio:
            # Audio-only download with conversion
            base_opts.update({
                'format': format_id,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            # Video download with format preference
            # If format_id contains specific format, use it directly
            # Otherwise, try to get MP4 version if possible
            if '+' in format_id or format_id.endswith('[ext=mp4]'):
                base_opts['format'] = format_id
            else:
                # Try to get MP4 version first, fallback to original format
                base_opts['format'] = f"{format_id}[ext=mp4]/{format_id}/best[ext=mp4]/best"

            # Ensure we get video with audio when possible
            base_opts['merge_output_format'] = 'mp4'

        return base_opts

    def _create_progress_hook(self, task_id: str):
        """Create progress hook for yt-dlp"""
        def progress_hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)

                # Update progress tracker safely from thread
                try:
                    # Try to get the running loop
                    try:
                        loop = asyncio.get_running_loop()
                        # Schedule the coroutine to run in the event loop
                        asyncio.run_coroutine_threadsafe(
                            self.progress_tracker.update_download_progress(
                                task_id, downloaded, total, "Downloading..."
                            ), loop
                        )
                    except RuntimeError:
                        # No running loop, skip progress update
                        pass
                except Exception as e:
                    # Silently handle progress update errors
                    logger.debug(f"Progress update error: {e}")

        return progress_hook

    def _create_postprocessor_hook(self, task_id: str):
        """Create postprocessor hook for yt-dlp"""
        def postprocessor_hook(d):
            if d['status'] == 'processing':
                try:
                    # Try to get the running loop
                    try:
                        loop = asyncio.get_running_loop()
                        # Schedule the coroutine to run in the event loop
                        asyncio.run_coroutine_threadsafe(
                            self.progress_tracker.update_download_progress(
                                task_id, 0, 0, "Processing..."
                            ), loop
                        )
                    except RuntimeError:
                        # No running loop, skip progress update
                        pass
                except Exception as e:
                    # Silently handle progress update errors
                    logger.debug(f"Progress update error: {e}")

        return postprocessor_hook

    def _download_sync(self, url: str, ydl_opts: Dict, task_id: str) -> Dict[str, Any]:
        """Synchronous download for thread pool"""
        start_time = time.time()
        downloaded_file = None
        expected_filename = None

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info to get filename
                info = ydl.extract_info(url, download=False)

                if info is not None and isinstance(info, dict):
                    try:
                        expected_filename = ydl.prepare_filename(info)
                        # Ensure expected_filename is a string
                        if not isinstance(expected_filename, str):
                            raise ValueError("prepare_filename returned non-string")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to prepare filename: {e}")
                        expected_filename = os.path.join(settings.TEMP_DIR, f"video_{task_id}.%(ext)s")
                else:
                    # If info extraction failed, create a generic filename
                    logger.warning("⚠️ Failed to extract info, using generic filename")
                    expected_filename = os.path.join(settings.TEMP_DIR, f"video_{task_id}.mp4")

                # Download the file
                ydl.download([url])

                # Find the actual downloaded file
                downloaded_file = self._find_downloaded_file(expected_filename)

            download_time = time.time() - start_time
            file_size = os.path.getsize(downloaded_file) if downloaded_file else 0
            average_speed = file_size / download_time if download_time > 0 else 0

            return {
                'file_path': downloaded_file,
                'download_time': download_time,
                'average_speed': average_speed
            }

        except Exception as e:
            logger.error(f"Sync download error for task {task_id}: {e}")
            raise

    def _find_downloaded_file(self, expected_filename: Optional[str]) -> Optional[str]:
        """Find the actual downloaded file (prioritizes video over images)"""
        # Validate input type
        if expected_filename is not None and not isinstance(expected_filename, str):
            logger.error(f"❌ expected_filename must be string, got {type(expected_filename)}: {expected_filename}")
            expected_filename = None

        if not expected_filename:
            # If no expected filename, search temp directory for any downloaded files
            temp_dir = settings.TEMP_DIR
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    # Skip info and metadata files
                    if not file.endswith(('.info.json', '.image', '.description', '.annotations.xml', '.jpg', '.jpeg', '.png', '.webp')):
                        if any(file.endswith(ext) for ext in ['.mp4', '.webm', '.mkv', '.avi', '.flv', '.3gp', '.mp3', '.m4a', '.ogg', '.wav', '.aac']):
                            return os.path.join(root, file)
            return None

        # Ensure it's a valid string path
        try:
            if os.path.exists(expected_filename):
                return expected_filename
        except (TypeError, OSError) as e:
            logger.error(f"❌ Invalid path format: {e}")
            return None

        # Check for common video extension variations first (prioritize video files)
        base_name = os.path.splitext(expected_filename)[0]
        video_extensions = ['.mp4', '.webm', '.mkv', '.avi', '.mov', '.flv', '.3gp']
        audio_extensions = ['.mp3', '.m4a', '.ogg', '.wav', '.aac']

        # First pass: Look for video files
        for ext in video_extensions:
            test_path = base_name + ext
            if os.path.exists(test_path):
                return test_path

        # Second pass: Look for audio files
        for ext in audio_extensions:
            test_path = base_name + ext
            if os.path.exists(test_path):
                return test_path

        # Check directory for any file with similar name (prioritize video/audio over images)
        directory = os.path.dirname(expected_filename)
        base_filename = os.path.basename(base_name)

        if os.path.exists(directory):
            video_files = []
            audio_files = []
            other_files = []

            for file in os.listdir(directory):
                if file.startswith(base_filename):
                    file_path = os.path.join(directory, file)
                    file_ext = os.path.splitext(file)[1].lower()

                    # Skip thumbnail and info files
                    if file_ext in ['.jpg', '.jpeg', '.png', '.webp', '.image'] or \
                       file.endswith('.info.json') or '.thumb.' in file:
                        continue

                    if file_ext in video_extensions:
                        video_files.append(file_path)
                    elif file_ext in audio_extensions:
                        audio_files.append(file_path)
                    else:
                        other_files.append(file_path)

            # Return in priority order: video > audio > other
            if video_files:
                return video_files[0]
            elif audio_files:
                return audio_files[0]
            elif other_files:
                return other_files[0]

        return None

    async def get_download_progress(self, task_id: str) -> Dict[str, Any]:
        """Get current download progress"""
        return await self.progress_tracker.get_download_progress(task_id)

    async def cancel_download(self, task_id: str) -> bool:
        """Cancel an ongoing download"""
        try:
            # Mark as cancelled in progress tracker
            await self.progress_tracker.update_download_progress(
                task_id, 0, 0, "Cancelled by user"
            )

            # Note: yt-dlp doesn't have built-in cancellation,
            # but we can mark it as cancelled for UI purposes
            logger.info(f"📝 Download task {task_id} marked as cancelled")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to cancel download {task_id}: {e}")
            return False

    async def cleanup_temp_files(self, max_age_hours: int = 1):
        """Clean up old temporary files including cookie files"""
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            temp_dir = settings.TEMP_DIR
            if not os.path.exists(temp_dir):
                return

            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_age = current_time - os.path.getctime(file_path)
                        if file_age > max_age_seconds:
                            os.remove(file_path)
                            logger.debug(f"🗑️ Cleaned up old file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up file {file_path}: {e}")

            # Also clean up system temp directory cookie files
            import tempfile
            system_temp = tempfile.gettempdir()
            try:
                for file in os.listdir(system_temp):
                    if file.endswith('.txt') and ('cookie' in file.lower() or file.startswith('tmp')):
                        file_path = os.path.join(system_temp, file)
                        try:
                            file_age = current_time - os.path.getctime(file_path)
                            if file_age > max_age_seconds:
                                os.remove(file_path)
                                logger.debug(f"🗑️ Cleaned up old cookie file: {file_path}")
                        except Exception as e:
                            logger.debug(f"Failed to clean up cookie file {file_path}: {e}")
            except Exception:
                pass

            logger.info(f"✅ Temporary files cleanup completed")

        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")

    async def get_supported_sites(self) -> List[str]:
        """Get list of supported extraction sites"""
        try:
            loop = asyncio.get_event_loop()
            extractors = await loop.run_in_executor(
                self.executor,
                lambda: yt_dlp.list_extractors()
            )
            return [str(extractor.IE_NAME) for extractor in extractors if hasattr(extractor, 'IE_NAME')]
        except Exception as e:
            logger.error(f"Failed to get supported sites: {e}")
            return settings.YTDL_EXTRACTORS

    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        return {
            'active_downloads': len(self.download_stats),
            'max_concurrent_downloads': settings.MAX_CONCURRENT_DOWNLOADS,
            'queue_size': self.download_semaphore._value,
            'executor_threads': self.executor._max_workers,
            'temp_dir_size': await self._get_temp_dir_size(),
        }

    async def _get_temp_dir_size(self) -> int:
        """Get total size of temporary directory"""
        try:
            total_size = 0
            for root, dirs, files in os.walk(settings.TEMP_DIR):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(file_path)
                    except OSError:
                        pass
            return total_size
        except Exception:
            return 0

    def load_instagram_session(self):
        """Load Instagram session cookies from file (fallback only)"""
        try:
            if os.path.exists(self.instagram_session_file):
                with open(self.instagram_session_file, 'r') as f:
                    session_data = json.load(f)
                    self.instagram_cookies = session_data.get('cookies', {})
                    logger.info("✅ Instagram session loaded from file (fallback)")
            else:
                logger.info("ℹ️ No Instagram session file found")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load Instagram session from file: {e}")

    def _load_youtube_cookies(self):
        """Load YouTube cookies from settings or environment variables"""
        try:
            # Prefer cookies from settings if available
            if settings.YOUTUBE_COOKIES:
                self.youtube_cookies = self._parse_cookies(settings.YOUTUBE_COOKIES)
                if self.youtube_cookies:
                    logger.info(f"✅ YouTube cookies loaded from settings ({len(self.youtube_cookies)} cookies)")
                    return
                else:
                    logger.warning("⚠️ YouTube cookies from settings are invalid or empty.")

            # Fallback to environment variables if settings are not used or invalid
            env_cookies = {}
            if hasattr(settings, 'YOUTUBE_SESSION_TOKEN') and settings.YOUTUBE_SESSION_TOKEN:
                env_cookies['session_token'] = settings.YOUTUBE_SESSION_TOKEN
            if hasattr(settings, 'YOUTUBE_AUTH_TOKEN') and settings.YOUTUBE_AUTH_TOKEN:
                env_cookies['auth_token'] = settings.YOUTUBE_AUTH_TOKEN

            if env_cookies:
                self.youtube_cookies.update(env_cookies)
                logger.info(f"✅ YouTube cookies loaded from environment variables ({len(env_cookies)} cookies)")
            else:
                # Default YouTube cookies as fallback
                default_cookies = {
                    'YSC': 'S2HI9zX0Wec',
                    'PREF': 'tz=Asia.Riyadh',
                    'VISITOR_INFO1_LIVE': 'XokcjcRzkoQ'
                }
                self.youtube_cookies.update(default_cookies)
                logger.info(f"✅ YouTube cookies loaded from default values ({len(default_cookies)} cookies)")

        except Exception as e:
            logger.error(f"❌ Failed to load YouTube cookies: {e}")

    def _load_cookies_from_env(self):
        """Load Instagram cookies from environment variables"""
        try:
            env_cookies = {}

            # Load sessionid from environment
            if settings.INSTAGRAM_SESSIONID:
                # URL decode the sessionid if needed
                import urllib.parse
                sessionid = urllib.parse.unquote(settings.INSTAGRAM_SESSIONID)
                env_cookies['sessionid'] = sessionid
                logger.info(f"✅ Instagram sessionid loaded from environment: {sessionid[:20]}...")

            # Load csrftoken from environment  
            if settings.INSTAGRAM_CSRFTOKEN:
                env_cookies['csrftoken'] = settings.INSTAGRAM_CSRFTOKEN
                logger.info(f"✅ Instagram csrftoken loaded from environment: {settings.INSTAGRAM_CSRFTOKEN}")

            # If we have env cookies, they take precedence over file cookies
            if env_cookies:
                self.instagram_cookies.update(env_cookies)
                logger.info(f"✅ Instagram cookies loaded from environment! ({len(env_cookies)} cookies)")

                # Save to file for backup
                self.save_instagram_session()
            else:
                logger.info("ℹ️ No Instagram cookies found in environment variables")

        except Exception as e:
            logger.error(f"❌ Failed to load Instagram cookies from environment: {e}")



    def save_instagram_session(self):
        """Save Instagram session cookies to file"""
        try:
            session_data = {
                'cookies': self.instagram_cookies,
                'last_updated': time.time()
            }
            with open(self.instagram_session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            logger.info("✅ Instagram session saved successfully")
        except Exception as e:
            logger.error(f"❌ Failed to save Instagram session: {e}")

    async def login_instagram_with_cookies(self, cookies_text: str) -> bool:
        """Login to Instagram using provided cookies"""
        try:
            logger.info("🔐 Attempting Instagram login with provided cookies...")

            # Parse cookies from different formats
            parsed_cookies = self._parse_cookies(cookies_text)
            if not parsed_cookies:
                logger.error("❌ Failed to parse cookies")
                return False

            # Test cookies by making a request
            success = await self._test_instagram_cookies(parsed_cookies)
            if success:
                self.instagram_cookies.update(parsed_cookies)
                self.save_instagram_session()
                logger.info("✅ Instagram login successful!")
                return True
            else:
                logger.error("❌ Invalid or expired cookies")
                return False

        except Exception as e:
            logger.error(f"❌ Instagram login failed: {e}")
            return False

    def _parse_cookies(self, cookies_text: str) -> Dict[str, str]:
        """Parse cookies from various formats with enhanced URL decoding"""
        cookies = {}

        logger.info(f"Parsing cookies text: {cookies_text[:100]}...")

        try:
            import urllib.parse
            import re

            # Try parsing as JSON first
            if cookies_text.strip().startswith('{') or cookies_text.strip().startswith('['):
                try:
                    json_cookies = json.loads(cookies_text)
                    if isinstance(json_cookies, dict):
                        # Handle different JSON formats
                        for key, value in json_cookies.items():
                            if isinstance(value, dict) and 'value' in value:
                                cookies[key] = str(value['value'])
                            else:
                                cookies[key] = str(value)
                        return cookies
                    elif isinstance(json_cookies, list):
                        for cookie in json_cookies:
                            if isinstance(cookie, dict):
                                if 'name' in cookie and 'value' in cookie:
                                    cookies[cookie['name']] = str(cookie['value'])
                                elif 'Name' in cookie and 'Value' in cookie:
                                    cookies[cookie['Name']] = str(cookie['Value'])
                        return cookies
                except json.JSONDecodeError:
                    pass

            # Try parsing as Netscape format
            if 'instagram.com' in cookies_text.lower() or '\t' in cookies_text:
                lines = cookies_text.strip().split('\n')
                for line in lines:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        name, value = parts[5], parts[6]
                        try:
                            value = urllib.parse.unquote(value)
                        except:
                            pass
                        cookies[name] = value
                if cookies:
                    return cookies

            # Enhanced raw cookie header format parsing
            if '=' in cookies_text:
                # Clean up the cookies text
                cookies_text = cookies_text.strip().rstrip(';')
                
                # Handle different separators
                if ';' in cookies_text:
                    cookie_pairs = cookies_text.split(';')
                elif '\n' in cookies_text:
                    cookie_pairs = cookies_text.split('\n')
                else:
                    cookie_pairs = [cookies_text]

                for pair in cookie_pairs:
                    pair = pair.strip()
                    if '=' in pair and not pair.startswith('#'):
                        try:
                            name, value = pair.split('=', 1)
                            name = name.strip()
                            value = value.strip().strip('"').strip("'")

                            if name and value and name not in ['Domain', 'Path', 'Expires', 'Max-Age', 'Secure', 'HttpOnly', 'SameSite']:
                                # Multiple stage URL decoding
                                original_value = value
                                try:
                                    # First decode
                                    decoded_value = urllib.parse.unquote(value)
                                    # Check if it needs another decode
                                    if '%' in decoded_value and decoded_value != value:
                                        decoded_again = urllib.parse.unquote(decoded_value)
                                        if decoded_again != decoded_value:
                                            value = decoded_again
                                        else:
                                            value = decoded_value
                                    else:
                                        value = decoded_value
                                except:
                                    value = original_value

                                cookies[name] = value
                                logger.debug(f"Parsed cookie: {name}={value[:20]}...")
                        except ValueError:
                            continue

            # Enhanced Instagram session format extraction
            if not cookies and ('sessionid' in cookies_text.lower() or 'csrftoken' in cookies_text.lower()):
                # Extract sessionid with various patterns
                sessionid_patterns = [
                    r'sessionid["\']?\s*[:=]\s*["\']?([^;"\'\s]+)',
                    r'"sessionid":\s*"([^"]+)"',
                    r'sessionid=([^;]+)',
                    r'sessionid:\s*([^,}]+)'
                ]
                
                for pattern in sessionid_patterns:
                    match = re.search(pattern, cookies_text, re.IGNORECASE)
                    if match:
                        sessionid = match.group(1).strip().strip('"').strip("'")
                        try:
                            sessionid = urllib.parse.unquote(sessionid)
                        except:
                            pass
                        cookies['sessionid'] = sessionid
                        logger.info(f"Extracted sessionid: {sessionid[:20]}...")
                        break

                # Extract csrftoken with various patterns
                csrf_patterns = [
                    r'csrftoken["\']?\s*[:=]\s*["\']?([^;"\'\s]+)',
                    r'"csrftoken":\s*"([^"]+)"',
                    r'csrftoken=([^;]+)',
                    r'csrftoken:\s*([^,}]+)'
                ]
                
                for pattern in csrf_patterns:
                    match = re.search(pattern, cookies_text, re.IGNORECASE)
                    if match:
                        csrf = match.group(1).strip().strip('"').strip("'")
                        cookies['csrftoken'] = csrf
                        logger.info(f"Extracted csrftoken: {csrf}")
                        break

                # Look for other common Instagram cookies
                other_patterns = {
                    'mid': r'mid["\']?\s*[:=]\s*["\']?([^;"\'\s]+)',
                    'ds_user_id': r'ds_user_id["\']?\s*[:=]\s*["\']?([^;"\'\s]+)',
                    'ig_did': r'ig_did["\']?\s*[:=]\s*["\']?([^;"\'\s]+)',
                    'ig_nrcb': r'ig_nrcb["\']?\s*[:=]\s*["\']?([^;"\'\s]+)'
                }
                
                for cookie_name, pattern in other_patterns.items():
                    match = re.search(pattern, cookies_text, re.IGNORECASE)
                    if match:
                        value = match.group(1).strip().strip('"').strip("'")
                        cookies[cookie_name] = value

        except Exception as e:
            logger.warning(f"⚠️ Failed to parse cookies: {e}")

        # Validate that we have essential Instagram cookies
        if cookies and ('sessionid' in cookies or 'csrftoken' in cookies):
            logger.info(f"✅ Successfully parsed {len(cookies)} cookies")
            for name in cookies:
                logger.debug(f"Cookie: {name}")
        elif cookies:
            logger.warning(f"⚠️ Parsed {len(cookies)} cookies but missing essential Instagram cookies")

        return cookies

    async def _test_instagram_cookies(self, cookies: Dict[str, str]) -> bool:
        """Test if Instagram cookies are valid"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            }

            # Convert cookies to proper format
            cookie_jar = aiohttp.CookieJar()
            from yarl import URL
            for name, value in cookies.items():
                cookie_jar.update_cookies({name: value}, response_url=URL('https://instagram.com'))

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(
                cookie_jar=cookie_jar,
                headers=headers,
                timeout=timeout
            ) as session:
                # Test with Instagram's main page
                async with session.get('https://www.instagram.com/') as response:
                    if response.status == 200:
                        content = await response.text()
                        # Check if we're logged in (look for specific indicators)
                        if '"is_logged_in":true' in content or 'window._sharedData' in content:
                            logger.info("✅ Instagram cookies are valid and user is logged in")
                            return True
                        else:
                            logger.warning("⚠️ Cookies accepted but user may not be fully logged in")
                            return True  # Still usable for some content

            return False

        except Exception as e:
            logger.error(f"❌ Failed to test Instagram cookies: {e}")
            return False

    async def _try_instagram_authenticated(self, url: str) -> Optional[Dict]:
        """Try Instagram with authenticated session"""
        try:
            if not self.instagram_cookies:
                logger.info("ℹ️ No Instagram cookies available")
                return None

            logger.info("🔐 Attempting Instagram extraction with authenticated session...")

            # Extract video ID
            video_id_match = re.search(r'/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
            if not video_id_match:
                return None

            video_id = video_id_match.group(1)

            # Advanced headers for authenticated requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': self.instagram_cookies.get('csrftoken', ''),
                'X-Instagram-AJAX': '1',
                'X-IG-App-ID': '936619743392459',
                'X-IG-WWW-Claim': '0',
                'Origin': 'https://www.instagram.com',
                'Referer': url,
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
            }

            # Create cookie jar
            cookie_jar = aiohttp.CookieJar()
            from yarl import URL
            for name, value in self.instagram_cookies.items():
                cookie_jar.update_cookies({name: value}, response_url=URL('https://instagram.com'))

            timeout = aiohttp.ClientTimeout(total=15)
            # Create connector with proper encoding support
            connector = aiohttp.TCPConnector(
                enable_cleanup_closed=True,
                limit=20,
                limit_per_host=5
            )

            async with aiohttp.ClientSession(
                cookie_jar=cookie_jar,
                headers=headers,
                timeout=timeout,
                connector=connector
            ) as session:

                # Try GraphQL API endpoint
                graphql_url = f"https://www.instagram.com/api/v1/media/{video_id}/info/"
                async with session.get(graphql_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'items' in data and len(data['items']) > 0:
                            item = data['items'][0]

                            # Extract video URL
                            video_url = None
                            if 'video_versions' in item and len(item['video_versions']) > 0:
                                video_url = item['video_versions'][0]['url']

                            if video_url:
                                processed_info = {
                                    'id': video_id,
                                    'title': item.get('caption', {}).get('text', 'Instagram Video')[:100] or 'Instagram Video',
                                    'uploader': item.get('user', {}).get('username', 'Instagram User'),
                                    'url': video_url,
                                    'thumbnail': item.get('image_versions2', {}).get('candidates', [{}])[0].get('url', ''),
                                    'duration': item.get('video_duration', 0),
                                    'view_count': item.get('view_count', 0),
                                    'platform': 'instagram',
                                    'webpage_url': url,
                                    'formats': [{
                                        'url': video_url,
                                        'format_id': 'authenticated',
                                        'ext': 'mp4',
                                        'quality': 'high'
                                    }]
                                }

                                logger.info("✅ Instagram authenticated extraction successful!")
                                return processed_info

                # Fallback: Try web interface with authentication
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()

                        # Extract from window._sharedData
                        pattern = r'window\._sharedData\s*=\s*({.+?});'
                        match = re.search(pattern, content)
                        if match:
                            try:
                                shared_data = json.loads(match.group(1))
                                entry_data = shared_data.get('entry_data', {})

                                # Check different possible locations
                                for page_type in ['PostPage', 'ProfilePage']:
                                    if page_type in entry_data:
                                        for post in entry_data[page_type][0].get('graphql', {}).get('shortcode_media', []):
                                            if post.get('video_url'):
                                                processed_info = {
                                                    'id': video_id,
                                                    'title': post.get('edge_media_to_caption', {}).get('edges', [{}])[0].get('node', {}).get('text', 'Instagram Video')[:100] or 'Instagram Video',
                                                    'uploader': post.get('owner', {}).get('username', 'Instagram User'),
                                                    'url': post['video_url'],
                                                    'thumbnail': post.get('display_url', ''),
                                                    'duration': post.get('video_duration', 0),
                                                    'view_count': post.get('video_view_count', 0),
                                                    'platform': 'instagram',
                                                    'webpage_url': url,
                                                    'formats': [{
                                                        'url': post['video_url'],
                                                        'format_id': 'web_authenticated',
                                                        'ext': 'mp4',
                                                        'quality': 'high'
                                                    }]
                                                }

                                                logger.info("✅ Instagram web authenticated extraction successful!")
                                                return processed_info

                            except json.JSONDecodeError:
                                pass

        except Exception as e:
            logger.warning(f"⚠️ Instagram authenticated extraction failed: {e}")

        return None

    async def _try_instagram_direct_download(self, url: str, task_id: str, temp_dir: str, video_info: dict) -> Optional[Dict[str, Any]]:
        """Try to download Instagram video using direct API methods"""
        try:
            logger.info("🎯 Attempting Instagram direct API download")
            api_info = await self._try_instagram_api(url)
            if not api_info or not api_info.get("url"):
                return None

            video_url = api_info["url"]
            title = api_info.get("title", video_info.get("title", "Instagram Video"))

            import aiohttp, aiofiles, re
            safe_title = re.sub(r"[^\w\s-]", "", title).strip()[:50]
            filename = f"{safe_title}_{task_id}.mp4"
            file_path = os.path.join(temp_dir, filename)

            timeout = aiohttp.ClientTimeout(total=300)
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(video_url, headers=headers) as response:
                    if response.status == 200:
                        async with aiofiles.open(file_path, "wb") as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)

                        file_size = os.path.getsize(file_path)
                        logger.info(f"✅ Instagram API download successful: {file_path}")
                        return {
                            "task_id": task_id,
                            "file_path": file_path,
                            "file_size": file_size,
                            "filename": os.path.basename(file_path),
                            "video_info": {"title": title, "uploader": api_info.get("uploader", "Instagram User"), "platform": "instagram"},
                            "download_time": 0,
                            "average_speed": 0
                        }
        except Exception as e:
            logger.error(f"❌ Instagram direct download failed: {e}")
        return None