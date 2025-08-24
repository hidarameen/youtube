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
                if attempt >= self.retry_attempts:
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
        
        # Group by quality and select best
        quality_groups = {}
        for fmt in video_formats:
            height = fmt.get('height', 0)
            ext = fmt.get('ext', 'mp4')
            
            if height >= 144:  # Minimum quality
                key = f"{height}p"
                if key not in quality_groups or fmt.get('tbr', 0) > quality_groups[key].get('tbr', 0):
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
                
                if not result or not os.path.exists(result['file_path']):
                    raise ValueError("Download failed - file not created")
                
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
            # Video download
            base_opts['format'] = format_id
        
        return base_opts
    
    def _create_progress_hook(self, task_id: str):
        """Create progress hook for yt-dlp"""
        def progress_hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                
                # Update progress tracker asynchronously
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(
                        self.progress_tracker.update_download_progress(
                            task_id, downloaded, total, "Downloading..."
                        )
                    )
        
        return progress_hook
    
    def _create_postprocessor_hook(self, task_id: str):
        """Create postprocessor hook for yt-dlp"""
        def postprocessor_hook(d):
            if d['status'] == 'processing':
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(
                        self.progress_tracker.update_download_progress(
                            task_id, 0, 0, "Processing..."
                        )
                    )
        
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
        """Find the actual downloaded file (handles extension changes)"""
        if os.path.exists(expected_filename):
            return expected_filename
        
        # Check for common extension variations
        base_name = os.path.splitext(expected_filename)[0]
        extensions = ['.mp4', '.webm', '.mkv', '.avi', '.mov', '.mp3', '.m4a', '.ogg']
        
        for ext in extensions:
            test_path = base_name + ext
            if os.path.exists(test_path):
                return test_path
        
        # Check directory for any file with similar name
        directory = os.path.dirname(expected_filename)
        base_filename = os.path.basename(base_name)
        
        if os.path.exists(directory):
            for file in os.listdir(directory):
                if file.startswith(base_filename):
                    return os.path.join(directory, file)
        
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
