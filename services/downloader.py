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
        self.bandwidth_limit = settings.MAX_DOWNLOAD_BANDWIDTH if hasattr(settings, 'MAX_DOWNLOAD_BANDWIDTH') else None
        
        # File integrity checking
        self.verify_checksums = True
        
        # Active downloads tracking
        self.active_downloads: Dict[str, Any] = {}
        
        # Instagram authentication and cookies
        self.instagram_cookies: Dict[str, Any] = {}
        self.instagram_session_file = "instagram_session.json"
        self.load_instagram_session()
        
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
                    ydl_opts.update({
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept-Encoding': 'gzip, deflate, br',
                        }
                    })
                    
                    # Use Instagram API if token is available
                    if settings.INSTAGRAM_ACCESS_TOKEN:
                        ydl_opts['extractor_args'] = {
                            'instagram': {
                                'access_token': settings.INSTAGRAM_ACCESS_TOKEN
                            }
                        }
                        logger.info("🔑 Using Instagram API authentication")
                
                elif platform == 'facebook':
                    ydl_opts.update({
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.9',
                        }
                    })
                    
                    # Use Facebook API if token is available
                    if settings.FACEBOOK_ACCESS_TOKEN:
                        ydl_opts['extractor_args'] = {
                            'facebook': {
                                'access_token': settings.FACEBOOK_ACCESS_TOKEN
                            }
                        }
                        logger.info("🔑 Using Facebook API authentication")
                
                # Extract info in thread pool
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(
                    self.executor, 
                    self._extract_info_sync, 
                    url, 
                    ydl_opts
                )
                
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
                        elif platform == 'facebook' and settings.FACEBOOK_ACCESS_TOKEN:
                            logger.info("🔄 Trying Facebook API method...")
                            try:
                                api_info = await self._try_facebook_api(url)
                                if api_info:
                                    logger.info("✅ Facebook API extraction successful!")
                                    return api_info
                                else:
                                    logger.warning("❌ Facebook API returned no data")
                            except Exception as api_e:
                                logger.warning(f"❌ Facebook API method failed: {api_e}")
                        
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
        """Try alternative Instagram API methods for better access"""
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
            
            # Try authenticated method first (if cookies available)
            if self.instagram_cookies:
                authenticated_result = await self._try_instagram_authenticated(url)
                if authenticated_result:
                    return authenticated_result
            
            # Try Instagram Basic Display API (for public content)
            basic_api_result = await self._try_instagram_basic_display(video_id, url)
            if basic_api_result:
                return basic_api_result
            
            # Try alternative scraping method with headers
            scraping_result = await self._try_instagram_scraping(url)
            if scraping_result:
                return scraping_result
            
            logger.warning("❌ All Instagram API methods failed")
            return None
            
        except Exception as e:
            logger.warning(f"❌ Instagram API extraction failed: {e}")
        
        return None
    
    async def _try_instagram_basic_display(self, video_id: str, url: str) -> Optional[Dict]:
        """Try Instagram Basic Display API"""
        try:
            import aiohttp
            
            # Try to get media info using Instagram's embed endpoint
            embed_url = f"https://www.instagram.com/p/{video_id}/embed/"
            
            timeout = aiohttp.ClientTimeout(total=10)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
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
        """Try alternative Instagram scraping method"""
        try:
            import aiohttp
            import re
            
            logger.info("🔄 Trying Instagram scraping method...")
            
            timeout = aiohttp.ClientTimeout(total=15)
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Extract video ID from URL
                        video_id_match = re.search(r'/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
                        video_id = video_id_match.group(1) if video_id_match else 'unknown'
                        
                        # Try to find video URL in the page content
                        video_patterns = [
                            r'"video_url":"([^"]+)"',
                            r'"src":"([^"]+\.mp4[^"]*)"',
                            r'videoUrl":"([^"]+)"',
                        ]
                        
                        video_url = None
                        for pattern in video_patterns:
                            match = re.search(pattern, content)
                            if match:
                                video_url = match.group(1).replace('\\u0026', '&').replace('\\/', '/')
                                break
                        
                        if video_url:
                            # Try to extract title/caption
                            title_patterns = [
                                r'"caption":"([^"]+)"',
                                r'"text":"([^"]+)"',
                                r'<title>([^<]+)</title>',
                            ]
                            
                            title = 'Instagram Video'
                            for pattern in title_patterns:
                                match = re.search(pattern, content)
                                if match:
                                    title = match.group(1)[:100]
                                    break
                            
                            processed_info = {
                                'id': video_id,
                                'title': title,
                                'uploader': 'Instagram User',
                                'url': video_url,
                                'thumbnail': '',
                                'duration': 0,
                                'view_count': 0,
                                'platform': 'instagram',
                                'webpage_url': url,
                                'formats': [{
                                    'url': video_url,
                                    'format_id': 'scraped',
                                    'ext': 'mp4',
                                    'quality': 'unknown'
                                }]
                            }
                            
                            logger.info(f"✅ Instagram scraping extraction successful!")
                            return processed_info
                        
        except Exception as e:
            logger.debug(f"Scraping method failed: {e}")
        
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
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info to get filename
                info = ydl.extract_info(url, download=False)
                expected_filename = ydl.prepare_filename(info)
                
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
    
    def _find_downloaded_file(self, expected_filename: str) -> Optional[str]:
        """Find the actual downloaded file (prioritizes video over images)"""
        if os.path.exists(expected_filename):
            return expected_filename
        
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
        """Clean up old temporary files"""
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
            return [extractor.IE_NAME for extractor in extractors if hasattr(extractor, 'IE_NAME')]
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
        """Load Instagram session cookies from file"""
        try:
            if os.path.exists(self.instagram_session_file):
                with open(self.instagram_session_file, 'r') as f:
                    session_data = json.load(f)
                    self.instagram_cookies = session_data.get('cookies', {})
                    logger.info("✅ Instagram session loaded successfully")
            else:
                logger.info("ℹ️ No Instagram session file found, will create new one")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load Instagram session: {e}")
    
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
        """Parse cookies from various formats (Netscape, JSON, raw headers)"""
        cookies = {}
        
        try:
            # Try parsing as JSON first
            if cookies_text.strip().startswith('{'):
                json_cookies = json.loads(cookies_text)
                if isinstance(json_cookies, dict):
                    return json_cookies
                elif isinstance(json_cookies, list):
                    for cookie in json_cookies:
                        if 'name' in cookie and 'value' in cookie:
                            cookies[cookie['name']] = cookie['value']
                    return cookies
            
            # Try parsing as Netscape format
            if 'instagram.com' in cookies_text.lower():
                lines = cookies_text.strip().split('\n')
                for line in lines:
                    if line.startswith('#') or not line.strip():
                        continue
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        name, value = parts[5], parts[6]
                        cookies[name] = value
                return cookies
            
            # Try parsing as raw cookie header format
            if '=' in cookies_text:
                cookie_pairs = cookies_text.split(';')
                for pair in cookie_pairs:
                    if '=' in pair:
                        name, value = pair.split('=', 1)
                        cookies[name.strip()] = value.strip()
                return cookies
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse cookies: {e}")
        
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
            for name, value in cookies.items():
                cookie_jar.update_cookies({name: value}, response_url='https://instagram.com')
            
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
            for name, value in self.instagram_cookies.items():
                cookie_jar.update_cookies({name: value}, response_url='https://instagram.com')
            
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(
                cookie_jar=cookie_jar, 
                headers=headers, 
                timeout=timeout
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
